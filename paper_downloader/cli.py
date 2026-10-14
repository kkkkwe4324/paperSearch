import argparse
import random
import sys
from pathlib import Path

from .downloader import download_batch
from .search import SearchBlockedError, cache_key, ensure_chrome_cdp, fetch_scholar_pages, fetch_scholar_pages_browser, fetch_scholar_pages_cdp, read_cached_results, write_results
from .session import cdp_endpoint, open_context
from .policy import validate_range


def console_text(value: str) -> str:
    text = str(value).replace("\xa0", " ")
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    return text.encode(encoding, errors="replace").decode(encoding)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="paper-downloader")
    sub = parser.add_subparsers(dest="command", required=True)

    login = sub.add_parser("login", help="Manually authenticate once in a persistent browser")
    login.add_argument("--data-dir", type=Path, default=Path.home() / ".paper-downloader")
    login.add_argument("--cdp-port", type=int, default=9222)

    download = sub.add_parser("download", help="Download authorized IEEE/ACM/ScienceDirect PDFs")
    download.add_argument("input", type=Path)
    download.add_argument("--output", type=Path, default=Path("downloads"))
    download.add_argument("--data-dir", type=Path, default=Path.home() / ".paper-downloader")
    download.add_argument("--delay", type=float, help=argparse.SUPPRESS)
    download.add_argument("--min-delay", type=float, default=15.0)
    download.add_argument("--max-delay", type=float, default=30.0)
    download.add_argument("--retry-count", type=int, default=3)
    download.add_argument("--resume", action="store_true")
    download.add_argument("--cdp", action="store_true", help="Connect to an already logged-in Chrome")
    download.add_argument("--cdp-port", type=int, default=9222)

    search = sub.add_parser("search", help="Search Google Scholar conservatively")
    search.add_argument("query")
    search.add_argument("--pages", type=int, default=3)
    search.add_argument("--page-size", type=int, default=10)
    search.add_argument("--min-delay", type=float, default=20.0)
    search.add_argument("--max-delay", type=float, default=40.0)
    search.add_argument("--results-dir", type=Path, default=Path("results"))
    search.add_argument("--data-dir", type=Path, default=Path.home() / ".paper-downloader")
    search.add_argument("--refresh", action="store_true", help="Ignore the local cache")
    search.add_argument("--browser", action="store_true", help="Use a persistent visible Scholar browser")
    search.add_argument("--cdp", action="store_true", help="Attach to a manually started Chrome via CDP")
    search.add_argument("--cdp-port", type=int, default=9222)
    return parser


def _require_playwright():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise SystemExit("Playwright is required: python -m pip install -r requirements.txt && playwright install chromium") from exc
    return sync_playwright


def run_login(data_dir: Path, *, cdp_port: int = 9222) -> int:
    sync_playwright = _require_playwright()
    data_dir.mkdir(parents=True, exist_ok=True)
    ensure_chrome_cdp(data_dir, cdp_port)
    with sync_playwright() as playwright:
        browser = playwright.chromium.connect_over_cdp(cdp_endpoint(cdp_port))
        if not browser.contexts:
            raise SystemExit("CDP Chrome has no browser context")
        context = browser.contexts[0]
        page = context.pages[0] if context.pages else context.new_page()
        page.goto("https://ieeexplore.ieee.org", wait_until="domcontentloaded", timeout=60_000)
        print("请在打开的浏览器中完成 IEEE 南科大 SSO/CARSI、验证码和 MFA。完成后回到终端按 Enter。")
        input()
        acm_page = context.new_page()
        acm_page.goto("https://dl.acm.org", wait_until="domcontentloaded", timeout=60_000)
        print("请在打开的浏览器中完成 ACM 南科大 SSO/CARSI、验证码和 MFA。完成后回到终端按 Enter。")
        input()
        sciencedirect_page = context.new_page()
        sciencedirect_page.goto("https://www.sciencedirect.com", wait_until="domcontentloaded", timeout=60_000)
        print("请在打开的浏览器中完成 ScienceDirect 南科大机构登录、验证码和 MFA。完成后回到终端按 Enter。")
        input()
    return 0


def run_download(args) -> int:
    sync_playwright = _require_playwright()
    with sync_playwright() as playwright:
        browser = None
        if args.cdp:
            browser = playwright.chromium.connect_over_cdp(cdp_endpoint(args.cdp_port))
            if not browser.contexts:
                raise SystemExit("CDP Chrome has no browser context")
            context = browser.contexts[0]
        else:
            context = open_context(playwright, args.data_dir, headless=False)
        page = context.pages[0] if context.pages else context.new_page()
        counts = download_batch(
            page,
            args.input,
            args.output,
            args.output / "download-state.jsonl",
            delay=args.delay if args.delay is not None else args.min_delay,
            max_delay=args.max_delay,
            retry_count=args.retry_count,
            resume=args.resume,
        )
        if browser is None:
            context.close()
    print("下载结果:", ", ".join(f"{key}={value}" for key, value in counts.items()))
    return 1 if counts["failed"] or counts["auth_required"] or counts["rate_limited"] else 0


def run_search(args) -> int:
    stem = cache_key(args.query, args.pages, args.page_size)
    cached_path = args.results_dir / f"{stem}.jsonl"
    if cached_path.exists() and not args.refresh:
        results = read_cached_results(cached_path)
        pages = [results[offset:offset + args.page_size] for offset in range(0, len(results), args.page_size)]
        print(f"使用本地缓存: {cached_path}")
    else:
        pages = None
    try:
        if pages is None:
            if args.cdp:
                pages = fetch_scholar_pages_cdp(
                    args.query, args.pages, args.page_size, port=args.cdp_port,
                    min_delay=args.min_delay, max_delay=args.max_delay,
                )
            elif args.browser:
                ensure_chrome_cdp(args.data_dir, args.cdp_port)
                pages = fetch_scholar_pages_cdp(
                    args.query, args.pages, args.page_size, port=args.cdp_port,
                    min_delay=args.min_delay, max_delay=args.max_delay,
                    wait_for_verification=False,
                )
            else:
                pages = fetch_scholar_pages(args.query, args.pages, args.page_size, min_delay=args.min_delay, max_delay=args.max_delay)
    except SearchBlockedError as exc:
        pages = exc.partial_pages
        if pages:
            results = [item for page in pages for item in page]
            jsonl_path, csv_path = write_results(results, args.results_dir, stem)
            print(f"Google Scholar search stopped: {exc}")
            print(f"Saved partial results: {jsonl_path} and {csv_path}")
            return 1
        print(f"Google Scholar search stopped: {exc}")
        return 1
    except Exception as exc:
        print(f"Google Scholar search stopped: {exc}")
        return 1
    results = [item for page in pages for item in page]
    jsonl_path, csv_path = write_results(results, args.results_dir, stem)
    for number, page in enumerate(pages, 1):
        print(f"\n第 {number} 页 ({len(page)} 条)")
        for offset, item in enumerate(page, 1):
            abstract = item.abstract or item.snippet or "(无摘要)"
            print(f"{(number - 1) * args.page_size + offset}. {console_text(item.title)} [{console_text(item.year)}] citations={item.citation_count}")
            print(f"   作者: {console_text(item.authors)}")
            print(f"   会议/期刊: {console_text(item.venue or '(未知)')}")
            print(f"   摘要: {console_text(abstract[:400])}")
            if item.doi:
                print(f"   DOI: {console_text(item.doi)} provider={console_text(item.provider or 'unknown')}")
    print(f"\n已保存: {jsonl_path} 和 {csv_path}")
    return 0


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if not 1 <= getattr(args, "cdp_port", 9222) <= 65535:
            raise ValueError("CDP port must be between 1 and 65535")
        if args.command == "search":
            if not 1 <= args.pages <= 5:
                raise ValueError("pages must be between 1 and 5")
            if not (20 <= args.min_delay <= 40 and 20 <= args.max_delay <= 40):
                raise ValueError("Scholar delays must be between 20 and 40 seconds")
            validate_range(args.min_delay, args.max_delay, "Scholar delay")
        elif args.command == "download":
            if args.delay is not None and args.delay < 15:
                raise ValueError("download delay must be at least 15 seconds")
            if not (15 <= args.min_delay <= 30 and 15 <= args.max_delay <= 30):
                raise ValueError("download delays must be between 15 and 30 seconds")
            validate_range(args.min_delay, args.max_delay, "download delay")
            if not 1 <= args.retry_count <= 3:
                raise ValueError("retry count must be between 1 and 3")
    except ValueError as exc:
        parser.error(str(exc))
    if args.command == "login":
        return run_login(args.data_dir, cdp_port=args.cdp_port)
    if args.command == "search":
        return run_search(args)
    return run_download(args)
