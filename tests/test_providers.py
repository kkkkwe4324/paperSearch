import pytest

from paper_downloader.providers import normalize_doi, provider_for_doi


def test_routes_ieee_and_acm_dois():
    assert provider_for_doi("https://doi.org/10.1109/ABC.1") == "ieee"
    assert provider_for_doi("10.23919/PCMP.2023.000219") == "ieee"
    assert provider_for_doi("10.1145/1234567.1234568") == "acm"


def test_normalizes_and_rejects_unknown_dois():
    assert normalize_doi(" DOI: 10.1109/ABC.1 ") == "10.1109/ABC.1"
    assert provider_for_doi("10.1000/example") is None


def test_rejects_malformed_doi():
    with pytest.raises(ValueError):
        normalize_doi("not-a-doi")
