"""Data models: Subtitle, Show, plus filter and grouping helpers.

The filters and grouping functions port ``filters.go`` and the ``Subtitles``
methods from matcornic/addic7ed; the metadata fields port the objects returned
by same31/addic7ed-api.
"""

import re
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Pattern, Union

from .languages import lang_to_iso639_2b

DEFAULT_BASE_URL = "https://www.addic7ed.com"


@dataclass
class Subtitle:
    """A single subtitle entry for one (version, language) pair."""

    version: str
    language: str
    link: str
    referer: str = "/show/1"
    base_url: str = DEFAULT_BASE_URL
    lang_id: str = ""
    hearing_impaired: bool = False
    corrected: bool = False
    completed: bool = True
    completed_pct: Optional[int] = None
    downloads: Optional[int] = None
    times_edited: Optional[int] = None
    distribution: str = "UNKNOWN"
    team: str = "UNKNOWN"
    show_title: str = ""
    episode_title: str = ""
    uploader: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.lang_id:
            self.lang_id = lang_to_iso639_2b(self.language)

    # --- Go-parity helpers -------------------------------------------------

    @property
    def is_updated(self) -> bool:
        """True when the download link is an updated re-upload (/updated/...)."""
        return "updated" in self.link

    @property
    def is_original(self) -> bool:
        """True when this is the original upload of the subtitle."""
        return not self.is_updated

    @property
    def url(self) -> str:
        """Absolute download URL."""
        if self.link.startswith("http://") or self.link.startswith("https://"):
            return self.link
        return self.base_url.rstrip("/") + (self.link if self.link.startswith("/") else "/" + self.link)

    @property
    def referer_url(self) -> str:
        """Absolute URL of the page to send as Referer when downloading."""
        return self.base_url.rstrip("/") + (self.referer or "/show/1")

    def __str__(self) -> str:
        return "Link: {}, Version: {}, Language: {}".format(self.link, self.version, self.language)

    def to_dict(self) -> dict:
        """JSON-serialisable representation (used by the CLI and mpv)."""
        return {
            "version": self.version,
            "language": self.language,
            "lang_id": self.lang_id,
            "link": self.link,
            "url": self.url,
            "referer": self.referer,
            "referer_url": self.referer_url,
            "hearing_impaired": self.hearing_impaired,
            "corrected": self.corrected,
            "completed": self.completed,
            "completed_pct": self.completed_pct,
            "downloads": self.downloads,
            "times_edited": self.times_edited,
            "distribution": self.distribution,
            "team": self.team,
            "show_title": self.show_title,
            "episode_title": self.episode_title,
            "uploader": self.uploader,
            "is_updated": self.is_updated,
            "is_original": self.is_original,
        }

    def download_to(self, path: str, client: object = None) -> None:
        """Download this subtitle to ``path``.

        A client instance can be passed to reuse its connection pool; otherwise
        a one-off default client is created.
        """
        if client is None:
            from .client import Addic7edClient

            client = Addic7edClient()
        client.download_to_file(self, path)


@dataclass
class Show:
    """A TV show (or movie) episode page with its subtitles."""

    name: str
    subtitles: List[Subtitle] = field(default_factory=list)
    url: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "url": self.url,
            "subtitles": [s.to_dict() for s in self.subtitles],
        }

    def __str__(self) -> str:
        return "Show(name={!r}, subtitles={})".format(self.name, len(self.subtitles))


# ---------------------------------------------------------------------------
# Filters (port of filters.go)
# ---------------------------------------------------------------------------

FilterCallable = Callable[[Subtitle], bool]


def with_language(language: str) -> FilterCallable:
    """Keep subtitles whose language matches (case-insensitive, trimmed)."""
    wanted = language.strip().lower()

    def predicate(sub: Subtitle) -> bool:
        return sub.language.strip().lower() == wanted

    return predicate


def with_version(version: str) -> FilterCallable:
    """Keep subtitles whose version matches (case-insensitive, trimmed)."""
    wanted = version.strip().lower()

    def predicate(sub: Subtitle) -> bool:
        return sub.version.strip().lower() == wanted

    return predicate


def with_version_regexp(pattern: Union[str, Pattern]) -> FilterCallable:
    """Keep subtitles whose version matches a regular expression."""
    compiled = re.compile(pattern) if isinstance(pattern, str) else pattern

    def predicate(sub: Subtitle) -> bool:
        return compiled.search(sub.version.strip()) is not None

    return predicate


def filter_subtitles(subtitles: List[Subtitle], predicate: FilterCallable) -> List[Subtitle]:
    """Return the subtitles for which ``predicate(sub)`` is True."""
    return [s for s in subtitles if predicate(s)]


def group_by(subtitles: List[Subtitle], key: Callable[[Subtitle], str]) -> Dict[str, List[Subtitle]]:
    """Group subtitles by an arbitrary property. Insertion order is preserved."""
    grouped: Dict[str, List[Subtitle]] = {}
    for sub in subtitles:
        grouped.setdefault(key(sub), []).append(sub)
    return grouped


def group_by_version(subtitles: List[Subtitle]) -> Dict[str, List[Subtitle]]:
    """Group subtitles by version."""
    return group_by(subtitles, lambda s: s.version)


def group_by_language(subtitles: List[Subtitle]) -> Dict[str, List[Subtitle]]:
    """Group subtitles by language."""
    return group_by(subtitles, lambda s: s.language)
