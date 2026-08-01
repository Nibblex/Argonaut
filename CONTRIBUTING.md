# Contributing to Argonaut

[![CI](https://github.com/Nibblex/Argonaut/actions/workflows/ci.yml/badge.svg)](https://github.com/Nibblex/Argonaut/actions/workflows/ci.yml)
[![Coverage](https://raw.githubusercontent.com/Nibblex/Argonaut/badges/coverage.svg)](https://github.com/Nibblex/Argonaut/actions/workflows/ci.yml)

`README.md` is the user manual — the Help menu opens it — so it stays about
using Argonaut. Everything about building, testing and releasing it is here.

## Running from a checkout

```bash
pip install -e .
python3 -m argonaut
```

Python 3.10 or newer (the pymupdf wheels need it). You also need at least one
Argos language package; install it from the running application, or with
`argospm install translate-en_es`.

## Tests

```bash
pip install -e .[test]     # pytest-cov and pytest-qt are both required
pytest                     # the whole suite
pytest tests/test_i18n.py::test_placeholders_match_english   # one test
pytest -o addopts="" tests/test_window.py                    # without coverage
```

`pyproject.toml` puts `--cov=argonaut` in `addopts`, so a bare `pytest`
fails outright unless `pytest-cov` is installed — the `[test]` extra brings
it, along with `pytest-qt` for the `qtbot` fixture.

The suite runs Qt headless and needs no language models: `tests/conftest.py`
sets `QT_QPA_PLATFORM=offscreen` itself, sandboxes `XDG_CONFIG_HOME` and
`XDG_DATA_HOME` per test, and fakes the translation engines. It also makes
every modal dialog raise instead of blocking, so a test that expects one has
to patch it.

CI runs the suite on Python 3.10 through 3.14; that matrix, `requires-python`
and the classifiers in `pyproject.toml` have to stay in step.

## Layout

All modules live in the `src/argonaut/` package:

- `__init__.py` — package version (`__version__`).
- `main.py` — entry point; silences dependency warnings and launches the window.
- `window/` — the main window, split by responsibility: `main_window.py`
  (widgets, menus and window state), `engine.py` (backend, threads, quality,
  the cache and history menus and the NLLB model), `files.py` and
  `file_list.py` (the file list, its columns and its empty state),
  `translation_run.py` (driving a batch and reporting its progress),
  `theme.py` (light/dark/system palettes), `about_dialog.py` and
  `history_dialog.py`.
- `worker.py` — thread that translates the file list and emits progress signals.
- `pdf.py` — fixed PDF translator (paragraphs, progress, cancellation).
- `typesetting.py` — lays the translation back into the page: line breaking,
  fitting each paragraph to its box, and a font per script.
- `translation.py` — language detection, supported formats and the
  progress/cache wrapper.
- `history.py` — persistent record of the files each batch translated.
- `nllb.py` — optional NLLB-200 backend (CTranslate2 + SentencePiece)
  exposing the same duck-typed API as argostranslate, so the two engines are
  interchangeable everywhere else.
- `download.py` — shared streaming download with progress and cancellation.
- `packages.py` — Argos package index, download, installation and removal.
- `package_dialog.py` — dialog to browse, install and remove packages.
- `i18n.py` — interface language: which one is in force, how it is chosen and
  saved, and lazy access to the data files below.
- `locales/<code>.json` — the interface strings, one file per language.
- `locales/language_names.json` — the translation languages' names in each of
  those interface languages (generated; see below).

Packaging lives at the top level: `pyproject.toml` (PyPI),
`io.github.nibblex.Argonaut.yml` (Flatpak manifest) and `data/` (desktop
entry, AppStream metainfo and icon for Flathub).

If you work with a coding agent, point it at this file: the repository ships
no `AGENTS.md`.

## Interface strings

Every user-facing string goes through `i18n.tr("key")`, with the keys in
`src/argonaut/locales/<code>.json` — twelve hand-written files. Adding a key
to `en.json` alone fails the suite: `tests/test_i18n.py` requires every
language to carry the same keys and the same `{placeholders}`, so a new
string has to be added to all twelve in the same change. Missing keys fall
back to English at runtime.

Menu titles carry `&` accelerators, and the suite also checks that the ones
competing in the same menu are present and distinct in every language. The
groups it checks are listed in `ACCELERATOR_GROUPS`; moving a menu means
moving its key to the group it now competes in.

To add an interface language: copy `en.json`, translate the values, list the
code in `LANGUAGES` in `i18n.py` (which sets the menu order and the name
shown), add it to `UI` in `tools/gen_language_names.py` and regenerate.

`locales/language_names.json` is generated from CLDR and should never be
hand-edited:

```bash
pip install babel && python tools/gen_language_names.py
```

Babel is a development tool, not a runtime dependency; the result is
committed. A language with no entry keeps the English name the engine reports.

## Releasing

Work reaches `main` through branches, not directly: a topic branch merges
`--no-ff` into `dev`, `dev` merges `--no-ff` into `main`, and the annotated
tag goes on `main` **after** that merge, so it points at the tree actually
released rather than at the branch head before it.

Bump `__version__` in `src/argonaut/__init__.py` **and** add a matching
`<release>` entry to `data/io.github.nibblex.Argonaut.metainfo.xml`. Nothing
checks that the two agree.

### PyPI

```bash
git checkout dev  && git merge --no-ff my-branch && git push origin dev
git checkout main && git merge --no-ff dev       && git push origin main
git tag -a v1.8.0 -m "Argonaut 1.8.0"
git push origin v1.8.0
gh release create v1.8.0 --title "Argonaut 1.8.0" --notes-file notes.md
```

Publishing the release triggers `.github/workflows/publish.yml`, which builds
the wheel and the sdist and uploads them via trusted publishing. Pushing the
tag alone publishes nothing, so the CI run on `main` can be used as a gate: a
version is permanent on PyPI once uploaded. CI never runs on `dev` — it
watches `main` and pull requests only — so the local suite is what gates the
merge.

### Flathub

Flathub builds have no network access, so the Python dependencies are pinned
first with [flatpak-pip-generator](https://github.com/flatpak/flatpak-builder-tools).
`requirements.txt` is its input and deliberately omits PyQt5, which the PyQt
BaseApp provides; it and the `dependencies` in `pyproject.toml` are kept in
step by hand.

```bash
python3 flatpak-pip-generator --requirements-file=requirements.txt \
    --output python3-requirements
```

Build locally, then lint the manifest and the metainfo:

```bash
flatpak-builder --user --install --force-clean build-dir \
    io.github.nibblex.Argonaut.yml
flatpak run --command=flatpak-builder-lint org.flatpak.Builder \
    manifest io.github.nibblex.Argonaut.yml
flatpak run --command=flatpak-builder-lint org.flatpak.Builder \
    appstream data/io.github.nibblex.Argonaut.metainfo.xml
```

First submission: open a PR against
[flathub/flathub](https://github.com/flathub/flathub) (branch `new-pr`)
adding the manifest, per the
[submission guide](https://docs.flathub.org/docs/for-app-authors/submission).
The screenshot the metainfo points at is `data/screenshots/main-window.png`,
served from `main` on GitHub, so replacing it there updates the store page
without a new release.
