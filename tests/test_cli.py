"""CLI tests: JSON mode, exit codes, output formats. Client is stubbed."""

import json

import pytest

import pyaddic7ed.cli as cli
from pyaddic7ed.models import Show, Subtitle

FAKE_SRT = b"1\n00:00:01,000 --> 00:00:03,000\nHello!\n"


class StubClient:
    def __init__(self):
        self.subs = [
            Subtitle(
                version="WEB.BAE",
                language="English",
                link="/original/173311/1",
                referer="/show/116",
                downloads=1737,
                hearing_impaired=True,
                corrected=True,
                show_title="South Park",
                episode_title="Back to the Cold War",
            ),
            Subtitle(
                version="web-dl",
                language="French",
                link="/original/173311/5",
                referer="/show/116",
                downloads=931,
            ),
        ]

    def get_show_titles(self):
        return ["South Park", "Dark", "Friends"]

    def search(self, show, season=None, episode=None, languages=None, completed_only=True):
        return self.subs

    def search_by_filename(self, file_name):
        return Show(name="South Park - 25x04 - Back to the Cold War", subtitles=self.subs)

    def search_best(self, file_name, language):
        return "South Park - 25x04 - Back to the Cold War", self.subs[0]

    def download_to_file(self, subtitle, path):
        with open(path, "wb") as handle:
            handle.write(FAKE_SRT)

    def download_subtitle(self, subtitle):
        return FAKE_SRT


@pytest.fixture
def stub(monkeypatch):
    client = StubClient()
    monkeypatch.setattr(cli, "_make_client", lambda args: client)
    return client


def run_cli(capsys, *argv):
    code = cli.main(list(argv))
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_titles_json(stub, capsys):
    code, out, _ = run_cli(capsys, "titles", "--json")
    assert code == 0
    data = json.loads(out)
    assert "South Park" in data


def test_titles_human(stub, capsys):
    code, out, _ = run_cli(capsys, "titles")
    assert code == 0
    assert "South Park" in out


def test_search_json(stub, capsys):
    code, out, _ = run_cli(capsys, "search", "South Park", "-s", "25", "-e", "4", "--json")
    assert code == 0
    data = json.loads(out)
    assert isinstance(data, list) and len(data) == 2
    assert data[0]["version"] == "WEB.BAE"
    assert data[0]["lang_id"] == "eng"
    assert data[0]["url"] == "https://www.addic7ed.com/original/173311/1"
    assert data[0]["hearing_impaired"] is True


def test_search_human_table(stub, capsys):
    code, out, _ = run_cli(capsys, "search", "South Park", "-s", "25", "-e", "4")
    assert code == 0
    assert "WEB.BAE" in out
    assert "version" in out  # table header


def test_filename_json(stub, capsys):
    code, out, _ = run_cli(capsys, "filename", "Show.S01E01", "--json")
    assert code == 0
    data = json.loads(out)
    assert data["name"] == "South Park - 25x04 - Back to the Cold War"
    assert len(data["subtitles"]) == 2


def test_best_json_with_download(stub, capsys, tmp_path):
    out_path = str(tmp_path / "out.srt")
    code, out, _ = run_cli(
        capsys, "best", "Show.S01E01", "-l", "eng", "-o", out_path, "--json"
    )
    assert code == 0
    data = json.loads(out)
    assert data["output"] == out_path
    assert data["language"] == "English"
    assert data["show"] == "South Park - 25x04 - Back to the Cold War"
    with open(out_path, "rb") as handle:
        assert handle.read() == FAKE_SRT


def test_best_language_code_resolved(stub, capsys, tmp_path):
    stub.download_to_file_calls = []

    def dl(sub, path):
        stub.download_to_file_calls.append((sub, path))
        with open(path, "wb") as handle:
            handle.write(FAKE_SRT)

    stub.download_to_file = dl
    code, out, _ = run_cli(capsys, "best", "Show.S01E01", "-l", "fre", "-o", str(tmp_path / "x.srt"), "--json")
    assert code == 0


def test_download_stdout(stub, capsys):
    code, out, _ = run_cli(capsys, "download", "/original/1/1")
    assert code == 0
    assert FAKE_SRT.decode() in out


def test_download_json_to_file(stub, capsys, tmp_path):
    out_path = str(tmp_path / "d.srt")
    code, out, _ = run_cli(capsys, "download", "/original/1/1", "-o", out_path, "--json")
    assert code == 0
    data = json.loads(out)
    assert data["output"] == out_path


def test_no_command_shows_help(capsys):
    code, out, _ = run_cli(capsys)
    assert code == cli.EXIT_ERROR
    assert "usage" in out.lower() or "COMMAND" in out


def test_not_found_exit_code(monkeypatch, capsys):
    from pyaddic7ed.exceptions import ShowNotFoundError

    class EmptyClient:
        def get_show_titles(self):
            return []

    monkeypatch.setattr(cli, "_make_client", lambda args: EmptyClient())
    code, out, err = run_cli(capsys, "titles", "--json")
    assert code == cli.EXIT_NOT_FOUND


def test_error_exit_code(monkeypatch, capsys):
    from pyaddic7ed.exceptions import NetworkError

    class BrokenClient:
        def get_show_titles(self):
            raise NetworkError("boom")

    monkeypatch.setattr(cli, "_make_client", lambda args: BrokenClient())
    code, out, err = run_cli(capsys, "titles", "--json")
    assert code == cli.EXIT_ERROR
    assert "boom" in err
