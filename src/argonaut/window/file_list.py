"""The file list's columns, per-file data roles and its sortable row item."""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QTreeWidgetItem

NAME_COL = 0
TYPE_COL = 1
SIZE_COL = 2
MODIFIED_COL = 3
FOLDER_COL = 4
STATUS_COL = 5
# header text keys, one per column, in column order
COLUMN_KEYS = (
    "col_name", "col_type", "col_size", "col_modified", "col_folder", "col_status",
)
# columns the user can show/hide from the header's context menu (Name always shows)
HIDEABLE_COLS = (TYPE_COL, SIZE_COL, MODIFIED_COL, FOLDER_COL, STATUS_COL)

FILE_PATH_ROLE = Qt.UserRole
FILE_SIZE_ROLE = Qt.UserRole + 1
FILE_MTIME_ROLE = Qt.UserRole + 2
FILE_STATE_ROLE = Qt.UserRole + 3
FILE_REUSED_ROLE = Qt.UserRole + 4  # segments this file served from the cache

# per-file translation states, in the order used to sort the Status column
STATUS_STATES = ("pending", "translating", "done", "skipped", "failed", "cancelled")


def _status_rank(item):
    state = item.data(STATUS_COL, FILE_STATE_ROLE)
    return STATUS_STATES.index(state) if state in STATUS_STATES else -1


class FileItem(QTreeWidgetItem):
    """A row in the file list. The size and modified columns sort by their
    raw numeric value rather than their formatted text, and the status column
    by its state's rank; the rest sort case-insensitively by their text."""

    def __lt__(self, other):
        tree = self.treeWidget()
        column = tree.sortColumn() if tree else NAME_COL
        if column == SIZE_COL:
            return (self.data(SIZE_COL, FILE_SIZE_ROLE) or 0) < (
                other.data(SIZE_COL, FILE_SIZE_ROLE) or 0
            )
        if column == MODIFIED_COL:
            return (self.data(MODIFIED_COL, FILE_MTIME_ROLE) or 0) < (
                other.data(MODIFIED_COL, FILE_MTIME_ROLE) or 0
            )
        if column == STATUS_COL:
            return _status_rank(self) < _status_rank(other)
        return self.text(column).lower() < other.text(column).lower()


def human_size(num_bytes):
    """Human-readable byte count, e.g. 512 B, 3.4 KB, 12.0 MB."""
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            break
        size /= 1024
    return f"{int(size)} B" if unit == "B" else f"{size:.1f} {unit}"
