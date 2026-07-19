# Argonaut

Minimalist document translator with a Qt (PyQt5) interface that uses
[argos-translate-files](https://github.com/LibreTranslate/argos-translate-files)
as an offline translation engine.

## Requirements

```bash
pip install PyQt5 argos-translate-lt argos-translate-files langdetect
```

You need at least one language package installed, for example:

```bash
argospm update
argospm install translate-en_es
```

## Usage

From a checkout:

```bash
python3 -m argonaut
```

Or install it (provides the `argonaut` command):

```bash
pip install argonaut-translator
```

## Structure

All modules live in the `src/argonaut/` package:

- `__init__.py` — package version (`__version__`).
- `main.py` — entry point; silences dependency warnings and launches
  the window.
- `window.py` — main window (PyQt5).
- `worker.py` — thread that translates the file list and emits progress signals.
- `pdf.py` — fixed PDF translator (paragraphs, progress, cancellation).
- `translation.py` — language detection, supported formats and the
  progress/cache wrapper.
- `i18n.py` — interface languages (English by default, Spanish, French,
  German, Italian and Portuguese).

Packaging lives at the top level: `pyproject.toml` (PyPI),
`io.github.nibblex.Argonaut.yml` (Flatpak manifest) and `data/`
(desktop entry, AppStream metainfo and icon for Flathub).

## Interface language

The interface starts in English. In the **Language** menu you can switch
to Spanish, French, German, Italian or Portuguese; the change applies
instantly and the preference is saved (QSettings) for future launches.
To add a language just add its dictionary in `i18n.py` (missing keys fall
back to English). The **Help** menu includes "About Argonaut", showing
the version, a short description of the project, the translation engine,
the supported formats, the author and the license.

## Persistent settings

When the window closes, QSettings stores — besides the interface
language — the source and target languages, the output folder and the
window size/position; everything is restored on the next launch. If a
saved language is no longer installed or the folder no longer exists,
the default value is used.

1. Choose the source and target languages (⇄ button to swap them).
   By default the source is "Detect language": each document's language
   is detected automatically, so you can mix files in different
   languages in the same batch.
2. Drag documents onto the window or add them with "Add…".
3. Optionally pick a folder with "Output…" where all translations are
   saved (× returns to the default behaviour: next to each original).
4. Press "Translate". Each translated file is saved with the target
   language suffix (e.g. `report_es.docx`).
5. During translation you can press "Cancel": the operation stops
   (even mid-file) and the files already translated are kept.

Note about PDFs: they are translated paragraph by paragraph while
preserving the layout, so a long document can take a while on CPU.
The bar shows the real percentage of translated paragraphs. Rotated
text (e.g. vertical watermarks) is kept untranslated, and links from
the original document are not preserved in the translated copy.

Supported formats: `.txt` `.docx` `.odt` `.odp` `.pptx` `.epub`
`.html` `.srt` `.pdf`

## Releasing

To publish a new version, bump `__version__` in `src/argonaut/__init__.py`
and add a `<release>` entry in `data/*.metainfo.xml`.

**PyPI**

```bash
pip install build twine
python3 -m build
twine upload dist/*
```

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
