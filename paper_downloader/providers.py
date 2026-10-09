import re

DOI_RE = re.compile(r"^10\.\d{4,9}/\S+$", re.IGNORECASE)


def normalize_doi(value: str) -> str:
    doi = value.strip()
    doi = re.sub(r"^https?://doi\.org/", "", doi, flags=re.IGNORECASE)
    doi = re.sub(r"^doi:\s*", "", doi, flags=re.IGNORECASE)
    doi = doi.rstrip(".,;")
    if not DOI_RE.match(doi):
        raise ValueError(f"Invalid DOI: {value!r}")
    return doi


def provider_for_doi(value: str) -> str | None:
    try:
        doi = normalize_doi(value).lower()
    except ValueError:
        return None
    if doi.startswith(("10.1109/", "10.23919/")):
        return "ieee"
    if doi.startswith("10.1145/"):
        return "acm"
    return None


def doi_url(doi: str) -> str:
    return f"https://doi.org/{normalize_doi(doi)}"


def acm_pdf_url(doi: str) -> str:
    return f"https://dl.acm.org/doi/pdf/{normalize_doi(doi)}"
