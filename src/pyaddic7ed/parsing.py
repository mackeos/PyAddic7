"""HTML parsing for addic7ed.com pages.

Targets the current site markup (verified November 2025):

- Show/episode title: ``<span class="titulo">Show - NNxNN - Title <small>...</small></span>``
- One subtitle block per ``table.tabel95`` with ``align="center"``: a
  ``NewsTitle`` cell ("Version X, ..."), then per language a row with a
  ``td.language``, the completion cell and an ``a.face-button`` download
  anchor (``/original/<id>/<n>`` or ``/updated/<id>/<n>``), followed by a
  ``newsDate`` info row carrying the Corrected / Hearing Impaired icons, the
  "N times edited" and "N Downloads" counters.
- Search pages either show ``<b>N results found</b>`` with ``serie/...`` /
  ``movie/...`` links, or are already a show page.
"""

import re
from typing import List, Optional, Tuple

from bs4 import BeautifulSoup, Tag

from .exceptions import ParsingError
from .languages import lang_to_iso639_2b
from .models import DEFAULT_BASE_URL, Subtitle

# "Version TEAM, Duration: ..." -> "TEAM" (port of cleanTitle in addic7ed.go)
_NEWS_TITLE_RE = re.compile(r"Version\s+(.+?)\s*,", re.IGNORECASE)
# "South Park - 25x04 - Back to the Cold War <small>Subtitle</small>"
# applied to the clean .titulo text (see parse_show_and_episode_titles)
_TV_TITLE_TEXT_RE = re.compile(r"(.+?)\s*-\s*\d+x\d+\s*-\s*(.+)$")
# "Deadpool (2016) <small>Subtitle</small>"
_MOVIE_TITLE_TEXT_RE = re.compile(r"(.+?)\s*\(\d{4}\)\s*$")
# Breadcrumb link used as download referer (JS referer extraction)
_SHOW_ID_RE = re.compile(r"/show/(\d+)")
_COMPLETED_PCT_RE = re.compile(r"(\d+)\s*%\s*Completed", re.IGNORECASE)
_DOWNLOADS_RE = re.compile(r"(\d+)\s*Downloads", re.IGNORECASE)
_EDITED_RE = re.compile(r"(\d+)\s*times?\s*edited", re.IGNORECASE)
_RESULTS_FOUND_RE = re.compile(r"<b>\d+ results found</b>")
_ZERO_RESULTS_RE = re.compile(r"<b>0 results found</b>")
_SERIE_LINK_RE = re.compile(r"^serie/[^/]+/(\d+)/(\d+)/")
_SERIE_ANY_RE = re.compile(r"^serie/")
_MOVIE_LINK_RE = re.compile(r"^movie/\d+")

# JS-lib distribution/team extraction (from version strings)
_DISTRIBUTION_RE = re.compile(r"HDTV|WEB(.DL|.?RIP)?|WR|BRRIP|BDRIP|BLURAY", re.IGNORECASE)
_TEAM_STRIP_RE = re.compile(
    r".?(REPACK|PROPER|[XH].?264|HDTV|480P|720P|1080P|2160P|AMZN|WEB(.DL|.?RIP)?|WR|BRRIP|BDRIP|BLURAY)+.?",
    re.IGNORECASE,
)


def clean_version_title(title: str) -> str:
    """Extract the version name from a NewsTitle (port of ``cleanTitle``).

    ``"Version WEB.BAE, Duration: 0.00"`` -> ``"WEB.BAE"``.
    """
    parts = title.split(",")
    clean = parts[0]
    fields = clean.split()
    if len(fields) >= 2:
        clean = fields[1]
    elif len(fields) == 1:
        clean = fields[0]
    else:
        clean = title
    return clean


def extract_distribution(version: str) -> str:
    """Extract HDTV / WEB-DL / BLURAY from a version string (JS port)."""
    match = _DISTRIBUTION_RE.search(version)
    if not match:
        return "UNKNOWN"
    token = match.group(0).upper()
    if re.match(r"^WEB(\.DL|\.?RIP)?$", token) or token == "WR":
        return "WEB-DL"
    if token in ("BRRIP", "BDRIP", "BLURAY"):
        return "BLURAY"
    return token


def extract_team(version: str) -> str:
    """Extract the release team from a version string (JS port)."""
    stripped = _TEAM_STRIP_RE.sub("", version).strip().upper()
    return stripped or "UNKNOWN"


def _make_soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


def parse_show_name(html: str) -> Optional[str]:
    """Find the show/episode name in a show page (port of ``findShowName``).

    Takes the first non-``<small>`` text node inside ``span.titulo``.
    """
    soup = _make_soup(html)
    titulo = soup.find(class_="titulo")
    if titulo is None:
        return None
    for node in titulo.contents:
        if getattr(node, "name", None) == "small":
            continue
        text = node.string if node.string is not None else str(node)
        text = text.strip()
        if text:
            return text
    return None


def parse_referer(html: str) -> str:
    """Find the show page path used as Referer (first ``/show/<id>`` link)."""
    match = _SHOW_ID_RE.search(html)
    return "/show/{}".format(match.group(1)) if match else "/show/1"


def parse_show_and_episode_titles(html: str, page_type: str) -> Tuple[str, str]:
    """Return ``(show_title, episode_title)`` parsed from the page title."""
    soup = _make_soup(html)
    titulo = soup.find(class_="titulo")
    if titulo is None:
        return "", ""
    # Clean text of the title, excluding the trailing <small>Subtitle</small>.
    parts = []
    for node in titulo.contents:
        if getattr(node, "name", None) == "small":
            continue
        text = node.string if node.string is not None else str(node)
        if text:
            parts.append(text)
    clean = " ".join(p.strip() for p in parts if p.strip())
    if page_type == "movie":
        match = _MOVIE_TITLE_TEXT_RE.match(clean)
    else:
        match = _TV_TITLE_TEXT_RE.match(clean)
    if not match:
        return "", ""
    if page_type == "movie":
        return match.group(1).strip(), ""
    return match.group(1).strip(), match.group(2).strip()


def _parse_completed_cell(cell: Optional[Tag]) -> Tuple[bool, Optional[int]]:
    """Interpret the completion cell: ``<b>Completed</b>`` or ``N% Completed``."""
    if cell is None:
        return True, None
    text = cell.get_text(" ", strip=True)
    pct = _COMPLETED_PCT_RE.search(text)
    if pct:
        return False, int(pct.group(1))
    return ("completed" in text.lower()), None


def _parse_language_cell(cell: Tag) -> str:
    """Language name from the ``td.language`` cell (first text node)."""
    first_text = cell.find(string=True, recursive=False)
    if first_text is not None and first_text.strip():
        return first_text.strip()
    return cell.get_text(strip=True)


def parse_subtitle_blocks(
    html: str,
    base_url: str = DEFAULT_BASE_URL,
    page_type: str = "tv",
) -> List[Subtitle]:
    """Parse every subtitle block of a show/episode/movie page."""
    soup = _make_soup(html)
    show_title, episode_title = parse_show_and_episode_titles(html, page_type)
    referer = parse_referer(html)

    subtitles: List[Subtitle] = []
    seen_links = set()

    tables = [
        t
        for t in soup.select("table.tabel95")
        if (t.get("align") or "").lower() == "center" and t.find(class_="NewsTitle")
    ]

    for table in tables:
        news_title = table.find(class_="NewsTitle")
        version = clean_version_title(news_title.get_text(" ", strip=True)) if news_title else ""
        version = version.strip()
        uploader = None
        if news_title is not None:
            news_row = news_title.find_parent("tr")
            if news_row is not None:
                user_link = news_row.find("a", href=re.compile(r"^/user/\d+"))
                if user_link is not None:
                    uploader = user_link.get_text(strip=True)

        pending = None  # subtitle waiting for its info row
        for tr in table.find_all("tr"):
            lang_cell = tr.find(class_="language")
            info_row = any("newsDate" in (td.get("class") or []) for td in tr.find_all("td"))

            if lang_cell is not None:
                face = tr.find("a", class_="face-button")
                link = face.get("href") if face is not None else None
                if not link:
                    # Fallback for the old markup (JS upstream era):
                    # <a href="/original/..."><strong>Download</strong></a>
                    for anchor in tr.find_all("a", href=True):
                        href = anchor["href"].strip()
                        if href.startswith("/original/") or href.startswith("/updated/"):
                            link = href
                            break
                if not link:
                    continue
                completed, completed_pct = _parse_completed_cell(
                    next(
                        (
                            td
                            for td in tr.find_all("td")
                            if "Completed" in td.get_text()
                        ),
                        None,
                    )
                )
                language = _parse_language_cell(lang_cell)
                sub = Subtitle(
                    version=version,
                    language=language,
                    link=link.strip(),
                    referer=referer,
                    base_url=base_url,
                    lang_id=lang_to_iso639_2b(language),
                    completed=completed,
                    completed_pct=completed_pct,
                    distribution=extract_distribution(version),
                    team=extract_team(version),
                    show_title=show_title,
                    episode_title=episode_title,
                    uploader=uploader,
                )
                if sub.link in seen_links:
                    continue
                seen_links.add(sub.link)
                subtitles.append(sub)
                pending = sub
            elif pending is not None and info_row:
                text = tr.get_text(" ", strip=True)
                imgs = [img.get("title") or "" for img in tr.find_all("img")]
                downloads = _DOWNLOADS_RE.search(text)
                edited = _EDITED_RE.search(text)
                if downloads:
                    pending.downloads = int(downloads.group(1))
                if edited:
                    pending.times_edited = int(edited.group(1))
                if any("Hearing Impaired" in t for t in imgs):
                    pending.hearing_impaired = True
                if any("Corrected" in t for t in imgs):
                    pending.corrected = True
                pending = None

    return subtitles


def parse_search_result_links(html: str) -> List[str]:
    """Return the ``serie/...`` / ``movie/...`` links of a search results page."""
    soup = _make_soup(html)
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if _SERIE_ANY_RE.match(href) or _MOVIE_LINK_RE.match(href):
            if href not in links:
                links.append(href)
    return links


def pick_search_result(
    html: str,
    season: Optional[int],
    episode: Optional[int],
) -> Optional[str]:
    """Choose the result link of a search page (JS port with a robust fallback).

    TV: prefer a ``serie/<show>/<season>/<episode>/...`` link matching the
    requested season/episode; fall back to the first ``serie/`` link.
    Movie: first ``movie/<id>`` link.
    """
    links = parse_search_result_links(html)
    if season is not None:
        wanted_season = int(season)
        wanted_episode = int(episode) if episode is not None else None
        for link in links:
            match = _SERIE_LINK_RE.match(link)
            if match:
                link_season = int(match.group(1))
                link_episode = int(match.group(2))
                if wanted_episode is not None:
                    if link_season == wanted_season and link_episode == wanted_episode:
                        return link
                elif link_season == wanted_season:
                    return link
        # Fallback: first serie link (Go upstream takes the first result).
        for link in links:
            if _SERIE_ANY_RE.match(link):
                return link
        return None
    for link in links:
        if _MOVIE_LINK_RE.match(link):
            return link
    return None


def parse_show_titles(html: str) -> List[str]:
    """Show titles from the homepage ``<option value="<id>">Title</option>`` dropdown."""
    titles = []
    for match in re.finditer(r'<option value="\d+" ?>([^<]*)</option>', html):
        title = match.group(1).replace("&amp;", "&").strip()
        if title and title not in titles:
            titles.append(title)
    return titles


def looks_like_results_page(html: str) -> bool:
    """True when the response is a search results page (JS parity)."""
    return _RESULTS_FOUND_RE.search(html) is not None


def is_zero_results(html: str) -> bool:
    """True when the search page says "0 results found"."""
    return _ZERO_RESULTS_RE.search(html) is not None


def page_has_subtitle_tables(html: str) -> bool:
    """Cheap check that a page parsed as a show page contains subtitle blocks."""
    try:
        soup = _make_soup(html)
    except Exception as exc:  # pragma: no cover - bs4 rarely raises
        raise ParsingError("Could not parse HTML page: {}".format(exc)) from exc
    return bool(soup.select("table.tabel95"))
