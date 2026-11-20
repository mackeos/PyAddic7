import pytest

from pyaddic7.parsing import (
    clean_version_title,
    extract_distribution,
    extract_team,
    is_zero_results,
    looks_like_results_page,
    parse_referer,
    parse_search_result_links,
    parse_show_and_episode_titles,
    parse_show_name,
    parse_show_titles,
    parse_subtitle_blocks,
    pick_search_result,
)


def read_fixture(name):
    with open("tests/fixtures/{}".format(name), encoding="utf-8") as handle:
        return handle.read()


# ---------------------------------------------------------------------------
# clean_version_title / distribution / team (JS + Go ports)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "title,expected",
    [
        ("Version WEB.BAE, Duration: 0.00", "WEB.BAE"),
        ("Version BATV, 0.00 MBs", "BATV"),
        ("Version DVDRip-DiMENSiON, Duration: 0.00", "DVDRip-DiMENSiON"),
        ("Version HMAX.WEB-DL.NTb, Duration: 22.20", "HMAX.WEB-DL.NTb"),
        ("Version web-dl, Duration: 0.00", "web-dl"),
    ],
)
def test_clean_version_title(title, expected):
    assert clean_version_title(title) == expected


@pytest.mark.parametrize(
    "version,expected_dist,expected_team",
    [
        ("WEB.BAE", "WEB-DL", "BAE"),
        ("HMAX.WEB-DL.NTb", "WEB-DL", "HMAXNTB"),
        ("KILLERS", "UNKNOWN", "KILLERS"),
        ("720P.HDTV", "HDTV", ""),
        ("AMZN.WEBRip", "WEB-DL", ""),
        ("BDRIP.GRP", "BLURAY", "GRP"),
        ("web-dl", "WEB-DL", ""),
        ("BAE+MeGusta", "UNKNOWN", "BAE+MEGUSTA"),
    ],
)
def test_distribution_and_team(version, expected_dist, expected_team):
    assert extract_distribution(version) == expected_dist
    assert extract_team(version) == expected_team or expected_team == ""


def test_team_unknown_when_empty():
    assert extract_team("720P.HDTV") == "UNKNOWN"


# ---------------------------------------------------------------------------
# Show page parsing on real fixtures
# ---------------------------------------------------------------------------


def test_parse_show_name_south_park():
    html = read_fixture("episode_south_park.html")
    assert parse_show_name(html) == "South Park - 25x04 - Back to the Cold War"


def test_parse_show_name_the_flash():
    html = read_fixture("episode_the_flash.html")
    assert parse_show_name(html) == "The Flash - 01x01 - Pilot"


def test_parse_referer():
    html = read_fixture("episode_south_park.html")
    assert parse_referer(html) == "/show/116"


def test_parse_titles_tv():
    html = read_fixture("episode_south_park.html")
    show, episode = parse_show_and_episode_titles(html, "tv")
    assert show == "South Park"
    assert episode == "Back to the Cold War"


def test_parse_titles_movie_synthetic():
    html = (
        '<html><body><span class="titulo"> Deadpool (2016) '
        "<small>Subtitle</small></span></body></html>"
    )
    show, episode = parse_show_and_episode_titles(html, "movie")
    assert show == "Deadpool"
    assert episode == ""


def test_south_park_subtitles_complete_metadata():
    html = read_fixture("episode_south_park.html")
    subs = parse_subtitle_blocks(html, page_type="tv")
    assert len(subs) == 6

    first = subs[0]
    assert first.version == "WEB.BAE"
    assert first.language == "English"
    assert first.lang_id == "eng"
    assert first.link == "/original/173311/1"
    assert first.referer == "/show/116"
    assert first.completed is True
    assert first.downloads == 1737
    assert first.times_edited == 0
    assert first.hearing_impaired is True
    assert first.corrected is True
    assert first.distribution == "WEB-DL"
    assert first.team == "BAE"
    assert first.show_title == "South Park"
    assert first.episode_title == "Back to the Cold War"
    assert first.is_original is True

    # per-block uploaders
    uploaders = {s.uploader for s in subs}
    assert "QueenMaddie" in uploaders

    # download counts from the info rows, in document order
    assert [s.downloads for s in subs] == [1737, 2057, 1445, 931, 1047, 1036]

    # languages
    languages = [s.language for s in subs]
    assert languages[:3] == ["English", "English", "English"]
    assert languages[3] == "French"
    assert languages[4:] == ["Portuguese (Brazilian)", "Portuguese (Brazilian)"]
    assert subs[4].lang_id == "por"


def test_the_flash_subtitles_metadata():
    html = read_fixture("episode_the_flash.html")
    subs = parse_subtitle_blocks(html, page_type="tv")
    assert len(subs) == 3
    assert [s.language for s in subs] == ["English", "Portuguese (Brazilian)", "Russian"]
    assert [s.downloads for s in subs] == [16845, 812, 550]
    assert [s.times_edited for s in subs] == [2, 0, 1012]
    assert subs[0].version == "DVDRip"
    assert subs[2].version == "DVDRip-DiMENSiON"


# ---------------------------------------------------------------------------
# Synthetic markup: incomplete rows, updated links, multi-language tables
# ---------------------------------------------------------------------------

SYNTHETIC = """
<html><body>
<a href="/show/123">Show</a>
<span class="titulo"> My Show - 01x02 - Pilot <small>Subtitle</small></span>
<table width="100%" border="0" align="center" class="tabel95">
 <tr><td colspan="3" class="NewsTitle">Version GRP.720P, Duration: 0.00 <a href="/user/55">UploaderX</a></td></tr>
 <tr><td class="newsDate">Duration: 42:00</td></tr>
 <tr>
   <td class="language">English<a href="javascript:saveFavorite(9,1,1)">x</a></td>
   <td width="19%"><b>Completed</b></td>
   <td colspan="3"><a class="face-button" href="/original/9/1">Download</a></td>
 </tr>
 <tr><td class="newsDate"><img title="Corrected" /><img title="Hearing Impaired" />3 times edited · 777 Downloads · 400 sequences</td></tr>
 <tr>
   <td class="language">French<a href="javascript:saveFavorite(10,1,2)">x</a></td>
   <td width="19%">60% Completed</td>
   <td colspan="3"><a class="face-button" href="/updated/10/2">Download</a></td>
 </tr>
 <tr><td class="newsDate">101 times edited · 55 Downloads · 400 sequences</td></tr>
</table>
</body></html>
"""


def test_synthetic_completed_and_incomplete():
    subs = parse_subtitle_blocks(SYNTHETIC)
    assert len(subs) == 2
    english, french = subs
    assert english.completed is True
    assert english.completed_pct is None
    assert english.hearing_impaired is True
    assert english.corrected is True
    assert english.downloads == 777
    assert english.times_edited == 3
    assert english.uploader == "UploaderX"
    assert english.lang_id == "eng"

    assert french.completed is False
    assert french.completed_pct == 60
    assert french.is_updated is True
    assert french.link == "/updated/10/2"
    assert french.lang_id == "fre"
    assert french.downloads == 55


def test_synthetic_old_style_strong_download_link():
    # The markup the JS upstream was written against (<strong>Download</strong>)
    old_style = (
        '<html><body><a href="/show/9">S</a>'
        '<table width="100%" border="0" align="center" class="tabel95">'
        '<tr><td class="NewsTitle">Version OLD.TEAM, Duration: 0.00</td></tr>'
        '<tr><td class="language">English</td>'
        "<td width=\"19%\"><b>Completed</b></td>"
        '<td colspan="3"><a href="/original/5/1"><strong>Download</strong></a></td></tr>'
        "<tr><td class='newsDate'>12 Downloads</td></tr>"
        "</table></body></html>"
    )
    subs = parse_subtitle_blocks(old_style)
    assert len(subs) == 1
    assert subs[0].link == "/original/5/1"
    assert subs[0].downloads == 12


# ---------------------------------------------------------------------------
# Search result pages
# ---------------------------------------------------------------------------


def test_search_one_result():
    html = read_fixture("search_one_result.html")
    assert looks_like_results_page(html) is True
    assert is_zero_results(html) is False
    links = parse_search_result_links(html)
    assert "serie/South_Park/25/4/Back_to_the_Cold_War" in links
    assert pick_search_result(html, 25, 4) == "serie/South_Park/25/4/Back_to_the_Cold_War"


def test_search_three_results_picks_matching_season_episode():
    html = read_fixture("search_three_results.html")
    links = parse_search_result_links(html)
    assert len(links) == 3
    # JS parity: the first link matching season 8 / episode 11
    assert pick_search_result(html, 8, 11) == "serie/Shameless/8/11/_Episode_11"


def test_search_movie():
    html = read_fixture("search_movie.html")
    assert pick_search_result(html, None, None) == "movie/109056"


def test_zero_results_marker():
    html = "<html><body><b>0 results found</b></body></html>"
    assert looks_like_results_page(html) is True
    assert is_zero_results(html) is True


# ---------------------------------------------------------------------------
# Homepage show titles
# ---------------------------------------------------------------------------


def test_show_titles():
    html = read_fixture("homepage.html")
    titles = parse_show_titles(html)
    assert len(titles) > 7000
    assert "South Park" in titles
    # entities are unescaped
    assert all("&amp;" not in t for t in titles)
