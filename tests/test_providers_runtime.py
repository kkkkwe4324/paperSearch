from paper_downloader.providers_runtime import download_pdf


class Response:
    status = 200

    def __init__(self, body):
        self._body = body
        self.url = "https://dl.acm.org/doi/pdf/10.1145/1.2"

    def body(self):
        return self._body


class Page:
    url = "https://dl.acm.org/doi/10.1145/1.2"

    def __init__(self):
        self.urls = []

    def goto(self, url, **kwargs):
        self.urls.append(url)
        if "/pdf/" in url:
            return Response(b"%PDF-1.7\n" + b"x" * 10000)
        return Response(b"<html>article</html>")


def test_acm_download_uses_browser_navigation_for_pdf(tmp_path):
    page = Page()
    output = tmp_path / "paper.pdf"

    download_pdf(page, "10.1145/1.2", output)

    assert output.read_bytes().startswith(b"%PDF-")
    assert page.urls[-1].endswith("/doi/pdf/10.1145/1.2")
