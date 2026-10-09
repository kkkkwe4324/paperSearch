from paper_downloader.files import is_valid_pdf


def test_accepts_realistic_pdf_header(tmp_path):
    path = tmp_path / "paper.pdf"
    path.write_bytes(b"%PDF-1.7\n" + b"x" * 10000)
    assert is_valid_pdf(path)


def test_rejects_html_login_page(tmp_path):
    path = tmp_path / "paper.pdf"
    path.write_text("<html>login</html>")
    assert not is_valid_pdf(path)
