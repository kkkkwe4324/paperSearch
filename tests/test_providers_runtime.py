import base64

from paper_downloader.providers_runtime import AuthRequiredError, RateLimitedError, _assert_authorized, download_pdf


class Response:
    status = 200

    def __init__(self, body):
        self._body = body
        self.url = "https://dl.acm.org/doi/pdf/10.1145/1.2"

    def body(self):
        return self._body


class Request:
    def __init__(self):
        self.urls = []

    def get(self, url, **kwargs):
        self.urls.append(url)
        return Response(b"%PDF-1.7\n" + b"x" * 10000)


class Context:
    def __init__(self):
        self.request = Request()


class Page:
    url = "https://dl.acm.org/doi/10.1145/1.2"

    def __init__(self):
        self.urls = []
        self.context = Context()

    def goto(self, url, **kwargs):
        self.urls.append(url)
        return Response(b"<html>article</html>")


class ScienceDirectRequest(Request):
    def get(self, url, **kwargs):
        self.urls.append(url)
        response = Response(b"%PDF-1.7\n" + b"x" * 10000)
        response.url = url
        return response


class ScienceDirectCdpSession:
    def __init__(self):
        self.handlers = {}

    def send(self, method, params=None):
        if method == "Fetch.getResponseBody":
            return {"body": base64.b64encode(b"%PDF-1.7\n" + b"x" * 10000).decode("ascii"), "base64Encoded": True}
        return {}

    def on(self, event, handler):
        self.handlers[event] = handler

    def detach(self):
        pass


class ScienceDirectPage:
    url = "https://linkinghub.elsevier.com/retrieve/pii/S1234567890123456"

    def __init__(self):
        self.cdp = ScienceDirectCdpSession()
        self.context = type("Context", (), {
            "request": ScienceDirectRequest(),
            "new_cdp_session": lambda context, page: self.cdp,
        })()
        self.waited_for_article = False
        self.waited_for_link = False
        self.fetched_pdf = None

    def goto(self, url, **kwargs):
        if "/pdfft?" in url:
            self.fetched_pdf = url
            self.cdp.handlers["Fetch.requestPaused"]({
                "requestId": "pdf-1",
                "request": {"url": "https://pdf.sciencedirectassets.com/article/main.pdf"},
                "responseStatusCode": 200,
            })
            response = Response(b"")
            response.body = lambda: (_ for _ in ()).throw(RuntimeError("PDF viewer consumed response"))
            return response
        self.url = "https://linkinghub.elsevier.com/retrieve/pii/S1234567890123456"
        response = Response(b"<html>article</html>")
        response.url = self.url
        return response

    def locator(self, selector):
        assert selector == "a[href*='/pdfft?']"
        page = self
        class Link:
            def wait_for(self, **kwargs):
                page.waited_for_link = True

            def get_attribute(self, name):
                return "/science/article/pii/S1234567890123456/pdfft?token=abc"
        class Links:
            first = Link()
            def get_attribute(self, name):
                raise AssertionError("must select the article's first PDF link")
        return Links()

    def wait_for_url(self, pattern, **kwargs):
        self.waited_for_article = True
        self.url = "https://www.sciencedirect.com/science/article/pii/S1234567890123456"


def test_acm_download_uses_browser_cookies_for_pdf_request(tmp_path):
    page = Page()
    output = tmp_path / "paper.pdf"

    download_pdf(page, "10.1145/1.2", output)

    assert output.read_bytes().startswith(b"%PDF-")
    assert page.context.request.urls == ["https://dl.acm.org/doi/pdf/10.1145/1.2"]


def test_provider_waf_challenge_is_rate_limited():
    try:
        _assert_authorized("https://ieeexplore.ieee.org/document/1", b"awsWafCookieDomainList gokuProps")
    except RateLimitedError:
        return
    raise AssertionError("WAF challenge must stop as rate limited")


def test_sciencedirect_cloudflare_challenge_stops_retries():
    try:
        _assert_authorized(
            "https://pdf.sciencedirectassets.com/article/main.pdf",
            b"<title>Security verification</title><div>Cloudflare challenge-platform</div>",
        )
    except RateLimitedError:
        return
    raise AssertionError("ScienceDirect Cloudflare challenge must stop retries")


def test_provider_denied_redirect_requires_authentication():
    try:
        _assert_authorized("https://ieeexplore.ieee.org/document/1/?denied=", b"access restricted")
    except AuthRequiredError:
        return
    raise AssertionError("provider denied redirect must require authentication")


def test_sciencedirect_download_reads_pdf_in_the_authenticated_browser_page(tmp_path):
    page = ScienceDirectPage()
    output = tmp_path / "paper.pdf"

    download_pdf(page, "10.1016/j.apenergy.2023.121234", output)

    assert output.read_bytes().startswith(b"%PDF-")
    assert page.waited_for_article
    assert page.waited_for_link
    assert page.fetched_pdf == (
        "https://www.sciencedirect.com/science/article/pii/S1234567890123456/pdfft?token=abc"
    )
    assert page.context.request.urls == []


def test_sciencedirect_reuses_an_already_verified_pdf_tab(tmp_path):
    class LoadedPdfTab:
        url = "https://pdf.sciencedirectassets.com/1-s2.0-S1234567890123456/main.pdf"

        def evaluate(self, script):
            assert "fetch(location.href" in script
            self.fetched = True
            return {
                "status": 200,
                "contentType": "application/pdf",
                "base64": base64.b64encode(b"%PDF-1.7\n" + b"x" * 10000).decode("ascii"),
            }

    page = ScienceDirectPage()
    loaded_pdf = LoadedPdfTab()
    page.context.pages = [page, loaded_pdf]
    output = tmp_path / "paper.pdf"

    download_pdf(page, "10.1016/j.apenergy.2023.121234", output)

    assert output.read_bytes().startswith(b"%PDF-")
    assert loaded_pdf.fetched
    assert page.fetched_pdf is None
