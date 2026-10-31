import base64
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

from .files import is_valid_pdf
from .providers import acm_pdf_url, doi_url, normalize_doi, provider_for_doi

IEEE_DOCUMENT_RE = re.compile(r"ieeexplore\.ieee\.org/document/(\d+)", re.IGNORECASE)
SCIENCEDIRECT_PII_RE = re.compile(
    r"(?:sciencedirect\.com/science/article/(?:abs/)?pii|linkinghub\.elsevier\.com/retrieve/pii)/([A-Z0-9]+)",
    re.IGNORECASE,
)
AUTH_MARKERS = ("/login", "/signin", "/cas", "/sso", "wayf", "denied=")


def _loaded_sciencedirect_pdf(context, pii: str):
    for page in getattr(context, "pages", []):
        parsed = urlparse(page.url)
        if (
            parsed.hostname != "pdf.sciencedirectassets.com"
            or not parsed.path.lower().endswith(".pdf")
            or pii.lower() not in parsed.path.lower()
        ):
            continue
        try:
            result = page.evaluate("""async () => {
                const response = await fetch(location.href, {credentials: 'include'});
                const contentType = response.headers.get('content-type') || '';
                const bytes = new Uint8Array(await response.arrayBuffer());
                let binary = '';
                for (let i = 0; i < bytes.length; i += 0x8000) {
                    binary += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
                }
                return {
                    status: response.status,
                    contentType,
                    base64: contentType.toLowerCase().startsWith('application/pdf') && response.status === 200
                        ? btoa(binary)
                        : ''
                };
            }""")
        except Exception as exc:
            raise RateLimitedError("Provider rate limit: browser verification challenge") from exc
        if result.get("base64"):
            return result["status"], page.url, base64.b64decode(result["base64"])
        raise RateLimitedError("Provider rate limit: browser verification challenge")
    return None


def _sciencedirect_pdf_response(page, target: str):
    client = page.context.new_cdp_session(page)
    captured = []

    def continue_response(request_id):
        try:
            client.send("Fetch.continueResponse", {"requestId": request_id})
        except Exception:
            client.send("Fetch.continueRequest", {"requestId": request_id})

    def on_request_paused(event):
        request = event["request"]
        parsed = urlparse(request["url"])
        host = parsed.hostname or ""
        path = parsed.path.lower()
        if not (
            host == "www.sciencedirect.com"
            or host.endswith(".sciencedirectassets.com")
            or host.endswith(".elsevier.com")
        ) or not ("/pdfft" in path or path.endswith(".pdf")):
            continue_response(event["requestId"])
            return
        try:
            result = client.send("Fetch.getResponseBody", {"requestId": event["requestId"]})
            body = result["body"]
            if result.get("base64Encoded"):
                body = base64.b64decode(body)
            else:
                body = body.encode("utf-8")
            captured.append((event.get("responseStatusCode", 0), request["url"], body))
        except Exception:
            pass
        continue_response(event["requestId"])

    client.send("Fetch.enable", {"patterns": [
        {"urlPattern": "*pdfft*", "requestStage": "Response"},
        {"urlPattern": "*.pdf*", "requestStage": "Response"},
    ]})
    client.on("Fetch.requestPaused", on_request_paused)
    try:
        try:
            response = page.goto(target, wait_until="domcontentloaded", timeout=180_000)
        except Exception:
            if not captured:
                raise
            response = None
        if captured:
            return captured[-1]
        if response is None:
            raise ValueError("ScienceDirect PDF navigation returned no response")
        return response.status, str(response.url or page.url), response.body()
    finally:
        client.detach()


class AuthRequiredError(RuntimeError):
    pass


class RateLimitedError(RuntimeError):
    pass


class AccessDeniedError(RuntimeError):
    status = 403


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
        if any(word in body[:4096].lower() for word in (
            b"awswaf", b"gokuprops", b"captcha", b"unusual traffic",
            b"cloudflare", b"challenge-platform", b"security verification", b"cf-chl-",
        )):
            raise RateLimitedError("Provider rate limit: verification challenge")
        raise ValueError("The provider response is not a PDF")


def download_pdf(page, doi: str, output_path: Path) -> int:
    doi = normalize_doi(doi)
    provider = provider_for_doi(doi)
    if provider not in {"ieee", "acm", "sciencedirect"}:
        raise ValueError(f"Unsupported DOI provider: {doi}")

    if provider == "ieee":
        response = page.goto(doi_url(doi), wait_until="domcontentloaded", timeout=60_000)
        if response and response.status >= 400:
            if response.status == 403:
                raise AccessDeniedError("Provider returned HTTP 403")
            if response.status == 429:
                raise RateLimitedError("Provider rate limit")
            raise ValueError(f"IEEE DOI navigation returned HTTP {response.status}")
        match = IEEE_DOCUMENT_RE.search(page.url)
        if not match:
            raise ValueError(f"Could not resolve IEEE article number for {doi}")
        target = f"https://ieeexplore.ieee.org/stampPDF/getPDF.jsp?arnumber={match.group(1)}"
    elif provider == "acm":
        page.goto(f"https://dl.acm.org/doi/{doi}", wait_until="domcontentloaded", timeout=60_000)
        target = acm_pdf_url(doi)
    else:
        loaded_pdf = None
        response = page.goto(doi_url(doi), wait_until="domcontentloaded", timeout=60_000)
        if response and response.status >= 400:
            if response.status == 403:
                raise AccessDeniedError("Provider returned HTTP 403")
            if response.status == 429:
                raise RateLimitedError("Provider rate limit")
            raise ValueError(f"ScienceDirect DOI navigation returned HTTP {response.status}")
        if "linkinghub.elsevier.com" in page.url:
            page.wait_for_url("**/science/article/pii/**", timeout=60_000)
        match = SCIENCEDIRECT_PII_RE.search(page.url)
        if not match:
            raise ValueError(f"Could not resolve ScienceDirect PII for {doi}")
        loaded_pdf = _loaded_sciencedirect_pdf(page.context, match.group(1))
        if not loaded_pdf:
            links = page.locator("a[href*='/pdfft?']")
            try:
                links.first.wait_for(state="attached", timeout=20_000)
            except Exception as exc:
                raise ValueError(f"ScienceDirect article page has no PDF link for {doi}") from exc
            href = links.first.get_attribute("href")
            target = urljoin("https://www.sciencedirect.com", href or "")
            parsed = urlparse(target)
            if parsed.hostname != "www.sciencedirect.com" or f"/pii/{match.group(1)}/pdfft" not in parsed.path:
                raise ValueError(f"ScienceDirect PDF link did not match {doi}")

    if provider == "sciencedirect":
        if loaded_pdf:
            status, response_url, body = loaded_pdf
        else:
            status, response_url, body = _sciencedirect_pdf_response(page, target)
        if status == 403:
            raise AccessDeniedError("Provider returned HTTP 403")
        if status == 429:
            raise RateLimitedError("Provider rate limit")
    else:
        response = page.context.request.get(target, timeout=180_000)
        if response.status == 403:
            raise AccessDeniedError("Provider returned HTTP 403")
        if response.status == 429:
            raise RateLimitedError("Provider rate limit")
        body = response.body()
        response_url = str(response.url or page.url)
    _assert_authorized(response_url, body)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = output_path.with_suffix(output_path.suffix + ".part")
    temp_path.write_bytes(body)
    if not is_valid_pdf(temp_path):
        temp_path.unlink(missing_ok=True)
        raise ValueError("Downloaded file failed PDF validation")
    temp_path.replace(output_path)
    return len(body)
