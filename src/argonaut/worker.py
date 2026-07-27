"""Worker thread that translates the file list without blocking the UI."""

import os
import time

from PyQt5.QtCore import QSettings, QThread, pyqtSignal
from argostranslatefiles import argostranslatefiles

from argonaut import nllb, packages
from argonaut.history import TranslationHistory
from argonaut.i18n import lang_text, tr
from argonaut.pdf import FastPdfTranslator
from argonaut.translation import (
    CancelledError,
    ProgressTranslation,
    TranslationCache,
    detect_language,
)


class CancellableThread(QThread):
    """A worker the window can ask to stop. Nothing is interrupted by force:
    the thread checks ``was_cancelled`` at its own safe points, so a call
    already in flight still has to return first."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def was_cancelled(self):
        return self._cancelled


def speed_units():
    """The configured family for download-speed labels: network bits
    ("bits", the default) or the bytes a download manager shows."""
    saved = QSettings().value("speed_units", "bits")
    return saved if saved in ("bits", "bytes") else "bits"


def quality_mode():
    """The configured speed/quality trade-off: "quality" (each engine's
    default beam width, the default) or "fast" (greedy decoding)."""
    saved = QSettings().value("quality_mode", "quality")
    return saved if saved in ("quality", "fast") else "quality"


def speed_text(bytes_per_second, units="bits"):
    """Download speed label; empty while the speed is still unknown.
    "bits" renders network units ("16.8 Mbps", "400 kbps"); "bytes" what a
    download manager shows ("2.0 MB/s", "400 KB/s"), binary like the MB
    figures next to it."""
    if bytes_per_second <= 0:
        return ""
    if units == "bytes":
        if bytes_per_second >= 2**20:
            return f"{bytes_per_second / 2**20:.1f} MB/s"
        return f"{max(1, round(bytes_per_second / 1024))} KB/s"
    bits = bytes_per_second * 8
    if bits >= 1_000_000:
        return f"{bits / 1_000_000:.1f} Mbps"
    return f"{max(1, round(bits / 1000))} kbps"


class MegabyteProgress:
    """Forwards byte counts to a (done MB, total MB, bytes per second)
    signal, but only when the megabyte figure actually changes: a download
    otherwise reports thousands of times for a bar that can show a few
    hundred steps. The speed is measured over a short sliding window, so
    it follows the connection's current pace rather than the download's
    lifetime average (0.0 until the first window completes)."""

    WINDOW = 1.0  # seconds per speed sample

    def __init__(self, signal, clock=time.monotonic):
        self._signal = signal
        self._clock = clock
        self.reset()

    def reset(self):
        self._last = -1
        self._speed = 0.0
        self._anchor = None  # (time, bytes) the current window started at

    def __call__(self, done, total):
        now = self._clock()
        if self._anchor is None:
            self._anchor = (now, done)
        t0, done0 = self._anchor
        if now - t0 >= self.WINDOW:
            self._speed = (done - done0) / (now - t0)
            self._anchor = (now, done)
        mb = done >> 20
        if mb != self._last:
            self._last = mb
            self._signal.emit(mb, max(1, total >> 20), self._speed)


class ModelDownloadWorker(CancellableThread):
    """Downloads the NLLB model without blocking the UI."""

    progress = pyqtSignal(int, int, float)  # done MB, total MB, bytes/sec
    download_finished = pyqtSignal(bool, str)  # ok, error ("" when cancelled)

    def run(self):
        try:
            nllb.download_model(
                on_progress=MegabyteProgress(self.progress),
                is_cancelled=self.was_cancelled,
            )
        except CancelledError:
            self.download_finished.emit(False, "")
        except Exception as exc:  # noqa: BLE001
            self.download_finished.emit(False, str(exc))
        else:
            self.download_finished.emit(True, "")


class PackageListWorker(QThread):
    """Fetches the Argos package index without blocking the UI."""

    listed = pyqtSignal(list, str)  # available packages, error ("" = ok)

    def run(self):
        try:
            available = packages.get_available()
        except Exception as exc:  # noqa: BLE001
            self.listed.emit([], str(exc))
        else:
            self.listed.emit(available, "")


class PackageSizeWorker(CancellableThread):
    """Fetches package archive sizes with HEAD requests, a few at a time."""

    size_ready = pyqtSignal(int, int)  # list row, bytes (0 = unknown)

    def __init__(self, to_measure, parent=None):
        super().__init__(parent)
        self.to_measure = to_measure  # list of (row, package)

    def run(self):
        from concurrent.futures import ThreadPoolExecutor, as_completed

        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = {
                pool.submit(packages.get_size, pkg): row
                for row, pkg in self.to_measure
            }
            for future in as_completed(futures):
                if self._cancelled:
                    pool.shutdown(wait=False, cancel_futures=True)
                    return
                self.size_ready.emit(futures[future], future.result())


class PackageInstallWorker(CancellableThread):
    """Downloads and installs a list of Argos packages."""

    package_started = pyqtSignal(int, int, str)  # index, total, "English → Spanish"
    progress = pyqtSignal(int, int, float)  # done MB, total MB, bytes/sec
    package_failed = pyqtSignal(str, str)  # description, error
    install_finished = pyqtSignal(int)  # packages installed

    def __init__(self, to_install, parent=None):
        super().__init__(parent)
        self.to_install = to_install
        self._report = MegabyteProgress(self.progress)

    def run(self):
        installed = 0
        for i, pkg in enumerate(self.to_install):
            if self._cancelled:
                break
            self._report.reset()  # each package has its own byte count
            self.package_started.emit(
                i, len(self.to_install), packages.pair_text(pkg)
            )
            try:
                packages.install(
                    pkg, on_progress=self._report, is_cancelled=self.was_cancelled
                )
            except CancelledError:
                break
            except Exception as exc:  # noqa: BLE001
                self.package_failed.emit(packages.pair_text(pkg), str(exc))
            else:
                installed += 1
        self.install_finished.emit(installed)


class TranslateWorker(CancellableThread):
    """Translates a list of files. If src_lang is None, detects each
    file's language separately. Segments repeated across the batch are
    served from a shared cache, and files whose output already exists
    can be skipped instead of retranslated."""

    file_started = pyqtSignal(int, str)
    file_done = pyqtSignal(int, str, float)  # index, output path, seconds
    file_failed = pyqtSignal(int, str)
    file_skipped = pyqtSignal(int, str)  # index, existing output path
    # index, segments this file reused from the cache, batch reuse so far and
    # the segments that reuse is out of (so the window can show a rate)
    file_cache_stats = pyqtSignal(int, int, int, int)
    progress_update = pyqtSignal(int, int)  # chunks done, total (0 = unknown)
    # current phase as a (translation key, kwargs) pair, so the window can
    # re-render it if the interface language changes mid-translation
    phase_changed = pyqtSignal(str, dict)
    language_detected = pyqtSignal(int, str)  # file index, detected language
    finished_all = pyqtSignal()

    YIELD_EVERY = 0.05  # seconds between hand-overs to the interface thread

    def __init__(self, src_lang, dst_lang, languages, files, output_dir=None,
                 skip_existing=False, engine_id="argos", parent=None):
        super().__init__(parent)
        self.src_lang = src_lang
        self.dst_lang = dst_lang
        self.languages = languages
        self.files = files
        self.output_dir = output_dir  # None = next to each original
        self.skip_existing = skip_existing
        self.engine_id = engine_id
        self._last_emit = 0.0
        self._last_yield = 0.0
        self._current_name = ""
        self._total_chunks = 0  # 0 until the file says how much work it holds
        self._batch_segments = 0  # cacheable segments seen across the batch
        self._pkg_versions = None  # pair -> version, read once per batch
        # shared across every file so a repeated paragraph translates once
        # for the whole batch (namespaced by engine, model version and
        # language pair inside the proxy); the settings are read here but
        # the cache itself is opened in run(): opening prunes expired
        # entries, too much work for the click handler that constructs it
        cache_on = QSettings().value("cache_enabled", True, type=bool)
        self._greedy = quality_mode() == "fast"
        self._cache_ttl_days = QSettings().value("cache_ttl_days", 90, type=int)
        self._cache_db_path = TranslationCache.default_db_path() if cache_on else None
        self._batch_cache = None
        # the history is opened alongside the cache, and for the same reason:
        # opening it prunes expired entries
        history_on = QSettings().value("history_enabled", True, type=bool)
        self._history_ttl_days = QSettings().value("history_ttl_days", 90, type=int)
        self._history_db_path = (
            TranslationHistory.default_db_path() if history_on else None
        )
        self._history = None

    def output_path_for(self, to_code, file_path):
        # same naming scheme as the library, but honouring the output
        # folder if one was chosen
        name, ext = os.path.splitext(os.path.basename(file_path))
        dir_path = self.output_dir or os.path.dirname(file_path)
        return os.path.join(dir_path, f"{name}_{to_code}{ext}")

    def get_output_path(self, underlying_translation, file_path):
        return self.output_path_for(underlying_translation.to_lang.code, file_path)

    def expected_output_path(self, file_path):
        # the target is always the destination language, whatever the source
        # turns out to be, so the skip check needs no language detection
        return self.output_path_for(self.dst_lang.code, file_path)

    def resolve_translation(self, index, path):
        src = self.src_lang
        name = os.path.basename(path)
        if src is None:
            src = detect_language(path, self.languages)
            if src is None:
                raise RuntimeError(tr("err_detect", name=name))
            self.language_detected.emit(index, lang_text(src))
        if src is self.dst_lang:
            raise RuntimeError(
                tr("err_already", name=name, lang=lang_text(self.dst_lang))
            )
        translation = src.get_translation(self.dst_lang)
        if translation is None:
            raise RuntimeError(
                tr(
                    "err_no_model",
                    name=name,
                    src=lang_text(src),
                    dst=lang_text(self.dst_lang),
                )
            )
        return translation

    def _engine_version(self, translation):
        """Version tag for the cache namespace, so entries produced by an
        older model stop being served after a package upgrade."""
        if self.engine_id != "argos":
            version = nllb.MODEL_REPO  # one fixed model, replaced only by us
        else:
            if self._pkg_versions is None:
                self._pkg_versions = packages.installed_versions()
            pair = (translation.from_lang.code, translation.to_lang.code)
            version = self._pkg_versions.get(pair, "")
        # greedy output is not beam output: the modes never serve each
        # other's entries, and quality-mode keys stay as they always were
        return f"{version}+greedy" if self._greedy else version

    def run(self):
        self._batch_cache = TranslationCache(
            self._cache_db_path, ttl_days=self._cache_ttl_days
        )
        self._history = TranslationHistory(
            self._history_db_path, ttl_days=self._history_ttl_days
        )
        try:
            self._translate_files()
        finally:
            # a cancelled batch has to let go of its database connection and
            # of the segments it has translated so far, just like a finished one
            self._batch_cache.close()
            self._history.close()
            # the window leaves its busy state on this signal, so it is
            # emitted from a finally: an unexpected error must never leave the
            # interface stuck with every control disabled
            self.finished_all.emit()

    def _translate_files(self):
        for i, path in enumerate(self.files):
            if self._cancelled:
                break
            self.file_started.emit(i, path)
            self._current_name = os.path.basename(path)
            file_start = time.monotonic()
            try:
                if self.skip_existing:
                    existing = self.expected_output_path(path)
                    if os.path.exists(existing):
                        self.file_skipped.emit(i, existing)
                        continue
                translation = self.resolve_translation(i, path)
                self._total_chunks = 0
                self.progress_update.emit(0, 0)
                proxy = ProgressTranslation(
                    translation,
                    self._report_progress,
                    self.was_cancelled,
                    cache=self._batch_cache,
                    engine_id=self.engine_id,
                    engine_version=self._engine_version(translation),
                )
                if path.lower().endswith(".pdf"):
                    out = self.get_output_path(translation, path)
                    FastPdfTranslator(
                        pdf_path=path,
                        output_path=out,
                        underlying_translation=proxy,
                        on_count_ready=self._report_total,
                        on_read=self._report_read,
                        on_translated_page=self._report_translated_page,
                        on_page=self._report_page,
                        on_save=self._report_save,
                        is_cancelled=self.was_cancelled,
                    ).translate_pdf()
                else:
                    out = argostranslatefiles.translate_file(
                        proxy, path, get_output_path=self.get_output_path
                    )
                self._batch_segments += proxy.segments
                self.file_cache_stats.emit(
                    i, proxy.reused, self._batch_cache.reused, self._batch_segments
                )
                elapsed = time.monotonic() - file_start
                self._history.record(
                    path, out or "",
                    translation.from_lang.code, translation.to_lang.code,
                    self.engine_id, elapsed,
                    reused=proxy.reused, segments=proxy.segments,
                )
                self.file_done.emit(i, out or "", elapsed)
            except CancelledError:
                break
            except Exception as exc:  # noqa: BLE001
                self.file_failed.emit(i, str(exc))

    def _report_total(self, total):
        """How many chunks the current file holds, known once it is parsed."""
        self._total_chunks = total
        self.progress_update.emit(0, total)

    def _report_progress(self, done):
        now = time.monotonic()
        total = self._total_chunks
        if done == total or now - self._last_emit > 0.2:
            self._last_emit = now
            self.progress_update.emit(done, total)

    def _report_pages(self, key, done, total, move_bar=True):
        """Says which page of the current file a phase is on. On a long book
        the percentage can sit on the same figure for a minute, so the page
        number is what tells the user the run is alive."""
        if move_bar:
            self.progress_update.emit(done, total)
        self.phase_changed.emit(
            key, {"name": self._current_name, "done": done, "total": total}
        )
        self._yield_to_ui()

    def _yield_to_ui(self):
        """Hands the interpreter over to the interface thread for a moment.

        Not on every page: reading a 400-page book takes about as long as
        one millisecond per page would, so sleeping each time paced the
        phase rather than the work. Yielding at most every YIELD_EVERY
        seconds still gives the window dozens of chances a second to
        repaint, while costing a fixed fraction of the run instead of a
        toll per page."""
        now = time.monotonic()
        if now - self._last_yield >= self.YIELD_EVERY:
            self._last_yield = now
            time.sleep(0.001)

    def _report_read(self, done, total):
        # reading is preparation: moving the bar here would sweep it to 100%
        # and send it back to 0% when the translation itself starts, so the
        # page number goes in the message and the bar stays indeterminate
        self._report_pages("reading", done, total, move_bar=False)

    def _report_translated_page(self, done, total):
        # the bar is already counting paragraphs, a finer measure than pages
        self._report_pages("translating_page", done, total, move_bar=False)

    def _report_page(self, done, total):
        self._report_pages("generating", done, total)

    def _report_save(self):
        self.progress_update.emit(0, 0)
        self.phase_changed.emit("saving", {"name": self._current_name})
