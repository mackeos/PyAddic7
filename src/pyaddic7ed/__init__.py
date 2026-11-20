"""pyaddic7ed - Python API to search and download subtitles from addic7ed.com.

Full-featured Python port of matcornic/addic7ed (Go) and same31/addic7ed-api
(JavaScript). See the README for usage examples.
"""

__version__ = "0.1.0"

from .client import Addic7edClient, resolve_language
from .exceptions import (
    Addic7edError,
    DownloadError,
    NetworkError,
    NoSubtitleFoundError,
    ParsingError,
    ShowNotFoundError,
)
from .models import (
    Show,
    Subtitle,
    filter_subtitles,
    group_by,
    group_by_language,
    group_by_version,
    with_language,
    with_version,
    with_version_regexp,
)

__all__ = [
    "Addic7edClient",
    "Addic7ed",
    "Show",
    "Subtitle",
    "Addic7edError",
    "NetworkError",
    "ParsingError",
    "ShowNotFoundError",
    "NoSubtitleFoundError",
    "DownloadError",
    "with_language",
    "with_version",
    "with_version_regexp",
    "filter_subtitles",
    "group_by",
    "group_by_version",
    "group_by_language",
    "resolve_language",
    "search",
    "search_by_filename",
    "search_best",
    "download",
    "download_bytes",
    "get_show_titles",
    "__version__",
]

# ``Addic7ed`` alias keeps the naming of the Go upstream (addic7ed.New()).
Addic7ed = Addic7edClient

_DEFAULT_CLIENT: Addic7edClient = None  # type: ignore[assignment]


def _client(**kwargs) -> Addic7edClient:
    """Return the module-level default client, creating it on first use."""
    global _DEFAULT_CLIENT
    if _DEFAULT_CLIENT is None or kwargs:
        if kwargs:
            return Addic7edClient(**kwargs)
        _DEFAULT_CLIENT = Addic7edClient()
    return _DEFAULT_CLIENT


def search(show, season=None, episode=None, languages=None, completed_only=True, **kwargs):
    """Search subtitles by show title (+ season/episode) or movie title (JS parity)."""
    return _client(**kwargs).search(
        show, season=season, episode=episode, languages=languages, completed_only=completed_only
    )


def search_by_filename(file_name, **kwargs):
    """Search all subtitles by video file name (Go ``SearchAll`` parity)."""
    return _client(**kwargs).search_by_filename(file_name)


def search_best(file_name, language, **kwargs):
    """Best subtitle for a video file name in a language (Go ``SearchBest`` parity)."""
    return _client(**kwargs).search_best(file_name, language)


def download(subtitle, filename, **kwargs):
    """Download a subtitle object to a file (JS ``download`` parity)."""
    return _client(**kwargs).download_to_file(subtitle, filename)


def download_bytes(subtitle, **kwargs):
    """Download a subtitle object and return the file content as bytes."""
    return _client(**kwargs).download_subtitle(subtitle)


def get_show_titles(**kwargs):
    """List all show titles on the site (JS ``getShowTitles`` parity)."""
    return _client(**kwargs).get_show_titles()
