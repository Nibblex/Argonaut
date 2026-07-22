"""Main application window."""

import os
import time

import psutil
from PyQt5.QtCore import QSettings, QTimer, QUrl, Qt
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtWidgets import (
    QAction,
    QActionGroup,
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QStyle,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

import argostranslate.settings
import argostranslate.translate

from argonaut import nllb
from argonaut.i18n import LANGUAGES, current_language, set_language, tr
from argonaut.package_dialog import PackageDialog
from argonaut.translation import SUPPORTED_EXTS
from argonaut.worker import ModelDownloadWorker, TranslateWorker

FILE_PATH_ROLE = Qt.UserRole
FILE_SIZE_ROLE = Qt.UserRole + 1


def human_size(num_bytes):
    """Human-readable byte count, e.g. 512 B, 3.4 KB, 12.0 MB."""
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            break
        size /= 1024
    return f"{int(size)} B" if unit == "B" else f"{size:.1f} {unit}"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setMinimumSize(520, 420)
        self.setAcceptDrops(True)
        self.worker = None
        self.downloader = None
        self.results = []
        self.detected = {}
        self._status_base = ""
        self._eta_total = None
        self._eta_t0 = 0.0
        self._eta_done0 = 0

        self.backend = QSettings().value("backend", "argos")
        if self.backend == "nllb" and not nllb.is_model_installed():
            self.backend = "argos"  # the model was removed from disk

        self.max_threads = os.cpu_count() or 1
        saved = QSettings().value("cpu_threads", min(4, self.max_threads), type=int)
        self.cpu_threads = min(max(1, saved), self.max_threads)
        argostranslate.settings.intra_threads = self.cpu_threads

        self.languages = self.load_languages()

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

        # --- settings menu ---
        self.settings_menu = self.menuBar().addMenu("")
        self.engine_menu = self.settings_menu.addMenu("")
        engine_group = QActionGroup(self)
        engine_group.setExclusive(True)
        self.argos_action = QAction("Argos Translate", self, checkable=True)
        self.argos_action.triggered.connect(lambda: self.change_backend("argos"))
        self.nllb_action = QAction("", self, checkable=True)
        self.nllb_action.triggered.connect(lambda: self.change_backend("nllb"))
        for action in (self.argos_action, self.nllb_action):
            engine_group.addAction(action)
            self.engine_menu.addAction(action)
        (self.nllb_action if self.backend == "nllb" else self.argos_action).setChecked(True)
        self.threads_menu = self.settings_menu.addMenu("")
        threads_group = QActionGroup(self)
        threads_group.setExclusive(True)
        for n in range(1, self.max_threads + 1):
            action = QAction(str(n), self, checkable=True)
            action.setChecked(n == self.cpu_threads)
            action.triggered.connect(lambda _, n=n: self.change_cpu_threads(n))
            threads_group.addAction(action)
            self.threads_menu.addAction(action)
        self.settings_menu.addSeparator()
        self.pkg_install_action = QAction("", self)
        self.pkg_install_action.triggered.connect(self.show_package_dialog)
        self.settings_menu.addAction(self.pkg_install_action)
        self.nllb_remove_action = QAction("", self)
        self.nllb_remove_action.triggered.connect(self.remove_nllb_model)
        self.settings_menu.addAction(self.nllb_remove_action)
        # kept accurate even if the model directory is deleted externally
        self.settings_menu.aboutToShow.connect(
            lambda: self.nllb_remove_action.setEnabled(nllb.is_model_installed())
        )
        self.nllb_remove_action.setEnabled(nllb.is_model_installed())

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

        self.total_label = QLabel()
        self.total_label.setStyleSheet("color: gray;")
        layout.addWidget(self.total_label)

        self.hint = QLabel()
        self.hint.setWordWrap(True)
        self.hint.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(self.hint)

        files_row = QHBoxLayout()
        self.add_btn = QPushButton()
        self.add_btn.clicked.connect(self.add_files)
        self.open_file_btn = QPushButton()
        self.open_file_btn.clicked.connect(self.open_selected)
        self.remove_btn = QPushButton()
        self.remove_btn.clicked.connect(self.remove_selected)
        self.clear_btn = QPushButton()
        self.clear_btn.clicked.connect(self.clear_files)
        files_row.addWidget(self.add_btn)
        files_row.addWidget(self.open_file_btn)
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

        # --- skip already-translated files ---
        self.skip_existing_cb = QCheckBox()
        self.skip_existing_cb.toggled.connect(
            lambda checked: QSettings().setValue("skip_existing", checked)
        )
        layout.addWidget(self.skip_existing_cb)

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

        self.engine_label = QLabel()
        self.engine_label.setStyleSheet("color: gray;")
        self.statusBar().addPermanentWidget(self.engine_label)

        # --- CPU/RAM usage of this process ---
        self.process = psutil.Process()
        self.process.cpu_percent()  # prime the counter; the first call is always 0
        self.resource_label = QLabel()
        self.resource_label.setStyleSheet("color: gray;")
        self.statusBar().addPermanentWidget(self.resource_label)
        self._resource_timer = QTimer(self)
        self._resource_timer.timeout.connect(self.update_resource_usage)
        self._resource_timer.start(2000)
        self.update_resource_usage()

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
            self._select_language(self.from_combo, src, first=1)
        dst = settings.value("to_lang", "")
        if dst:
            self._select_language(self.to_combo, dst, first=0)
        out = settings.value("output_dir", "")
        if out and os.path.isdir(out):
            self.output_dir = out
            self.output_label.setText(out)
            self.output_label.setStyleSheet("")
            self.open_out_btn.setEnabled(True)
        self.skip_existing_cb.setChecked(
            settings.value("skip_existing", False, type=bool)
        )

    def closeEvent(self, event):
        if self.downloader is not None and self.downloader.isRunning():
            self.downloader.cancel()
            self.downloader.wait(2000)
        settings = QSettings()
        settings.setValue("geometry", self.saveGeometry())
        src = self.from_combo.currentData()
        settings.setValue("from_lang", src.code if src else "")
        dst = self.to_combo.currentData()
        settings.setValue("to_lang", dst.code if dst else "")
        settings.setValue("output_dir", self.output_dir or "")
        super().closeEvent(event)

    # --- translation engine ---
    def load_languages(self):
        if self.backend == "nllb":
            return nllb.get_installed_languages(threads=self.cpu_threads)
        return argostranslate.translate.get_installed_languages()

    def change_cpu_threads(self, n):
        if n == self.cpu_threads:
            return
        self.cpu_threads = n
        QSettings().setValue("cpu_threads", n)
        argostranslate.settings.intra_threads = n
        # already-loaded CTranslate2 translators keep their thread count, so
        # fresh Language objects are created and the value applies on the
        # next translation, when the translator is (re)instantiated
        argostranslate.translate.get_installed_languages.cache_clear()
        self.languages = self.load_languages()
        self.reload_language_combos()

    def show_package_dialog(self):
        dialog = PackageDialog(self)
        dialog.packages_changed.connect(self.on_packages_changed)
        dialog.exec_()

    def on_packages_changed(self):
        self.languages = self.load_languages()
        self.reload_language_combos()
        if self.worker is None or not self.worker.isRunning():
            self.translate_btn.setEnabled(bool(self.languages))
            if not self.clear_status_btn.isVisible():
                self.status.setText(
                    tr("ready") if self.languages else tr("no_packages")
                )

    def change_backend(self, name):
        if name == self.backend:
            return
        if name == "nllb" and not nllb.is_model_installed():
            answer = QMessageBox.question(
                self,
                tr("nllb_download_title"),
                tr("nllb_download_msg", size=nllb.MODEL_SIZE_MB),
            )
            if answer != QMessageBox.Yes:
                self.argos_action.setChecked(True)
                return
            self.start_model_download()
            return
        self.apply_backend(name)

    def apply_backend(self, name):
        self.backend = name
        QSettings().setValue("backend", name)
        self.languages = self.load_languages()
        self.reload_language_combos()
        self.translate_btn.setEnabled(bool(self.languages))
        (self.nllb_action if name == "nllb" else self.argos_action).setChecked(True)
        self.nllb_remove_action.setEnabled(nllb.is_model_installed())
        self.update_engine_label()
        self.status.setText(tr("ready") if self.languages else tr("no_packages"))
        self.clear_status_btn.setVisible(False)

    def update_resource_usage(self):
        # normalized to total capacity so it reads like a system monitor
        # (100% = all cores busy) even when the engine uses every core
        cpu = self.process.cpu_percent() / (psutil.cpu_count() or 1)
        ram = self.process.memory_info().rss >> 20
        self.resource_label.setText(f"CPU {cpu:.0f}%  ·  RAM {ram} MB")

    def update_engine_label(self):
        name = "NLLB-200" if self.backend == "nllb" else "Argos Translate"
        self.engine_label.setText(tr("engine_status", name=name))

    def remove_nllb_model(self):
        answer = QMessageBox.question(
            self,
            tr("nllb_download_title"),
            tr("nllb_remove_msg", size=nllb.MODEL_SIZE_MB),
        )
        if answer != QMessageBox.Yes:
            return
        if self.backend == "nllb":
            self.apply_backend("argos")
        nllb.remove_model()
        self.nllb_remove_action.setEnabled(False)
        self.status.setText(tr("nllb_removed"))

    def reload_language_combos(self):
        """Repopulates both combos with the current backend's languages,
        keeping the selection when the language exists in both."""
        src = self.from_combo.currentData()
        dst = self.to_combo.currentData()
        self.from_combo.clear()
        self.to_combo.clear()
        self.from_combo.addItem(tr("detect_language"), None)
        for lang in self.languages:
            self.from_combo.addItem(str(lang), lang)
            self.to_combo.addItem(str(lang), lang)
        self.select_defaults()
        if src is not None:
            self._select_language(self.from_combo, src.code, first=1)
        if dst is not None:
            self._select_language(self.to_combo, dst.code, first=0)

    @staticmethod
    def _select_language(combo, code, first):
        for i in range(first, combo.count()):
            if combo.itemData(i).code == code:
                combo.setCurrentIndex(i)
                return

    def start_model_download(self):
        self.downloader = ModelDownloadWorker(parent=self)
        self.downloader.progress.connect(self.on_download_progress)
        self.downloader.download_finished.connect(self.on_download_finished)
        self.set_busy(True)
        self.progress.setRange(0, 0)
        self.status.setText(tr("downloading_model"))
        self.downloader.start()

    def on_download_progress(self, done, total):
        self.progress.setRange(0, total)
        self.progress.setValue(done)
        self.progress.setFormat(f"%p% — {done}/{total} MB")

    def on_download_finished(self, ok, error):
        self.set_busy(False)
        self.translate_btn.setEnabled(bool(self.languages))
        if ok:
            self.apply_backend("nllb")
        else:
            self.argos_action.setChecked(True)
            self.status.setText(tr("cancelled") if not error else tr("ready"))
            if error:
                QMessageBox.warning(
                    self,
                    tr("nllb_download_title"),
                    tr("download_failed", error=error),
                )

    # --- interface language ---
    def change_language(self, code):
        set_language(code)
        self.retranslate_ui()

    def retranslate_ui(self):
        """Applies the current language to all static texts."""
        self.setWindowTitle(tr("app_title"))
        self.lang_menu.setTitle(tr("menu_language"))
        self.settings_menu.setTitle(tr("menu_settings"))
        self.engine_menu.setTitle(tr("menu_engine"))
        self.nllb_action.setText(tr("engine_nllb"))
        self.threads_menu.setTitle(tr("menu_threads"))
        self.pkg_install_action.setText(tr("pkg_install"))
        self.nllb_remove_action.setText(tr("nllb_remove"))
        self.update_engine_label()
        self.help_menu.setTitle(tr("menu_help"))
        self.about_action.setText(tr("about"))
        self.from_combo.setItemText(0, tr("detect_language"))
        self.swap_btn.setToolTip(tr("swap_tooltip"))
        self.hint.setText(tr("hint", formats=" ".join(SUPPORTED_EXTS)))
        self.update_total_size()
        self.add_btn.setText(tr("add"))
        self.open_file_btn.setText(tr("open"))
        self.open_file_btn.setToolTip(tr("open_tooltip"))
        self.remove_btn.setText(tr("remove"))
        self.clear_btn.setText(tr("clear"))
        self.out_btn.setText(tr("output"))
        self.out_btn.setToolTip(tr("output_tooltip"))
        self.open_out_btn.setToolTip(tr("output_open_tooltip"))
        self.reset_out_btn.setToolTip(tr("output_reset_tooltip"))
        self.skip_existing_cb.setText(tr("skip_existing"))
        self.skip_existing_cb.setToolTip(tr("skip_existing_tooltip"))
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

    def paths(self):
        return [
            self.file_list.item(i).data(FILE_PATH_ROLE)
            for i in range(self.file_list.count())
        ]

    def add_paths(self, paths):
        existing = set(self.paths())
        for path in paths:
            ext = os.path.splitext(path)[1].lower()
            if ext in SUPPORTED_EXTS and path not in existing:
                existing.add(path)
                self.add_file_item(path)
        self.update_total_size()

    def add_file_item(self, path):
        try:
            size = os.path.getsize(path)
        except OSError:
            size = 0
        item = QListWidgetItem(f"{path}  ·  {human_size(size)}")
        item.setData(FILE_PATH_ROLE, path)
        item.setData(FILE_SIZE_ROLE, size)
        self.file_list.addItem(item)

    def update_total_size(self):
        count = self.file_list.count()
        if not count:
            self.total_label.clear()
            return
        total = sum(
            self.file_list.item(i).data(FILE_SIZE_ROLE) or 0 for i in range(count)
        )
        self.total_label.setText(
            tr("batch_total", count=count, size=human_size(total))
        )

    def clear_files(self):
        self.file_list.clear()
        self.update_total_size()

    def open_selected(self):
        for item in self.file_list.selectedItems():
            path = item.data(FILE_PATH_ROLE)
            if os.path.exists(path):
                QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def remove_selected(self):
        for item in self.file_list.selectedItems():
            self.file_list.takeItem(self.file_list.row(item))
        self.update_total_size()

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        self.add_paths(
            self.expand_dirs(
                url.toLocalFile()
                for url in event.mimeData().urls()
                if url.isLocalFile()
            )
        )

    @staticmethod
    def expand_dirs(paths):
        """Yields files as-is and walks dropped directories recursively;
        add_paths filters out the unsupported extensions."""
        for path in paths:
            if os.path.isdir(path):
                for root, dirs, files in os.walk(path):
                    dirs.sort()
                    for name in sorted(files):
                        yield os.path.join(root, name)
            else:
                yield path

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
        files = self.paths()
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
            src, dst, self.languages, files,
            output_dir=self.output_dir,
            skip_existing=self.skip_existing_cb.isChecked(),
            parent=self,
        )
        self.worker.file_started.connect(self.on_file_started)
        self.worker.progress_update.connect(self.on_progress)
        self.worker.phase_changed.connect(self.status.setText)
        self.worker.language_detected.connect(self.on_language_detected)
        self.worker.file_done.connect(self.on_file_done)
        self.worker.file_failed.connect(self.on_file_failed)
        self.worker.file_skipped.connect(self.on_file_skipped)
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
        if self.downloader is not None and self.downloader.isRunning():
            self.downloader.cancel()
            self.cancel_btn.setEnabled(False)
            self.status.setText(tr("cancelling"))
        elif self.worker is not None:
            self.worker.cancel()
            self.cancel_btn.setEnabled(False)
            self.status.setText(tr("cancelling"))

    def on_file_started(self, index, path):
        self.reset_eta()
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
            eta = self.estimate_eta(done, total)
            text = f"%p% — {done}/{total}"
            if eta is not None:
                text += f" — ~{self.format_duration(eta)}"
            self.progress.setFormat(text)
        else:
            self.progress.setRange(0, 0)
            self.reset_eta()

    # --- remaining-time estimation ---
    def reset_eta(self):
        self._eta_total = None

    def estimate_eta(self, done, total):
        """Estimated seconds left, from the average pace since this phase
        started. None while there is not enough signal (or on the sample
        that resets the estimator when the file or phase changes)."""
        now = time.monotonic()
        if self._eta_total != total or done < self._eta_done0:
            self._eta_total = total
            self._eta_t0 = now
            self._eta_done0 = done
            return None
        progressed = done - self._eta_done0
        elapsed = now - self._eta_t0
        if progressed <= 0 or elapsed < 1.0 or done >= total:
            return None
        return (total - done) * elapsed / progressed

    def on_file_done(self, index, out_path, seconds):
        text = f"{out_path}  ({self.format_duration(seconds)})"
        if index in self.detected:
            text += f"  ({tr('detected', name=self.detected[index])})"
        self.results.append(("ok", text))

    @staticmethod
    def format_duration(seconds):
        minutes, secs = divmod(int(seconds), 60)
        hours, minutes = divmod(minutes, 60)
        days, hours = divmod(hours, 24)
        if days:
            return f"{days}d {hours}h" if hours else f"{days}d"
        if hours:
            return f"{hours}h {minutes:02d}m" if minutes else f"{hours}h"
        return f"{minutes:02d}:{secs:02d}"

    def on_file_failed(self, index, error):
        self.results.append(("error", error))

    def on_file_skipped(self, index, out_path):
        self.results.append(("skipped", out_path))

    def on_finished(self):
        cancelled = self.worker is not None and self.worker.was_cancelled()
        self.set_busy(False)
        ok = [r for kind, r in self.results if kind == "ok"]
        skipped = [r for kind, r in self.results if kind == "skipped"]
        errors = [r for kind, r in self.results if kind == "error"]
        lines = []
        if cancelled:
            lines.append(tr("cancelled"))
        if ok:
            lines.append(tr("translated_header"))
            lines.extend(f"  → {p}" for p in ok)
        if skipped:
            lines.append(tr("skipped_header"))
            lines.extend(f"  ↷ {p}" for p in skipped)
        if errors:
            lines.append(tr("errors_header"))
            lines.extend(f"  ✗ {e}" for e in errors)
        self.status.setText("\n".join(lines) or tr("ready"))
        self.clear_status_btn.setVisible(bool(lines))
