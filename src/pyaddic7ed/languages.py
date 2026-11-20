"""ISO 639-2/B language codes for the languages used on addic7ed.com.

The JavaScript upstream (same31/addic7ed-api) converts the language name shown
on the site into an ISO 639-2/B code with the ``langs`` npm package, stripping
parenthesised qualifiers first (``Portuguese (Brazilian)`` -> ``Portuguese``),
and falls back to the first three characters of the name lowercased.

This module reproduces that behaviour with a hard-coded table of the names
addic7ed.com actually uses, so no extra dependency is needed.
"""

import re
from typing import Dict

# Language name (as shown on addic7ed.com, case-insensitive) -> ISO 639-2/B.
# Parenthesised qualifiers are stripped before lookup, so "Portuguese
# (Brazilian)" and "Spanish (Latino)" resolve through their base entries.
_ISO_639_2B: Dict[str, str] = {
    "albanian": "alb",
    "arabic": "ara",
    "armenian": "hye",
    "azerbaijani": "aze",
    "basque": "baq",
    "belarusian": "bel",
    "bengali": "ben",
    "bosnian": "bos",
    "bulgarian": "bul",
    "catalan": "cat",
    "chinese": "chi",
    "croatian": "hrv",
    "czech": "ces",
    "danish": "dan",
    "dutch": "dut",
    "english": "eng",
    "esperanto": "epo",
    "estonian": "est",
    "finnish": "fin",
    "french": "fre",
    "galician": "glg",
    "german": "ger",
    "greek": "gre",
    "hebrew": "heb",
    "hindi": "hin",
    "hungarian": "hun",
    "icelandic": "ice",
    "indonesian": "ind",
    "irish": "gle",
    "italian": "ita",
    "japanese": "jpn",
    "korean": "kor",
    "latvian": "lav",
    "lithuanian": "lit",
    "macedonian": "mac",
    "malay": "msa",
    "norwegian": "nor",
    "persian": "per",
    "farsi": "per",
    "polish": "pol",
    "portuguese": "por",
    "romanian": "rum",
    "russian": "rus",
    "serbian": "srp",
    "slovak": "slo",
    "slovenian": "slv",
    "spanish": "spa",
    "swedish": "swe",
    "thai": "tha",
    "turkish": "tur",
    "ukrainian": "ukr",
    "vietnamese": "vie",
}

_STRIP_PARENS = re.compile(r"\(.+\)")


def lang_to_iso639_2b(name: str) -> str:
    """Convert an addic7ed language name to an ISO 639-2/B code.

    Falls back to the first three characters of the name lowercased, exactly
    like the JavaScript upstream does when the ``langs`` lookup fails.
    """
    cleaned = _STRIP_PARENS.sub("", name).strip()
    code = _ISO_639_2B.get(cleaned.lower())
    if code:
        return code
    return name[:3].lower()


def iso639_2b_to_names(code: str) -> list:
    """Reverse lookup: ISO 639-2/B code -> list of addic7ed language names."""
    code = code.strip().lower()
    return [k.capitalize() for k, v in _ISO_639_2B.items() if v == code]
