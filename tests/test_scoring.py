import pytest

from pyaddic7.models import Subtitle
from pyaddic7.scoring import (
    jaro,
    jaro_winkler,
    jaro_with_prefix,
    pick_best_subtitle,
    score_versions,
    words_from_string,
)


# ---------------------------------------------------------------------------
# Jaro-Winkler: canonical test vectors + go-textdistance parity
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "a,b,expected",
    [
        ("MARTHA", "MARHTA", 0.944444),
        ("DWAYNE", "DUANE", 0.822222),
        ("DIXON", "DICKSONX", 0.766667),
        ("abc", "abc", 1.0),
        ("", "", 1.0),
        ("abc", "", 0.0),
        ("CRATE", "TRACE", 0.733333),
    ],
)
def test_jaro_canonical(a, b, expected):
    assert round(jaro(a, b), 6) == pytest.approx(expected, abs=1e-5)


@pytest.mark.parametrize(
    "a,b,expected",
    [
        ("MARTHA", "MARHTA", 0.961111),
        ("DWAYNE", "DUANE", 0.84),
        ("DIXON", "DICKSONX", 0.813333),
        ("dixon", "dicksonx", 0.813333),
    ],
)
def test_jaro_winkler_canonical(a, b, expected):
    assert round(jaro_winkler(a, b), 6) == pytest.approx(expected, abs=1e-5)


def test_jaro_winkler_below_threshold_not_boosted():
    # Jaro("DIXON","JONES") = 0.69 < 0.7 -> no Winkler boost
    assert jaro_winkler("DIXON", "JONES") == jaro("DIXON", "JONES")


def test_prefix_cap_at_four():
    similarity, prefix = jaro_with_prefix("XXXXXXXXABCDE", "XXXXXXXXABCZ")
    assert prefix > 4
    similarity2, prefix2 = jaro_with_prefix("AB", "AB")
    assert similarity2 == 1.0


# ---------------------------------------------------------------------------
# words_from_string (Go wordsFromString)
# ---------------------------------------------------------------------------


def test_words_from_string():
    assert words_from_string("Show.S01E01.720p.HDTV.x264-BATV[ettv]") == [
        "Show",
        "S01E01",
        "720p",
        "HDTV",
        "x264",
        "BATV",
        "ettv",
    ]
    assert words_from_string("The Big Bang Theory - 06x12") == [
        "The",
        "Big",
        "Bang",
        "Theory",
        "06x12",
    ]
    assert words_from_string("") == []


# ---------------------------------------------------------------------------
# score_versions + pick_best_subtitle (Go scoreBestSubVersions)
# ---------------------------------------------------------------------------


def _subs(version):
    return [Subtitle(version=version, language="English", link="/original/1/1")]


def test_score_versions_prefers_matching_release_tags():
    file_name = "Shameless.US.S08E11.720p.HDTV.x264-BATV[ettv]"
    by_version = {"BATV": _subs("BATV"), "KILLERS": _subs("KILLERS")}
    scores = score_versions(file_name, by_version)
    assert scores["BATV"] > scores["KILLERS"]

    file_name = "Dark.S01E05.720p.WEBRip.x264-STRiFE"
    by_version = {"WEBRip.x264-STRiFE": _subs("WEBRip.x264-STRiFE"), "KILLERS": _subs("KILLERS")}
    scores = score_versions(file_name, by_version)
    assert scores["WEBRip.x264-STRiFE"] > scores["KILLERS"]


def test_more_exact_matches_wins():
    # 3 exact matches must beat 2 (Go comment: weight multiplies match count)
    file_name = "aaa bbb ccc ddd 720p"
    by_version = {"aaa bbb ccc": _subs("aaa bbb ccc"), "aaa bbb zzz": _subs("aaa bbb zzz")}
    scores = score_versions(file_name, by_version)
    assert scores["aaa bbb ccc"] > scores["aaa bbb zzz"]


def test_pick_best_prefers_updated_within_version():
    original = Subtitle(version="GRP", language="English", link="/original/5/1")
    updated = Subtitle(version="GRP", language="English", link="/updated/5/2")
    by_version = {"GRP": [original, updated]}
    scores = {"GRP": 5.0}
    assert pick_best_subtitle(scores, by_version) is updated


def test_pick_best_falls_back_to_last_within_version():
    first = Subtitle(version="GRP", language="English", link="/original/5/1")
    last = Subtitle(version="GRP", language="English", link="/original/5/3")
    by_version = {"GRP": [first, last]}
    scores = {"GRP": 5.0}
    assert pick_best_subtitle(scores, by_version) is last


def test_pick_best_deterministic_on_ties():
    a = _subs("AAA")[0]
    b = _subs("BBB")[0]
    by_version = {"AAA": [a], "BBB": [b]}
    scores = {"AAA": 1.0, "BBB": 1.0}
    assert pick_best_subtitle(scores, by_version) is a


def test_pick_best_zero_scores_falls_back_to_first():
    a = _subs("AAA")[0]
    b = _subs("BBB")[0]
    by_version = {"AAA": [a], "BBB": [b]}
    scores = {"AAA": 0.0, "BBB": 0.0}
    assert pick_best_subtitle(scores, by_version) is a
