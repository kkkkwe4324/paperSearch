from pathlib import Path
from importlib.resources import files

import pytest

from paper_downloader.workspace import (
    add_direction,
    add_idea,
    discover_workspace,
    init_workspace,
    resolve_direction,
)


def test_init_and_add_direction_preserve_existing_notes(tmp_path):
    init_workspace(tmp_path)
    assert (tmp_path / ".papersearch.toml").exists()
    assert all((tmp_path / name / "README.md").exists() for name in ("ideas", "demos", "reproductions", "literature"))

    readme = tmp_path / "README.md"
    readme.write_text("my existing overview\n", encoding="utf-8")
    init_workspace(tmp_path)
    assert readme.read_text(encoding="utf-8") == "my existing overview\n"

    add_idea(tmp_path, "idea_a")
    add_direction(tmp_path, "idea_a", "latency")
    direction = tmp_path / "ideas" / "idea_a" / "directions" / "latency"
    assert (direction / "papers.md").exists()
    assert (direction / "search_logs").is_dir()
    assert (direction / "reading_notes").is_dir()
    assert resolve_direction(tmp_path, "idea_a", "latency") == direction


def test_discover_workspace_from_nested_directory(tmp_path):
    init_workspace(tmp_path)
    nested = tmp_path / "ideas" / "one" / "directions" / "two"
    nested.mkdir(parents=True)
    assert discover_workspace(nested) == tmp_path


def test_unknown_and_unsafe_direction_names_fail(tmp_path):
    init_workspace(tmp_path)
    with pytest.raises(ValueError, match="slug"):
        add_idea(tmp_path, "../escape")
    with pytest.raises(ValueError, match="unknown idea"):
        add_direction(tmp_path, "missing", "topic")
    with pytest.raises(ValueError, match="unknown direction"):
        resolve_direction(tmp_path, "missing", "topic")


def test_templates_and_example_include_research_evidence_fields():
    package = files("paper_downloader").joinpath("templates")
    for name in ("papers.md", "search-log.md", "reading-note.md", "venue-policy.md"):
        assert package.joinpath(name).is_file()
    example = Path(__file__).resolve().parents[1] / "examples/research-workspace/ideas/satellite_llm/directions/service_pool/papers.md"
    text = example.read_text(encoding="utf-8")
    for field in ("Zotero key", "Venue and publication status", "Reading state", "Screening decision", "Zotero collections"):
        assert field in text
