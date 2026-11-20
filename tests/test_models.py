import pytest

from pyaddic7.models import (
    Subtitle,
    filter_subtitles,
    group_by_language,
    group_by_version,
    with_language,
    with_version,
    with_version_regexp,
)


def _sub(**kwargs):
    defaults = dict(
        version="BATV",
        language="English",
        link="/original/173311/1",
        referer="/show/116",
        base_url="https://www.addic7ed.com",
    )
    defaults.update(kwargs)
    return Subtitle(**defaults)


def test_url_resolution():
    assert _sub().url == "https://www.addic7ed.com/original/173311/1"
    assert _sub(link="/updated/1/2").url == "https://www.addic7ed.com/updated/1/2"
    assert _sub(link="http://mirror.example/original/1").url == "http://mirror.example/original/1"


def test_referer_url_defaults():
    assert _sub().referer_url == "https://www.addic7ed.com/show/116"
    assert _sub(referer="").referer_url == "https://www.addic7ed.com/show/1"


def test_is_updated_flags():
    assert _sub().is_updated is False
    assert _sub().is_original is True
    assert _sub(link="/updated/173311/1").is_updated is True
    assert _sub(link="/updated/173311/1").is_original is False


def test_lang_id_auto_filled():
    assert _sub().lang_id == "eng"
    assert _sub(language="French").lang_id == "fre"
    assert _sub(language="Portuguese (Brazilian)").lang_id == "por"


def test_to_dict_shape():
    data = _sub().to_dict()
    for key in (
        "version",
        "language",
        "lang_id",
        "link",
        "url",
        "referer",
        "referer_url",
        "hearing_impaired",
        "corrected",
        "completed",
        "downloads",
        "distribution",
        "team",
        "show_title",
        "episode_title",
        "uploader",
        "is_updated",
        "is_original",
    ):
        assert key in data
    assert data["url"] == "https://www.addic7ed.com/original/173311/1"


# ---------------------------------------------------------------------------
# Filters and grouping (filters.go ports)
# ---------------------------------------------------------------------------


def test_with_language_filter():
    subs = [_sub(), _sub(language="French"), _sub(language=" english ")]
    kept = filter_subtitles(subs, with_language("English"))
    assert len(kept) == 2


def test_with_version_filter():
    subs = [_sub(), _sub(version="killers")]
    kept = filter_subtitles(subs, with_version("KILLERS"))
    assert len(kept) == 1
    assert kept[0].version == "killers"


def test_with_version_regexp_filter():
    subs = [_sub(), _sub(version="WEBRip.x264-STRiFE")]
    kept = filter_subtitles(subs, with_version_regexp(r"STRiFE"))
    assert len(kept) == 1
    assert kept[0].version == "WEBRip.x264-STRiFE"


def test_grouping():
    subs = [
        _sub(),
        _sub(link="/original/2/1", version="KILLERS"),
        _sub(language="French", link="/original/3/1"),
    ]
    by_version = group_by_version(subs)
    assert set(by_version) == {"BATV", "KILLERS"}
    assert len(by_version["BATV"]) == 2

    by_language = group_by_language(subs)
    assert set(by_language) == {"English", "French"}
    assert len(by_language["English"]) == 2
