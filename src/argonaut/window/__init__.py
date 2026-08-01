"""Main application window, split by concern:

- file_list: the columns, per-file roles and the sortable row item
- files: adding/removing/opening files, drag and drop, the output folder
- engine: backend, threads, cache and history menus, packages, NLLB model
- translation_run: driving a batch and reflecting its progress
- main_window: widget construction, persistence and the deferred close

Everything the old argonaut.window module exposed is re-exported here, so
``from argonaut.window import MainWindow`` keeps working. The modules the
tests monkeypatch through this namespace (argostranslate, nllb, time,
QDesktopServices, TranslationCache, TranslationHistory) are imported for
the same reason."""

import time  # noqa: F401  (patched via argonaut.window.time in tests)

from PyQt5.QtGui import QDesktopServices  # noqa: F401

import argostranslate.settings  # noqa: F401
import argostranslate.translate  # noqa: F401

from argonaut import nllb  # noqa: F401
from argonaut.history import TranslationHistory  # noqa: F401
from argonaut.package_dialog import PackageDialog  # noqa: F401
from argonaut.translation import TranslationCache  # noqa: F401
from argonaut.window.file_list import (
    COLUMN_KEYS,
    FILE_MTIME_ROLE,
    FILE_PATH_ROLE,
    FILE_REUSED_ROLE,
    FILE_SIZE_ROLE,
    FILE_STATE_ROLE,
    FOLDER_COL,
    HIDEABLE_COLS,
    MODIFIED_COL,
    NAME_COL,
    SIZE_COL,
    STATUS_COL,
    STATUS_STATES,
    TYPE_COL,
    FileItem,
    FileTree,
    human_size,
)
from argonaut.window.main_window import MainWindow

__all__ = [
    "COLUMN_KEYS",
    "FILE_MTIME_ROLE",
    "FILE_PATH_ROLE",
    "FILE_REUSED_ROLE",
    "FILE_SIZE_ROLE",
    "FILE_STATE_ROLE",
    "FOLDER_COL",
    "HIDEABLE_COLS",
    "MODIFIED_COL",
    "NAME_COL",
    "SIZE_COL",
    "STATUS_COL",
    "STATUS_STATES",
    "TYPE_COL",
    "FileItem",
    "FileTree",
    "MainWindow",
    "human_size",
]
