"""Offline client tests: every HTTP call is served from saved fixtures."""

import pytest

import pyaddic7
from pyaddic7.client import (
    Addic7edClient,
    _looks_like_html,
    _normalize_subtitle_bytes,
    format_show_number,
    resolve_language,
)
from pyaddic7.exceptions import (
    DownloadError,
    NetworkError,
    NoSubtitleFoundError,
    ShowNotFoundError,
)

FIXTURES = "tests/fixtures/"

FAKE_SRT = "1\n00:00:01,000 --> 00:00:03,000\nHello!\n".encode("utf-8")
FAKE_LATIN1_SRT = "1\n00:00:01,000 --> 00:00:03,000\n Caf\xe9 fran\xe7ais\n".encode("latin-1")


class FakeResponse:
    def __init__(self, body, status_code=200, content_type="text/html"):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.content = body
        self.status_code = status_code
        self.headers = {"Content-Type": content_type}
        self.encoding = "utf-8"
        self.apparent_encoding = "utf-8"

    @property
    def text(self):
        return self.content.decode("utf-8", errors="replace")

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests

            raise requests.HTTPError("HTTP {}".format(self.status_code))


class FakeSession:
    """Serves fixture HTML by URL and records calls."""

    def __init__(self, routes=None):
        self.routes = routes or {}
        self.calls = []

    def get(self, url, timeout=None, headers=None):
        self.calls.append({"url": url, "headers": headers or {}})
        for pattern, response in self.routes.items():
            if pattern in url:
                if isinstance(response, Exception):
                    raise response
                return response
        return FakeResponse("<html><body>no route for {}</body></html>".format(url))


def read_fixture(name):
    with open(FIXTURES + name, encoding="utf-8") as handle:
        return handle.read()


def make_client(routes):
    client = Addic7edClient()
    client.session = FakeSession(routes)
    return client


# ---------------------------------------------------------------------------
# format_show_number / resolve_language / helpers
# ---------------------------------------------------------------------------


def test_format_show_number():
    assert format_show_number(25) == "25"
    assert format_show_number(4) == "04"
    assert format_show_number("12") == "12"
    assert format_show_number("3") == "03"


def test_resolve_language():
    assert resolve_language("English") == "English"
    assert resolve_language("eng") == "English"
    assert resolve_language("fre") == "French"


def test_normalize_subtitle_bytes_utf8_strips_bom():
    body = b"\xef\xbb\xbf" + FAKE_SRT
    assert _normalize_subtitle_bytes(body) == FAKE_SRT
    # utf-8 content with a legitimate replacement char must NOT be re-decoded
    tricky = "line \ufffd stays\n".encode("utf-8")
    assert _normalize_subtitle_bytes(tricky) == tricky


def test_normalize_subtitle_bytes_latin1_fallback():
    out = _normalize_subtitle_bytes(FAKE_LATIN1_SRT)
    expected = "1\n00:00:01,000 --> 00:00:03,000\n Café français\n".encode("utf-8")
    assert expected == out


def test_looks_like_html():
    assert _looks_like_html(b"<!doctype html><html>") is True
    assert _looks_like_html(b"<html><body>hi</body></html>") is True
    assert _looks_like_html(FAKE_SRT) is False


# ---------------------------------------------------------------------------
# get_show_titles
# ---------------------------------------------------------------------------


def test_get_show_titles():
    client = make_client({"addic7ed.com": FakeResponse(read_fixture("homepage.html"))})
    titles = client.get_show_titles()
    assert "South Park" in titles
    assert len(titles) > 7000


# ---------------------------------------------------------------------------
# search (JS parity)
# ---------------------------------------------------------------------------


def _routes_for_search():
    return {
        "srch.php?search=South%20Park%2025%2004": FakeResponse(read_fixture("search_one_result.html")),
        "srch.php?search=South%20Park%202025": FakeResponse(read_fixture("search_one_result.html")),
        "serie/South_Park/25/4": FakeResponse(read_fixture("episode_south_park.html")),
        "srch.php?search=Shameless": FakeResponse(read_fixture("search_three_results.html")),
        "serie/Shameless/8/11": FakeResponse(read_fixture("episode_south_park.html")),
        "srch.php?search=Deadpool": FakeResponse(read_fixture("search_movie.html")),
        "movie/109056": FakeResponse(read_fixture("episode_south_park.html")),
        "srch.php?search=NoShow": FakeResponse("<html><b>0 results found</b></html>"),
    }


def test_search_tv():
    client = make_client(_routes_for_search())
    subs = client.search("South Park", season=25, episode=4)
    assert len(subs) == 6
    assert all(s.completed for s in subs)
    # the episode page was fetched after the results page
    urls = [c["url"] for c in client.session.calls]
    assert any("serie/South_Park/25/4" in u for u in urls)


def test_search_tv_language_filter():
    client = make_client(_routes_for_search())
    subs = client.search("South Park", season=25, episode=4, languages=["fre"])
    assert len(subs) == 1
    assert subs[0].language == "French"
    assert subs[0].lang_id == "fre"


def test_search_completed_only():
    client = make_client(_routes_for_search())
    subs = client.search("South Park", season=25, episode=4)
    assert all(s.completed for s in subs)


def test_search_zero_results():
    client = make_client(_routes_for_search())
    assert client.search("NoShow") == []


def test_search_movie():
    client = make_client(_routes_for_search())
    subs = client.search("Deadpool 2016")
    assert len(subs) == 6  # movie page served from the South Park fixture


def test_search_multi_results_picks_matching():
    client = make_client(_routes_for_search())
    subs = client.search("Shameless", season=8, episode=11)
    assert len(subs) == 6
    urls = [c["url"] for c in client.session.calls]
    assert any("serie/Shameless/8/11" in u for u in urls)


# ---------------------------------------------------------------------------
# search_by_filename (Go parity)
# ---------------------------------------------------------------------------


def _routes_for_filename():
    return {
        "srch.php?search=South.Park.S25E04": FakeResponse(read_fixture("episode_south_park.html")),
        "srch.php?search=Shameless.US.S08E11": FakeResponse(read_fixture("search_three_results.html")),
        "serie/Shameless/8/11": FakeResponse(read_fixture("episode_south_park.html")),
        "srch.php?search=DoesNotExist": FakeResponse(
            "<html><body><b>0 results found</b></body></html>"
        ),
    }


def test_search_by_filename_direct_page():
    client = make_client(_routes_for_filename())
    show = client.search_by_filename("South.Park.S25E04.720p.WEB.h264-BAE")
    assert show.name == "South Park - 25x04 - Back to the Cold War"
    assert len(show.subtitles) == 6
    assert show.subtitles[0].version == "WEB.BAE"


def test_search_by_filename_follows_first_result():
    client = make_client(_routes_for_filename())
    show = client.search_by_filename("Shameless.US.S08E11.720p.HDTV.x264-BATV[ettv]")
    assert show.name == "South Park - 25x04 - Back to the Cold War"  # fixture episode page
    urls = [c["url"] for c in client.session.calls]
    # first result of the fixture results page is followed
    assert any("serie/Shameless/8/11" in u for u in urls)


def test_search_by_filename_unknown_show():
    client = make_client(_routes_for_filename())
    with pytest.raises(ShowNotFoundError):
        client.search_by_filename("DoesNotExist")


def test_search_by_filename_empty():
    client = Addic7edClient()
    client.session = FakeSession()
    with pytest.raises(ShowNotFoundError):
        client.search_by_filename("  ")


# ---------------------------------------------------------------------------
# search_best (Go parity)
# ---------------------------------------------------------------------------


def test_search_best():
    client = make_client(_routes_for_filename())
    show_name, sub = client.search_best("South.Park.S25E04.720p.WEB.h264-BAE", "English")
    assert show_name == "South Park - 25x04 - Back to the Cold War"
    assert sub.language == "English"
    assert sub.version in {"WEB.BAE", "HMAX.WEB-DL.NTb"}


def test_search_best_no_language():
    client = make_client(_routes_for_filename())
    with pytest.raises(NoSubtitleFoundError):
        client.search_best("South.Park.S25E04.720p.WEB.h264-BAE", "Klingon")


def test_best_for_show():
    client = make_client(_routes_for_filename())
    show = client.search_by_filename("South.Park.S25E04.720p.WEB.h264-BAE")
    show_name, sub = client.best_for_show(show, "South.Park.S25E04.720p.WEB.h264-BAE", "French")
    assert sub.language == "French"
    assert show_name == show.name


# ---------------------------------------------------------------------------
# download
# ---------------------------------------------------------------------------


def test_download_subtitle_success_with_show_referer():
    routes = {
        "srch.php?search=South.Park.S25E04": FakeResponse(read_fixture("episode_south_park.html")),
        "/original/173311/1": FakeResponse(FAKE_SRT, content_type="application/octet-stream"),
        "/show/116": FakeResponse(read_fixture("episode_south_park.html")),
    }
    client = make_client(routes)
    show = client.search_by_filename("South.Park.S25E04")
    sub = show.subtitles[0]
    data = client.download_subtitle(sub)
    assert data == FAKE_SRT
    call = client.session.calls[-1]
    assert call["url"].endswith("/original/173311/1")
    assert call["headers"]["Referer"] == "https://www.addic7ed.com/show/116"


def test_download_falls_back_to_link_referer_when_html():
    # First attempt (show-page referer) returns HTML, second (link referer) works
    html_page = FakeResponse("<html><body>blocked</body></html>")
    routes = {
        "/original/1/1": FakeResponse("<html><body>blocked</body></html>"),
        "/original/2/1": FakeResponse(FAKE_SRT, content_type="application/octet-stream"),
    }

    class FlakySession(FakeSession):
        def __init__(self):
            super().__init__(routes)
            self.attempts = []

        def get(self, url, timeout=None, headers=None):
            self.attempts.append(headers or {})
            if len(self.attempts) == 1:
                return html_page
            return routes["/original/2/1"]

    client = Addic7edClient()
    client.session = FlakySession()
    from pyaddic7.models import Subtitle

    sub = Subtitle(version="V", language="English", link="/original/2/1", referer="/show/9")
    data = client.download_subtitle(sub)
    assert data == FAKE_SRT
    # first attempt used the show-page referer, second the link itself
    assert client.session.attempts[0]["Referer"] == "https://www.addic7ed.com/show/9"
    assert client.session.attempts[1]["Referer"] == "https://www.addic7ed.com/original/2/1"


def test_download_error_when_both_attempts_return_html():
    class AlwaysHtmlSession(FakeSession):
        def get(self, url, timeout=None, headers=None):
            return FakeResponse("<html><body>blocked</body></html>")

    client = Addic7edClient()
    client.session = AlwaysHtmlSession()
    from pyaddic7.models import Subtitle

    sub = Subtitle(version="V", language="English", link="/original/3/1", referer="/show/9")
    with pytest.raises(DownloadError):
        client.download_subtitle(sub)


def test_download_to_file(tmp_path):
    routes = {
        "srch.php?search=South.Park.S25E04": FakeResponse(read_fixture("episode_south_park.html")),
        "/original/173311/1": FakeResponse(FAKE_SRT, content_type="application/octet-stream"),
    }
    client = make_client(routes)
    show = client.search_by_filename("South.Park.S25E04")
    out = tmp_path / "sub.srt"
    client.download_to_file(show.subtitles[0], str(out))
    assert out.read_bytes() == FAKE_SRT


# ---------------------------------------------------------------------------
# network error / retries
# ---------------------------------------------------------------------------


def test_network_error_after_retries():
    import requests

    client = Addic7edClient(max_retries=1)
    client.session = FakeSession(
        {"addic7ed.com": requests.ConnectionError("nope")}
    )
    with pytest.raises(NetworkError):
        client.get_show_titles()


def test_default_module_level_api(monkeypatch):
    routes = {
        "srch.php?search=South%20Park%2025%2004": FakeResponse(read_fixture("search_one_result.html")),
        "serie/South_Park/25/4": FakeResponse(read_fixture("episode_south_park.html")),
    }
    client = make_client(routes)
    monkeypatch.setattr(pyaddic7, "_DEFAULT_CLIENT", client)
    subs = pyaddic7.search("South Park", season=25, episode=4)
    assert len(subs) == 6
