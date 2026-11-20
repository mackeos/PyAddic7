"""Exceptions raised by PyAddic7."""


class Addic7edError(Exception):
    """Base class for all PyAddic7 errors."""


class NetworkError(Addic7edError):
    """The addic7ed.com server could not be reached or answered with an error."""


class ParsingError(Addic7edError):
    """A page could not be parsed; the site markup may have changed."""


class ShowNotFoundError(Addic7edError):
    """No show/episode page matched the search query."""


class NoSubtitleFoundError(Addic7edError):
    """No subtitle matched the search criteria (language, completion, ...)."""


class DownloadError(Addic7edError):
    """The subtitle file could not be downloaded (site returned an HTML page)."""
