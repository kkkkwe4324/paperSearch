"""Open-access PDF fallback using fulltext-article-downloader and OpenAlex."""

import json
from html.parser import HTMLParser
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import quote, urljoin, urlparse
from urllib.request import Request, urlopen

from .files import is_valid_pdf


class _PdfLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.current = None

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.current = [dict(attrs).get("href", ""), []]

    def handle_data(self, data):
        if self.current:
            self.current[1].append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self.current:
            href, text = self.current
            label = " ".join(text).lower()
            if href and (".pdf" in href.lower() or "pdf" in label or "published version" in label):
                self.links.append(href)
            self.current = None


def _request(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; paper-downloader/0.1)"})
    with urlopen(request, timeout=30) as response:
        return response.read()


def _pdf_candidate_urls(landing_page: str, href: str) -> list[str]:
    url = urljoin(landing_page, href)
    candidates = [url]
    parsed = urlparse(url)
    if parsed.hostname == "research.monash.edu" and parsed.path.startswith("/files/"):
        candidates.append(f"https://researchmgt.monash.edu/ws{parsed.path}{('?' + parsed.query) if parsed.query else ''}")
    return candidates


def _openalex_pdf(doi: str) -> bytes | None:
    endpoint = f"https://api.openalex.org/works/https://doi.org/{quote(doi, safe='/')}"
    try:
        data = json.loads(_request(endpoint))
    except Exception:
        return None
    locations = [location for location in data.get("locations", []) if location.get("is_oa")]
    locations.sort(key=lambda location: urlparse(location.get("landing_page_url") or location.get("pdf_url") or "").hostname in {"www.sciencedirect.com", "sciencedirect.com"})
    for location in locations:
        pdf_url = location.get("pdf_url")
        if pdf_url:
            try:
                body = _request(pdf_url)
                if body.startswith(b"%PDF-") and len(body) >= 10_000:
                    return body
            except Exception:
                pass
        landing_page = location.get("landing_page_url")
        if not landing_page:
            continue
        try:
            html = _request(landing_page).decode("utf-8", errors="replace")
            parser = _PdfLinks()
            parser.feed(html)
            for href in parser.links:
                for pdf_url in _pdf_candidate_urls(landing_page, href):
                    try:
                        body = _request(pdf_url)
                        if body.startswith(b"%PDF-") and len(body) >= 10_000:
                            return body
                    except Exception:
                        continue
        except Exception:
            continue
    return None


def fetch_open_pdf(doi: str, target: Path) -> str | None:
    from fulltext_article_downloader import fetch

    source = None
    with TemporaryDirectory(prefix="paper-oa-") as temporary:
        try:
            result = fetch(
                doi,
                temporary,
                tools=["unpaywall", "europepmc", "osti"],
                skip_existing=False,
            )
            if result["success"]:
                candidate = Path(result["path"])
                if candidate.suffix.lower() == ".pdf" and is_valid_pdf(candidate):
                    target.parent.mkdir(parents=True, exist_ok=True)
                    candidate.replace(target)
                    return result["source"] or "open_access"
        except Exception:
            pass

    body = _openalex_pdf(doi)
    if not body:
        return None
    target.parent.mkdir(parents=True, exist_ok=True)
    temp_path = target.with_suffix(target.suffix + ".part")
    temp_path.write_bytes(body)
    if not is_valid_pdf(temp_path):
        temp_path.unlink(missing_ok=True)
        return None
    temp_path.replace(target)
    return "openalex"
