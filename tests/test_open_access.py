import json
import sys
from types import SimpleNamespace

from paper_downloader import open_access
from paper_downloader.open_access import fetch_open_pdf


class UrlResponse:
    def __init__(self, body):
        self.body = body

    def read(self):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


def test_openalex_finds_repository_pdf_when_publisher_location_is_blocked(tmp_path, monkeypatch):
    requests = []
    locations = {
        "locations": [
            {
                "is_oa": True,
                "pdf_url": "https://www.sciencedirect.com/blocked.pdf",
                "landing_page_url": "https://www.sciencedirect.com/article",
                "source": {"display_name": "ScienceDirect"},
            },
            {
                "is_oa": True,
                "pdf_url": None,
                "landing_page_url": "https://research.monash.edu/en/publications/paper",
                "source": {"display_name": "Monash University Research Portal"},
            },
        ]
    }

    def open_url(request, timeout):
        url = request.full_url
        requests.append(url)
        if "api.openalex.org" in url:
            return UrlResponse(json.dumps(locations).encode())
        if "research.monash.edu/en/publications/paper" in url:
            return UrlResponse(b'<a href="/files/123/paper_oa.pdf">Final published version</a>')
        if "research.monash.edu/files/123/paper_oa.pdf" in url:
            return UrlResponse(b"403 Forbidden")
        if "researchmgt.monash.edu/ws/files/123/paper_oa.pdf" in url:
            return UrlResponse(b"%PDF-1.7\n" + b"x" * 10000)
        raise AssertionError(f"unexpected URL: {url}")

    monkeypatch.setitem(sys.modules, "fulltext_article_downloader", SimpleNamespace(
        fetch=lambda *args, **kwargs: {"success": False}
    ))
    monkeypatch.setattr(open_access, "urlopen", open_url)

    target = tmp_path / "paper.pdf"
    source = fetch_open_pdf("10.1016/j.apenergy.2023.122592", target)

    assert source == "openalex"
    assert target.read_bytes().startswith(b"%PDF-")
    assert any("researchmgt.monash.edu/ws/files/123/paper_oa.pdf" in url for url in requests)
    assert not any("blocked.pdf" in url for url in requests)
