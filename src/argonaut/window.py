"""Main application window."""

import os

from PyQt5.QtCore import QSettings, QUrl, Qt
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtWidgets import (
    QAction,
    QActionGroup,
    QApplication,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QStyle,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

import argostranslate.translate

from argonaut.i18n import LANGUAGES, current_language, set_language, tr
from argonaut.translation import SUPPORTED_EXTS
from argonaut.worker import TranslateWorker


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setMinimumSize(520, 420)
        self.setAcceptDrops(True)
        self.worker = None
        self.results = []
        self.detected = {}
        self._status_base = ""

        self.languages = argostranslate.translate.get_installed_languages()

        # --- interface language menu ---
        self.lang_menu = self.menuBar().addMenu("")
        group = QActionGroup(self)
        group.setExclusive(True)
        for code, name in LANGUAGES:
            action = QAction(name, self, checkable=True)
            action.setChecked(code == current_language())
            action.triggered.connect(lambda _, c=code: self.change_language(c))
            group.addAction(action)
            self.lang_menu.addAction(action)

        # --- help menu ---
        self.help_menu = self.menuBar().addMenu("")
        self.about_action = QAction("", self)
        self.about_action.triggered.connect(self.show_about)
        self.help_menu.addAction(self.about_action)

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        # --- language selection ---
        lang_row = QHBoxLayout()
        self.from_combo = QComboBox()
        self.to_combo = QComboBox()
        self.from_combo.addItem("", None)  # "Detect language" (text set in retranslate)
        for lang in self.languages:
            self.from_combo.addItem(str(lang), lang)
            self.to_combo.addItem(str(lang), lang)

        self.swap_btn = QToolButton()
        self.swap_btn.setText("⇄")
        self.swap_btn.clicked.connect(self.swap_languages)

        lang_row.addWidget(self.from_combo, 1)
        lang_row.addWidget(self.swap_btn)
        lang_row.addWidget(self.to_combo, 1)
        layout.addLayout(lang_row)

        self.select_defaults()

        # --- file list ---
        self.file_list = QListWidget()
        self.file_list.setSelectionMode(QListWidget.ExtendedSelection)
        layout.addWidget(self.file_list, 1)

        self.hint = QLabel()
        self.hint.setWordWrap(True)
        self.hint.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(self.hint)

        files_row = QHBoxLayout()
        self.add_btn = QPushButton()
        self.add_btn.clicked.connect(self.add_files)
        self.remove_btn = QPushButton()
        self.remove_btn.clicked.connect(self.remove_selected)
        self.clear_btn = QPushButton()
        self.clear_btn.clicked.connect(self.file_list.clear)
        files_row.addWidget(self.add_btn)
        files_row.addWidget(self.remove_btn)
        files_row.addWidget(self.clear_btn)
        files_row.addStretch(1)
        layout.addLayout(files_row)

        # --- output folder ---
        self.output_dir = None
        out_row = QHBoxLayout()
        self.out_btn = QPushButton()
        self.out_btn.clicked.connect(self.choose_output_dir)
        self.output_label = QLabel()
        self.output_label.setStyleSheet("color: gray;")
        self.open_out_btn = QToolButton()
        self.open_out_btn.setIcon(self.style().standardIcon(QStyle.SP_DirOpenIcon))
        self.open_out_btn.setEnabled(False)
        self.open_out_btn.clicked.connect(self.open_output_dir)
        self.reset_out_btn = QToolButton()
        self.reset_out_btn.setText("×")
        self.reset_out_btn.clicked.connect(self.reset_output_dir)
        out_row.addWidget(self.out_btn)
        out_row.addWidget(self.output_label, 1)
        out_row.addWidget(self.open_out_btn)
        out_row.addWidget(self.reset_out_btn)
        layout.addLayout(out_row)

        # --- progress and action ---
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        status_row = QHBoxLayout()
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.clear_status_btn = QToolButton()
        self.clear_status_btn.setVisible(False)
        self.clear_status_btn.clicked.connect(self.clear_status)
        status_row.addWidget(self.status, 1)
        status_row.addWidget(self.clear_status_btn, 0, Qt.AlignTop)
        layout.addLayout(status_row)

        action_row = QHBoxLayout()
        self.translate_btn = QPushButton()
        self.translate_btn.setDefault(True)
        self.translate_btn.clicked.connect(self.start_translation)
        self.cancel_btn = QPushButton()
        self.cancel_btn.setVisible(False)
        self.cancel_btn.clicked.connect(self.cancel_translation)
        action_row.addWidget(self.translate_btn, 1)
        action_row.addWidget(self.cancel_btn, 1)
        layout.addLayout(action_row)

        self.setCentralWidget(central)

        if not self.languages:
            self.translate_btn.setEnabled(False)

        self.retranslate_ui()
        self.restore_settings()

    # --- settings persistence ---
    def restore_settings(self):
        settings = QSettings()
        geometry = settings.value("geometry")
        if geometry is not None:
            self.restoreGeometry(geometry)
        src = settings.value("from_lang", "")
        if src:  # empty = "Detect language" (index 0, already selected)
            for i in range(1, self.from_combo.count()):
                if self.from_combo.itemData(i).code == src:
                    self.from_combo.setCurrentIndex(i)
                    break
        dst = settings.value("to_lang", "")
        for i in range(self.to_combo.count()):
            if self.to_combo.itemData(i).code == dst:
                self.to_combo.setCurrentIndex(i)
                break
        out = settings.value("output_dir", "")
        if out and os.path.isdir(out):
            self.output_dir = out
            self.output_label.setText(out)
            self.output_label.setStyleSheet("")
            self.open_out_btn.setEnabled(True)

    def closeEvent(self, event):
        settings = QSettings()
        settings.setValue("geometry", self.saveGeometry())
        src = self.from_combo.currentData()
        settings.setValue("from_lang", src.code if src else "")
        dst = self.to_combo.currentData()
        settings.setValue("to_lang", dst.code if dst else "")
        settings.setValue("output_dir", self.output_dir or "")
        super().closeEvent(event)

    # --- interface language ---
    def change_language(self, code):
        set_language(code)
        self.retranslate_ui()

    def retranslate_ui(self):
        """Applies the current language to all static texts."""
        self.setWindowTitle(tr("app_title"))
        self.lang_menu.setTitle(tr("menu_language"))
        self.help_menu.setTitle(tr("menu_help"))
        self.about_action.setText(tr("about"))
        self.from_combo.setItemText(0, tr("detect_language"))
        self.swap_btn.setToolTip(tr("swap_tooltip"))
        self.hint.setText(tr("hint", formats=" ".join(SUPPORTED_EXTS)))
        self.add_btn.setText(tr("add"))
        self.remove_btn.setText(tr("remove"))
        self.clear_btn.setText(tr("clear"))
        self.out_btn.setText(tr("output"))
        self.out_btn.setToolTip(tr("output_tooltip"))
        self.open_out_btn.setToolTip(tr("output_open_tooltip"))
        self.reset_out_btn.setToolTip(tr("output_reset_tooltip"))
        if self.output_dir is None:
            self.output_label.setText(tr("output_default"))
        self.clear_status_btn.setText(tr("clear_status"))
        self.clear_status_btn.setToolTip(tr("clear_status_tooltip"))
        self.translate_btn.setText(tr("translate"))
        self.cancel_btn.setText(tr("cancel"))
        # don't clobber the status while a translation runs or a summary is shown
        if (self.worker is None or not self.worker.isRunning()) and (
            not self.clear_status_btn.isVisible()
        ):
            self.status.setText(
                tr("ready") if self.languages else tr("no_packages")
            )

    # --- about ---
    def show_about(self):
        QMessageBox.about(
            self,
            tr("about_title"),
            tr(
                "about_text",
                version=QApplication.applicationVersion(),
                formats=" ".join(SUPPORTED_EXTS),
            ),
        )

    # --- languages ---
    def select_defaults(self):
        self.from_combo.setCurrentIndex(0)  # Detect language
        names = [self.to_combo.itemText(i) for i in range(self.to_combo.count())]
        if "Spanish" in names:
            self.to_combo.setCurrentIndex(names.index("Spanish"))

    def swap_languages(self):
        # the source combo has "Detect language" at index 0
        fi = self.from_combo.currentIndex()
        ti = self.to_combo.currentIndex()
        if fi == 0:
            return
        self.from_combo.setCurrentIndex(ti + 1)
        self.to_combo.setCurrentIndex(fi - 1)

    # --- files ---
    def add_files(self):
        patterns = " ".join(f"*{ext}" for ext in SUPPORTED_EXTS)
        paths, _ = QFileDialog.getOpenFileNames(
            self, tr("select_documents"), "", tr("documents_filter", patterns=patterns)
        )
        self.add_paths(paths)

    def add_paths(self, paths):
        existing = {
            self.file_list.item(i).text() for i in range(self.file_list.count())
        }
        for path in paths:
            ext = os.path.splitext(path)[1].lower()
            if ext in SUPPORTED_EXTS and path not in existing:
                existing.add(path)
                self.file_list.addItem(path)

    def remove_selected(self):
        for item in self.file_list.selectedItems():
            self.file_list.takeItem(self.file_list.row(item))

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        self.add_paths(
            url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()
        )

    # --- output folder ---
    def choose_output_dir(self):
        path = QFileDialog.getExistingDirectory(
            self, tr("output_dir_title"), self.output_dir or ""
        )
        if path:
            self.output_dir = path
            self.output_label.setText(path)
            self.output_label.setStyleSheet("")
            self.open_out_btn.setEnabled(True)

    def reset_output_dir(self):
        self.output_dir = None
        self.output_label.setText(tr("output_default"))
        self.output_label.setStyleSheet("color: gray;")
        self.open_out_btn.setEnabled(False)

    def open_output_dir(self):
        if self.output_dir and os.path.isdir(self.output_dir):
            QDesktopServices.openUrl(QUrl.fromLocalFile(self.output_dir))

    # --- translation ---
    def start_translation(self):
        files = [self.file_list.item(i).text() for i in range(self.file_list.count())]
        if not files:
            QMessageBox.information(
                self, tr("no_files_title"), tr("no_files_msg")
            )
            return

        src = self.from_combo.currentData()  # None = automatic detection
        dst = self.to_combo.currentData()
        if src is not None:
            if src is dst:
                QMessageBox.warning(
                    self, tr("languages_title"), tr("same_language")
                )
                return
            if src.get_translation(dst) is None:
                QMessageBox.warning(
                    self,
                    tr("no_model_title"),
                    tr("no_model_msg", src=src, dst=dst),
                )
                return

        self.results = []
        self.detected = {}  # file index -> detected language
        self.set_busy(True)
        self.progress.setRange(0, 0)  # indeterminate until the first update
        self.progress.setFormat("%p%")

        self.worker = TranslateWorker(
            src, dst, self.languages, files, output_dir=self.output_dir, parent=self
        )
        self.worker.file_started.connect(self.on_file_started)
        self.worker.progress_update.connect(self.on_progress)
        self.worker.phase_changed.connect(self.status.setText)
        self.worker.language_detected.connect(self.on_language_detected)
        self.worker.file_done.connect(self.on_file_done)
        self.worker.file_failed.connect(self.on_file_failed)
        self.worker.finished_all.connect(self.on_finished)
        self.worker.start()

    def clear_status(self):
        self.status.setText(tr("ready"))
        self.clear_status_btn.setVisible(False)

    def set_busy(self, busy):
        if busy:
            self.clear_status_btn.setVisible(False)
        self.translate_btn.setEnabled(not busy)
        self.cancel_btn.setVisible(busy)
        self.cancel_btn.setEnabled(busy)
        self.progress.setVisible(busy)

    def cancel_translation(self):
        if self.worker is not None:
            self.worker.cancel()
            self.cancel_btn.setEnabled(False)
            self.status.setText(tr("cancelling"))

    def on_file_started(self, index, path):
        self._status_base = tr(
            "translating",
            name=os.path.basename(path),
            index=index + 1,
            total=len(self.worker.files),
        )
        self.status.setText(self._status_base)

    def on_language_detected(self, index, name):
        self.detected[index] = name
        self.status.setText(f"{self._status_base} — {tr('detected', name=name)}")

    def on_progress(self, done, total):
        if total > 0:
            self.progress.setRange(0, total)
            self.progress.setValue(done)
            self.progress.setFormat(f"%p% — {done}/{total}")
        else:
            self.progress.setRange(0, 0)

    def on_file_done(self, index, out_path):
        text = out_path
        if index in self.detected:
            text += f"  ({tr('detected', name=self.detected[index])})"
        self.results.append(("ok", text))

    def on_file_failed(self, index, error):
        self.results.append(("error", error))

    def on_finished(self):
        cancelled = self.worker is not None and self.worker.was_cancelled()
        self.set_busy(False)
        ok = [r for kind, r in self.results if kind == "ok"]
        errors = [r for kind, r in self.results if kind == "error"]
        lines = []
        if cancelled:
            lines.append(tr("cancelled"))
        if ok:
            lines.append(tr("translated_header"))
            lines.extend(f"  → {p}" for p in ok)
        if errors:
            lines.append(tr("errors_header"))
            lines.extend(f"  ✗ {e}" for e in errors)
        self.status.setText("\n".join(lines) or tr("ready"))
        self.clear_status_btn.setVisible(bool(lines))
