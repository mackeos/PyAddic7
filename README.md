# pyaddic7ed

Python API to search and download subtitles from [addic7ed.com](https://www.addic7ed.com).

`pyaddic7ed` is a full-featured Python port of the two main upstream libraries:

| Upstream | Language | What it contributed |
| --- | --- | --- |
| [matcornic/addic7ed](https://github.com/matcornic/addic7ed) | Go | search by video file name, best-version selection via Jaro-Winkler scoring, filters and grouping, `is_updated`/`is_original` |
| [same31/addic7ed-api](https://github.com/same31/addic7ed-api) | JavaScript | search by show + season + episode (TV **and** movies), completed-only filter, ISO 639-2/B language codes, hearing-impaired/corrected/download-count metadata, distribution + team extraction, `get_show_titles`, encoding fallback |

It ships both a Python library and a CLI (`addic7ed`) with JSON output, designed so an
[mpv](https://mpv.io) Lua script (or any other program) can call it via `subprocess`.

As addic7ed.com does not provide an official API, this package scrapes the public
HTML pages and is **not affiliated with addic7ed.com**. Use it respectfully.

## Features

- Two search modes:
  - by **show/season/episode** or **movie title** (same31/addic7ed-api style)
  - by **video file name** (matcornic/addic7ed style), following the first search hit
- `search_best()` picks the release version that best matches your file name
  (Jaro-Winkler word scoring, a faithful port of the Go implementation)
- Rich `Subtitle` metadata: version, language + ISO 639-2/B code, distribution
  (HDTV / WEB-DL / BLURAY), release team, hearing impaired, corrected, completed
  percentage, download count, times edited, uploader, updated flag
- Filters and grouping: `with_language`, `with_version`, `with_version_regexp`,
  `group_by_version`, `group_by_language`
- `get_show_titles()` lists every show on the site
- Correct download handling for the current site markup (`/original/<id>/<n>`
  and `/updated/<id>/<n>` links) with the required `Referer` header, redirect
  detection, and utf-8 / latin-1 encoding fallback
- Sync API on `requests` (thread-safe client), Python 3.9+
- CLI with `--json` on every command and stable exit codes for scripting

## Installation

```bash
pip install pyaddic7ed
```

Requires Python 3.9+ and only `requests` + `beautifulsoup4`.

## Library usage

### Search by show, season and episode (TV or movie)

```python
from pyaddic7ed import search, download

# TV show (season/episode are optional)
subs = search("South Park", season=25, episode=4)          # completed subs only
subs = search("South Park", season=25, episode=4,
              languages=["eng", "fre"])                     # ISO 639-2/B filter
subs = search("South Park", season=25, episode=4,
              completed_only=False)                          # include incomplete
subs = search("Deadpool 2016")                              # movie

if subs:
    sub = subs[0]
    print(sub.version, sub.language, sub.lang_id, sub.downloads)
    download(sub, "South.Park.S25E04.srt")
```

### Search by video file name

```python
from pyaddic7ed import search_by_filename

show = search_by_filename("South.Park.S25E04.720p.WEB.h264-BAE")
print(show.name)          # "South Park - 25x04 - Back to the Cold War"
for sub in show.subtitles:
    print(sub.version, sub.language, sub.is_updated)
```

### Best subtitle for a file name

```python
from pyaddic7ed import search_best

show_name, sub = search_best("South.Park.S25E04.720p.WEB.h264-BAE", "English")
print(show_name, sub.version)
sub.download_to("South.Park.S25E04.srt")     # needs the default client
```

or with one client instance (recommended: reuses the connection):

```python
from pyaddic7ed import Addic7edClient

client = Addic7edClient(verbose=True)
show_name, sub = client.search_best("South.Park.S25E04.720p.WEB.h264-BAE", "English")
client.download_to_file(sub, "South.Park.S25E04.srt")

# in-memory download
data = client.download_subtitle(sub)
```

### Filters and grouping

```python
from pyaddic7ed import search_by_filename, with_language, with_version_regexp
from pyaddic7ed import filter_subtitles, group_by_version

show = search_by_filename("Dark.S01E05.720p.WEBRip.x264-STRiFE")

english = filter_subtitles(show.subtitles, with_language("English"))
killers = filter_subtitles(show.subtitles, with_version_regexp(r"STRiFE"))
by_version = group_by_version(show.subtitles)
```

### Show titles

```python
from pyaddic7ed import get_show_titles

titles = get_show_titles()
assert "South Park" in titles
```

### Subtitle properties

| Property | Meaning |
| --- | --- |
| `version` | release version as shown on the site (e.g. `WEB.BAE`, `BATV`) |
| `language` | language name as shown on the site (e.g. `English`) |
| `lang_id` | ISO 639-2/B code (e.g. `eng`), JS-lib compatible |
| `link` | download path (`/original/173311/1`, `/updated/...`) |
| `url` | absolute download URL |
| `referer` | show page path to send as `Referer` when downloading |
| `distribution` | `HDTV`, `WEB-DL`, `BLURAY` or `UNKNOWN`, extracted from version |
| `team` | release team (e.g. `KILLERS`), extracted from version |
| `hearing_impaired` / `corrected` | flags from the site icons |
| `completed` / `completed_pct` | completion state and percentage |
| `downloads`, `times_edited` | site counters |
| `is_updated` / `is_original` | whether the link is an `/updated/` re-upload |
| `show_title`, `episode_title` | parsed from the page title |
| `uploader` | who uploaded the subtitle |

## CLI usage

```
addic7ed titles [--json]
addic7ed search SHOW [-s SEASON] [-e EPISODE] [-l eng,fre] [--include-incomplete] [--json]
addic7ed filename FILE [--json]
addic7ed best FILE -l English|eng [-o out.srt] [--json]
addic7ed download LINK [-o out.srt] [--json]
```

Global options: `--base-url`, `--user-agent`, `--timeout`, `--retries`, `-v/--verbose`.

Examples:

```bash
addic7ed best "South.Park.S25E04.720p.WEB.h264-BAE" -l eng -o South.Park.S25E04.srt
addic7ed search "South Park" -s 25 -e 4 --json
addic7ed filename "Dark.S01E05.720p.WEBRip.x264-STRiFE" --json
addic7ed download /original/173311/1 -o sub.srt
addic7ed titles | head -5
```

Exit codes: `0` success, `1` nothing found, `2` error (network/parsing/download or bad usage).

## Using it from mpv

The CLI is designed for `subprocess` calls from a Lua script:

```lua
-- inside an mpv Lua script: download an English sub for the current file
local path = mp.get_property("path")
local out  = mp.command_native({"expand-path", "~/.config/mpv/subs.srt"})
local args = { "addic7ed", "best", path, "-l", "eng", "-o", out, "--json" }
mp.command_native_async({
    name = "subprocess",
    playback_only = false,
    capture_stdout = true,
    args = args,
}, function(ok, res)
    if ok and res.status == 0 then
        mp.commandv("sub-add", out, "auto")
    end
end)
```

## Development and testing

```bash
git clone <your fork> && cd pyaddic7ed
pip install -e ".[dev]"

pytest -m "not live"   # offline tests (saved HTML fixtures, no network)
pytest -m live         # real addic7ed.com integration tests
pytest                 # everything
```

The offline tests parse snapshots of real pages saved in `tests/fixtures/`, so
the parser can be regression-tested without network access. Live tests search
real episodes and download one real subtitle file.

## Publishing

```bash
python -m build
python -m twine check dist/*
python -m twine upload dist/*
```

## License and credits

MIT - see [LICENSE](LICENSE). This is a port of, and stands on the shoulders of:

- [matcornic/addic7ed](https://github.com/matcornic/addic7ed) by Mathieu Cornic
- [same31/addic7ed-api](https://github.com/same31/addic7ed-api) by Matthieu Mitrani

Not affiliated with, endorsed by, or connected to addic7ed.com in any way.
