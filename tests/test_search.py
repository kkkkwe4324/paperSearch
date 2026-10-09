import csv
import json

from paper_downloader.search import (
    PaperResult,
    cache_key,
    normalize_result,
    search_pages,
    write_results,
    fetch_scholar_page,
    SearchBlockedError,
    parse_scholar_meta,
    parse_scholar_html,
    scholar_browser_launch_options,
)
from paper_downloader.session import profile_path
import inspect


def test_normalizes_scholar_result_and_routes_doi():
    result = normalize_result({"bib": {"title": " Paper ", "author": "A; B", "pub_year": "2024"}, "num_citations": 3, "pub_url": "https://doi.org/10.1109/X.1"})
    assert result.title == "Paper"
    assert result.provider == "ieee"
    assert result.citation_count == 3


def test_cache_key_is_stable_and_safe():
    key = cache_key("microgrid energy", 5, 10)
    assert key == cache_key("microgrid energy", 5, 10)
    assert "/" not in key and " " not in key


def test_exports_jsonl_and_csv(tmp_path):
    results = [PaperResult(title="Paper", authors="A", year="2024")]
    jsonl, csv_path = write_results(results, tmp_path, "query")
    assert json.loads(jsonl.read_text())['title'] == "Paper"
    with csv_path.open(newline="", encoding="utf-8") as handle:
        assert list(csv.DictReader(handle))[0]["title"] == "Paper"


def test_search_pages_waits_between_pages():
    sleeps = []
    pages = search_pages("q", 2, 2, fetch=lambda page: [f"{page}-a", f"{page}-b"], sleep=sleeps.append, delay=1)
    assert pages == [["0-a", "0-b"], ["1-a", "1-b"]]
    assert sleeps == [1]


def test_scholar_page_stops_on_captcha():
    class Response:
        status_code = 200
        text = "<html>unusual traffic captcha</html>"

    class Session:
        def get(self, *args, **kwargs):
            return Response()

    try:
        fetch_scholar_page("PINN", 0, session=Session())
    except SearchBlockedError:
        return
    raise AssertionError("captcha page must stop the search")


def test_parses_authors_venue_and_year():
    authors, venue, year = parse_scholar_meta("A Author, B Author - Journal of Testing, 2024 - publisher.org")
    assert authors == "A Author, B Author"
    assert venue == "Journal of Testing"
    assert year == "2024"


def test_parses_browser_scholar_html():
    html = '''
    <div class="gs_ri">
      <h3 class="gs_rt"><a href="https://example.test/paper">A Paper</a></h3>
      <div class="gs_a">A Author, B Author - Test Journal, 2024 - Publisher</div>
      <div class="gs_rs">This is the abstract snippet.</div>
      <div class="gs_fl"><a href="/scholar?cites=1">Cited by 12</a></div>
    </div>'''
    result = parse_scholar_html(html, 10)[0]
    assert result.title == "A Paper"
    assert result.authors == "A Author, B Author"
    assert result.venue == "Test Journal"
    assert result.year == "2024"
    assert result.snippet == "This is the abstract snippet."
    assert result.citation_count == 12


def test_browser_mode_uses_installed_chrome_channel(tmp_path):
    options = scholar_browser_launch_options(tmp_path)
    assert options["channel"] == "chrome"
    assert options["headless"] is False
    assert options["user_data_dir"] == str(profile_path(tmp_path))


def test_scholar_function_defaults_are_conservative():
    parameters = inspect.signature(__import__("paper_downloader.search", fromlist=["fetch_scholar_pages"]).fetch_scholar_pages).parameters
    assert parameters["min_delay"].default == 20.0
    assert parameters["max_delay"].default == 40.0
