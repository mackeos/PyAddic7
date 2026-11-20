"""Best-version selection: Jaro-Winkler scoring port of matcornic/addic7ed.

``jaro`` and ``jaro_winkler`` are faithful ports of masatana/go-textdistance
(the library the Go upstream uses), and ``score_versions`` / ``pick_best``
reproduce ``scoreBestSubVersions`` and ``findBestSubtitleFromScores`` from
``addic7ed.go``.
"""

import math
from typing import Dict, List

from .models import Subtitle

_WEIGHT_WHEN_EXACT_MATCH = 10.0


def _min(a: int, b: int) -> int:
    return a if a < b else b


def _max(a: int, b: int) -> int:
    return a if a > b else b


def jaro(s1: str, s2: str) -> float:
    """Jaro distance between two strings (returns a similarity in [0, 1]).

    Direct port of ``textdistance.JaroDistance`` from go-textdistance, which
    also returns the common-prefix length used by the Winkler step; this
    function only returns the similarity.
    """
    similarity, _prefix = jaro_with_prefix(s1, s2)
    return similarity


def jaro_with_prefix(s1: str, s2: str):
    """Return ``(jaro_similarity, common_prefix_length)``.

    Port of go-textdistance's ``JaroDistance`` (Lucene-influenced variant).
    """
    if s1 == s2:
        return 1.0, 0
    longer, shorter = list(s1), list(s2)
    if len(longer) < len(shorter):
        longer, shorter = shorter, longer
    scope = int(math.floor(len(longer) / 2)) - 1
    m = 0
    match_flags = [False] * len(longer)
    match_indexes = [-1] * len(shorter)

    for i in range(len(shorter)):
        k = _min(i + scope + 1, len(longer))
        for j in range(_max(i - scope, 0), k):
            if match_flags[j] or shorter[i] != longer[j]:
                continue
            match_indexes[i] = j
            match_flags[j] = True
            m += 1
            break

    ms1 = [shorter[i] for i in range(len(shorter)) if match_indexes[i] != -1]
    ms2 = [longer[i] for i in range(len(longer)) if match_flags[i]]

    t = 0
    for i, c in enumerate(ms1):
        if c != ms2[i]:
            t += 1

    prefix = 0
    for i in range(len(shorter)):
        if longer[i] == shorter[i]:
            prefix += 1
        else:
            break

    if m == 0:
        return 0.0, 0
    newt = t / 2.0
    newm = float(m)
    similarity = (1.0 / 3.0) * (
        newm / len(shorter) + newm / len(longer) + (newm - newt) / newm
    )
    return similarity, prefix


def jaro_winkler(s1: str, s2: str) -> float:
    """Jaro-Winkler distance: threshold 0.7, prefix capped at 4, scale 0.1.

    Direct port of go-textdistance's ``JaroWinklerDistance``.
    """
    threshold = 0.7
    similarity, prefix = jaro_with_prefix(s1, s2)
    if similarity < threshold:
        return similarity
    return similarity + (_min(prefix, 4) * 0.1 * (1.0 - similarity))


def words_from_string(s: str) -> List[str]:
    """Split a string on every non-alphanumeric character (port of ``wordsFromString``)."""
    words = []
    current = []
    for ch in s:
        if ch.isalnum():
            current.append(ch)
        elif current:
            words.append("".join(current))
            current = []
    if current:
        words.append("".join(current))
    return words


def score_versions(
    file_name: str,
    subtitles_by_version: Dict[str, List[Subtitle]],
    verbose: bool = False,
) -> Dict[str, float]:
    """Score every version against the video file name.

    Port of ``scoreBestSubVersions``: common words between the file name and
    the version name raise the score, weighted exact matches (similarity >
    0.9) dominate.
    """
    words_from_title = words_from_string(file_name)
    scores: Dict[str, float] = {}
    for version, _subs in subtitles_by_version.items():
        version_words = words_from_string(version)
        exact_matches = 0.0
        similarity_score = 0.0
        for word_from_title in words_from_title:
            for word_from_version in version_words:
                distance = jaro_winkler(word_from_version.lower(), word_from_title.lower())
                if distance > 0.9:
                    exact_matches += distance
                similarity_score += distance
                if verbose:
                    print(
                        "--- Comparison: {} (version '{}' compared to '{}') - "
                        "exact-matches={} => distance={}".format(
                            version, word_from_version, word_from_title, exact_matches, distance
                        )
                    )
        cardinality = float(len(version_words) * len(words_from_title))
        computed_similarity = similarity_score / cardinality if cardinality else 0.0
        proportion_exact = exact_matches / len(version_words) if version_words else 0.0
        exact_match_score = proportion_exact * (exact_matches * _WEIGHT_WHEN_EXACT_MATCH)
        scores[version] = computed_similarity + exact_match_score
        if verbose:
            print(
                "===> TOTAL SCORE file={} version={} = similarity({}) + exact-match({}) = {}".format(
                    file_name, version, computed_similarity, exact_match_score, scores[version]
                )
            )
    return scores


def pick_best_subtitle(
    scores: Dict[str, float],
    subtitles_by_version: Dict[str, List[Subtitle]],
) -> Subtitle:
    """Pick the best subtitle from the version scores.

    Port of ``findBestSubtitleFromScores``: highest score wins; inside the
    winning version an updated subtitle is preferred, otherwise the last one.
    Ties resolve to the first version in insertion order (deterministic, the
    Go map iteration is not).
    """
    best_version = ""
    best_score = -1.0
    for version, score in scores.items():
        if score > best_score:
            best_version = version
            best_score = score
    if best_version == "":
        # Nothing scored above 0: fall back to the first version, like Go.
        for version in subtitles_by_version:
            best_version = version
            break
    best_subs = subtitles_by_version.get(best_version, [])
    best_sub = best_subs[-1] if best_subs else None
    for sub in best_subs:
        if sub.is_updated:
            best_sub = sub
            break
    return best_sub
