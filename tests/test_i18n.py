import re

import pytest

from argonaut import i18n
from argonaut.i18n import (
    DEFAULT,
    LANGUAGES,
    STRINGS,
    current_language,
    load_language,
    set_language,
    tr,
)


def test_default_language_is_english():
    assert current_language() == "en"
    assert tr("translate") == "Translate"


def test_set_language_switches_strings():
    set_language("es")
    assert current_language() == "es"
    assert tr("translate") == "Traducir"


def test_set_language_persists_and_reloads():
    set_language("fr")
    assert load_language() == "fr"


def test_unknown_language_is_ignored():
    set_language("xx")
    assert current_language() == DEFAULT


def test_missing_key_falls_back_to_english(monkeypatch):
    set_language("es")
    monkeypatch.delitem(STRINGS["es"], "translate")
    assert tr("translate") == "Translate"


def test_unknown_key_returns_the_key():
    assert tr("nonexistent_key") == "nonexistent_key"


def test_menu_lists_every_translated_language():
    assert [code for code, _ in LANGUAGES] == sorted(STRINGS, key=lambda c: c != "en")


@pytest.mark.parametrize("code", [code for code, _ in LANGUAGES])
def test_all_languages_have_all_english_keys(code):
    assert set(STRINGS[code]) == set(STRINGS["en"])


@pytest.mark.parametrize("code", [code for code, _ in LANGUAGES])
def test_placeholders_match_english(code):
    placeholders = lambda s: sorted(re.findall(r"{(\w+)}", s))
    for key, english in STRINGS["en"].items():
        assert placeholders(STRINGS[code][key]) == placeholders(english), key


@pytest.mark.parametrize("code", [code for code, _ in LANGUAGES])
def test_about_text_renders(code):
    set_language(code)
    text = tr("about_text", version="9.9.9", formats=".txt .pdf")
    assert "Argonaut 9.9.9" in text
    assert ".txt .pdf" in text
    assert "github.com/Nibblex/Argonaut" in text
