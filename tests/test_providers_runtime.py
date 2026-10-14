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


class ScienceDirectPage:
    url = "https://linkinghub.elsevier.com/retrieve/pii/S1234567890123456"

    def __init__(self):
        self.context = type("Context", (), {"request": ScienceDirectRequest()})()

    def goto(self, url, **kwargs):
        self.url = "https://linkinghub.elsevier.com/retrieve/pii/S1234567890123456"
        response = Response(b"<html>article</html>")
        response.url = self.url
        return response


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


def test_provider_denied_redirect_requires_authentication():
    try:
        _assert_authorized("https://ieeexplore.ieee.org/document/1/?denied=", b"access restricted")
    except AuthRequiredError:
        return
    raise AssertionError("provider denied redirect must require authentication")


def test_sciencedirect_download_resolves_pii_and_uses_browser_cookies(tmp_path):
    page = ScienceDirectPage()
    output = tmp_path / "paper.pdf"

    download_pdf(page, "10.1016/j.apenergy.2023.121234", output)

    assert output.read_bytes().startswith(b"%PDF-")
    assert page.context.request.urls == [
        "https://www.sciencedirect.com/science/article/pii/S1234567890123456/pdf"
    ]
