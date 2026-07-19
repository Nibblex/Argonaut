import pytest
from PyQt5.QtWidgets import QFileDialog, QMessageBox

import argonaut.window
from argonaut.i18n import tr
from argonaut.window import MainWindow
from tests.conftest import FakeLanguage, FakeTranslation


@pytest.fixture
def langs(monkeypatch):
    english = FakeLanguage("en", "English")
    spanish = FakeLanguage("es", "Spanish")
    english._translations["es"] = FakeTranslation(english, spanish)
    monkeypatch.setattr(
        argonaut.window.argostranslate.translate,
        "get_installed_languages",
        lambda: [english, spanish],
    )
    return english, spanish


@pytest.fixture
def window(qtbot, langs):
    win = MainWindow()
    qtbot.addWidget(win)
    return win


def test_no_installed_languages_disables_translation(qtbot, monkeypatch):
    monkeypatch.setattr(
        argonaut.window.argostranslate.translate, "get_installed_languages", lambda: []
    )
    win = MainWindow()
    qtbot.addWidget(win)
    assert not win.translate_btn.isEnabled()
    assert win.status.text() == tr("no_packages")


def test_defaults_detect_language_and_spanish_target(window):
    assert window.from_combo.currentIndex() == 0
    assert window.from_combo.currentData() is None
    assert window.to_combo.currentText() == "Spanish"


def test_add_paths_filters_and_deduplicates(window):
    window.add_paths(["/a/doc.txt", "/a/doc.txt", "/a/image.jpg", "/a/book.epub"])
    items = [window.file_list.item(i).text() for i in range(window.file_list.count())]
    assert items == ["/a/doc.txt", "/a/book.epub"]


def test_remove_selected(window):
    window.add_paths(["/a/one.txt", "/a/two.txt"])
    window.file_list.item(0).setSelected(True)
    window.remove_selected()
    items = [window.file_list.item(i).text() for i in range(window.file_list.count())]
    assert items == ["/a/two.txt"]


def test_swap_languages(window):
    window.from_combo.setCurrentIndex(1)  # English
    window.to_combo.setCurrentIndex(1)  # Spanish
    window.swap_languages()
    assert window.from_combo.currentText() == "Spanish"
    assert window.to_combo.currentText() == "English"


def test_swap_does_nothing_on_detect_language(window):
    window.from_combo.setCurrentIndex(0)
    before = window.to_combo.currentIndex()
    window.swap_languages()
    assert window.from_combo.currentIndex() == 0
    assert window.to_combo.currentIndex() == before


def test_change_language_retranslates_ui(window):
    window.change_language("es")
    assert window.translate_btn.text() == "Traducir"
    assert window.windowTitle() == "Argonaut — Documentos"
    window.change_language("en")
    assert window.translate_btn.text() == "Translate"


def test_output_dir_choose_and_reset(window, tmp_path):
    window.output_dir = str(tmp_path)
    window.output_label.setText(str(tmp_path))
    window.reset_output_dir()
    assert window.output_dir is None
    assert window.output_label.text() == tr("output_default")


def test_translation_requires_files(window, monkeypatch):
    boxes = []
    monkeypatch.setattr(
        QMessageBox, "information", lambda *args: boxes.append(args[2])
    )
    window.start_translation()
    assert boxes == [tr("no_files_msg")]


def test_translation_rejects_same_language(window, monkeypatch, langs):
    english, _ = langs
    boxes = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: boxes.append(args[2]))
    window.add_paths(["/a/doc.txt"])
    window.from_combo.setCurrentIndex(1)  # English
    window.to_combo.setCurrentIndex(0)  # English
    window.start_translation()
    assert boxes == [tr("same_language")]


def test_translation_rejects_missing_model(window, monkeypatch):
    boxes = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: boxes.append(args[2]))
    window.add_paths(["/a/doc.txt"])
    window.from_combo.setCurrentIndex(2)  # Spanish: no es->en model registered
    window.to_combo.setCurrentIndex(0)  # English
    window.start_translation()
    assert len(boxes) == 1
    assert "Spanish" in boxes[0] and "English" in boxes[0]


def test_finished_summary_lists_results_and_errors(window):
    window.worker = None
    window.results = [("ok", "/a/doc_es.txt"), ("error", "boom")]

    class DoneWorker:
        def isRunning(self):
            return False

        def was_cancelled(self):
            return False

    window.worker = DoneWorker()
    window.on_finished()
    text = window.status.text()
    assert "/a/doc_es.txt" in text
    assert "boom" in text
    assert not window.clear_status_btn.isHidden()
    window.clear_status()
    assert window.status.text() == tr("ready")
    assert window.clear_status_btn.isHidden()


def test_add_files_dialog(window, monkeypatch, tmp_path):
    doc = tmp_path / "doc.txt"
    doc.write_text("hello")
    monkeypatch.setattr(
        QFileDialog, "getOpenFileNames", staticmethod(lambda *a, **k: ([str(doc)], ""))
    )
    window.add_files()
    assert window.file_list.item(0).text() == str(doc)


def test_choose_output_dir_dialog(window, monkeypatch, tmp_path):
    monkeypatch.setattr(
        QFileDialog, "getExistingDirectory", staticmethod(lambda *a, **k: str(tmp_path))
    )
    window.choose_output_dir()
    assert window.output_dir == str(tmp_path)
    assert window.output_label.text() == str(tmp_path)


def test_full_translation_through_the_window(window, qtbot, tmp_path):
    doc = tmp_path / "doc.txt"
    doc.write_text("hello world")
    window.add_paths([str(doc)])
    window.from_combo.setCurrentIndex(1)  # English
    window.to_combo.setCurrentIndex(1)  # Spanish

    window.start_translation()
    qtbot.waitUntil(lambda: not window.worker.isRunning(), timeout=5000)
    qtbot.waitUntil(lambda: window.translate_btn.isEnabled(), timeout=5000)

    out = tmp_path / "doc_es.txt"
    assert out.exists()
    assert "HELLO WORLD" in out.read_text()
    assert str(out) in window.status.text()


def test_settings_persist_between_windows(qtbot, langs):
    win = MainWindow()
    qtbot.addWidget(win)
    win.from_combo.setCurrentIndex(1)  # English
    win.to_combo.setCurrentIndex(1)  # Spanish
    win.close()

    win2 = MainWindow()
    qtbot.addWidget(win2)
    assert win2.from_combo.currentText() == "English"
    assert win2.to_combo.currentText() == "Spanish"
