# Portable research workspaces and Zotero routing

Date: 2026-11-07

## Purpose

Make `paperSearch` reusable from independent research folders. A new folder should have a predictable place for ideas, directions within each idea, demos, reproductions, literature lists, search logs, and reading notes. An LLM using `paperSearch` should find the same instructions and examples in the tool repository without the user restating them. Zotero remains the bibliographic and PDF library; workspace Markdown records research judgments and links to Zotero items.

## Existing constraints

- `paperSearch` currently writes search results to `--results-dir` and downloads to `--output`, both relative to the caller unless absolute paths are supplied. It has no workspace, idea, direction, or Zotero concept.
- The current Star workspace contains four idea directories, while its top-level navigation lists two. It has an existing idea-specific literature CSV and many reading notes. Existing files and links must remain in place during initial adoption.
- The live Zotero local API currently exposes 57 active collections. The numbered taxonomy includes roots such as `01 端侧大模型系统`, `06 卫星计算与网络`, and `10投机解码`, numbered children such as `01.2` and `06.3`, and one `03.3.1` grandchild. Some names under `10投机解码` still start `05.6`–`05.8`; parentage must come from the live tree, not parsed numbering. A raw SQLite table contains more historical rows, so it is not the collection authority.
- `paperSearch` is a separate Git repository with pre-existing modified and untracked files. Implementation must preserve them.

## Recommended approach

Use a project-local configuration plus checked-in templates and examples. The CLI discovers a `.papersearch.toml` from the current directory upward, or accepts an explicit `--workspace` path. It never hard-codes the Star path. Without a workspace, existing search and download behavior remains unchanged.

Alternative 1, documentation alone, would guide an LLM but not make CLI output routing reliable. Alternative 2, a global database or service, would couple independent research folders and add deployment work. The project-local approach gives consistent behavior with small changes.

## Workspace layout

```text
research-workspace/
  .papersearch.toml
  README.md
  ideas/
    README.md
    <idea>/
      README.md
      directions/
        <direction>/
          README.md
          papers.md
          search_logs/
          reading_notes/
          incoming/
  demos/
    README.md
  reproductions/
    README.md
  literature/
    README.md
  archive/
    README.md
```

The top-level `ideas/`, `demos/`, and `reproductions/` are different kinds of work, linked by Markdown rather than duplicated. `ideas/<idea>/README.md` states the question, current judgment, evidence gaps, status, and next decision. A direction README narrows that question and links its literature and search history. Existing Star paths stay where they are; navigation pages can point to them during incremental adoption.

The direction's `papers.md` is a fixed-format Markdown table. Each row records paper title and stable identifier (DOI/arXiv and Zotero item key when present), verified venue and publication status, relevance/role, screening decision and reason, reading status and scope, local reading note, Zotero collections, and last verification date. One Zotero item may appear in multiple direction tables; no PDF copy is made for each direction. Unknown Zotero links are marked `pending`, not invented.

The `search_logs/` template records date, source, exact query, purpose, raw result path, screening counts, and follow-up. `reading_notes/` uses a short card with question, assumptions, method, evidence, limitations, and relationship to the direction. Templates are not claims that a paper was fully read.

## CLI and documentation

- `paper-downloader init --workspace <path>` creates missing workspace configuration, navigation pages, and empty category directories. It does not overwrite existing files.
- `paper-downloader add-idea <slug> --workspace <path>` and `add-direction <slug> --idea <idea> --workspace <path>` create an idea or direction from templates and update navigation. Slugs are validated; a search/download does not silently create a misspelled direction.
- `search` and `download` accept `--workspace`, `--idea`, and `--direction`. With a valid context, raw search outputs go under that direction's `search_logs/`; download files and state go to its `incoming/`. These files are staging artifacts, not the canonical Zotero library. Existing explicit `--results-dir`/`--output` overrides remain valid and are reported clearly.
- `paperSearch` contains `examples/research-workspace/`, reusable templates, a search policy, and one `LLM_WORKFLOW.md`. README, USAGE, LLM_QUICKSTART, and AGENTS point to this workflow. The workflow says exactly when to update `papers.md`, how to mark uncertain metadata, and how to link demos/reproductions.

The workspace config stores layout version and project-specific venue lists/policy paths. It does not store Zotero credentials, local absolute paths, or a copied collection tree.

## Search and screening policy

The rolling primary window is three years from the search date. Formally published work in that window is normally promoted to the core related-work list only after venue and relevance checks. Each workspace defines field-appropriate quality tiers (A/B) with examples; Scholar text alone does not establish venue or peer-review status. Recent work, initially defined as the last 12 months, may enter a provisional candidate list from a wider set of conferences, workshops, early access, preprints, or technical reports, but its status is explicit and it cannot be presented as equivalent to a strong peer-reviewed source. Older foundational work is separately marked. A directly relevant paper that threatens novelty is retained even when its venue is weak, with that reason recorded. Filtering happens after retrieval so weak-venue near neighbors are not hidden from novelty checks.

This default is adapted from Star's existing `screening_protocol.md`; the per-workspace venue list must be reviewed for its field. A search log records the exact date and three-year boundary.

## Zotero routing

Zotero collections classify paper topics, not the workspace's ideas. Before every classification, the tool reads the live Zotero collection tree through the local API. The current numbered names are examples, not a hard-coded taxonomy; collection keys and parent relationships identify destinations. The tool never writes Zotero's SQLite database.

For a candidate paper:

1. Match existing Zotero items by verified DOI, then normalized title and version relationship. Ambiguous matches require review; never create a duplicate merely because the first lookup missed.
2. If absent, record `pending Zotero import` in `papers.md` and stage the verified PDF/metadata. The first version of this feature documents import through Zotero's own identifier/Connector workflow; it does not fabricate incomplete metadata or automatically import a PDF as a finished citation.
3. For an existing item, produce a routing preview containing the current memberships, proposed existing root/subcollections, paper evidence, and a reason. Reuse existing collections. If no child fits, choose the root or `09 杂项与待归类` for unresolved cases and record a proposed new child separately. Do not create, rename, delete, or renumber collections automatically.
4. On explicit `zotero apply` for the preview, request local API write authorization through Zotero's own dialog. Re-fetch the item's version and memberships, union the approved collections with existing ones, and write with a version precondition. Never replace the collection array with only the new target. Report conflicts rather than silently retrying against changed state.
5. Re-read the item and collection membership after a successful write, then update the direction's `papers.md` with the actual Zotero key and collection path. A write failure leaves the Markdown row marked pending rather than claiming success.

The local API can be unavailable or disabled. In that case workspace Markdown work continues, while live routing preview and `apply` stop with the required Zotero setting. Secrets remain in process memory and are never written to config, logs, prompts, or the repository.

## Errors, adoption, and verification

Unknown idea/direction, malformed config, invalid slugs, mismatched workspace version, missing Zotero item, ambiguous DOI/title match, unavailable API, write denial, and version conflict all stop with an actionable message. Existing CLI calls without a workspace retain their old paths and behavior.

Initial adoption of Star updates navigation and a few active direction lists first; it does not move or rewrite the whole literature corpus. Existing `local_corpus.csv` can be used as a migration source, but its IDs and metadata are not silently treated as globally canonical.

Verification covers: fresh independent workspace creation; idempotent init; existing directory preservation; idea/direction routing; legacy CLI compatibility; Markdown template consistency; three-year and recent-window policy examples; Zotero tree parentage despite misleading numeric prefixes; duplicate/ambiguous matching; membership union; denied authorization and version conflict; post-write readback. No live Zotero write occurs in tests.

## Out of scope for the first implementation

- Automatic renumbering or cleanup of the user's existing Zotero collection tree.
- Full migration, deduplication, or rewriting of all Star reading notes and PDF caches.
- Automatic venue-quality judgment from search snippets alone.
- Automatic import of incomplete bibliographic entries or PDFs into Zotero.
- A central service or database shared by independent research folders.
