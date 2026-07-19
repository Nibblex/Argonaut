#!/usr/bin/env python3
"""Minimalist document translator (PyQt5 + argos-translate-files).

Entry point: sets up warning silencing (which must happen before importing
the libraries that emit them) and launches the main window.
"""

import logging
import os
import sys
import warnings

# silence harmless warnings: window-activation attempts on Wayland, the
# requests version check and the mwt processor that stanza adds on its own
os.environ.setdefault(
    "QT_LOGGING_RULES", "*.debug=false;qt.qpa.wayland.warning=false"
)
warnings.filterwarnings("ignore", message=".*doesn't match a supported version.*")
# a filter rather than setLevel: argostranslate resets the stanza logger
# level to WARNING every time it creates its pipeline, but filters persist
logging.getLogger("stanza").addFilter(lambda r: r.levelno >= logging.ERROR)

from PyQt5.QtWidgets import QApplication

from argonaut import __version__
from argonaut.i18n import load_language
from argonaut.window import MainWindow


def main():
    app = QApplication(sys.argv)
    # organization and application identify where QSettings stores the language
    app.setOrganizationName("Argonaut")
    app.setApplicationName("Argonaut")
    app.setApplicationVersion(__version__)
    load_language()
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
