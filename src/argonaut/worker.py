"""Worker thread that translates the file list without blocking the UI."""

import os
import time

from PyQt5.QtCore import QThread, pyqtSignal
from argostranslatefiles import argostranslatefiles

from argonaut import nllb, packages
from argonaut.i18n import tr
from argonaut.pdf import FastPdfTranslator, count_pdf_paragraphs
from argonaut.translation import CancelledError, ProgressTranslation, detect_language


class ModelDownloadWorker(QThread):
    """Downloads the NLLB model without blocking the UI."""

    progress = pyqtSignal(int, int)  # done MB, total MB
    download_finished = pyqtSignal(bool, str)  # ok, error ("" when cancelled)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        last = -1

        def report(done, total):
            nonlocal last
            mb = done >> 20
            if mb != last:
                last = mb
                self.progress.emit(mb, max(1, total >> 20))

        try:
            nllb.download_model(
                on_progress=report, is_cancelled=lambda: self._cancelled
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


class PackageSizeWorker(QThread):
    """Fetches package archive sizes with HEAD requests, a few at a time."""

    size_ready = pyqtSignal(int, int)  # list row, bytes (0 = unknown)

    def __init__(self, to_measure, parent=None):
        super().__init__(parent)
        self.to_measure = to_measure  # list of (row, package)
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

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


class PackageInstallWorker(QThread):
    """Downloads and installs a list of Argos packages."""

    package_started = pyqtSignal(int, int, str)  # index, total, "English → Spanish"
    progress = pyqtSignal(int, int)  # done MB, total MB of the current package
    package_failed = pyqtSignal(str, str)  # description, error
    install_finished = pyqtSignal(int)  # packages installed

    def __init__(self, to_install, parent=None):
        super().__init__(parent)
        self.to_install = to_install
        self._cancelled = False
        self._last_mb = -1

    def cancel(self):
        self._cancelled = True

    def was_cancelled(self):
        return self._cancelled

    def _report(self, done, total):
        mb = done >> 20
        if mb != self._last_mb:
            self._last_mb = mb
            self.progress.emit(mb, max(1, total >> 20))

    def run(self):
        installed = 0
        for i, pkg in enumerate(self.to_install):
            if self._cancelled:
                break
            self._last_mb = -1
            self.package_started.emit(
                i, len(self.to_install), f"{pkg.from_name} → {pkg.to_name}"
            )
            try:
                packages.install(
                    pkg, on_progress=self._report, is_cancelled=self.was_cancelled
                )
            except CancelledError:
                break
            except Exception as exc:  # noqa: BLE001
                self.package_failed.emit(f"{pkg.from_name} → {pkg.to_name}", str(exc))
            else:
                installed += 1
        self.install_finished.emit(installed)


class TranslateWorker(QThread):
    """Translates a list of files. If src_lang is None, detects each
    file's language separately."""

    file_started = pyqtSignal(int, str)
    file_done = pyqtSignal(int, str, float)  # index, output path, seconds
    file_failed = pyqtSignal(int, str)
    progress_update = pyqtSignal(int, int)  # chunks done, total (0 = unknown)
    phase_changed = pyqtSignal(str)  # description of the current phase
    language_detected = pyqtSignal(int, str)  # file index, detected language
    finished_all = pyqtSignal()

    def __init__(self, src_lang, dst_lang, languages, files, output_dir=None, parent=None):
        super().__init__(parent)
        self.src_lang = src_lang
        self.dst_lang = dst_lang
        self.languages = languages
        self.files = files
        self.output_dir = output_dir  # None = next to each original
        self._cancelled = False
        self._last_emit = 0.0
        self._current_name = ""

    def get_output_path(self, underlying_translation, file_path):
        # same naming scheme as the library, but honouring the output
        # folder if one was chosen
        name, ext = os.path.splitext(os.path.basename(file_path))
        to_code = underlying_translation.to_lang.code
        dir_path = self.output_dir or os.path.dirname(file_path)
        return os.path.join(dir_path, f"{name}_{to_code}{ext}")

    def cancel(self):
        self._cancelled = True

    def was_cancelled(self):
        return self._cancelled

    def resolve_translation(self, index, path):
        src = self.src_lang
        name = os.path.basename(path)
        if src is None:
            src = detect_language(path, self.languages)
            if src is None:
                raise RuntimeError(tr("err_detect", name=name))
            self.language_detected.emit(index, str(src))
        if src is self.dst_lang:
            raise RuntimeError(tr("err_already", name=name, lang=self.dst_lang))
        translation = src.get_translation(self.dst_lang)
        if translation is None:
            raise RuntimeError(
                tr("err_no_model", name=name, src=src, dst=self.dst_lang)
            )
        return translation

    def run(self):
        for i, path in enumerate(self.files):
            if self._cancelled:
                break
            self.file_started.emit(i, path)
            self._current_name = os.path.basename(path)
            file_start = time.monotonic()
            try:
                translation = self.resolve_translation(i, path)
                is_pdf = path.lower().endswith(".pdf")
                total = count_pdf_paragraphs(path) if is_pdf else 0
                self.progress_update.emit(0, total)
                proxy = ProgressTranslation(
                    translation,
                    lambda done, t=total: self._report_progress(done, t),
                    self.was_cancelled,
                )
                if is_pdf:
                    out = self.get_output_path(translation, path)
                    FastPdfTranslator(
                        pdf_path=path,
                        output_path=out,
                        underlying_translation=proxy,
                        on_page=self._report_page,
                        on_save=self._report_save,
                        is_cancelled=self.was_cancelled,
                    ).translate_pdf()
                else:
                    out = argostranslatefiles.translate_file(
                        proxy, path, get_output_path=self.get_output_path
                    )
                self.file_done.emit(i, out or "", time.monotonic() - file_start)
            except CancelledError:
                break
            except Exception as exc:  # noqa: BLE001
                self.file_failed.emit(i, str(exc))
        self.finished_all.emit()

    def _report_progress(self, done, total):
        now = time.monotonic()
        if done == total or now - self._last_emit > 0.2:
            self._last_emit = now
            self.progress_update.emit(done, total)

    def _report_page(self, done, total):
        self.progress_update.emit(done, total)
        self.phase_changed.emit(
            tr("generating", name=self._current_name, done=done, total=total)
        )
        time.sleep(0.001)  # yield the GIL so the UI stays responsive

    def _report_save(self):
        self.progress_update.emit(0, 0)
        self.phase_changed.emit(tr("saving", name=self._current_name))
