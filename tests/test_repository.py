from pathlib import Path
import subprocess


def test_gitignore_excludes_generated_download_artifacts():
    gitignore = (Path(__file__).parent.parent / ".gitignore").read_text()

    for pattern in ("*.pdf", "downloads/", "results/", ".paper-downloader/", "*.jsonl"):
        assert pattern in gitignore


def test_git_ignores_local_artifacts_and_browser_profiles():
    repo_root = Path(__file__).parent.parent

    for candidate in (
        ".venv/x",
        "__pycache__/x.pyc",
        ".pytest_cache/x",
        ".paper-downloader/browser-profile/Cookies",
        "browser-profile/Cookies",
        "scholar-browser/Cookies",
        "scholar-chrome-profile/Cookies",
        "downloads/paper.pdf",
        "results/query.csv",
        "dist/a.whl",
        "build/a",
        "release/a",
        "state.jsonl",
        "paper.part",
        "paper.pdf",
    ):
        result = subprocess.run(
            ["git", "check-ignore", "-q", candidate], cwd=repo_root, check=False
        )
        assert result.returncode == 0, candidate
