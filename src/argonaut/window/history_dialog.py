"""Dialog listing the translations recorded in the history."""

import os
from datetime import datetime

from PyQt5.QtCore import QUrl, Qt, pyqtSignal
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)

from argonaut.history import TranslationHistory
from argonaut.i18n import tr
from argonaut.window.translation_run import TranslationRunMixin

DATE_COL = 0
FILE_COL = 1
PAIR_COL = 2
ENGINE_COL = 3
TIME_COL = 4
COLUMN_KEYS = (
    "hist_col_date", "hist_col_file", "hist_col_pair",
    "hist_col_engine", "hist_col_time",
)

OUTPUT_ROLE = Qt.UserRole  # where the translation was written
SOURCE_ROLE = Qt.UserRole + 1

ENGINE_NAMES = {"nllb": "NLLB-200", "argos": "Argos Translate"}


class HistoryDialog(QDialog):
    """Shows what was translated, newest first. Double-clicking a row opens
    the translated file; rows whose output no longer exists are greyed out
    rather than hidden, since the history is a record of what happened."""

    history_cleared = pyqtSignal()  # so the menu's size label can refresh

    def __init__(self, db_path=None, parent=None):
        super().__init__(parent)
        self.db_path = db_path or TranslationHistory.default_db_path()
        self.setWindowTitle(tr("hist_title"))
        self.setMinimumSize(620, 380)

        layout = QVBoxLayout(self)
        self.tree = QTreeWidget()
        self.tree.setRootIsDecorated(False)
        self.tree.setAlternatingRowColors(True)
        self.tree.setSortingEnabled(True)
        self.tree.setHeaderLabels([tr(key) for key in COLUMN_KEYS])
        self.tree.itemDoubleClicked.connect(self.open_item)
        layout.addWidget(self.tree, 1)

        self.summary = QLabel()
        self.summary.setStyleSheet("color: gray;")
        layout.addWidget(self.summary)

        buttons = QHBoxLayout()
        self.open_btn = QPushButton(tr("hist_open"))
        self.open_btn.setEnabled(False)
        self.open_btn.clicked.connect(self.open_selected)
        self.clear_btn = QPushButton(tr("hist_clear"))
        self.clear_btn.clicked.connect(self.clear_history)
        self.close_btn = QPushButton(tr("close"))
        self.close_btn.clicked.connect(self.accept)
        buttons.addWidget(self.open_btn)
        buttons.addWidget(self.clear_btn)
        buttons.addStretch(1)
        buttons.addWidget(self.close_btn)
        layout.addLayout(buttons)

        self.tree.itemSelectionChanged.connect(self.update_buttons)
        self.reload()

    def reload(self):
        """Reads the database again and repopulates the list."""
        self.tree.setSortingEnabled(False)  # sorting while filling is wasted work
        self.tree.clear()
        history = TranslationHistory(self.db_path, ttl_days=0)  # never prune here
        try:
            entries = history.entries()
        finally:
            history.close()
        for entry in entries:
            self.tree.addTopLevelItem(self._item_for(entry))
        self.tree.setSortingEnabled(True)
        for col in range(self.tree.columnCount()):
            self.tree.resizeColumnToContents(col)
        self.summary.setText(
            tr("hist_count", count=len(entries)) if entries else tr("hist_empty")
        )
        self.clear_btn.setEnabled(bool(entries))
        self.update_buttons()

    @staticmethod
    def _item_for(entry):
        item = QTreeWidgetItem()
        item.setText(
            DATE_COL,
            datetime.fromtimestamp(entry.translated_at).strftime("%Y-%m-%d %H:%M"),
        )
        item.setText(FILE_COL, os.path.basename(entry.source_path))
        item.setText(PAIR_COL, f"{entry.from_code} → {entry.to_code}")
        item.setText(ENGINE_COL, ENGINE_NAMES.get(entry.engine, entry.engine))
        item.setText(TIME_COL, TranslationRunMixin.format_duration(entry.seconds))
        item.setTextAlignment(TIME_COL, Qt.AlignRight | Qt.AlignVCenter)
        item.setData(FILE_COL, OUTPUT_ROLE, entry.output_path)
        item.setData(FILE_COL, SOURCE_ROLE, entry.source_path)
        item.setToolTip(
            FILE_COL, f"{entry.source_path}\n→ {entry.output_path}"
        )
        if not (entry.output_path and os.path.exists(entry.output_path)):
            item.setDisabled(True)  # the translation was moved or deleted
            item.setToolTip(FILE_COL, item.toolTip(FILE_COL) + f"\n{tr('hist_missing')}")
        return item

    def selected_output(self):
        items = self.tree.selectedItems()
        if not items:
            return None
        path = items[0].data(FILE_COL, OUTPUT_ROLE)
        return path if path and os.path.exists(path) else None

    def update_buttons(self):
        self.open_btn.setEnabled(self.selected_output() is not None)

    def open_selected(self):
        path = self.selected_output()
        if path:
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def open_item(self, item, _column):
        path = item.data(FILE_COL, OUTPUT_ROLE)
        if path and os.path.exists(path):
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def clear_history(self):
        count, _ = TranslationHistory.db_info(self.db_path)
        answer = QMessageBox.question(
            self, tr("hist_title"), tr("hist_clear_msg", count=count)
        )
        if answer != QMessageBox.Yes:
            return
        TranslationHistory.purge_db(self.db_path)
        self.reload()
        self.history_cleared.emit()
