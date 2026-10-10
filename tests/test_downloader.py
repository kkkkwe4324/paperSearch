from paper_downloader.downloader import output_path, read_dois, should_skip


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
