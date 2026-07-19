import logging
import os


def test_importing_main_configures_warning_silencing():
    import argonaut.main as main

    assert callable(main.main)
    assert "QT_LOGGING_RULES" in os.environ
    assert logging.getLogger("stanza").filters
