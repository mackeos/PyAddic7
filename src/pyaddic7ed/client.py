"""Sync client for addic7ed.com.

``Addic7edClient`` merges the feature set of both upstreams:

- ``search_by_filename`` / ``search_best``: matcornic/addic7ed (Go)
- ``search`` / ``download`` / ``get_show_titles``: same31/addic7ed-api (JS)

Download requests send the browser ``Referer`` (show page, with a fallback to
the link itself) - without it addic7ed.com serves an HTML page instead of the
subtitle file.
"""

import logging
import re
import time
from typing import Dict, List, Optional, Tuple, Union
from urllib.parse import quote

import requests

from .exceptions import (
    DownloadError,
    NetworkError,
    NoSubtitleFoundError,
    ShowNotFoundError,
)
from .languages import iso639_2b_to_names
from .models import DEFAULT_BASE_URL, Show, Subtitle, with_language
from .parsing import (
    is_zero_results,
    looks_like_results_page,
    parse_show_name,
    parse_subtitle_blocks,
    parse_show_titles,
    pick_search_result,
)
from .scoring import pick_best_subtitle, score_versions

logger = logging.getLogger("pyaddic7ed")

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/65.0.3325.181 Safari/537.36"
)

_SRCH_URL = "/srch.php?search={query}&Submit=Search"


def format_show_number(number: Union[int, str]) -> str:
    """Zero-pad small season/episode numbers (JS ``formatShowNumber``)."""
    value = int(str(number))
    if value < 10:
        return "0{}".format(value)
    return str(value)


class Addic7edClient:
    """Synchronous addic7ed.com client (thread-safe: one ``requests.Session``)."""

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        user_agent: str = DEFAULT_USER_AGENT,
        timeout: float = 20.0,
        max_retries: int = 2,
        verbose: bool = False,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.user_agent = user_agent
        self.timeout = timeout
        self.max_retries = max_retries
        self.verbose = verbose
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": self.user_agent,
                "Cache-Control": "no-cache",
                "Referer": self.base_url,
            }
        )

    # -- logging ------------------------------------------------------------

    def _log(self, message: str) -> None:
        if self.verbose:
            print(message)
        logger.debug(message)

    # -- HTTP ---------------------------------------------------------------

    def _get(self, url: str, referer: Optional[str] = None) -> requests.Response:
        """GET with retries; raises NetworkError on failure."""
        headers = {"Referer": referer} if referer else {}
        last_exc = None
        for attempt in range(self.max_retries + 1):
            try:
                response = self.session.get(url, timeout=self.timeout, headers=headers)
                if response.status_code >= 500 and attempt < self.max_retries:
                    self._log("addic7ed: HTTP {} on {}, retrying...".format(response.status_code, url))
                    time.sleep(1.0 + attempt)
                    continue
                response.raise_for_status()
                return response
            except requests.RequestException as exc:
                last_exc = exc
                if attempt < self.max_retries:
                    self._log("addic7ed: request failed ({}), retrying...".format(exc))
                    time.sleep(1.0 + attempt)
        raise NetworkError("Unable to reach addic7ed server: {}".format(last_exc))

    def _get_html(self, url: str, referer: Optional[str] = None) -> str:
        response = self._get(url, referer=referer)
        response.encoding = getattr(response, "apparent_encoding", None) or "utf-8"
        return response.text

    # -- public API ---------------------------------------------------------

    def get_show_titles(self) -> List[str]:
        """List every show title on the site (JS ``getShowTitles``)."""
        self._log("Fetching all show titles from {}...".format(self.base_url))
        html = self._get_html(self.base_url)
        titles = parse_show_titles(html)
        self._log("Found {} show titles".format(len(titles)))
        return titles

    def search(
        self,
        show: str,
        season: Optional[Union[int, str]] = None,
        episode: Optional[Union[int, str]] = None,
        languages: Optional[List[str]] = None,
        completed_only: bool = True,
    ) -> List[Subtitle]:
        """Search by show title (+ season/episode) or movie title (JS ``search``).

        ``languages`` filters on ISO 639-2/B codes (e.g. ``["eng", "fre"]``).
        With ``completed_only=True`` (default, JS parity) unfinished
        translations are skipped.
        """
        show = (show or "").strip()
        if not show:
            raise ShowNotFoundError("Show title must not be empty")

        page_type = "tv" if season is not None else "movie"
        query = show
        if season is not None:
            query = "{} {}".format(show, format_show_number(season))
            if episode is not None:
                query = "{} {}".format(query, format_show_number(episode))
        self._log("Searching subtitles for query {!r}...".format(query))

        url = self.base_url + _SRCH_URL.format(query=quote(query))
        body = self._get_html(url)

        if not looks_like_results_page(body):
            # The search page is already the show page (single hit inline).
            subtitles = parse_subtitle_blocks(body, base_url=self.base_url, page_type=page_type)
        elif is_zero_results(body):
            self._log("0 results found")
            subtitles = []
        else:
            link = pick_search_result(body, int(season) if season is not None else None, int(episode) if episode is not None else None)
            if link is None:
                self._log("No matching result link on the results page")
                subtitles = []
            else:
                episode_url = self.base_url + "/" + link.lstrip("/")
                self._log("Following result link {}".format(episode_url))
                episode_body = self._get_html(episode_url)
                subtitles = parse_subtitle_blocks(
                    episode_body, base_url=self.base_url, page_type=page_type
                )

        if completed_only:
            subtitles = [s for s in subtitles if s.completed]
        if languages:
            wanted = {code.lower() for code in languages}
            subtitles = [s for s in subtitles if s.lang_id.lower() in wanted]
        self._log("Search returned {} subtitle(s)".format(len(subtitles)))
        return subtitles

    def search_by_filename(self, file_name: str) -> Show:
        """Search by video file name and return the show page (Go ``SearchAll``).

        Follows the first search result when the query matches several shows,
        exactly like the Go upstream.
        """
        file_name = (file_name or "").strip()
        if not file_name:
            raise ShowNotFoundError("File name must not be empty")

        self._log("Searching show using addic7ed search page...")
        url = self.base_url + _SRCH_URL.format(query=quote(file_name))
        body = self._get_html(url)
        self._log("Addic7ed is up and we found a page")

        show_name = parse_show_name(body)
        if show_name is None:
            # Not a show page: it is (hopefully) a results page.
            from .parsing import parse_search_result_links

            results = parse_search_result_links(body)
            if not results:
                raise ShowNotFoundError("Show not found for file name {!r}".format(file_name))
            self._log(
                "Results page with {} result(s); following the first one...".format(len(results))
            )
            first = self.base_url + "/" + results[0].lstrip("/")
            body = self._get_html(first)
            show_name = parse_show_name(body)
            if show_name is None:
                raise ShowNotFoundError(
                    "Show not found for file name {!r} (first result did not lead to a show page)".format(
                        file_name
                    )
                )
            show_url = first
        else:
            show_url = url

        subtitles = parse_subtitle_blocks(body, base_url=self.base_url, page_type="tv")
        self._log("Found show {!r} with {} subtitle(s)".format(show_name, len(subtitles)))
        return Show(name=show_name, subtitles=subtitles, url=show_url)

    def search_best(self, file_name: str, language: str) -> Tuple[str, Subtitle]:
        """Best subtitle for a file name in a language (Go ``SearchBest``).

        ``language`` is the site language name (e.g. ``"English"``).
        Returns ``(show_name, subtitle)``.
        """
        show = self.search_by_filename(file_name)
        matching = [s for s in show.subtitles if with_language(language)(s)]
        if not matching:
            raise NoSubtitleFoundError(
                "Unable to find any subtitles for show {!r} in {!r}. "
                "Check available languages on Addic7ed website and retry".format(
                    show.name, language
                )
            )
        if len(matching) == 1:
            self._log("Only one subtitle found for lang {}".format(language))
            return show.name, matching[0]

        by_version: Dict[str, List[Subtitle]] = {}
        for sub in matching:
            by_version.setdefault(sub.version, []).append(sub)
        self._log("Found {} different versions, scoring...".format(len(by_version)))
        scores = score_versions(file_name, by_version, verbose=self.verbose)
        best = pick_best_subtitle(scores, by_version)
        if best is None:  # pragma: no cover - defensive
            raise NoSubtitleFoundError("Could not select a best subtitle")
        self._log("=> Best sub: {} ({})".format(best.version, best.link))
        return show.name, best

    def best_for_show(
        self,
        show: Show,
        file_name: str,
        language: str,
    ) -> Tuple[str, Subtitle]:
        """Apply the ``search_best`` scoring to an already-fetched ``Show``."""
        matching = [s for s in show.subtitles if with_language(language)(s)]
        if not matching:
            raise NoSubtitleFoundError(
                "Unable to find any subtitles for show {!r} in {!r}".format(show.name, language)
            )
        by_version: Dict[str, List[Subtitle]] = {}
        for sub in matching:
            by_version.setdefault(sub.version, []).append(sub)
        scores = score_versions(file_name, by_version, verbose=self.verbose)
        best = pick_best_subtitle(scores, by_version)
        if best is None:  # pragma: no cover - defensive
            raise NoSubtitleFoundError("Could not select a best subtitle")
        return show.name, best

    # -- download -----------------------------------------------------------

    def download_subtitle(self, subtitle: Subtitle) -> bytes:
        """Download a subtitle and return normalized utf-8 bytes.

        Sends the ``Referer`` of the show page (JS behaviour) and falls back
        to the link itself (Go behaviour) when the site answers with an HTML
        page instead of the subtitle file.
        """
        url = subtitle.url if subtitle.link.startswith("/") else self.base_url + "/" + subtitle.link

        attempts: List[Optional[str]] = [subtitle.referer_url, url]
        last_error: Optional[DownloadError] = None
        for referer in attempts:
            response = self._get(url, referer=referer)
            content_type = (response.headers.get("Content-Type") or "").lower()
            body = response.content
            if "text/html" in content_type or _looks_like_html(body):
                last_error = DownloadError(
                    "addic7ed returned an HTML page instead of a subtitle file "
                    "(url={}, referer={})".format(url, referer)
                )
                self._log("Download blocked with referer {}, trying fallback...".format(referer))
                continue
            return _normalize_subtitle_bytes(body)
        raise last_error or DownloadError("Could not download subtitle {}".format(url))

    def download_to_file(self, subtitle: Subtitle, path: str) -> None:
        """Download a subtitle and write it to ``path`` (utf-8)."""
        data = self.download_subtitle(subtitle)
        with open(path, "wb") as handle:
            handle.write(data)
        self._log("Subtitle written to {}".format(path))


def _looks_like_html(body: bytes) -> bool:
    sample = body[:512].lstrip().lower()
    return sample.startswith(b"<!doctype") or sample.startswith(b"<html") or b"<head" in sample


def _normalize_subtitle_bytes(body: bytes) -> bytes:
    """Normalize subtitle bytes to utf-8, porting the JS iconv logic.

    Valid utf-8 content is returned unchanged (BOM stripped, like iconv-lite).
    Invalid utf-8 content is decoded as latin-1 and re-encoded as utf-8 -
    the same fallback the JavaScript upstream applies.
    """
    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError:
        text = body.decode("latin-1")
        return text.encode("utf-8")
    if text.startswith("\ufeff"):
        text = text[1:]
    return text.encode("utf-8")


def resolve_language(language: str) -> str:
    """Resolve ``"eng"``-style ISO codes to the site language name.

    ``"English"`` stays ``"English"``; ``"eng"`` becomes ``"English"``.
    """
    if not language:
        return language
    if len(language.strip()) == 3 and " " not in language.strip():
        names = iso639_2b_to_names(language)
        if names:
            return names[0]
    return language
