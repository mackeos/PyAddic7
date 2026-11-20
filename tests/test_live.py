"""Live integration tests against the real addic7ed.com.

Run with:  pytest -m live
Deselect with:  pytest -m "not live"
"""

import pytest

from pyaddic7.client import Addic7edClient

pytestmark = pytest.mark.live


@pytest.fixture(scope="module")
def client():
    return Addic7edClient()


def test_get_show_titles_live(client):
    titles = client.get_show_titles()
    assert len(titles) > 1000
    assert "South Park" in titles


def test_search_tv_live(client):
    subs = client.search("South Park", season=25, episode=4, languages=["eng"])
    assert len(subs) >= 1
    sub = subs[0]
    assert sub.language == "English"
    assert sub.completed is True
    assert sub.link.startswith("/original/") or sub.link.startswith("/updated/")


def test_search_by_filename_live(client):
    show = client.search_by_filename("South.Park.S25E04.720p.WEB.h264-BAE")
    assert "South Park" in show.name
    assert len(show.subtitles) >= 1


def test_search_best_live(client):
    show_name, sub = client.search_best("South.Park.S25E04.720p.WEB.h264-BAE", "English")
    assert "South Park" in show_name
    assert sub.language == "English"


def test_download_real_subtitle_live(client, tmp_path):
    subs = client.search("South Park", season=25, episode=4, languages=["eng"])
    assert subs
    sub = subs[0]
    out = tmp_path / "south_park_s25e04.srt"
    client.download_to_file(sub, str(out))
    data = out.read_bytes()
    # a real subtitle file: no HTML, contains SRT timing arrows
    assert b"<html" not in data[:512].lower()
    assert b" --> " in data
    assert len(data) > 500


def test_download_referer_fallback_live(client, tmp_path):
    """The updated/original link must produce a subtitle, not an HTML page."""
    subs = client.search("South Park", season=25, episode=4)
    assert subs
    data = client.download_subtitle(subs[0])
    assert b" --> " in data


def test_movie_search_live(client):
    subs = client.search("Deadpool 2016")
    assert isinstance(subs, list)
