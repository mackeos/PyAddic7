"""Command line interface for PyAddic7.

Designed so other programs (e.g. an mpv Lua script through ``subprocess``)
can consume results: every command accepts ``--json`` and uses stable exit
codes (0 success, 1 nothing found, 2 error).
"""

import argparse
import json
import sys
from typing import List, Optional

from .client import Addic7edClient, resolve_language
from .exceptions import Addic7edError, NoSubtitleFoundError, ShowNotFoundError

EXIT_OK = 0
EXIT_NOT_FOUND = 1
EXIT_ERROR = 2


def _make_client(args: argparse.Namespace) -> Addic7edClient:
    return Addic7edClient(
        base_url=args.base_url,
        user_agent=args.user_agent,
        timeout=args.timeout,
        max_retries=args.retries,
        verbose=args.verbose,
    )


def _emit(data, as_json: bool, human: str) -> None:
    if as_json:
        json.dump(data, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
    else:
        print(human)


def _print_subtitles_table(subtitles) -> None:
    headers = ["version", "language", "lang", "distribution", "team", "downloads", "hi", "completed", "link"]
    rows = [
        [
            s.version,
            s.language,
            s.lang_id,
            s.distribution,
            s.team,
            str(s.downloads if s.downloads is not None else "-"),
            "yes" if s.hearing_impaired else "-",
            ("yes" if s.completed else "{}%".format(s.completed_pct if s.completed_pct is not None else "?")),
            s.link,
        ]
        for s in subtitles
    ]
    widths = [
        max(len(h), *(len(r[i]) for r in rows)) if rows else len(h)
        for i, h in enumerate(headers)
    ]
    line = "  ".join(h.ljust(w) for h, w in zip(headers, widths))
    print(line)
    print("  ".join("-" * w for w in widths))
    for row in rows:
        print("  ".join(c.ljust(w) for c, w in zip(row, widths)))


def cmd_titles(args: argparse.Namespace, client: Addic7edClient) -> int:
    titles = client.get_show_titles()
    _emit(titles, args.json, "{} shows:\n{}".format(len(titles), "\n".join(titles)))
    if not titles:
        return EXIT_NOT_FOUND
    return EXIT_OK


def cmd_search(args: argparse.Namespace, client: Addic7edClient) -> int:
    languages = [code.strip() for code in args.languages.split(",")] if args.languages else None
    subtitles = client.search(
        args.show,
        season=args.season,
        episode=args.episode,
        languages=languages,
        completed_only=not args.include_incomplete,
    )
    payload = [s.to_dict() for s in subtitles]
    _emit(
        payload,
        args.json,
        "{} subtitle(s):\n".format(len(subtitles)),
    )
    if not args.json and subtitles:
        _print_subtitles_table(subtitles)
    if not subtitles:
        return EXIT_NOT_FOUND
    return EXIT_OK


def cmd_filename(args: argparse.Namespace, client: Addic7edClient) -> int:
    show = client.search_by_filename(args.file)
    payload = show.to_dict()
    _emit(
        payload,
        args.json,
        "{}\n{} subtitle(s):\n".format(show.name, len(show.subtitles)),
    )
    if not args.json:
        _print_subtitles_table(show.subtitles)
    if not show.subtitles:
        return EXIT_NOT_FOUND
    return EXIT_OK


def cmd_best(args: argparse.Namespace, client: Addic7edClient) -> int:
    language = resolve_language(args.language)
    show_name, subtitle = client.search_best(args.file, language)
    if args.output:
        client.download_to_file(subtitle, args.output)
    payload = subtitle.to_dict()
    payload["show"] = show_name
    payload["output"] = args.output
    human = "{} - {} ({}, {})".format(show_name, subtitle.version, subtitle.language, subtitle.distribution)
    if args.output:
        human += " -> {}".format(args.output)
    _emit(payload, args.json, human)
    return EXIT_OK


def cmd_download(args: argparse.Namespace, client: Addic7edClient) -> int:
    from .models import Subtitle

    link = args.link
    subtitle = Subtitle(version="cli", language="", link=link, referer=args.referer)
    if args.output:
        client.download_to_file(subtitle, args.output)
        payload = {"output": args.output, "link": link}
        _emit(payload, args.json, "Downloaded {} -> {}".format(link, args.output))
        return EXIT_OK
    data = client.download_subtitle(subtitle)
    if args.json:
        json.dump({"link": link, "bytes": len(data)}, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        sys.stdout.buffer.write(data)
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="addic7ed",
        description="Search and download subtitles from addic7ed.com",
    )
    parser.add_argument("--base-url", default=None, help="Alternative addic7ed base URL")
    parser.add_argument("--user-agent", default=None, help="Override the browser User-Agent")
    parser.add_argument("--timeout", type=float, default=20.0, help="HTTP timeout in seconds (default 20)")
    parser.add_argument("--retries", type=int, default=2, help="Retry attempts on network errors (default 2)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging to stdout")

    sub = parser.add_subparsers(dest="command", metavar="COMMAND")

    p_titles = sub.add_parser("titles", help="List all show titles")
    p_titles.add_argument("--json", action="store_true", help="Output JSON")
    p_titles.set_defaults(func=cmd_titles)

    p_search = sub.add_parser("search", help="Search by show title (+season/episode or movie)")
    p_search.add_argument("show", help="Show or movie title")
    p_search.add_argument("-s", "--season", type=int, default=None, help="Season number")
    p_search.add_argument("-e", "--episode", type=int, default=None, help="Episode number")
    p_search.add_argument("-l", "--languages", default=None, help="Comma-separated ISO 639-2/B codes (e.g. eng,fre)")
    p_search.add_argument("--include-incomplete", action="store_true", help="Include unfinished translations")
    p_search.add_argument("--json", action="store_true", help="Output JSON")
    p_search.set_defaults(func=cmd_search)

    p_file = sub.add_parser("filename", help="Search by video file name (all subtitles)")
    p_file.add_argument("file", help="Video file name, e.g. Show.S01E01.720p.x264-GRP")
    p_file.add_argument("--json", action="store_true", help="Output JSON")
    p_file.set_defaults(func=cmd_filename)

    p_best = sub.add_parser("best", help="Best subtitle for a video file name, optionally download it")
    p_best.add_argument("file", help="Video file name, e.g. Show.S01E01.720p.x264-GRP")
    p_best.add_argument("-l", "--language", required=True, help="Language name (English) or ISO code (eng)")
    p_best.add_argument("-o", "--output", default=None, help="Download the subtitle to this path")
    p_best.add_argument("--json", action="store_true", help="Output JSON")
    p_best.set_defaults(func=cmd_best)

    p_dl = sub.add_parser("download", help="Download a subtitle by link or path")
    p_dl.add_argument("link", help="Download link, e.g. /original/173311/1")
    p_dl.add_argument("-o", "--output", default=None, help="Write to this path (default: stdout)")
    p_dl.add_argument("--referer", default="/show/1", help="Referer path (default /show/1)")
    p_dl.add_argument("--json", action="store_true", help="Output JSON")
    p_dl.set_defaults(func=cmd_download)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.base_url is None:
        args.base_url = "https://www.addic7ed.com"
    if args.user_agent is None:
        from .client import DEFAULT_USER_AGENT

        args.user_agent = DEFAULT_USER_AGENT
    if not getattr(args, "func", None):
        parser.print_help()
        return EXIT_ERROR

    client = _make_client(args)
    try:
        return args.func(args, client)
    except (ShowNotFoundError, NoSubtitleFoundError) as exc:
        print("Not found: {}".format(exc), file=sys.stderr)
        return EXIT_NOT_FOUND
    except Addic7edError as exc:
        print("Error: {}".format(exc), file=sys.stderr)
        return EXIT_ERROR
    except KeyboardInterrupt:
        return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
