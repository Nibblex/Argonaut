import types

import pytest
from PyQt5.QtCore import Qt

from argonaut import packages
from argonaut.i18n import tr
from argonaut.package_dialog import PackageDialog


def fake_pkg(from_code, to_code, from_name, to_name):
    return types.SimpleNamespace(
        type="translate",
        from_code=from_code,
        to_code=to_code,
        from_name=from_name,
        to_name=to_name,
        links=[],
        code=f"translate-{from_code}_{to_code}",
        package_version="1.9",
    )


EN_ES = fake_pkg("en", "es", "English", "Spanish")
EN_FR = fake_pkg("en", "fr", "English", "French")


@pytest.fixture
def installed(monkeypatch):
    pairs = {("en", "fr")}
    monkeypatch.setattr(packages, "installed_pairs", lambda: set(pairs))
    return pairs


@pytest.fixture
def dialog(qtbot, monkeypatch, installed):
    monkeypatch.setattr(packages, "get_available", lambda: [EN_ES, EN_FR])
    dlg = PackageDialog()
    qtbot.addWidget(dlg)
    qtbot.waitUntil(lambda: dlg.package_list.count() == 2, timeout=5000)
    qtbot.waitUntil(lambda: not dlg.lister.isRunning(), timeout=5000)
    return dlg


def test_lists_packages_and_marks_installed(dialog):
    spanish, french = dialog.package_list.item(0), dialog.package_list.item(1)
    assert spanish.text() == "English → Spanish"
    assert spanish.checkState() == Qt.Unchecked
    assert french.text() == f"English → French  ({tr('pkg_installed')})"
    assert french.flags() & Qt.ItemIsUserCheckable  # selectable for removal
    assert not dialog.install_btn.isEnabled()
    assert not dialog.remove_btn.isEnabled()
    assert dialog.status.text() == tr("ready")


def test_checking_packages_enables_the_matching_button(dialog):
    dialog.package_list.item(0).setCheckState(Qt.Checked)  # not installed
    assert dialog.install_btn.isEnabled()
    assert not dialog.remove_btn.isEnabled()
    dialog.package_list.item(0).setCheckState(Qt.Unchecked)
    dialog.package_list.item(1).setCheckState(Qt.Checked)  # installed
    assert not dialog.install_btn.isEnabled()
    assert dialog.remove_btn.isEnabled()


def test_filter_hides_non_matching_packages(dialog):
    dialog.filter_edit.setText("span")
    assert not dialog.package_list.item(0).isHidden()
    assert dialog.package_list.item(1).isHidden()
    dialog.filter_edit.setText("")
    assert not dialog.package_list.item(1).isHidden()


def test_install_flow_installs_checked_packages(dialog, qtbot, monkeypatch, installed):
    calls = []

    def fake_install(pkg, on_progress=None, is_cancelled=None):
        on_progress(2 * 2**20, 4 * 2**20)
        calls.append(pkg)
        installed.add(packages.pair(pkg))

    monkeypatch.setattr(packages, "install", fake_install)
    emitted = []
    dialog.packages_changed.connect(lambda: emitted.append(True))

    dialog.package_list.item(0).setCheckState(Qt.Checked)
    dialog.install_btn.click()
    qtbot.waitUntil(lambda: dialog.installer is None, timeout=5000)

    assert calls == [EN_ES]
    assert emitted == [True]
    assert tr("pkg_done", count=1) in dialog.status.text()
    item = dialog.package_list.item(0)
    assert f"({tr('pkg_installed')})" in item.text()
    assert item.checkState() == Qt.Unchecked
    assert not dialog.install_btn.isEnabled()  # nothing left selected


def test_install_failure_is_reported(dialog, qtbot, monkeypatch):
    def broken_install(pkg, on_progress=None, is_cancelled=None):
        raise RuntimeError("boom")

    monkeypatch.setattr(packages, "install", broken_install)
    emitted = []
    dialog.packages_changed.connect(lambda: emitted.append(True))

    dialog.package_list.item(0).setCheckState(Qt.Checked)
    dialog.install_btn.click()
    qtbot.waitUntil(lambda: dialog.installer is None, timeout=5000)

    assert emitted == []
    assert "boom" in dialog.status.text()
    assert dialog.package_list.item(0).checkState() == Qt.Checked  # still selectable


def test_select_all_checks_every_package(dialog):
    dialog.select_all.click()
    assert dialog.select_all.checkState() == Qt.Checked
    for i in range(dialog.package_list.count()):
        assert dialog.package_list.item(i).checkState() == Qt.Checked
    assert dialog.install_btn.isEnabled()  # not-installed ones selected
    assert dialog.remove_btn.isEnabled()  # installed ones selected

    dialog.select_all.click()
    assert dialog.select_all.checkState() == Qt.Unchecked
    for i in range(dialog.package_list.count()):
        assert dialog.package_list.item(i).checkState() == Qt.Unchecked


def test_select_all_respects_the_filter(dialog):
    dialog.filter_edit.setText("span")  # hides English → French
    dialog.select_all.click()
    assert dialog.package_list.item(0).checkState() == Qt.Checked
    assert dialog.package_list.item(1).checkState() == Qt.Unchecked
    # once the filter is cleared, only part of the list is checked
    dialog.filter_edit.setText("")
    assert dialog.select_all.checkState() == Qt.PartiallyChecked


def test_select_all_mirrors_manual_checks(dialog):
    dialog.package_list.item(0).setCheckState(Qt.Checked)
    assert dialog.select_all.checkState() == Qt.PartiallyChecked
    dialog.package_list.item(1).setCheckState(Qt.Checked)
    assert dialog.select_all.checkState() == Qt.Checked
    dialog.package_list.item(0).setCheckState(Qt.Unchecked)
    dialog.package_list.item(1).setCheckState(Qt.Unchecked)
    assert dialog.select_all.checkState() == Qt.Unchecked


def test_sizes_are_fetched_cached_and_shown(qtbot, monkeypatch, installed):
    from PyQt5.QtCore import QSettings

    from argonaut.package_dialog import size_key

    monkeypatch.setattr(packages, "get_available", lambda: [EN_ES, EN_FR])
    monkeypatch.setattr(
        packages,
        "get_size",
        lambda pkg: 70 * 2**20 if pkg is EN_ES else 0,
    )
    dlg = PackageDialog()
    qtbot.addWidget(dlg)
    qtbot.waitUntil(lambda: dlg.package_list.count() == 2, timeout=5000)
    qtbot.waitUntil(
        lambda: dlg.package_list.item(0).text() == "English → Spanish  ·  70 MB",
        timeout=5000,
    )
    # unknown sizes are left out; the installed mark keeps its place
    assert (
        dlg.package_list.item(1).text()
        == f"English → French  ({tr('pkg_installed')})"
    )
    assert QSettings().value(size_key(EN_ES), 0, type=int) == 70 * 2**20
    qtbot.waitUntil(lambda: not dlg.sizer.isRunning(), timeout=5000)
    dlg.close()

    # a second dialog reads the cache and does not measure that package again
    measured = []
    monkeypatch.setattr(
        packages, "get_size", lambda pkg: measured.append(pkg) or 0
    )
    dlg2 = PackageDialog()
    qtbot.addWidget(dlg2)
    qtbot.waitUntil(lambda: dlg2.package_list.count() == 2, timeout=5000)
    assert dlg2.package_list.item(0).text() == "English → Spanish  ·  70 MB"
    qtbot.waitUntil(lambda: not dlg2.sizer.isRunning(), timeout=5000)
    assert measured == [EN_FR]


def test_remove_flow_uninstalls_checked_packages(dialog, qtbot, monkeypatch, installed):
    from PyQt5.QtWidgets import QMessageBox

    removed = []

    def fake_uninstall(pair):
        removed.append(pair)
        installed.discard(pair)

    monkeypatch.setattr(packages, "uninstall", fake_uninstall)
    monkeypatch.setattr(
        QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.Yes)
    )
    emitted = []
    dialog.packages_changed.connect(lambda: emitted.append(True))

    dialog.package_list.item(1).setCheckState(Qt.Checked)  # English → French
    dialog.remove_btn.click()

    assert removed == [("en", "fr")]
    assert emitted == [True]
    assert tr("pkg_removed", count=1) in dialog.status.text()
    item = dialog.package_list.item(1)
    assert item.text() == "English → French"  # mark cleared, installable again
    assert not dialog.remove_btn.isEnabled()


def test_remove_declined_keeps_packages(dialog, monkeypatch):
    from PyQt5.QtWidgets import QMessageBox

    removed = []
    monkeypatch.setattr(packages, "uninstall", lambda pair: removed.append(pair))
    monkeypatch.setattr(
        QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.No)
    )
    dialog.package_list.item(1).setCheckState(Qt.Checked)
    dialog.remove_btn.click()
    assert removed == []
    assert f"({tr('pkg_installed')})" in dialog.package_list.item(1).text()


def test_index_error_is_shown(qtbot, monkeypatch):
    def broken_index():
        raise RuntimeError("offline")

    monkeypatch.setattr(packages, "get_available", broken_index)
    dlg = PackageDialog()
    qtbot.addWidget(dlg)
    qtbot.waitUntil(lambda: not dlg.lister.isRunning(), timeout=5000)
    qtbot.waitUntil(
        lambda: dlg.status.text() == tr("pkg_load_failed", error="offline"),
        timeout=5000,
    )
    assert dlg.package_list.count() == 0
