from paper_downloader.cli import build_parser, console_text, run_search
from paper_downloader.search import PaperResult, SearchBlockedError
from pathlib import Path


def test_download_parser_keeps_one_session_options():
    args = build_parser().parse_args(["download", "papers.txt", "--delay", "7", "--resume"])
    assert args.command == "download"
    assert args.input == Path("papers.txt")
    assert args.delay == 7
    assert args.resume is True


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
