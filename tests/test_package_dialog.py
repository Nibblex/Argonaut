import types

import pytest
from PyQt5.QtCore import Qt

from argonaut import packages
from argonaut.i18n import tr
from argonaut.package_dialog import SIZE_ROLE, PackageDialog


def fake_pkg(from_code, to_code, from_name, to_name, version="1.9"):
    return types.SimpleNamespace(
        type="translate",
        from_code=from_code,
        to_code=to_code,
        from_name=from_name,
        to_name=to_name,
        links=[],
        code=f"translate-{from_code}_{to_code}",
        package_version=version,
    )


EN_ES = fake_pkg("en", "es", "English", "Spanish")
EN_FR = fake_pkg("en", "fr", "English", "French")
EN_DE = fake_pkg("en", "de", "English", "German", version="1.3")


@pytest.fixture
def installed(monkeypatch):
    """English → French is installed and current; English → German is
    installed but older than the 1.3 the index offers."""
    versions = {("en", "fr"): "1.9", ("en", "de"): "1.0"}
    monkeypatch.setattr(packages, "installed_versions", lambda: dict(versions))
    return versions


@pytest.fixture
def dialog(qtbot, monkeypatch, installed):
    monkeypatch.setattr(packages, "get_available", lambda: [EN_ES, EN_FR, EN_DE])
    dlg = PackageDialog()
    qtbot.addWidget(dlg)
    qtbot.waitUntil(lambda: dlg.package_list.count() == 3, timeout=5000)
    qtbot.waitUntil(lambda: not dlg.lister.isRunning(), timeout=5000)
    return dlg


def test_lists_packages_with_their_state(dialog):
    spanish, french, german = (dialog.package_list.item(i) for i in range(3))
    assert spanish.text() == "English → Spanish  ·  v1.9"  # available: offered version
    assert spanish.checkState() == Qt.Unchecked
    assert french.text() == f"English → French  ·  v1.9  ({tr('pkg_installed')})"
    assert french.flags() & Qt.ItemIsUserCheckable  # selectable for removal
    # installed at 1.0 while the index offers 1.3
    assert german.text() == (
        f"English → German  ·  v1.0  ({tr('pkg_outdated', version='1.3')})"
    )
    assert not dialog.install_btn.isEnabled()
    assert not dialog.update_btn.isEnabled()
    assert not dialog.remove_btn.isEnabled()
    assert dialog.status.text() == tr("ready")


def test_selection_summary_counts_and_totals_sizes(dialog):
    for item in dialog.all_items():
        item.setData(SIZE_ROLE, 50 * 2**20)
    assert dialog.selection_label.text() == ""  # nothing checked yet

    dialog.package_list.item(0).setCheckState(Qt.Checked)
    assert dialog.selection_label.text() == tr("pkg_selection", count=1, size="50 MB")
    dialog.package_list.item(1).setCheckState(Qt.Checked)
    assert dialog.selection_label.text() == tr("pkg_selection", count=2, size="100 MB")

    # an unmeasured package makes the total a lower bound
    dialog.package_list.item(2).setData(SIZE_ROLE, 0)
    dialog.package_list.item(2).setCheckState(Qt.Checked)
    assert dialog.selection_label.text() == tr(
        "pkg_selection", count=3, size="≥ 100 MB"
    )

    dialog.select_all.click()  # clears the selection
    assert dialog.selection_label.text() == ""


def test_checking_packages_enables_the_matching_button(dialog):
    dialog.package_list.item(0).setCheckState(Qt.Checked)  # not installed
    assert dialog.install_btn.isEnabled()
    assert not dialog.update_btn.isEnabled()
    assert not dialog.remove_btn.isEnabled()

    dialog.package_list.item(0).setCheckState(Qt.Unchecked)
    dialog.package_list.item(1).setCheckState(Qt.Checked)  # installed, current
    assert not dialog.install_btn.isEnabled()
    assert not dialog.update_btn.isEnabled()
    assert dialog.remove_btn.isEnabled()

    dialog.package_list.item(1).setCheckState(Qt.Unchecked)
    dialog.package_list.item(2).setCheckState(Qt.Checked)  # outdated
    assert not dialog.install_btn.isEnabled()
    assert dialog.update_btn.isEnabled()
    assert dialog.remove_btn.isEnabled()  # an outdated package is installed too


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
        installed[packages.pair(pkg)] = pkg.package_version

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


def test_state_filter_selects_by_installation_state(dialog):
    spanish, french, german = (dialog.package_list.item(i) for i in range(3))
    assert [dialog.state_combo.itemData(i) for i in range(4)] == [
        "all",
        "installed",
        "available",
        "outdated",
    ]

    dialog.state_combo.setCurrentIndex(1)  # installed: includes the outdated one
    assert dialog.visible_items() == [french, german]

    dialog.state_combo.setCurrentIndex(2)  # not installed
    assert dialog.visible_items() == [spanish]

    dialog.state_combo.setCurrentIndex(3)  # update available
    assert dialog.visible_items() == [german]

    dialog.state_combo.setCurrentIndex(0)  # all
    assert dialog.visible_items() == [spanish, french, german]


def test_state_and_text_filters_combine(dialog):
    dialog.state_combo.setCurrentIndex(2)  # not installed: only English → Spanish
    dialog.filter_edit.setText("french")  # …which does not match the text
    assert dialog.visible_items() == []
    dialog.filter_edit.setText("spanish")
    assert dialog.visible_items() == [dialog.package_list.item(0)]


def test_installing_drops_the_package_from_the_available_filter(
    dialog, qtbot, monkeypatch, installed
):
    monkeypatch.setattr(
        packages,
        "install",
        lambda pkg, on_progress=None, is_cancelled=None: installed.update(
            {packages.pair(pkg): pkg.package_version}
        ),
    )
    dialog.state_combo.setCurrentIndex(2)  # not installed
    dialog.package_list.item(0).setCheckState(Qt.Checked)
    dialog.install_btn.click()
    qtbot.waitUntil(lambda: dialog.installer is None, timeout=5000)
    assert dialog.visible_items() == []  # it is installed now, so it leaves


def test_filtering_drops_hidden_packages_from_the_selection(dialog):
    dialog.select_all.click()  # all three checked, no filter
    assert len(dialog.checked_items("available", "installed", "outdated")) == 3

    idx = [
        dialog.state_combo.itemData(i) for i in range(dialog.state_combo.count())
    ].index("outdated")
    dialog.state_combo.setCurrentIndex(idx)  # only English → German stays visible

    # the two hidden packages no longer count, even though still checked inside
    assert dialog.checked_items("available", "installed", "outdated") == [
        dialog.package_list.item(2)
    ]
    assert dialog.selection_label.text() == tr("pkg_selection", count=1, size="—")
    assert dialog.update_btn.isEnabled()
    assert not dialog.install_btn.isEnabled()  # the available one is hidden


def test_select_all_under_a_filter_selects_only_the_visible(dialog):
    dialog.filter_edit.setText("german")  # hides Spanish and French
    dialog.select_all.click()
    assert dialog.checked_items("available", "installed", "outdated") == [
        dialog.package_list.item(2)
    ]


def test_select_all_checks_every_package(dialog):
    dialog.select_all.click()
    assert dialog.select_all.checkState() == Qt.Checked
    for i in range(dialog.package_list.count()):
        assert dialog.package_list.item(i).checkState() == Qt.Checked
    assert dialog.install_btn.isEnabled()  # not-installed ones selected
    assert dialog.update_btn.isEnabled()  # the outdated one selected
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
    for i in range(1, 3):
        dialog.package_list.item(i).setCheckState(Qt.Checked)
    assert dialog.select_all.checkState() == Qt.Checked
    for i in range(3):
        dialog.package_list.item(i).setCheckState(Qt.Unchecked)
    assert dialog.select_all.checkState() == Qt.Unchecked


def test_update_flow_reinstalls_the_outdated_package(
    dialog, qtbot, monkeypatch, installed
):
    calls = []

    def fake_install(pkg, on_progress=None, is_cancelled=None):
        calls.append(pkg)
        installed[packages.pair(pkg)] = pkg.package_version

    monkeypatch.setattr(packages, "install", fake_install)
    emitted = []
    dialog.packages_changed.connect(lambda: emitted.append(True))

    german = dialog.package_list.item(2)
    german.setCheckState(Qt.Checked)
    dialog.update_btn.click()
    qtbot.waitUntil(lambda: dialog.installer is None, timeout=5000)

    assert calls == [EN_DE]  # only the outdated one, no uninstall step needed
    assert emitted == [True]
    assert tr("pkg_updated", count=1) in dialog.status.text()
    assert german.text() == f"English → German  ·  v1.3  ({tr('pkg_installed')})"
    assert german.checkState() == Qt.Unchecked
    assert not dialog.update_btn.isEnabled()


def test_update_only_touches_outdated_packages(dialog, qtbot, monkeypatch, installed):
    calls = []
    monkeypatch.setattr(
        packages,
        "install",
        lambda pkg, on_progress=None, is_cancelled=None: calls.append(pkg),
    )
    dialog.select_all.click()  # everything checked, including installed ones
    dialog.update_btn.click()
    qtbot.waitUntil(lambda: dialog.installer is None, timeout=5000)
    assert calls == [EN_DE]


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
        lambda: dlg.package_list.item(0).text()
        == "English → Spanish  ·  70 MB  ·  v1.9",
        timeout=5000,
    )
    # unknown sizes are left out; the version and installed mark keep their place
    assert (
        dlg.package_list.item(1).text()
        == f"English → French  ·  v1.9  ({tr('pkg_installed')})"
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
    assert dlg2.package_list.item(0).text() == "English → Spanish  ·  70 MB  ·  v1.9"
    qtbot.waitUntil(lambda: not dlg2.sizer.isRunning(), timeout=5000)
    assert measured == [EN_FR]


def test_remove_flow_uninstalls_checked_packages(dialog, qtbot, monkeypatch, installed):
    from PyQt5.QtWidgets import QMessageBox

    removed = []

    def fake_uninstall(pair):
        removed.append(pair)
        installed.pop(pair, None)

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
    # mark cleared, installable again; the offered version stays visible
    assert item.text() == "English → French  ·  v1.9"
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
