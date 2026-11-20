import pytest

from pyaddic7ed.languages import iso639_2b_to_names, lang_to_iso639_2b


@pytest.mark.parametrize(
    "name,expected",
    [
        ("English", "eng"),
        ("French", "fre"),
        ("German", "ger"),
        ("Greek", "gre"),
        ("Chinese", "chi"),
        ("Portuguese (Brazilian)", "por"),
        ("Spanish (Spain)", "spa"),
        ("Spanish (Latino)", "spa"),
        ("Serbian (Cyrillic)", "srp"),
        ("Czech", "ces"),
        ("Dutch", "dut"),
        ("Romanian", "rum"),
        ("Bulgarian", "bul"),
        ("Norwegian", "nor"),
        ("Hungarian", "hun"),
        ("Croatian", "hrv"),
        ("Turkish", "tur"),
        ("Russian", "rus"),
        ("Arabic", "ara"),
        ("Italian", "ita"),
        ("Swedish", "swe"),
    ],
)
def test_lang_to_iso639_2b(name, expected):
    assert lang_to_iso639_2b(name) == expected


def test_lang_fallback_three_chars():
    # Unknown language: first three characters lowercased (JS parity)
    assert lang_to_iso639_2b("Klingon") == "kli"


def test_reverse_lookup():
    assert "English" in iso639_2b_to_names("eng")
    assert "French" in iso639_2b_to_names("fre")
    assert iso639_2b_to_names("xyz") == []
