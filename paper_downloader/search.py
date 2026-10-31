import csv
import hashlib
import json
import random
import re
import socket
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Iterable

from .providers import provider_for_doi
from .session import chrome_command, profile_path

DOI_RE = re.compile(r"10\.\d{4,9}/[^\s<>\"]+", re.IGNORECASE)
FIELDS = ["title", "authors", "year", "venue", "doi", "abstract", "snippet", "citation_count", "pdf_url", "provider", "source"]


@dataclass
class PaperResult:
    title: str = ""
    authors: str = ""
    year: str = ""
    venue: str = ""
    doi: str = ""
    abstract: str = ""
    snippet: str = ""
    citation_count: int = 0
    pdf_url: str = ""
    provider: str = ""
    source: str = "google-scholar"


def parse_scholar_meta(value: str) -> tuple[str, str, str]:
    parts = [part.strip() for part in value.split(" - ")]
    authors = parts[0] if parts else ""
    year_match = re.search(r"\b(19|20)\d{2}\b", value)
    year = year_match.group(0) if year_match else ""
    venue = ""
    if len(parts) > 1:
        venue = re.sub(r",?\s*(19|20)\d{2}\b.*$", "", parts[1]).strip(" ,")
    return authors, venue, year


def normalize_result(raw: dict) -> PaperResult:
    bib = raw.get("bib", {})
    authors = bib.get("author", "")
    if isinstance(authors, list):
        authors = ", ".join(authors)
    links = raw.get("pub_url", "")
    match = DOI_RE.search(" ".join([str(links), str(bib.get("url", "")), str(bib.get("title", ""))]))
    doi = match.group(0).rstrip(".,;") if match else ""
    return PaperResult(
        title=str(bib.get("title", "")).strip(),
        authors=str(authors).strip(),
        year=str(bib.get("pub_year", "")).strip(),
        venue=str(bib.get("venue", bib.get("journal", ""))).strip(),
        doi=doi,
        abstract=str(bib.get("abstract", "")).strip(),
        snippet=str(raw.get("snippet", "")).strip(),
        citation_count=int(raw.get("num_citations", 0) or 0),
        pdf_url=str(raw.get("eprint_url", "") or "").strip(),
        provider=provider_for_doi(doi) or "",
    )


def cache_key(query: str, pages: int, page_size: int) -> str:
    value = f"v1:{query.strip().lower()}:{pages}:{page_size}".encode()
    return hashlib.sha256(value).hexdigest()[:16]


def write_results(results: Iterable[PaperResult], directory: Path, name: str) -> tuple[Path, Path]:
    directory.mkdir(parents=True, exist_ok=True)
    items = [asdict(result) for result in results]
    jsonl_path = directory / f"{name}.jsonl"
    csv_path = directory / f"{name}.csv"
    jsonl_path.write_text("".join(json.dumps(item, ensure_ascii=False) + "\n" for item in items), encoding="utf-8")
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(items)
    return jsonl_path, csv_path


def read_cached_results(path: Path) -> list[PaperResult]:
    if not path.exists():
        return []
    return [PaperResult(**json.loads(line)) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def search_pages(query: str, pages: int, page_size: int, *, fetch: Callable[[int], list], sleep: Callable[[float], None] = time.sleep, delay: float = 0) -> list[list]:
    result = []
    for page in range(pages):
        items = fetch(page)
        if not items:
            break
        result.append(items[:page_size])
        if page < pages - 1:
            sleep(delay)
    return result


class SearchBlockedError(RuntimeError):
    def __init__(self, message: str, *, partial_pages: list[list[PaperResult]] | None = None):
        super().__init__(message)
        self.partial_pages = partial_pages or []


def _content_while_navigating(page) -> str | None:
    try:
        return page.content()
    except Exception as exc:
        if "navigating and changing the content" in str(exc).lower():
            return None
        raise


def scholar_browser_launch_options(data_dir: Path) -> dict:
    return {
        "user_data_dir": str(profile_path(data_dir)),
        "headless": False,
        "channel": "chrome",
    }


def ensure_chrome_cdp(data_dir: Path, port: int) -> subprocess.Popen | None:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.5):
            return None
    except OSError:
        pass

    profile_path(data_dir).mkdir(parents=True, exist_ok=True)
    try:
        command = chrome_command(data_dir, port)
    except FileNotFoundError as exc:
        raise SearchBlockedError(str(exc)) from exc
    process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return process
        except OSError:
            time.sleep(0.2)
    process.terminate()
    raise SearchBlockedError("Chrome CDP 端口启动超时")


def fetch_scholar_pages(query: str, pages: int, page_size: int, *, min_delay: float = 20.0, max_delay: float = 40.0) -> list[list[PaperResult]]:
    from scholarly import scholarly

    navigator = getattr(scholarly, "_Scholarly__nav")
    def fail_on_captcha(_url):
        raise SearchBlockedError("Google Scholar returned a CAPTCHA challenge")
    navigator.pm1._handle_captcha2 = fail_on_captcha
    navigator.pm2._handle_captcha2 = fail_on_captcha
    scholarly.set_retries(0)
    scholarly.set_timeout(20)
    result = []
    for page in range(pages):
        try:
            iterator = scholarly.search_pubs(query, patents=False, citations=True, start_index=page * page_size)
            current = [normalize_result(next(iterator)) for _ in range(page_size)]
        except StopIteration:
            current = []
        except SearchBlockedError:
            raise
        except Exception as exc:
            message = str(exc).lower()
            if any(word in message for word in ("captcha", "429", "robot", "blocked", "rate limit", "403")):
                raise SearchBlockedError("Google Scholar returned an anti-bot or rate-limit challenge") from exc
            raise
        if not current:
            break
        result.append(current)
        if page < pages - 1:
            time.sleep(random.uniform(min_delay, max_delay))
    return result


def fetch_scholar_page(query: str, page: int, *, page_size: int = 10, session=None) -> list[PaperResult]:
    import requests
    from bs4 import BeautifulSoup

    session = session or requests.Session()
    response = session.get("https://scholar.google.com/scholar", params={"q": query, "start": page * page_size, "hl": "en"}, timeout=20)
    body = response.text.lower()
    if response.status_code in (403, 429) or any(marker in body for marker in ("captcha", "unusual traffic", "not a robot")):
        raise SearchBlockedError(f"Google Scholar blocked the request (HTTP {response.status_code})")
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    results = []
    for item in soup.select("div.gs_ri"):
        title_node = item.select_one("h3.gs_rt")
        meta = item.select_one("div.gs_a")
        authors, venue, year = parse_scholar_meta(meta.get_text(" ", strip=True) if meta else "")
        snippet = item.select_one("div.gs_rs")
        link = title_node.select_one("a") if title_node else None
        title = title_node.get_text(" ", strip=True) if title_node else ""
        href = link.get("href", "") if link else ""
        cited = item.select_one("div.gs_fl")
        cited_match = re.search(r"Cited by (\d+)", cited.get_text(" ", strip=True) if cited else "", re.I)
        results.append(PaperResult(title=title, authors=authors, venue=venue, year=year, snippet=snippet.get_text(" ", strip=True) if snippet else "", citation_count=int(cited_match.group(1)) if cited_match else 0, pdf_url=href, source="google-scholar"))
    return results


def parse_scholar_html(html: str, page_size: int = 10) -> list[PaperResult]:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    results = []
    for item in soup.select("div.gs_ri"):
        title = item.select_one("h3.gs_rt")
        meta = item.select_one("div.gs_a")
        authors, venue, year = parse_scholar_meta(meta.get_text(" ", strip=True) if meta else "")
        snippet = item.select_one("div.gs_rs")
        cited = item.select_one("div.gs_fl")
        match = DOI_RE.search(item.get_text(" ", strip=True))
        cited_match = re.search(r"Cited by (\d+)", cited.get_text(" ", strip=True) if cited else "", re.I)
        results.append(PaperResult(
            title=title.get_text(" ", strip=True) if title else "",
            authors=authors,
            venue=venue,
            year=year,
            snippet=snippet.get_text(" ", strip=True) if snippet else "",
            doi=match.group(0).rstrip(".,;") if match else "",
            citation_count=int(cited_match.group(1)) if cited_match else 0,
        ))
    return results[:page_size]


def fetch_scholar_pages_cdp(
    query: str,
    pages: int,
    page_size: int,
    *,
    port: int = 9222,
    min_delay: float = 10.0,
    max_delay: float = 20.0,
    verification_timeout: float = 300.0,
    wait_for_verification: bool = True,
) -> list[list[PaperResult]]:
    from urllib.parse import quote_plus
    from playwright.sync_api import sync_playwright

    result = []
    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
        except Exception as exc:
            raise SearchBlockedError(
                f"未检测到已启动的 Chrome CDP（端口 {port}）。请先手动启动真实 Chrome 并打开 Scholar。"
            ) from exc
        contexts = browser.contexts
        if not contexts:
            raise SearchBlockedError("CDP Chrome 没有可用浏览器上下文")
        page = contexts[0].pages[0] if contexts[0].pages else contexts[0].new_page()
        for number in range(pages):
            page.goto(
                f"https://scholar.google.com/scholar?q={quote_plus(query)}&start={number * page_size}&hl=en",
                wait_until="domcontentloaded",
                timeout=60_000,
            )
            html = page.content()
            items = parse_scholar_html(html, page_size)
            if not items and any(marker in html.lower() for marker in ("captcha-form", "gs_captcha_ccl", "unusual traffic", "not a robot")):
                if not wait_for_verification:
                    raise SearchBlockedError(
                        "Google Scholar returned an anti-bot challenge; no automatic verification was attempted.",
                        partial_pages=result,
                    )
                print("Google Scholar 需要人工验证，请在已打开的 Chrome 中完成验证；程序会自动等待。", flush=True)
                deadline = time.monotonic() + verification_timeout
                while time.monotonic() < deadline:
                    time.sleep(4)
                    html = _content_while_navigating(page)
                    if html is None:
                        continue
                    items = parse_scholar_html(html, page_size)
                    if items:
                        break
                if not items:
                    raise SearchBlockedError(
                        "Google Scholar verification was not cleared before timeout",
                        partial_pages=result,
                    )
            if not items:
                break
            result.append(items)
            if number < pages - 1:
                time.sleep(random.uniform(min_delay, max_delay))
        # 这是用户自己的 Chrome；退出 Playwright 连接，不关闭浏览器进程。
    return result


def fetch_scholar_pages_browser(query: str, pages: int, page_size: int, data_dir: Path) -> list[list[PaperResult]]:
    from urllib.parse import quote_plus
    from playwright.sync_api import sync_playwright
    from bs4 import BeautifulSoup

    result = []
    with sync_playwright() as playwright:
        try:
            context = playwright.chromium.launch_persistent_context(**scholar_browser_launch_options(data_dir))
        except Exception as exc:
            raise SearchBlockedError(
                "无法启动本机 Google Chrome；请改用 --cdp 连接已打开的 Chrome。"
            ) from exc
        page = context.pages[0] if context.pages else context.new_page()
        for number in range(pages):
            page.goto(f"https://scholar.google.com/scholar?q={quote_plus(query)}&start={number * page_size}&hl=en", wait_until="domcontentloaded", timeout=60_000)
            html = page.content()
            lowered = html.lower()
            if any(marker in lowered for marker in ("captcha-form", "gs_captcha_ccl", "unusual traffic", "not a robot")):
                raise SearchBlockedError(
                    "Google Scholar returned an anti-bot challenge; no automatic verification was attempted.",
                    partial_pages=result,
                )
            soup = BeautifulSoup(html, "html.parser")
            items = []
            for item in soup.select("div.gs_ri"):
                title = item.select_one("h3.gs_rt")
                meta = item.select_one("div.gs_a")
                authors, venue, year = parse_scholar_meta(meta.get_text(" ", strip=True) if meta else "")
                snippet = item.select_one("div.gs_rs")
                cited = item.select_one("div.gs_fl")
                match = DOI_RE.search(item.get_text(" ", strip=True))
                cited_match = re.search(r"Cited by (\d+)", cited.get_text(" ", strip=True) if cited else "", re.I)
                items.append(PaperResult(title=title.get_text(" ", strip=True) if title else "", authors=authors, venue=venue, year=year, snippet=snippet.get_text(" ", strip=True) if snippet else "", doi=match.group(0) if match else "", citation_count=int(cited_match.group(1)) if cited_match else 0))
            if not items:
                break
            result.append(items[:page_size])
            if number < pages - 1:
                time.sleep(random.uniform(20, 40))
        context.close()
    return result
