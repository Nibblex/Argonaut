import re

import pytest
from PyQt5.QtWidgets import QFileDialog, QMessageBox

import argonaut.window
from argonaut.i18n import tr
from argonaut.window import MainWindow
from tests.conftest import FakeLanguage, FakeTranslation


def fake_installed_languages(languages):
    """Mimics argostranslate's lru_cached get_installed_languages."""
    def get():
        return list(languages)

    get.cache_clear = lambda: None
    return get


@pytest.fixture
def langs(monkeypatch):
    english = FakeLanguage("en", "English")
    spanish = FakeLanguage("es", "Spanish")
    english._translations["es"] = FakeTranslation(english, spanish)
    monkeypatch.setattr(
        argonaut.window.argostranslate.translate,
        "get_installed_languages",
        fake_installed_languages([english, spanish]),
    )
    return english, spanish


@pytest.fixture
def window(qtbot, langs):
    win = MainWindow()
    qtbot.addWidget(win)
    return win


def test_no_installed_languages_disables_translation(qtbot, monkeypatch):
    monkeypatch.setattr(
        argonaut.window.argostranslate.translate,
        "get_installed_languages",
        fake_installed_languages([]),
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


def test_expand_dirs_walks_folders_recursively(window, tmp_path):
    docs = tmp_path / "docs"
    (docs / "sub").mkdir(parents=True)
    (docs / "b.txt").write_text("x")
    (docs / "image.jpg").write_text("x")  # filtered later by add_paths
    (docs / "sub" / "a.epub").write_text("x")
    loose = tmp_path / "loose.txt"
    loose.write_text("x")

    window.add_paths(window.expand_dirs([str(docs), str(loose)]))
    items = [window.file_list.item(i).text() for i in range(window.file_list.count())]
    assert items == [
        str(docs / "b.txt"),
        str(docs / "sub" / "a.epub"),
        str(loose),
    ]


def test_open_selected_files(window, monkeypatch, tmp_path):
    doc = tmp_path / "doc.txt"
    doc.write_text("hello")
    other = tmp_path / "other.txt"
    other.write_text("bye")
    window.add_paths([str(doc), str(other), "/missing/gone.txt"])

    opened = []
    monkeypatch.setattr(
        argonaut.window.QDesktopServices,
        "openUrl",
        staticmethod(lambda url: opened.append(url.toLocalFile())),
    )

    window.open_file_btn.click()  # nothing selected: nothing opens
    assert opened == []

    window.file_list.item(0).setSelected(True)
    window.file_list.item(2).setSelected(True)  # missing file: skipped
    window.open_file_btn.click()
    assert opened == [str(doc)]

    window.change_language("es")
    assert window.open_file_btn.text() == "Abrir"
    window.change_language("en")


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
    assert re.search(r"\(\d{2}:\d{2}\)", window.status.text())


def test_format_duration():
    assert MainWindow.format_duration(0) == "00:00"
    assert MainWindow.format_duration(65.7) == "01:05"
    assert MainWindow.format_duration(3599) == "59:59"
    assert MainWindow.format_duration(3600) == "1h"
    assert MainWindow.format_duration(3671) == "1h 01m"
    assert MainWindow.format_duration(2 * 3600 + 35 * 60) == "2h 35m"
    assert MainWindow.format_duration(24 * 3600) == "1d"
    assert MainWindow.format_duration(24 * 3600 + 3 * 3600 + 59 * 60) == "1d 3h"
    assert MainWindow.format_duration(72 * 3600) == "3d"


def test_eta_estimation(window, monkeypatch):
    t = [100.0]
    monkeypatch.setattr(argonaut.window.time, "monotonic", lambda: t[0])

    assert window.estimate_eta(0, 100) is None  # first sample only calibrates
    t[0] += 10
    assert window.estimate_eta(20, 100) == pytest.approx(40.0)  # 2/s, 80 left
    t[0] += 10
    assert window.estimate_eta(40, 100) == pytest.approx(30.0)
    assert window.estimate_eta(100, 100) is None  # finished: nothing left
    assert window.estimate_eta(0, 7) is None  # new total resets the estimator
    t[0] += 0.5
    assert window.estimate_eta(3, 7) is None  # too early to be reliable

    window.reset_eta()
    t[0] += 10
    assert window.estimate_eta(50, 100) is None  # reset discards the old pace


def test_progress_format_includes_eta(window, monkeypatch):
    t = [0.0]
    monkeypatch.setattr(argonaut.window.time, "monotonic", lambda: t[0])
    window.on_progress(0, 100)
    assert window.progress.format() == "%p% — 0/100"  # no estimate yet
    t[0] += 60
    window.on_progress(50, 100)
    assert window.progress.format() == "%p% — 50/100 — ~01:00"
    window.on_progress(0, 0)  # indeterminate phase resets the estimator
    t[0] += 60
    window.on_progress(50, 100)
    assert window.progress.format() == "%p% — 50/100"


def test_backend_switch_and_persistence(qtbot, langs, monkeypatch):
    fake_langs = [
        FakeLanguage("en", "English"),
        FakeLanguage("es", "Spanish"),
        FakeLanguage("ja", "Japanese"),
    ]
    monkeypatch.setattr(
        argonaut.window.nllb, "is_model_installed", lambda path=None: True
    )
    monkeypatch.setattr(
        argonaut.window.nllb,
        "get_installed_languages",
        lambda path=None, threads=None: fake_langs,
    )

    win = MainWindow()
    qtbot.addWidget(win)
    assert win.backend == "argos"
    assert win.argos_action.isChecked()

    win.change_backend("nllb")
    assert win.backend == "nllb"
    assert win.nllb_action.isChecked()
    assert win.from_combo.count() == 4  # detect + 3 languages
    assert win.to_combo.currentText() == "Spanish"
    win.close()

    win2 = MainWindow()
    qtbot.addWidget(win2)
    assert win2.backend == "nllb"
    assert win2.nllb_action.isChecked()
    assert win2.from_combo.count() == 4


def test_backend_switch_keeps_language_selection(window, monkeypatch):
    monkeypatch.setattr(
        argonaut.window.nllb, "is_model_installed", lambda path=None: True
    )
    monkeypatch.setattr(
        argonaut.window.nllb,
        "get_installed_languages",
        lambda path=None, threads=None: [
            FakeLanguage("en", "English"),
            FakeLanguage("es", "Spanish"),
        ],
    )
    window.from_combo.setCurrentIndex(1)  # English
    window.to_combo.setCurrentIndex(1)  # Spanish
    window.change_backend("nllb")
    assert window.from_combo.currentText() == "English"
    assert window.to_combo.currentText() == "Spanish"


def test_backend_falls_back_to_argos_without_model(qtbot, langs, monkeypatch):
    from PyQt5.QtCore import QSettings

    QSettings().setValue("backend", "nllb")
    monkeypatch.setattr(
        argonaut.window.nllb, "is_model_installed", lambda path=None: False
    )
    win = MainWindow()
    qtbot.addWidget(win)
    assert win.backend == "argos"


def test_backend_download_declined_keeps_argos(window, monkeypatch):
    monkeypatch.setattr(
        argonaut.window.nllb, "is_model_installed", lambda path=None: False
    )
    monkeypatch.setattr(
        QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.No)
    )
    window.change_backend("nllb")
    assert window.backend == "argos"
    assert window.argos_action.isChecked()


def test_backend_download_flow(window, monkeypatch, qtbot):
    monkeypatch.setattr(
        argonaut.window.nllb, "is_model_installed", lambda path=None: False
    )
    monkeypatch.setattr(
        QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.Yes)
    )

    def fake_download(path=None, base_url=None, on_progress=None, is_cancelled=None):
        on_progress(2 * 2**20, 4 * 2**20)

    monkeypatch.setattr(argonaut.window.nllb, "download_model", fake_download)
    monkeypatch.setattr(
        argonaut.window.nllb,
        "get_installed_languages",
        lambda path=None, threads=None: [
            FakeLanguage("en", "English"),
            FakeLanguage("es", "Spanish"),
        ],
    )

    window.change_backend("nllb")
    qtbot.waitUntil(lambda: window.backend == "nllb", timeout=5000)
    qtbot.waitUntil(lambda: window.translate_btn.isEnabled(), timeout=5000)
    assert window.nllb_action.isChecked()
    assert window.to_combo.currentText() == "Spanish"


def test_engine_label_shows_active_backend(window, monkeypatch):
    assert window.engine_label.text() == tr("engine_status", name="Argos Translate")
    monkeypatch.setattr(
        argonaut.window.nllb, "is_model_installed", lambda path=None: True
    )
    monkeypatch.setattr(
        argonaut.window.nllb,
        "get_installed_languages",
        lambda path=None, threads=None: [
            FakeLanguage("en", "English"),
            FakeLanguage("es", "Spanish"),
        ],
    )
    window.change_backend("nllb")
    assert window.engine_label.text() == tr("engine_status", name="NLLB-200")
    window.change_language("es")
    assert window.engine_label.text() == "Motor: NLLB-200"
    window.change_language("en")


def test_remove_nllb_model(window, monkeypatch):
    installed = [True]
    monkeypatch.setattr(
        argonaut.window.nllb, "is_model_installed", lambda path=None: installed[0]
    )
    monkeypatch.setattr(
        argonaut.window.nllb,
        "get_installed_languages",
        lambda path=None, threads=None: [
            FakeLanguage("en", "English"),
            FakeLanguage("es", "Spanish"),
        ],
    )
    removed = []

    def fake_remove(path=None):
        installed[0] = False
        removed.append(True)

    monkeypatch.setattr(argonaut.window.nllb, "remove_model", fake_remove)
    monkeypatch.setattr(
        QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.Yes)
    )

    window.change_backend("nllb")
    assert window.nllb_remove_action.isEnabled()

    window.remove_nllb_model()
    assert removed == [True]
    assert window.backend == "argos"  # falls back before deleting
    assert window.argos_action.isChecked()
    assert not window.nllb_remove_action.isEnabled()
    assert window.status.text() == tr("nllb_removed")


def test_remove_nllb_model_declined(window, monkeypatch):
    monkeypatch.setattr(
        QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.No)
    )
    removed = []
    monkeypatch.setattr(
        argonaut.window.nllb, "remove_model", lambda path=None: removed.append(True)
    )
    window.remove_nllb_model()
    assert removed == []


def test_resource_indicator(window):
    assert re.fullmatch(r"CPU \d+%  ·  RAM \d+ MB", window.resource_label.text())
    ram_before = int(re.search(r"RAM (\d+)", window.resource_label.text()).group(1))
    assert ram_before > 0
    window.update_resource_usage()
    assert re.fullmatch(r"CPU \d+%  ·  RAM \d+ MB", window.resource_label.text())
    assert window._resource_timer.isActive()
    assert window._resource_timer.interval() == 2000


def test_settings_menu_groups_engine_and_threads(window):
    assert window.settings_menu.title() == tr("menu_settings")
    actions = window.settings_menu.actions()
    assert actions[0].menu() is window.engine_menu
    assert actions[1].menu() is window.threads_menu
    assert window.pkg_install_action in actions
    assert window.nllb_remove_action in actions
    window.change_language("es")
    assert window.settings_menu.title() == "&Configuración"
    assert window.engine_menu.title() == "&Motor"
    window.change_language("en")


def test_package_menu_action_is_translated(window):
    assert window.pkg_install_action.text() == tr("pkg_install")
    window.change_language("es")
    assert window.pkg_install_action.text() == "Gestionar paquetes de idiomas…"
    window.change_language("en")


def test_installed_packages_refresh_the_window(qtbot, monkeypatch):
    english = FakeLanguage("en", "English")
    spanish = FakeLanguage("es", "Spanish")
    installed = fake_installed_languages([])
    monkeypatch.setattr(
        argonaut.window.argostranslate.translate, "get_installed_languages", installed
    )
    win = MainWindow()
    qtbot.addWidget(win)
    assert not win.translate_btn.isEnabled()

    monkeypatch.setattr(
        argonaut.window.argostranslate.translate,
        "get_installed_languages",
        fake_installed_languages([english, spanish]),
    )
    win.on_packages_changed()
    assert win.translate_btn.isEnabled()
    assert win.to_combo.count() == 2
    assert win.status.text() == tr("ready")


def test_cpu_threads_default_and_menu(window):
    import os

    max_threads = os.cpu_count() or 1
    assert window.max_threads == max_threads
    assert window.cpu_threads == min(4, max_threads)
    assert argonaut.window.argostranslate.settings.intra_threads == window.cpu_threads
    actions = window.threads_menu.actions()
    assert [a.text() for a in actions] == [str(n) for n in range(1, max_threads + 1)]
    assert actions[window.cpu_threads - 1].isChecked()
    window.change_language("es")
    assert window.threads_menu.title() == "Hilos de CPU"
    window.change_language("en")


def test_cpu_threads_change_applies_and_persists(qtbot, langs, monkeypatch):
    captured = []
    monkeypatch.setattr(
        argonaut.window.nllb,
        "get_installed_languages",
        lambda path=None, threads=None: captured.append(threads) or [],
    )
    win = MainWindow()
    qtbot.addWidget(win)
    win.change_cpu_threads(1)
    assert win.cpu_threads == 1
    assert argonaut.window.argostranslate.settings.intra_threads == 1
    win.close()

    win2 = MainWindow()
    qtbot.addWidget(win2)
    assert win2.cpu_threads == 1
    assert win2.threads_menu.actions()[0].isChecked()
    win2.change_backend("nllb")  # ineffective without the model, but harmless
    monkeypatch.setattr(
        argonaut.window.nllb, "is_model_installed", lambda path=None: True
    )
    win2.apply_backend("nllb")
    assert captured[-1] == 1  # the NLLB engine receives the configured value


def test_cpu_threads_saved_value_is_clamped(qtbot, langs):
    from PyQt5.QtCore import QSettings

    QSettings().setValue("cpu_threads", 9999)
    win = MainWindow()
    qtbot.addWidget(win)
    assert win.cpu_threads == win.max_threads


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
