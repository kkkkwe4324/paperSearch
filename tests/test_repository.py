from pathlib import Path


def test_gitignore_excludes_generated_download_artifacts():
    gitignore = (Path(__file__).parent.parent / ".gitignore").read_text()

    for pattern in ("*.pdf", "downloads/", "results/", ".paper-downloader/", "*.jsonl"):
        assert pattern in gitignore
