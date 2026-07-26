import types

import pytest

from argonaut import nllb, packages
from argonaut.i18n import tr
from argonaut.translation import CancelledError
from argonaut.worker import (
    MegabyteProgress,
    ModelDownloadWorker,
    PackageInstallWorker,
    PackageListWorker,
    PackageSizeWorker,
    TranslateWorker,
    speed_text,
)
from tests.conftest import FakeBatchTranslation, FakeLanguage, FakeTranslation
from tests.test_pdf import make_pdf
from tests.test_translation import ENGLISH_TEXT


def make_langs():
    english = FakeLanguage("en", "English")
    spanish = FakeLanguage("es", "Spanish")
    english._translations["es"] = FakeTranslation(english, spanish)
    return english, spanish


def make_worker(files, src, dst, languages=(), output_dir=None, skip_existing=False):
    return TranslateWorker(
        src, dst, list(languages), files,
        output_dir=output_dir, skip_existing=skip_existing,
    )


def test_output_path_next_to_original(qapp):
    _, spanish = make_langs()
    worker = make_worker([], None, spanish)
    translation = FakeTranslation(to_lang=spanish)
    assert worker.get_output_path(translation, "/data/report.txt") == "/data/report_es.txt"


def test_output_path_in_chosen_folder(qapp):
    _, spanish = make_langs()
    worker = make_worker([], None, spanish, output_dir="/out")
    translation = FakeTranslation(to_lang=spanish)
    assert worker.get_output_path(translation, "/data/report.txt") == "/out/report_es.txt"


def test_resolve_translation_rejects_same_language(qapp):
    english, _ = make_langs()
    worker = make_worker([], english, english)
    with pytest.raises(RuntimeError):
        worker.resolve_translation(0, "/data/report.txt")


def test_resolve_translation_requires_a_model(qapp):
    english, spanish = make_langs()
    worker = make_worker([], spanish, english)  # no es->en model registered
    with pytest.raises(RuntimeError):
        worker.resolve_translation(0, "/data/report.txt")


def test_resolve_translation_detects_language(qapp, tmp_path):
    english, spanish = make_langs()
    doc = tmp_path / "doc.txt"
    doc.write_text(ENGLISH_TEXT)
    detected = []
    worker = make_worker([str(doc)], None, spanish, languages=[english, spanish])
    worker.language_detected.connect(lambda i, name: detected.append((i, name)))
    translation = worker.resolve_translation(0, str(doc))
    assert translation is english._translations["es"]
    assert detected == [(0, "English")]


def test_run_translates_files(qapp, tmp_path):
    english, spanish = make_langs()
    doc = tmp_path / "doc.txt"
    doc.write_text("hello world")
    done, times, failed, finished = [], [], [], []
    worker = make_worker([str(doc)], english, spanish)
    worker.file_done.connect(lambda i, out, secs: (done.append(out), times.append(secs)))
    worker.file_failed.connect(lambda i, err: failed.append(err))
    worker.finished_all.connect(lambda: finished.append(True))
    worker.run()

    assert failed == []
    assert finished == [True]
    out = tmp_path / "doc_es.txt"
    assert done == [str(out)]
    assert "HELLO WORLD" in out.read_text()
    assert len(times) == 1 and times[0] >= 0


def test_run_translates_pdfs_reporting_the_page_phases(qapp, tmp_path):
    """PDFs take the FastPdfTranslator path: the file still lands in
    file_done, and the window is told the page each phase is on."""
    english = FakeLanguage("en", "English")
    spanish = FakeLanguage("es", "Spanish")
    english._translations["es"] = FakeBatchTranslation(english, spanish)
    doc = tmp_path / "doc.pdf"
    make_pdf(doc)
    done, failed, phases, progress = [], [], [], []
    worker = make_worker([str(doc)], english, spanish)
    worker.file_done.connect(lambda i, out, secs: done.append(out))
    worker.file_failed.connect(lambda i, err: failed.append(err))
    worker.phase_changed.connect(lambda key, kwargs: phases.append(key))
    worker.progress_update.connect(lambda d, t: progress.append((d, t)))
    worker.run()

    assert failed == []
    out = tmp_path / "doc_es.pdf"
    assert done == [str(out)] and out.exists()
    # every long phase reported, in order, with the save last
    assert phases[0] == "reading"
    assert "translating_page" in phases and "generating" in phases
    assert phases[-1] == "saving"
    assert (0, 2) in progress  # the two paragraphs, counted while parsing


def test_batch_shares_the_translation_cache_across_files(qapp, tmp_path):
    # two files with the same content translate their shared paragraph once
    english, spanish = make_langs()
    inner = english._translations["es"]
    for name in ("a.txt", "b.txt"):
        (tmp_path / name).write_text("hello world")
    worker = make_worker(
        [str(tmp_path / "a.txt"), str(tmp_path / "b.txt")], english, spanish
    )
    done, stats = [], []
    worker.file_done.connect(lambda i, out, secs: done.append(out))
    worker.file_cache_stats.connect(
        lambda i, reused, total: stats.append((i, reused, total))
    )
    worker.run()

    assert len(done) == 2
    assert inner.calls == 1  # the second file reused the first's translation
    # first file: nothing to reuse yet; second: its one segment came from cache
    assert stats == [(0, 0, 0), (1, 1, 1)]


def test_cache_entries_do_not_survive_a_package_upgrade(qapp, tmp_path, monkeypatch):
    """The persistent cache is namespaced by the installed package version:
    after an upgrade the old model's translations must not be served."""
    english, spanish = make_langs()
    inner = english._translations["es"]
    doc = tmp_path / "doc.txt"
    doc.write_text("hello world")
    versions = {("en", "es"): "1.0"}
    monkeypatch.setattr(packages, "installed_versions", lambda: dict(versions))

    make_worker([str(doc)], english, spanish).run()
    assert inner.calls == 1
    make_worker([str(doc)], english, spanish).run()
    assert inner.calls == 1  # same version: served from the persistent cache

    versions[("en", "es")] = "1.9"  # the pair was upgraded
    make_worker([str(doc)], english, spanish).run()
    assert inner.calls == 2  # the old model's entry is no longer valid


def test_engine_version_tags_argos_pairs_and_the_nllb_model(qapp, monkeypatch):
    english, spanish = make_langs()
    translation = english._translations["es"]
    monkeypatch.setattr(
        packages, "installed_versions", lambda: {("en", "es"): "1.7"}
    )
    worker = make_worker([], english, spanish)
    assert worker._engine_version(translation) == "1.7"
    assert worker._engine_version(translation) == "1.7"  # read once, reused

    nllb_worker = TranslateWorker(english, spanish, [], [], engine_id="nllb")
    assert nllb_worker._engine_version(translation) == nllb.MODEL_REPO


def test_fast_mode_namespaces_the_cache_apart(qapp, monkeypatch):
    """Greedy output differs from beam output, so fast mode must never be
    served quality-mode cache entries or poison them with its own."""
    from PyQt5.QtCore import QSettings

    english, spanish = make_langs()
    translation = english._translations["es"]
    monkeypatch.setattr(
        packages, "installed_versions", lambda: {("en", "es"): "1.7"}
    )
    QSettings().setValue("quality_mode", "fast")
    worker = make_worker([], english, spanish)
    assert worker._engine_version(translation) == "1.7+greedy"
    nllb_worker = TranslateWorker(english, spanish, [], [], engine_id="nllb")
    assert nllb_worker._engine_version(translation) == nllb.MODEL_REPO + "+greedy"


def test_a_finished_batch_is_recorded_in_the_history(qapp, tmp_path):
    from argonaut.history import TranslationHistory

    english, spanish = make_langs()
    source = tmp_path / "note.txt"
    source.write_text("hello world")
    worker = make_worker([str(source)], english, spanish)
    worker.run()

    history = TranslationHistory(TranslationHistory.default_db_path(), ttl_days=0)
    entry, = history.entries()
    history.close()
    assert entry.source_path == str(source)
    assert entry.output_path == str(tmp_path / "note_es.txt")
    assert (entry.from_code, entry.to_code) == ("en", "es")
    assert entry.engine == "argos"
    assert entry.seconds >= 0


def test_a_failed_file_is_not_recorded(qapp, tmp_path):
    """The history lists translations, not attempts."""
    from argonaut.history import TranslationHistory

    english, spanish = make_langs()
    worker = make_worker([str(tmp_path / "missing.txt")], english, spanish)
    worker.run()

    assert TranslationHistory.db_info(TranslationHistory.default_db_path())[0] == 0


def test_history_can_be_switched_off(qapp, tmp_path):
    from PyQt5.QtCore import QSettings

    from argonaut.history import TranslationHistory

    QSettings().setValue("history_enabled", False)
    english, spanish = make_langs()
    source = tmp_path / "note.txt"
    source.write_text("hello world")
    worker = make_worker([str(source)], english, spanish)
    worker.run()

    assert not worker._history.enabled
    assert TranslationHistory.db_info(TranslationHistory.default_db_path())[0] == 0
    assert (tmp_path / "note_es.txt").exists()  # the translation still happened


def test_run_reports_failures_and_continues(qapp, tmp_path):
    english, spanish = make_langs()
    good = tmp_path / "good.txt"
    good.write_text("hello world")
    missing = tmp_path / "missing.txt"
    done, failed = [], []
    worker = make_worker([str(missing), str(good)], english, spanish)
    worker.file_done.connect(lambda i, out, secs: done.append(out))
    worker.file_failed.connect(lambda i, err: failed.append(err))
    worker.run()

    assert len(failed) == 1
    assert done == [str(tmp_path / "good_es.txt")]


def test_run_skips_existing_output(qapp, tmp_path):
    english, spanish = make_langs()
    doc = tmp_path / "doc.txt"
    doc.write_text("hello world")
    existing = tmp_path / "doc_es.txt"
    existing.write_text("already translated")
    skipped, done = [], []
    worker = make_worker([str(doc)], english, spanish, skip_existing=True)
    worker.file_skipped.connect(lambda i, out: skipped.append(out))
    worker.file_done.connect(lambda i, out, secs: done.append(out))
    worker.run()

    assert skipped == [str(existing)]
    assert done == []
    assert existing.read_text() == "already translated"  # left untouched


def test_run_overwrites_when_skip_disabled(qapp, tmp_path):
    english, spanish = make_langs()
    doc = tmp_path / "doc.txt"
    doc.write_text("hello world")
    out = tmp_path / "doc_es.txt"
    out.write_text("stale")
    skipped, done = [], []
    worker = make_worker([str(doc)], english, spanish)  # skip_existing defaults off
    worker.file_skipped.connect(lambda i, o: skipped.append(o))
    worker.file_done.connect(lambda i, o, secs: done.append(o))
    worker.run()

    assert skipped == []
    assert done == [str(out)]
    assert "HELLO WORLD" in out.read_text()


def test_skip_happens_before_language_detection(qapp, tmp_path):
    # an existing output is skipped without reading the file, so a document
    # that detection could not handle still counts as skipped, not failed
    _, spanish = make_langs()
    doc = tmp_path / "doc.txt"
    doc.write_text("")  # empty: language detection would fail
    (tmp_path / "doc_es.txt").write_text("x")
    skipped, failed = [], []
    worker = make_worker(
        [str(doc)], None, spanish, languages=[spanish], skip_existing=True
    )
    worker.file_skipped.connect(lambda i, out: skipped.append(out))
    worker.file_failed.connect(lambda i, err: failed.append(err))
    worker.run()

    assert skipped == [str(tmp_path / "doc_es.txt")]
    assert failed == []


def test_run_fails_a_file_whose_language_cannot_be_detected(qapp, tmp_path):
    _, spanish = make_langs()
    doc = tmp_path / "doc.txt"
    doc.write_text("")  # nothing to detect a language from
    failed = []
    worker = make_worker([str(doc)], None, spanish, languages=[spanish])
    worker.file_failed.connect(lambda i, err: failed.append(err))
    worker.run()
    assert failed == [tr("err_detect", name="doc.txt")]


def test_cancelling_mid_file_stops_the_batch(qapp, tmp_path):
    """A cancel that lands while a file is being translated ends the run:
    the interrupted file gets no outcome and the next one never starts."""
    english, spanish = make_langs()

    def translate(text):
        raise CancelledError()  # what the proxy raises once cancel arrives

    english._translations["es"].translate = translate
    for name in ("a.txt", "b.txt"):
        (tmp_path / name).write_text("hello world")
    started, done, failed, finished = [], [], [], []
    worker = make_worker(
        [str(tmp_path / "a.txt"), str(tmp_path / "b.txt")], english, spanish
    )
    worker.file_started.connect(lambda i, path: started.append(i))
    worker.file_done.connect(lambda i, out, secs: done.append(out))
    worker.file_failed.connect(lambda i, err: failed.append(err))
    worker.finished_all.connect(lambda: finished.append(True))
    worker.run()

    assert started == [0]  # the second file never started
    assert done == [] and failed == []  # cancelling is not an error
    assert finished == [True]


def test_speed_text_picks_network_units():
    assert speed_text(0) == ""  # unknown yet: no label
    assert speed_text(100) == "1 kbps"  # tiny but nonzero: never "0 kbps"
    assert speed_text(50_000) == "400 kbps"
    assert speed_text(2 * 2**20) == "16.8 Mbps"


def test_speed_text_can_render_byte_units():
    assert speed_text(0, "bytes") == ""
    assert speed_text(100, "bytes") == "1 KB/s"
    assert speed_text(400 * 1024, "bytes") == "400 KB/s"
    assert speed_text(2 * 2**20, "bytes") == "2.0 MB/s"


def test_speed_units_setting_defaults_to_bits(qapp):
    from PyQt5.QtCore import QSettings

    from argonaut.worker import speed_units

    assert speed_units() == "bits"
    QSettings().setValue("speed_units", "bytes")
    assert speed_units() == "bytes"
    QSettings().setValue("speed_units", "parsecs")  # e.g. a newer version
    assert speed_units() == "bits"


def test_quality_mode_setting_defaults_to_quality(qapp):
    from PyQt5.QtCore import QSettings

    from argonaut.worker import quality_mode

    assert quality_mode() == "quality"
    QSettings().setValue("quality_mode", "fast")
    assert quality_mode() == "fast"
    QSettings().setValue("quality_mode", "turbo")  # e.g. a newer version
    assert quality_mode() == "quality"


def test_megabyte_progress_measures_speed_over_a_sliding_window():
    class FakeSignal:
        def __init__(self):
            self.emitted = []

        def emit(self, *args):
            self.emitted.append(args)

    t = [0.0]
    signal = FakeSignal()
    report = MegabyteProgress(signal, clock=lambda: t[0])
    total = 10 * 2**20

    report(0, total)
    assert signal.emitted == [(0, 10, 0.0)]  # no window measured yet

    t[0] = 1.0  # one full window later, 2 MB came in: 2 MB/s
    report(2 * 2**20, total)
    assert signal.emitted[-1] == (2, 10, float(2 * 2**20))

    t[0] = 1.5  # mid-window: the previous measurement is kept
    report(3 * 2**20, total)
    assert signal.emitted[-1] == (3, 10, float(2 * 2**20))

    report.reset()  # a new file starts a fresh window
    report(0, total)
    assert signal.emitted[-1] == (0, 10, 0.0)


def test_model_download_worker_reports_success(qapp, monkeypatch):
    monkeypatch.setattr(
        nllb, "download_model", lambda on_progress=None, is_cancelled=None: None
    )
    results = []
    worker = ModelDownloadWorker()
    worker.download_finished.connect(lambda ok, err: results.append((ok, err)))
    worker.run()
    assert results == [(True, "")]


def test_model_download_worker_reports_cancellation_without_error(qapp, monkeypatch):
    def cancelled(on_progress=None, is_cancelled=None):
        raise CancelledError()

    monkeypatch.setattr(nllb, "download_model", cancelled)
    results = []
    worker = ModelDownloadWorker()
    worker.download_finished.connect(lambda ok, err: results.append((ok, err)))
    worker.run()
    assert results == [(False, "")]  # cancelled, but nothing went wrong


def test_model_download_worker_reports_errors(qapp, monkeypatch):
    def broken(on_progress=None, is_cancelled=None):
        raise RuntimeError("offline")

    monkeypatch.setattr(nllb, "download_model", broken)
    results = []
    worker = ModelDownloadWorker()
    worker.download_finished.connect(lambda ok, err: results.append((ok, err)))
    worker.run()
    assert results == [(False, "offline")]


def fake_pkg(from_name="English", to_name="Spanish"):
    return types.SimpleNamespace(
        from_code=from_name[:2].lower(),
        to_code=to_name[:2].lower(),
        from_name=from_name,
        to_name=to_name,
    )


def test_package_list_worker_reports_packages(qapp, monkeypatch):
    available = [fake_pkg()]
    monkeypatch.setattr(packages, "get_available", lambda: available)
    results = []
    worker = PackageListWorker()
    worker.listed.connect(lambda pkgs, err: results.append((pkgs, err)))
    worker.run()
    assert results == [(available, "")]


def test_package_list_worker_reports_errors(qapp, monkeypatch):
    def broken():
        raise RuntimeError("offline")

    monkeypatch.setattr(packages, "get_available", broken)
    results = []
    worker = PackageListWorker()
    worker.listed.connect(lambda pkgs, err: results.append((pkgs, err)))
    worker.run()
    assert results == [([], "offline")]


def test_package_size_worker_reports_each_row(qapp, monkeypatch):
    sizes = {"Spanish": 10 * 2**20, "French": 0}
    monkeypatch.setattr(packages, "get_size", lambda pkg: sizes[pkg.to_name])
    results = []
    worker = PackageSizeWorker([(0, fake_pkg()), (3, fake_pkg(to_name="French"))])
    worker.size_ready.connect(lambda row, size: results.append((row, size)))
    worker.run()
    assert sorted(results) == [(0, 10 * 2**20), (3, 0)]


def test_package_size_worker_stops_on_cancel(qapp, monkeypatch):
    monkeypatch.setattr(packages, "get_size", lambda pkg: 5)
    results = []
    worker = PackageSizeWorker([(0, fake_pkg()), (1, fake_pkg(to_name="French"))])
    worker.size_ready.connect(lambda row, size: results.append(row))
    worker.cancel()
    worker.run()
    assert results == []  # nothing reported after the cancel


def test_package_install_worker_pre_cancelled_installs_nothing(qapp, monkeypatch):
    installed = []
    monkeypatch.setattr(
        packages, "install",
        lambda pkg, on_progress=None, is_cancelled=None: installed.append(pkg),
    )
    finished = []
    worker = PackageInstallWorker([fake_pkg()])
    worker.install_finished.connect(lambda n: finished.append(n))
    worker.cancel()
    worker.run()
    assert installed == []
    assert finished == [0]  # the summary still arrives


def test_package_install_worker_continues_after_failures(qapp, monkeypatch):
    good, bad = fake_pkg(), fake_pkg(to_name="French")

    def install(pkg, on_progress=None, is_cancelled=None):
        if pkg is bad:
            raise RuntimeError("boom")
        on_progress(2 * 2**20, 4 * 2**20)

    monkeypatch.setattr(packages, "install", install)
    started, progress, failed, finished = [], [], [], []
    worker = PackageInstallWorker([bad, good])
    worker.package_started.connect(lambda i, n, d: started.append((i, n, d)))
    worker.progress.connect(lambda done, total, speed: progress.append((done, total)))
    worker.package_failed.connect(lambda d, e: failed.append((d, e)))
    worker.install_finished.connect(lambda n: finished.append(n))
    worker.run()

    assert started == [
        (0, 2, "English → French"),
        (1, 2, "English → Spanish"),
    ]
    assert progress == [(2, 4)]
    assert failed == [("English → French", "boom")]
    assert finished == [1]


def test_package_install_worker_stops_on_cancel(qapp, monkeypatch):
    def install(pkg, on_progress=None, is_cancelled=None):
        raise CancelledError()

    monkeypatch.setattr(packages, "install", install)
    finished = []
    worker = PackageInstallWorker([fake_pkg(), fake_pkg(to_name="French")])
    worker.install_finished.connect(lambda n: finished.append(n))
    worker.run()
    assert finished == [0]


def test_cancelled_run_stops_before_translating(qapp, tmp_path):
    english, spanish = make_langs()
    doc = tmp_path / "doc.txt"
    doc.write_text("hello world")
    done, finished = [], []
    worker = make_worker([str(doc)], english, spanish)
    worker.file_done.connect(lambda i, out, secs: done.append(out))
    worker.finished_all.connect(lambda: finished.append(True))
    worker.cancel()
    worker.run()

    assert worker.was_cancelled()
    assert done == []
    assert finished == [True]


def test_unexpected_error_still_reports_the_batch_as_finished(qapp, tmp_path):
    """finished_all is what takes the window out of its busy state: without
    it the interface stays disabled forever, looking hung."""
    english, spanish = make_langs()
    worker = make_worker([str(tmp_path / "doc.txt")], english, spanish)
    worker.files = None  # anything that breaks the loop itself
    finished = []
    worker.finished_all.connect(lambda: finished.append(True))

    with pytest.raises(TypeError):
        worker.run()
    assert finished == [True]


def test_ui_yield_is_throttled(qapp, monkeypatch):
    """The interpreter is handed to the interface thread on a timer, not on
    every page: reading a long book takes about as long as one millisecond
    per page would, so yielding each time paced the phase, not the work."""
    from argonaut import worker as worker_mod

    english, spanish = make_langs()
    worker = make_worker([], english, spanish)
    clock, slept = [1000.0], []
    monkeypatch.setattr(worker_mod.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(worker_mod.time, "sleep", slept.append)

    worker._yield_to_ui()
    worker._yield_to_ui()  # same instant
    assert len(slept) == 1

    clock[0] += worker.YIELD_EVERY / 2
    worker._yield_to_ui()
    assert len(slept) == 1  # still inside the window

    clock[0] += worker.YIELD_EVERY
    worker._yield_to_ui()
    assert len(slept) == 2


def test_every_page_is_still_reported_while_yields_are_throttled(qapp, monkeypatch):
    """Throttling the hand-over must not throttle the page number: it is
    what tells the user a long book is still moving."""
    from argonaut import worker as worker_mod

    english, spanish = make_langs()
    worker = make_worker([], english, spanish)
    clock, slept = [1000.0], []
    monkeypatch.setattr(worker_mod.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(worker_mod.time, "sleep", slept.append)

    reported = []
    worker.phase_changed.connect(lambda key, kw: reported.append(kw["done"]))
    for page in range(1, 6):
        worker._report_pages("generating", page, 5)

    assert reported == [1, 2, 3, 4, 5]
    assert len(slept) == 1  # one hand-over for the five pages
