# Zotero Routing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let `paperSearch` inspect the live Zotero taxonomy, match an existing paper, preview topic collections, and add approved memberships without disturbing other collections.

**Architecture:** `zotero.py` talks only to Zotero's official local API, with an injected opener for offline tests. CLI `zotero collections`, `zotero plan`, and `zotero apply` separate inspection from mutation. Classification is supplied by a user or LLM from verified paper evidence; code validates keys and membership operations, never guesses a topic from numbering.

**Tech Stack:** Python 3.11 standard library (`urllib.request`, `urllib.parse`, `json`, `pathlib`), Zotero local API v3, pytest.

---

## File map

- Create `paper_downloader/zotero.py`: local API client, tree, exact matching, plan serialization, authorization, versioned membership union, readback.
- Modify `paper_downloader/cli.py`: `zotero collections`, `zotero plan`, `zotero apply`.
- Create `tests/test_zotero.py`; extend `tests/test_cli.py`.
- Extend `LLM_WORKFLOW.md`, `USAGE.md`, and `examples/research-workspace/.../papers.md` with a classification example and `pending Zotero import` state.

### Task 1: Live taxonomy and exact matching

- [ ] **Step 1: Write failing tests** in `tests/test_zotero.py` with a fake opener returning local API JSON. Assert `list_collections()` uses `parentCollection` and keys, so a `05.7` child under root `10投机解码` is displayed under `10`; assert `match_item(doi=...)` accepts only exact normalized DOI and reports multiple exact matches as ambiguous. Assert absent DOI returns `None`, not a fabricated record.
- [ ] **Step 2: Verify red.** Run `python -m pytest tests/test_zotero.py -q`; expect missing module/functions.
- [ ] **Step 3: Implement** `ZoteroClient` with base `http://127.0.0.1:23119/api/`, `urllib.request.build_opener(urllib.request.ProxyHandler({}))`, request timeout, `get_json`, `list_collections`, `collection_paths`, and `match_item`. Use the live `/api/users/0/collections` and `/api/users/0/items` endpoints; filter DOI/title exact in Python. Treat `401`/`403`/connection failures as actionable errors; do not use SQLite or embed user credentials.
- [ ] **Step 4: Verify green.** Run `python -m pytest tests/test_zotero.py -q`; expect passing tests.
- [ ] **Step 5: Commit** `zotero.py` and tests with `git commit -m "feat: inspect live Zotero collections and papers"`.

### Task 2: Preview and safe membership writes

- [ ] **Step 1: Write failing tests** for a plan containing item key/version, old collections, proposed target keys, reason, and collection paths; invalid keys fail. On apply, assert the PATCH body includes the union of old and proposed keys, preserves unrelated memberships, includes version precondition, and stops if the item changed after preview. Simulate authorization denial, 412 conflict, and readback failure without any live Zotero writes.
- [ ] **Step 2: Verify red.** Run `python -m pytest tests/test_zotero.py -q`; expect plan/apply failures.
- [ ] **Step 3: Implement** `make_plan(item, collections, target_keys, reason)` and `apply_plan(plan, client)`. Plan is JSON in a caller-specified file; validate collection keys against the current tree. Apply re-fetches the item, checks key/version, POSTs `/api/local/authorize` with the server ID, PATCHes `/api/users/0/items/<key>` with `{"collections": sorted(set(existing) | set(targets)), "version": current_version}`, and re-reads membership. Catch 401/403/409/412 with clear errors. Do not print, log, or persist the local write key.
- [ ] **Step 4: Verify green.** Run `python -m pytest tests/test_zotero.py -q`; expect passing tests.
- [ ] **Step 5: Commit** implementation/tests with `git commit -m "feat: preview and apply Zotero collection routing"`.

### Task 3: CLI and research-list handoff

- [ ] **Step 1: Write failing CLI tests** for `zotero collections`, `zotero plan --doi <doi> --collection <key> --reason <text> --output <plan.json>`, and `zotero apply <plan.json>`. Mock only the local API client. Assert missing Zotero item produces a pending-import outcome and no write, and that apply prints the confirmed item key/collections for updating `papers.md`.
- [ ] **Step 2: Verify red.** Run `python -m pytest tests/test_cli.py -q`; expect missing subcommands.
- [ ] **Step 3: Implement** parser and dispatch. `plan` resolves DOI/title against Zotero, prints candidate matches or writes a preview file; it never creates an item. `apply` reads preview JSON and reports actual post-write memberships. Update `LLM_WORKFLOW.md` so the agent writes the verified Zotero key/collections into the direction's `papers.md` only after readback; failures remain `pending`. Document Zotero's own identifier/Connector import path for absent entries.
- [ ] **Step 4: Verify green** with `python -m pytest tests/test_cli.py tests/test_zotero.py -q` and `python -m paper_downloader zotero --help`.
- [ ] **Step 5: Commit** CLI/docs/tests with `git commit -m "feat: expose Zotero routing workflow"`.

### Task 4: Full verification and non-mutating smoke test

- [ ] **Step 1: Run** `python -m pytest -q`; expect all tests passing.
- [ ] **Step 2: Run** `python -m paper_downloader zotero collections` against the live local API if available; confirm active numbered roots and child parentage. This is read-only.
- [ ] **Step 3: Run** a read-only `zotero plan` for a known item and review its preview; do not call live `apply` without an actual user-selected paper to classify.
- [ ] **Step 4: Review** `git diff --check`, changed files, and test output. Confirm no secrets or local absolute paths entered config/examples and pre-existing uncommitted files were not included.

## Plan review

The plan covers live taxonomy, duplicate matching, previews, additive versioned writes, Zotero authorization, failure handling, readback, and Markdown handoff. Workspace layout and screening are in `2026-11-07-workspace-layout.md`.
