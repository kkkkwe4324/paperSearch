from paper_downloader.downloader import download_batch, output_path, read_dois, should_skip
from paper_downloader.policy import classify_failure


def test_read_dois_ignores_comments_and_duplicates(tmp_path):
    path = tmp_path / "papers.txt"
    path.write_text("# comment\n DOI: 10.1109/X.1\n10.1109/X.1\n\n10.1145/1.2\n")
    assert read_dois(path) == ["10.1109/X.1", "10.1145/1.2"]


def test_resume_skips_only_valid_existing_pdf(tmp_path):
    path = tmp_path / "10.1109_X.1.pdf"
    path.write_bytes(b"%PDF-1.7\n" + b"x" * 10000)
    assert should_skip(path, resume=True)


def test_output_path_cannot_escape_output_directory(tmp_path):
    path = output_path(tmp_path, r"10.1109/ok..\..\outside")
    assert path.parent == tmp_path
    assert ".." not in path.name


def test_forbidden_is_not_misreported_as_rate_limit():
    assert classify_failure(403, "HTTP 403") == "access_denied"
    assert classify_failure(429, "HTTP 429") == "rate_limited"


def test_sciencedirect_uses_open_copy_before_publisher(tmp_path, monkeypatch):
    input_path = tmp_path / "dois.txt"
    input_path.write_text("10.1016/j.apenergy.2023.122592\n")
    output_dir = tmp_path / "pdfs"
    def open_copy(doi, target):
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"%PDF-1.7\n" + b"x" * 10000)
        return "semantic"
    monkeypatch.setattr("paper_downloader.downloader.fetch_open_pdf", open_copy)
    monkeypatch.setattr("paper_downloader.downloader.download_pdf", lambda *args: (_ for _ in ()).throw(AssertionError("publisher called")))
    counts = download_batch(None, input_path, output_dir, output_dir / "state.jsonl", sleep=lambda _: None)
    assert counts["success"] == 1
    assert '"source": "semantic"' in (output_dir / "state.jsonl").read_text()
