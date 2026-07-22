import pytest

from argonaut.worker import TranslateWorker
from tests.conftest import FakeLanguage, FakeTranslation
from tests.test_translation import ENGLISH_TEXT


def make_langs():
    english = FakeLanguage("en", "English")
    spanish = FakeLanguage("es", "Spanish")
    english._translations["es"] = FakeTranslation(english, spanish)
    return english, spanish


def make_worker(files, src, dst, languages=(), output_dir=None):
    return TranslateWorker(src, dst, list(languages), files, output_dir=output_dir)


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
