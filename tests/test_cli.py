import pytest

from paper_downloader.cli import build_parser, console_text, main, run_download, run_login, run_search
from paper_downloader.search import PaperResult, SearchBlockedError
from pathlib import Path
from paper_downloader.workspace import add_direction, add_idea, init_workspace


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


def test_cdp_download_uses_a_new_page_to_preserve_verified_pdf_tabs(monkeypatch, tmp_path):
    existing = object()
    download_page = object()

    class Context:
        pages = [existing]

        def new_page(self):
            return download_page

    class Browser:
        contexts = [Context()]

    class Chromium:
        def connect_over_cdp(self, endpoint):
            return Browser()

    class Playwright:
        chromium = Chromium()

    class Manager:
        def __enter__(self):
            return Playwright()

        def __exit__(self, *args):
            return None

    observed = []
    monkeypatch.setattr("paper_downloader.cli._require_playwright", lambda: Manager)
    monkeypatch.setattr("paper_downloader.cli.download_batch", lambda page, *args, **kwargs: observed.append(page) or {
        "success": 0, "failed": 0, "skipped": 0, "auth_required": 0, "rate_limited": 0, "access_denied": 0
    })
    args = build_parser().parse_args(["download", "papers.txt", "--cdp", "--output", str(tmp_path)])

    assert run_download(args) == 0
    assert observed == [download_page]


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


def test_workspace_commands_create_idea_and_direction(tmp_path):
    assert main(["init", "--workspace", str(tmp_path)]) == 0
    assert main(["add-idea", "idea_a", "--workspace", str(tmp_path)]) == 0
    assert main(["add-direction", "latency", "--idea", "idea_a", "--workspace", str(tmp_path)]) == 0
    assert (tmp_path / "ideas/idea_a/directions/latency/papers.md").exists()


def test_search_routes_into_registered_direction(monkeypatch, tmp_path):
    init_workspace(tmp_path)
    add_idea(tmp_path, "idea_a")
    add_direction(tmp_path, "idea_a", "latency")
    monkeypatch.setattr("paper_downloader.cli.fetch_scholar_pages", lambda *args, **kwargs: [[PaperResult(title="Found")]])

    assert main(["search", "example", "--pages", "1", "--workspace", str(tmp_path), "--idea", "idea_a", "--direction", "latency"]) == 0
    assert len(list((tmp_path / "ideas/idea_a/directions/latency/search_logs/results").glob("*.jsonl"))) == 1


def test_download_parser_respects_explicit_output_with_workspace(tmp_path):
    init_workspace(tmp_path)
    add_idea(tmp_path, "idea_a")
    add_direction(tmp_path, "idea_a", "latency")
    args = build_parser().parse_args(["download", "papers.txt", "--workspace", str(tmp_path), "--idea", "idea_a", "--direction", "latency", "--output", "custom"])
    from paper_downloader.cli import route_workspace_args
    route_workspace_args(args)
    assert args.output == Path("custom")


def test_search_rejects_unknown_direction_before_browser(tmp_path, monkeypatch):
    init_workspace(tmp_path)
    monkeypatch.setattr("paper_downloader.cli.run_search", lambda args: (_ for _ in ()).throw(AssertionError("browser started")))
    with pytest.raises(SystemExit) as error:
        main(["search", "example", "--workspace", str(tmp_path), "--idea", "idea_a", "--direction", "typo"])
    assert error.value.code == 2


def test_add_idea_discovers_workspace_from_nested_folder(tmp_path, monkeypatch):
    init_workspace(tmp_path)
    nested = tmp_path / "demos"
    monkeypatch.chdir(nested)
    assert main(["add-idea", "new_idea"]) == 0
    assert (tmp_path / "ideas/new_idea/README.md").exists()


def test_search_infers_direction_from_current_folder(tmp_path, monkeypatch):
    init_workspace(tmp_path)
    add_idea(tmp_path, "idea_a")
    direction = add_direction(tmp_path, "idea_a", "latency")
    monkeypatch.chdir(direction)
    monkeypatch.setattr("paper_downloader.cli.fetch_scholar_pages", lambda *args, **kwargs: [[PaperResult(title="Found")]])
    assert main(["search", "example", "--pages", "1"]) == 0
    assert len(list((direction / "search_logs/results").glob("*.jsonl"))) == 1


def test_workspace_search_requires_a_direction_at_workspace_root(tmp_path, monkeypatch):
    init_workspace(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("paper_downloader.cli.run_search", lambda args: (_ for _ in ()).throw(AssertionError("browser started")))
    with pytest.raises(SystemExit) as error:
        main(["search", "example", "--pages", "1"])
    assert error.value.code == 2


def test_zotero_cli_plans_and_applies_existing_item(monkeypatch, tmp_path, capsys):
    calls = []

    class Client:
        def collection_paths(self):
            return {"ROOT1234": "10投机解码"}

        def match_item(self, **kwargs):
            calls.append(("match", kwargs))
            return {"key": "PAPER123"}

        def make_plan(self, key, collections, reason):
            return {"schema": 1, "item_key": key, "add_collections": collections, "reason": reason}

        def apply_plan(self, plan):
            calls.append(("apply", plan))
            return {"key": "PAPER123", "collections": ["ROOT1234"]}

    monkeypatch.setattr("paper_downloader.cli.ZoteroClient", Client, raising=False)
    plan = tmp_path / "route.json"
    assert main(["zotero", "collections"]) == 0
    assert "10投机解码" in capsys.readouterr().out
    assert main(["zotero", "plan", "--doi", "10.1145/example.1", "--collection", "ROOT1234", "--reason", "direct method", "--output", str(plan)]) == 0
    assert plan.exists()
    assert main(["zotero", "apply", str(plan)]) == 0
    assert calls[-1][0] == "apply"


def test_zotero_plan_marks_missing_item_pending(monkeypatch, tmp_path, capsys):
    class Client:
        def match_item(self, **kwargs):
            return None

    monkeypatch.setattr("paper_downloader.cli.ZoteroClient", Client, raising=False)
    plan = tmp_path / "route.json"
    assert main(["zotero", "plan", "--doi", "10.1145/missing", "--collection", "ROOT1234", "--reason", "direct", "--output", str(plan)]) == 1
    assert not plan.exists()
    assert "pending Zotero import" in capsys.readouterr().out
