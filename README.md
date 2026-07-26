# Argonaut

[![PyPI](https://img.shields.io/pypi/v/argonaut-translator)](https://pypi.org/project/argonaut-translator/)
[![Python versions](https://img.shields.io/pypi/pyversions/argonaut-translator)](https://pypi.org/project/argonaut-translator/)
[![License: GPL-3.0](https://img.shields.io/github/license/Nibblex/Argonaut)](LICENSE)
[![Release](https://img.shields.io/github/v/tag/Nibblex/Argonaut?label=release)](https://github.com/Nibblex/Argonaut/tags)
[![CI](https://github.com/Nibblex/Argonaut/actions/workflows/ci.yml/badge.svg)](https://github.com/Nibblex/Argonaut/actions/workflows/ci.yml)
[![Coverage](https://raw.githubusercontent.com/Nibblex/Argonaut/badges/coverage.svg)](https://github.com/Nibblex/Argonaut/actions/workflows/ci.yml)

Minimalist document translator with a Qt (PyQt5) interface that uses
[argos-translate-files](https://github.com/LibreTranslate/argos-translate-files)
as an offline translation engine.

Two engines are available from *Settings → Engine*:

- **Argos Translate** (default) — light per-pair models, installed and
  removed from *Settings → Manage language packages…*.
- **NLLB-200** — Meta's
  [nllb-200-distilled-600M](https://huggingface.co/facebook/nllb-200-distilled-600M)
  (int8, CTranslate2), noticeably better quality and direct translation
  between any pair of 32 languages. The model (~630 MB) is downloaded on
  first use and stored under `~/.local/share/argonaut/`. Note that the
  NLLB weights are licensed CC-BY-NC 4.0 (non-commercial).

## Requirements

Python 3.10 or newer (the pymupdf wheels Argonaut depends on need it).

```bash
pip install PyQt5 argos-translate-lt argos-translate-files langdetect psutil pymupdf
```

You need at least one language package installed. Open
*Settings → Manage language packages…*, pick the pairs you want and
press "Install selected"; the dialog lists every package from the Argos
index with its version and download size, filters by installation state,
and lets you remove or update the installed ones (a package with a newer
version in the index is flagged and can be updated in place). They can
also be installed from the command line with `argospm install
translate-en_es`.

## Usage

Install it (provides the `argonaut` command):

```bash
pip install argonaut-translator
```

From a checkout, install in editable mode first:

```bash
pip install -e .
python3 -m argonaut
```

## Translating documents

1. Choose the source and target languages (⇄ button to swap them).
   By default the source is "Detect language": each document's language
   is detected automatically, so you can mix files in different
   languages in the same batch.
2. Drag documents or whole folders onto the window (dropped folders are
   walked recursively) or add them with "Add…". Each file shows its size
   and the list footer shows the batch total.
3. Optionally pick a folder with "Output…" where all translations are
   saved (× returns to the default behaviour: next to each original).
   Tick "Skip files already translated" to leave existing outputs
   untouched, which makes an interrupted batch resumable.
4. Press "Translate". Each translated file is saved with the target
   language suffix (e.g. `report_es.docx`).
5. During translation you can press "Cancel": the operation stops
   (even mid-file) and the files already translated are kept.

Note about PDFs: they are translated paragraph by paragraph while
preserving the layout, so a long document can take a while on CPU.
The bar shows the real percentage of translated paragraphs and an
estimate of the remaining time, and the status line names the phase and
the page it is on (reading, translating, generating, saving) so a long
book shows progress instead of an apparently idle bar. Rotated
text (e.g. vertical watermarks) is kept untranslated, and links from
the original document are not preserved in the translated copy.

Supported formats: `.txt` `.docx` `.odt` `.odp` `.pptx` `.epub`
`.html` `.srt` `.pdf`

## Settings

Everything below lives in the **Settings** menu and is remembered
between sessions.

- **Engine** — Argos Translate or NLLB-200 (see above).
- **CPU threads** — capped at the detected core count and defaulting to
  all of them. The NLLB engine splits this budget into several parallel
  CTranslate2 workers of about four threads each, which measured faster
  than one wide worker; budgets below eight threads are left as a single
  worker, where splitting measured slower.
- **Translation quality** — *Best quality*, or *Fast*, which decodes
  greedily: roughly 1.7× faster for a small loss in accuracy. The two
  modes never share cache entries, since their output differs.
- **Theme** — System (the desktop's own look, the default), Light or
  Dark.
- **Download speed units** — network units (`16.8 Mbps`) or the bytes a
  download manager shows (`2.0 MB/s`).
- **Cache** — see below.
- **History** — see below.
- **Manage language packages…** — the Argos package dialog.
- **Delete the NLLB-200 model…** — frees the ~630 MB the model occupies.

### Translation cache

A segment translated once is reused for the rest of the batch and, by
default, across sessions: a paragraph repeated in several files reaches
the engine only once. The window reports how many segments each file and
the batch as a whole reused.

The cache lives in a small sqlite database at
`~/.local/share/argonaut/translation_cache.db` (or under `$XDG_DATA_HOME`).
Entries are namespaced by engine, model version and language pair, so
upgrading a language package stops serving the old model's output. From
*Settings → Cache* you can turn it off, choose how long unused entries
are kept (never, 30 days, 90 days — the default — or a year; expired
ones are pruned when a translation starts), see the database's size and
entry count, and clear it.

### Translation history

Every file a batch finishes is recorded — what was translated, into which
language, where the result was written, with which engine and how long it
took. *Settings → History → View history…* lists them newest first;
double-clicking a row (or the "Open translation" button) opens the
translated file, and rows whose output has since been moved or deleted
stay listed, greyed out, since the history is a record of what happened
rather than a file browser.

Like the cache, it lives in its own sqlite database
(`~/.local/share/argonaut/history.db`) and the same submenu lets you stop
recording, choose how long entries are kept (never, 30 days, 90 days —
the default — or a year), see its size and entry count, and clear it.
Viewing and clearing keep working while recording is off, and only
successful translations are recorded: a file that failed is not history,
it is an error.

## Interface language

The interface starts in English. In the **Language** menu you can switch
to Spanish, French, German, Italian, Portuguese, Russian, Chinese,
Japanese, Dutch, Polish or Turkish; the change applies instantly and the
preference is saved (QSettings) for future launches. To add a language
just add its dictionary in `i18n.py` and list it in `LANGUAGES` (missing
keys fall back to English). The test suite checks that every language
carries the same keys, the same `{placeholders}` and no duplicate
keyboard accelerators within a menu.

The **Help** menu includes "About Argonaut…", a dialog with three tabs:
*About* (version, a short description, the supported formats and links to
the issue tracker and the releases), *Details* (a plain-text report with
the Python, Qt and dependency versions, the operating system, the active
engine, whether the NLLB model is installed and where the cache lives —
copyable with one button, ready to paste into a bug report) and
*Credits and licenses*.

## Persistent settings

When the window closes, QSettings stores — besides the interface
language — the source and target languages, the output folder and the
window size/position; everything is restored on the next launch. If a
saved language is no longer installed or the folder no longer exists,
the default value is used. Everything in the *Settings* menu is saved as
soon as it changes.

## Structure

All modules live in the `src/argonaut/` package:

- `__init__.py` — package version (`__version__`).
- `main.py` — entry point; silences dependency warnings and launches
  the window.
- `window/` — the main window, split by responsibility:
  `main_window.py` (widgets, menus and window state), `engine.py`
  (backend, threads, quality, the cache and history menus and the NLLB
  model), `files.py` and `file_list.py` (the file list and its columns),
  `translation_run.py` (driving a batch and reporting its progress),
  `theme.py` (light/dark/system palettes), `about_dialog.py` and
  `history_dialog.py`.
- `worker.py` — thread that translates the file list and emits progress signals.
- `pdf.py` — fixed PDF translator (paragraphs, progress, cancellation).
- `translation.py` — language detection, supported formats and the
  progress/cache wrapper.
- `history.py` — persistent record of the files each batch translated.
- `nllb.py` — optional NLLB-200 backend (CTranslate2 + SentencePiece)
  exposing the same duck-typed API as argostranslate.
- `download.py` — shared streaming download with progress and cancellation.
- `packages.py` — Argos package index, download, installation and removal.
- `package_dialog.py` — dialog to browse, install and remove packages.
- `i18n.py` — interface languages (English by default, Spanish, French,
  German, Italian, Portuguese, Russian, Chinese, Japanese, Dutch, Polish
  and Turkish).

Packaging lives at the top level: `pyproject.toml` (PyPI),
`io.github.nibblex.Argonaut.yml` (Flatpak manifest) and `data/`
(desktop entry, AppStream metainfo and icon for Flathub).

## Tests

```bash
pip install -e .[test]
pytest
```

The suite runs Qt headless (`QT_QPA_PLATFORM=offscreen`) and needs no
language models: translation engines are faked. Coverage is printed at
the end of the run; CI publishes the badge on every push to `main`.

## Releasing

To publish a new version, bump `__version__` in `src/argonaut/__init__.py`
and add a `<release>` entry in `data/*.metainfo.xml`.

**PyPI**

Publishing is automated: commit the bump, tag it and create a GitHub
release for that tag.

```bash
git tag -a v1.5.0 -m "Argonaut 1.5.0"
git push origin main && git push origin v1.5.0
gh release create v1.5.0 --title "Argonaut 1.5.0" --notes-file notes.md
```

Publishing the release triggers `.github/workflows/publish.yml`, which
builds the wheel and the sdist and uploads them to PyPI via trusted
publishing. Pushing the tag alone does not publish anything, so the CI
run on `main` (the test suite on Python 3.10 through 3.14) can be used
as a gate: a version is permanent on PyPI once uploaded.

**Flathub**

The manifest is `io.github.nibblex.Argonaut.yml`. Flathub builds
have no network access, so the Python dependencies must be pinned first
with [flatpak-pip-generator](https://github.com/flatpak/flatpak-builder-tools):

```bash
python3 flatpak-pip-generator --requirements-file=requirements.txt \
    --output python3-requirements
```

Test locally, then lint:

```bash
flatpak-builder --user --install --force-clean build-dir \
    io.github.nibblex.Argonaut.yml
flatpak run --command=flatpak-builder-lint org.flatpak.Builder \
    manifest io.github.nibblex.Argonaut.yml
```

First submission: take a screenshot for the metainfo (see the TODO in
`data/*.metainfo.xml`), then open a PR against
[flathub/flathub](https://github.com/flathub/flathub) (branch
`new-pr`) adding the manifest, per the
[submission guide](https://docs.flathub.org/docs/for-app-authors/submission).

## Author and license

© 2026 Sergio Rodríguez.

This project is distributed under the [GNU GPL v3](LICENSE) license,
in line with the license of PyQt5, which the interface depends on.
