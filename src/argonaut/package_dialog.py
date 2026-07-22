"""Dialog to browse, install and remove Argos language packages from
the GUI."""

from PyQt5.QtCore import QSettings, Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from argonaut import packages
from argonaut.i18n import tr
from argonaut.worker import (
    PackageInstallWorker,
    PackageListWorker,
    PackageSizeWorker,
)

PACKAGE_ROLE = Qt.UserRole
INSTALLED_ROLE = Qt.UserRole + 1
SIZE_ROLE = Qt.UserRole + 2


class PackageDialog(QDialog):
    """Lists the packages from the Argos index; the checked ones can be
    installed (with per-package download progress) or removed."""

    packages_changed = pyqtSignal()  # something was installed or removed

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("pkg_title"))
        self.setMinimumSize(380, 420)
        self.installer = None
        self.sizer = None
        self.errors = []

        layout = QVBoxLayout(self)

        filter_row = QHBoxLayout()
        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText(tr("pkg_filter"))
        self.filter_edit.textChanged.connect(self.apply_filter)
        self.select_all = QCheckBox(tr("pkg_select_all"))
        self.select_all.clicked.connect(self.on_select_all_clicked)
        filter_row.addWidget(self.filter_edit, 1)
        filter_row.addWidget(self.select_all)
        layout.addLayout(filter_row)

        self.package_list = QListWidget()
        self.package_list.itemChanged.connect(self.update_buttons)
        layout.addWidget(self.package_list, 1)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        self.status = QLabel(tr("pkg_loading"))
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        buttons = QHBoxLayout()
        self.install_btn = QPushButton(tr("pkg_install_btn"))
        self.install_btn.setEnabled(False)
        self.install_btn.clicked.connect(self.start_install)
        self.remove_btn = QPushButton(tr("pkg_remove_btn"))
        self.remove_btn.setEnabled(False)
        self.remove_btn.clicked.connect(self.start_remove)
        self.cancel_btn = QPushButton(tr("cancel"))
        self.cancel_btn.setVisible(False)
        self.cancel_btn.clicked.connect(self.cancel_install)
        self.close_btn = QPushButton(tr("close"))
        self.close_btn.clicked.connect(self.close)
        buttons.addWidget(self.install_btn, 1)
        buttons.addWidget(self.remove_btn, 1)
        buttons.addWidget(self.cancel_btn, 1)
        buttons.addWidget(self.close_btn)
        layout.addLayout(buttons)

        self.lister = PackageListWorker(parent=self)
        self.lister.listed.connect(self.on_listed)
        self.lister.start()

    # --- package list ---
    def on_listed(self, available, error):
        if error:
            self.status.setText(tr("pkg_load_failed", error=error))
            return
        installed = packages.installed_pairs()
        unmeasured = []
        for row, pkg in enumerate(available):
            item = QListWidgetItem()
            item.setData(PACKAGE_ROLE, pkg)
            item.setData(SIZE_ROLE, QSettings().value(size_key(pkg), 0, type=int))
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            self.set_installed(item, packages.pair(pkg) in installed)
            self.package_list.addItem(item)
            if not item.data(SIZE_ROLE):
                unmeasured.append((row, pkg))
        self.apply_filter(self.filter_edit.text())
        self.status.setText(tr("ready"))
        if unmeasured:
            self.sizer = PackageSizeWorker(unmeasured, parent=self)
            self.sizer.size_ready.connect(self.on_size_ready)
            self.sizer.start()

    def set_installed(self, item, installed):
        item.setData(INSTALLED_ROLE, installed)
        self.refresh_item_text(item)
        item.setCheckState(Qt.Unchecked)

    def refresh_item_text(self, item):
        pkg = item.data(PACKAGE_ROLE)
        text = f"{pkg.from_name} → {pkg.to_name}"
        size = item.data(SIZE_ROLE)
        if size:
            text += f"  ·  {max(1, round(size / 2**20))} MB"
        if item.data(INSTALLED_ROLE):
            text += f"  ({tr('pkg_installed')})"
        item.setText(text)

    def on_size_ready(self, row, size):
        if not size:
            return
        item = self.package_list.item(row)
        item.setData(SIZE_ROLE, size)
        QSettings().setValue(size_key(item.data(PACKAGE_ROLE)), size)
        self.refresh_item_text(item)

    def apply_filter(self, text):
        text = text.strip().lower()
        for i in range(self.package_list.count()):
            item = self.package_list.item(i)
            item.setHidden(bool(text) and text not in item.text().lower())
        self.sync_select_all()

    def visible_items(self):
        return [
            self.package_list.item(i)
            for i in range(self.package_list.count())
            if not self.package_list.item(i).isHidden()
        ]

    def on_select_all_clicked(self, checked):
        state = Qt.Checked if checked else Qt.Unchecked
        for item in self.visible_items():
            item.setCheckState(state)
        self.sync_select_all()

    def sync_select_all(self):
        """Mirrors the item check states: unchecked, checked or partial."""
        items = self.visible_items()
        checked = sum(item.checkState() == Qt.Checked for item in items)
        if not items or checked == 0:
            state = Qt.Unchecked
        elif checked == len(items):
            state = Qt.Checked
        else:
            state = Qt.PartiallyChecked
        self.select_all.setCheckState(state)

    def checked_items(self, installed):
        return [
            item
            for item in (
                self.package_list.item(i)
                for i in range(self.package_list.count())
            )
            if item.checkState() == Qt.Checked
            and bool(item.data(INSTALLED_ROLE)) == installed
        ]

    def update_buttons(self):
        self.sync_select_all()
        idle = self.installer is None
        self.install_btn.setEnabled(
            idle and bool(self.checked_items(installed=False))
        )
        self.remove_btn.setEnabled(
            idle and bool(self.checked_items(installed=True))
        )

    # --- installation ---
    def start_install(self):
        items = self.checked_items(installed=False)
        if not items:
            return
        self.errors = []
        self.set_busy(True)
        self.installer = PackageInstallWorker(
            [item.data(PACKAGE_ROLE) for item in items], parent=self
        )
        self.installer.package_started.connect(self.on_package_started)
        self.installer.progress.connect(self.on_progress)
        self.installer.package_failed.connect(
            lambda desc, err: self.errors.append(f"{desc}: {err}")
        )
        self.installer.install_finished.connect(self.on_install_finished)
        self.installer.start()

    def set_busy(self, busy):
        self.filter_edit.setEnabled(not busy)
        self.select_all.setEnabled(not busy)
        self.package_list.setEnabled(not busy)
        self.install_btn.setEnabled(not busy)
        self.remove_btn.setEnabled(not busy)
        self.cancel_btn.setVisible(busy)
        self.cancel_btn.setEnabled(busy)
        self.progress.setVisible(busy)
        self.progress.setRange(0, 0)

    def cancel_install(self):
        if self.installer is not None:
            self.installer.cancel()
            self.cancel_btn.setEnabled(False)
            self.status.setText(tr("cancelling"))

    def on_package_started(self, index, total, description):
        self.status.setText(
            tr("pkg_downloading", name=description, index=index + 1, total=total)
        )

    def on_progress(self, done, total):
        self.progress.setRange(0, total)
        self.progress.setValue(done)
        self.progress.setFormat(f"%p% — {done}/{total} MB")

    def on_install_finished(self, count):
        cancelled = self.installer is not None and self.installer.was_cancelled()
        self.installer = None
        self.set_busy(False)
        self.refresh_installed_marks()
        self.update_buttons()

        lines = []
        if cancelled:
            lines.append(tr("cancelled"))
        if count:
            lines.append(tr("pkg_done", count=count))
        if self.errors:
            lines.append(tr("errors_header"))
            lines.extend(f"  ✗ {e}" for e in self.errors)
        self.status.setText("\n".join(lines) or tr("ready"))
        if count:
            self.packages_changed.emit()

    def refresh_installed_marks(self):
        installed = packages.installed_pairs()
        for i in range(self.package_list.count()):
            item = self.package_list.item(i)
            if not item.data(INSTALLED_ROLE) and (
                packages.pair(item.data(PACKAGE_ROLE)) in installed
            ):
                self.set_installed(item, True)

    # --- removal ---
    def start_remove(self):
        items = self.checked_items(installed=True)
        if not items:
            return
        answer = QMessageBox.question(
            self, tr("pkg_title"), tr("pkg_remove_msg", count=len(items))
        )
        if answer != QMessageBox.Yes:
            return

        removed = 0
        errors = []
        for item in items:
            pkg = item.data(PACKAGE_ROLE)
            try:
                packages.uninstall(packages.pair(pkg))
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{pkg.from_name} → {pkg.to_name}: {exc}")
            else:
                removed += 1
                self.set_installed(item, False)

        lines = []
        if removed:
            lines.append(tr("pkg_removed", count=removed))
        if errors:
            lines.append(tr("errors_header"))
            lines.extend(f"  ✗ {e}" for e in errors)
        self.status.setText("\n".join(lines) or tr("ready"))
        self.update_buttons()
        if removed:
            self.packages_changed.emit()

    def closeEvent(self, event):
        if self.installer is not None and self.installer.isRunning():
            self.installer.cancel()
            self.installer.wait(5000)
        if self.sizer is not None and self.sizer.isRunning():
            self.sizer.cancel()
            self.sizer.wait(5000)
        if self.lister.isRunning():
            self.lister.wait(5000)
        super().closeEvent(event)


def size_key(pkg):
    """QSettings key caching a package's size; versioned so a new release
    of the package is measured again."""
    return f"pkg_size/{pkg.code}@{pkg.package_version}"
