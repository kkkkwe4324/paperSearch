# Portable Workspace Layout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make independent research folders use the same idea/direction, demo, reproduction, literature, and Markdown-note layout, with CLI output routed to a named direction.

**Architecture:** A small `workspace.py` owns config discovery, slug validation, scaffolding, and path resolution. The existing CLI calls it only when a workspace context is supplied or discovered. Templates are package resources so an installed `paper-downloader` can initialize a folder outside its repository.

**Tech Stack:** Python 3.11 standard library (`pathlib`, `tomllib`, `importlib.resources`, `argparse`), pytest.

---

## File map

- Create `paper_downloader/workspace.py`: discovery, config validation, scaffolding, safe direction paths.
- Create `paper_downloader/templates/`: `.papersearch.toml`, category/readme, idea, direction, paper-list, search-log, reading-card, venue-policy templates.
- Modify `pyproject.toml`: include package template data.
- Modify `paper_downloader/cli.py`: `init`, `add-idea`, `add-direction`, contextual `search`/`download` options and routing.
- Create `tests/test_workspace.py`; extend `tests/test_cli.py`.
- Add `examples/research-workspace/` and `LLM_WORKFLOW.md`; link it from `README.md`, `USAGE.md`, `LLM_QUICKSTART.md`, and `AGENTS.md`.

### Task 1: Workspace scaffolding

- [ ] **Step 1: Write failing tests** in `tests/test_workspace.py` for fresh init, second init preserving edited README, invalid slug rejection, and add-direction requiring an existing idea. Use `tmp_path` and assert the expected files exist; call `init_workspace(root)`, `add_idea(root, "test_idea")`, and `add_direction(root, "test_idea", "latency")`.
- [ ] **Step 2: Verify red.** Run `python -m pytest tests/test_workspace.py -q`; expect import/function failures.
- [ ] **Step 3: Implement** `workspace.py` with `TEMPLATE_NAMES`, `write_if_missing(path, text)`, `validate_slug` using `re.fullmatch(r"[a-z0-9][a-z0-9_-]*", slug)`, `init_workspace`, `add_idea`, and `add_direction`. Use `importlib.resources.files("paper_downloader").joinpath("templates", name).read_text(encoding="utf-8")`; use `Path.mkdir(parents=True, exist_ok=True)` and `write_if_missing`, never overwrite user files. Read config with `tomllib` and require `version == 1`.
- [ ] **Step 4: Verify green.** Run `python -m pytest tests/test_workspace.py -q`; expect all added tests to pass.
- [ ] **Step 5: Commit** only new template/workspace/tests files with `git add -- ...` and `git commit -m "feat: scaffold portable research workspaces"`.

### Task 2: Discovery and output routing

- [ ] **Step 1: Write failing tests** for `discover_workspace` walking from a nested directory, `resolve_direction` rejecting unknown idea/direction, and `main(["search", "query", "--workspace", str(root), "--idea", "test_idea", "--direction", "latency", "--pages", "1"])` routing results under `ideas/test_idea/directions/latency/search_logs/`. Stub only network fetch, not path logic. Add a download parser/routing test without starting a browser.
- [ ] **Step 2: Verify red.** Run `python -m pytest tests/test_workspace.py tests/test_cli.py -q`; expect failures for missing options/routing.
- [ ] **Step 3: Implement** `discover_workspace(start: Path) -> Path | None`, `resolve_direction(root, idea, direction) -> Path`, and `resolve_context(args)`. Add `--workspace`, `--idea`, `--direction` to `search` and `download`. Set contextual default `results_dir = direction / "search_logs" / "results"` and `output = direction / "incoming"` only if the caller did not pass explicit output flags. Reject one of `idea`/`direction` without the other. Keep calls without a workspace on their existing defaults.
- [ ] **Step 4: Verify green and legacy behavior.** Run `python -m pytest tests/test_workspace.py tests/test_cli.py -q`; expect all passing, including existing rate-limit and cache tests.
- [ ] **Step 5: Commit** the routing code/tests with `git commit -m "feat: route paper search by idea and direction"`.

### Task 3: User-facing protocol and example

- [ ] **Step 1: Write a failing package-data check** that loads every template from an installed package resource and verifies the example's `papers.md` has columns for DOI/arXiv, Zotero key, venue/status, role, screening, reading state/scope, note, collections, and checked date.
- [ ] **Step 2: Verify red.** Run `python -m pytest tests/test_workspace.py -q`; expect the absent example/protocol check to fail.
- [ ] **Step 3: Write** `LLM_WORKFLOW.md`, `AGENTS.md`, and `examples/research-workspace/` with one concrete idea, direction, demo, reproduction, paper list, search log, reading card, and venue-policy example. The protocol states: rolling three-year core window; field-specific A/B venues; last-12-month provisional exception; keep direct novelty threats even from weaker venues; verify venue status from publisher/proceedings; never infer full-text reading from search snippets. Link it from the existing three guides.
- [ ] **Step 4: Verify green** with `python -m pytest tests/test_workspace.py -q`, then `python -m paper_downloader init --workspace <temporary-folder>` and inspect generated files.
- [ ] **Step 5: Commit** docs, examples, and the package-data check with `git commit -m "docs: teach assistants the research workspace protocol"`.

### Task 4: Adopt navigation in Star without moving files

- [ ] **Step 1: Inspect** existing `C:/Users/32825/paper/star/README.md`, `ideas/README.md`, and the two idea directories without READMEs; record current links.
- [ ] **Step 2: Update** navigation to list all four idea directories. Add short READMEs to `adaptive_multitask_lora` and `task_target_factorized_drafter` using their existing `idea.md` or research entry as source; link their current files, not new copies. Add a Star-specific note linking to the portable `paperSearch` protocol and explain that existing paths are grandfathered in.
- [ ] **Step 3: Verify** every newly added relative Markdown link resolves locally and review the diff. Do not move existing PDFs, reports, code, or intermediate files.

## Plan review

The plan covers workspace initialization, direction registration, contextual routing, Markdown examples, search policy, and Star's entry-point drift. Zotero collection operations are in `2026-11-07-zotero-routing.md`.
