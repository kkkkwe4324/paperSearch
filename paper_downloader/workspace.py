"""Portable research-workspace layout and path resolution."""

import re
import tomllib
from importlib.resources import files
from pathlib import Path


def _template(name: str) -> str:
    return files("paper_downloader").joinpath("templates", name).read_text(encoding="utf-8")


def _write_missing(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(content, encoding="utf-8")


def _check_slug(slug: str) -> None:
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", slug):
        raise ValueError(f"invalid slug: {slug!r}; use lowercase letters, digits, _ or -")


def _check_workspace(root: Path) -> Path:
    root = Path(root).resolve()
    config = root / ".papersearch.toml"
    if not config.is_file():
        raise ValueError(f"not a paperSearch workspace: {root}; run 'paper-downloader init --workspace {root}'")
    try:
        data = tomllib.loads(config.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ValueError(f"invalid workspace config: {config}: {exc}") from exc
    if data.get("version") != 1:
        raise ValueError(f"unsupported workspace version in {config}")
    return root


def discover_workspace(start: Path) -> Path | None:
    for candidate in (Path(start).resolve(), *Path(start).resolve().parents):
        if (candidate / ".papersearch.toml").is_file():
            return _check_workspace(candidate)
    return None


def init_workspace(root: Path) -> Path:
    root = Path(root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    _write_missing(root / ".papersearch.toml", _template("workspace.toml"))
    for name in ("README.md", "ideas/README.md", "demos/README.md", "reproductions/README.md", "literature/README.md", "archive/README.md"):
        _write_missing(root / name, _template(name.replace("/", "_")))
    _write_missing(root / "literature" / "venue-policy.md", _template("venue-policy.md"))
    return _check_workspace(root)


def _add_link(index: Path, label: str, target: str) -> None:
    text = index.read_text(encoding="utf-8")
    link = f"- [{label}]({target})"
    if link not in text:
        index.write_text(text.rstrip() + "\n\n" + link + "\n", encoding="utf-8")


def add_idea(root: Path, idea: str) -> Path:
    root = _check_workspace(root)
    _check_slug(idea)
    path = root / "ideas" / idea
    path.mkdir(parents=True, exist_ok=True)
    _write_missing(path / "README.md", _template("idea.md").replace("<idea>", idea))
    _add_link(root / "ideas" / "README.md", idea, f"{idea}/README.md")
    return path


def add_direction(root: Path, idea: str, direction: str) -> Path:
    root = _check_workspace(root)
    _check_slug(idea)
    _check_slug(direction)
    idea_path = root / "ideas" / idea
    if not (idea_path / "README.md").is_file():
        raise ValueError(f"unknown idea: {idea}; run 'paper-downloader add-idea {idea}' first")
    path = idea_path / "directions" / direction
    path.mkdir(parents=True, exist_ok=True)
    for folder in ("search_logs", "reading_notes", "incoming"):
        (path / folder).mkdir(exist_ok=True)
    for name in ("README.md", "papers.md"):
        _write_missing(path / name, _template("direction.md" if name == "README.md" else "papers.md").replace("<direction>", direction))
    _add_link(idea_path / "README.md", direction, f"directions/{direction}/README.md")
    return path


def resolve_direction(root: Path, idea: str, direction: str) -> Path:
    root = _check_workspace(root)
    _check_slug(idea)
    _check_slug(direction)
    path = root / "ideas" / idea / "directions" / direction
    if not (path / "README.md").is_file():
        raise ValueError(f"unknown direction: {idea}/{direction}; run 'paper-downloader add-direction {direction} --idea {idea}' first")
    return path
