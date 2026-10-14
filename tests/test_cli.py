import pytest

from paper_downloader.cli import build_parser, console_text, main, run_login, run_search
from paper_downloader.search import PaperResult, SearchBlockedError
from pathlib import Path


def test_download_parser_keeps_one_session_options():
    args = build_parser().parse_args(["download", "papers.txt", "--delay", "7", "--resume"])
    assert args.command == "download"
    assert args.input == Path("papers.txt")
    assert args.delay == 7
    assert args.resume is True


def test_conservative_defaults_limit_scholar_and_download_rate():
    parser = build_parser()
    search = parser.parse_args(["search", "microgrid"])
    download = parser.parse_args(["download", "papers.txt"])

    assert (search.pages, search.min_delay, search.max_delay) == (3, 20.0, 40.0)
    assert (download.min_delay, download.max_delay, download.retry_count) == (15.0, 30.0, 3)


@pytest.mark.parametrize("argv", [
    ["search", "microgrid", "--pages", "0"],
    ["search", "microgrid", "--pages", "6"],
    ["search", "microgrid", "--min-delay", "41"],
    ["search", "microgrid", "--min-delay", "30", "--max-delay", "20"],
    ["download", "papers.txt", "--min-delay", "14"],
    ["download", "papers.txt", "--retry-count", "4"],
])
def test_main_rejects_unsafe_rate_settings_before_starting_browser(argv, monkeypatch):
    monkeypatch.setattr("paper_downloader.cli.run_search", lambda args: (_ for _ in ()).throw(AssertionError("browser started")))
    monkeypatch.setattr("paper_downloader.cli.run_download", lambda args: (_ for _ in ()).throw(AssertionError("browser started")))

    with pytest.raises(SystemExit) as error:
        main(argv)

    assert error.value.code == 2


def test_login_opens_publishers_for_separate_manual_confirmation(monkeypatch, tmp_path):
    visited = []

    class Page:
        def goto(self, url, **kwargs):
            visited.append(url)

    class Context:
        pages = [Page()]

        def new_page(self):
            return Page()

    class Browser:
        contexts = [Context()]

    class Chromium:
        def connect_over_cdp(self, endpoint):
            assert endpoint == "http://127.0.0.1:9333"
            return Browser()

    class Playwright:
        chromium = Chromium()

    class Manager:
        def __enter__(self):
            return Playwright()

        def __exit__(self, *args):
            return None

    monkeypatch.setattr("paper_downloader.cli.ensure_chrome_cdp", lambda *args: None)
    monkeypatch.setattr("paper_downloader.cli._require_playwright", lambda: Manager)
    monkeypatch.setattr("builtins.input", lambda: "")

    assert run_login(tmp_path, cdp_port=9333) == 0
    assert visited == ["https://ieeexplore.ieee.org", "https://dl.acm.org", "https://www.sciencedirect.com"]


def test_search_parser_accepts_paging_options():
    args = build_parser().parse_args(["search", "microgrid", "--pages", "3", "--page-size", "10", "--refresh"])
    assert args.command == "search"
    assert args.pages == 3
    assert args.page_size == 10
    assert args.refresh is True


def test_search_parser_accepts_cdp_mode():
    args = build_parser().parse_args(["search", "microgrid", "--cdp", "--cdp-port", "9333"])
    assert args.cdp is True
    assert args.cdp_port == 9333


def test_console_text_is_safe_for_windows_legacy_encoding(monkeypatch):
    class LegacyStdout:
        encoding = "gbk"

    monkeypatch.setattr("paper_downloader.cli.sys.stdout", LegacyStdout())
    assert console_text("venue\xa0name") == "venue name"
    assert "\u2020" not in console_text("summary \u2020")


def test_search_saves_partial_pages_when_scholar_blocks(monkeypatch, tmp_path, capsys):
    partial = [[PaperResult(title="Already found", year="2026")]]

    def blocked(*args, **kwargs):
        raise SearchBlockedError("unusual traffic", partial_pages=partial)

    monkeypatch.setattr("paper_downloader.cli.fetch_scholar_pages", blocked)
    args = build_parser().parse_args([
        "search", "example", "--pages", "2", "--results-dir", str(tmp_path), "--refresh"
    ])

    assert run_search(args) == 1
    assert (tmp_path / f"{args.query}").exists() is False
    saved = list(tmp_path.glob("*.jsonl"))
    assert len(saved) == 1
    assert "Already found" in saved[0].read_text(encoding="utf-8")
    assert "partial results" in capsys.readouterr().out


def test_browser_mode_uses_real_chrome_cdp(monkeypatch, tmp_path):
    calls = []

    def start(data_dir, port):
        calls.append(("start", data_dir, port))

    def search(*args, **kwargs):
        calls.append(("search", kwargs["port"], kwargs["wait_for_verification"]))
        return [[PaperResult(title="Found")]]

    monkeypatch.setattr("paper_downloader.cli.ensure_chrome_cdp", start)
    monkeypatch.setattr("paper_downloader.cli.fetch_scholar_pages_cdp", search)
    args = build_parser().parse_args([
        "search", "example", "--browser", "--results-dir", str(tmp_path)
    ])

    assert run_search(args) == 0
    assert calls == [("start", args.data_dir, args.cdp_port), ("search", args.cdp_port, False)]
