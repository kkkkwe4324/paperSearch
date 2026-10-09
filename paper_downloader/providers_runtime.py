import re
from pathlib import Path

from .files import is_valid_pdf
from .providers import acm_pdf_url, doi_url, normalize_doi, provider_for_doi

IEEE_DOCUMENT_RE = re.compile(r"ieeexplore\.ieee\.org/document/(\d+)", re.IGNORECASE)
AUTH_MARKERS = ("/login", "/signin", "/cas", "/sso", "wayf")


class AuthRequiredError(RuntimeError):
    pass


class RateLimitedError(RuntimeError):
    pass


def _is_auth_url(url: str) -> bool:
    lowered = url.lower()
    return any(marker in lowered for marker in AUTH_MARKERS)


def _assert_authorized(url: str, body: bytes) -> None:
    if _is_auth_url(url):
        raise AuthRequiredError("Authentication required")
    if not body.startswith(b"%PDF-"):
        sample = body[:80].decode("utf-8", errors="replace")
        lowered = sample.lower()
        if any(word in lowered for word in ("login", "sign in", "unauthorized", "access denied")):
            raise AuthRequiredError("The provider returned an authentication page")
        if any(word in body[:4096].lower() for word in (b"awswaf", b"gokuprops", b"captcha", b"unusual traffic")):
            raise RateLimitedError("Provider verification challenge")
        raise ValueError("The provider response is not a PDF")


def download_pdf(page, doi: str, output_path: Path) -> int:
    doi = normalize_doi(doi)
    provider = provider_for_doi(doi)
    if provider not in {"ieee", "acm"}:
        raise ValueError(f"Unsupported DOI provider: {doi}")

    if provider == "ieee":
        response = page.goto(doi_url(doi), wait_until="domcontentloaded", timeout=60_000)
        if response and response.status >= 400:
            if response.status in (403, 429):
                raise RateLimitedError("Provider rate limit")
            raise ValueError(f"IEEE DOI navigation returned HTTP {response.status}")
        match = IEEE_DOCUMENT_RE.search(page.url)
        if not match:
            raise ValueError(f"Could not resolve IEEE article number for {doi}")
        target = f"https://ieeexplore.ieee.org/stampPDF/getPDF.jsp?arnumber={match.group(1)}"
    else:
        page.goto(f"https://dl.acm.org/doi/{doi}", wait_until="domcontentloaded", timeout=60_000)
        target = acm_pdf_url(doi)

    response = page.goto(target, wait_until="commit", timeout=180_000)
    if response is None:
        raise ValueError("The provider returned no PDF response")
    if response.status in (403, 429):
        raise RateLimitedError("Provider rate limit")
    body = response.body()
    _assert_authorized(str(response.url or page.url), body)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = output_path.with_suffix(output_path.suffix + ".part")
    temp_path.write_bytes(body)
    if not is_valid_pdf(temp_path):
        temp_path.unlink(missing_ok=True)
        raise ValueError("Downloaded file failed PDF validation")
    temp_path.replace(output_path)
    return len(body)
