"""Worker thread that translates the file list without blocking the UI."""

import os
import time

from PyQt5.QtCore import QThread, pyqtSignal
from argostranslatefiles import argostranslatefiles

from argonaut.i18n import tr
from argonaut.pdf import FastPdfTranslator, count_pdf_paragraphs
from argonaut.translation import CancelledError, ProgressTranslation, detect_language


class TranslateWorker(QThread):
    """Translates a list of files. If src_lang is None, detects each
    file's language separately."""

    file_started = pyqtSignal(int, str)
    file_done = pyqtSignal(int, str)
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
                self.file_done.emit(i, out or "")
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
