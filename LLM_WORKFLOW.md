# Research workflow for assistants

This is the reusable protocol for any independent folder using `paperSearch`. See [the worked example](examples/research-workspace/README.md). The folder's `.papersearch.toml`, `literature/venue-policy.md`, and idea/direction READMEs provide project-specific context. The tool repository is not a research output folder.

## Start a workspace and choose a direction

```powershell
paper-downloader init --workspace C:\path\to\research
paper-downloader add-idea satellite_llm --workspace C:\path\to\research
paper-downloader add-direction service_pool --idea satellite_llm --workspace C:\path\to\research
```

Each idea states its research question, current judgment, evidence gaps, and next decision. Each direction has its own `papers.md`, `search_logs/`, and `reading_notes/`. Demos go in `demos/`; published-paper replications go in `reproductions/`. Link them to relevant directions instead of mixing their files with literature. Existing workspaces may link old paths rather than moving them.

When running from outside the direction, pass `--workspace`, `--idea`, and `--direction` to `search` or `download`. Inside the direction, the tool detects its context. An unknown direction is an error; register it before running the search.

## Search, screen, and record

1. Read the direction question and venue policy. Record the exact search date. The main candidate window is the preceding **three years**. The latest **12 months** may include wider-venue conference papers, workshops, early access, and preprints as provisional candidates. Older foundational papers are separate.
2. Search broadly enough to find direct novelty threats, even from weaker venues. Do not apply the venue rule to hide raw search hits. Verify title, authors, date, venue, main conference versus workshop, DOI, and publication status against official proceedings or publisher records before calling a venue A/B. Each workspace defines its own A/B venues; Scholar snippets do not establish quality.
3. Put formally published, directly relevant A/B papers in the core related-work list. Put recent lower-tier or unreviewed work in a provisional list with status. Keep direct novelty threats even if their venue is weaker, and explain why. Do not use citation count as a hard threshold.
4. Write the exact query, source, date, raw result path, counts, and screening decisions in `search_logs/` using the [search-log template](paper_downloader/templates/search-log.md). A search failure or zero hits is recorded, never interpreted as proof of absence.
5. Update the direction's `papers.md` using its fixed columns. Use `candidate`, `metadata_checked`, `abstract_screened`, `fulltext_acquired`, `fulltext_read`, or `excluded` as the reading/screening state. Record sections actually read. A downloaded PDF is not a fully read paper. Write a separate reading card only for meaningful reading, following the [reading-note template](paper_downloader/templates/reading-note.md).

## Zotero is the source of truth for citations and PDFs

Zotero collections represent **paper topics**, not idea folders. Read the live collection tree for each classification task; never infer parentage from numeric prefixes. Reuse an existing numbered root and child when appropriate. A single Zotero item may belong to several topic collections. Preserve its existing memberships. Do not create, rename, or renumber collections to match an idea automatically.

Before import, look for a verified DOI match and then title/version match. If the paper is absent or ambiguous, keep `Zotero key` as `pending` in `papers.md`. Use Zotero's identifier entry or Connector to import verified metadata and PDF; do not invent a completed citation from a Scholar snippet. The CLI's `zotero collections`, `zotero plan`, and `zotero apply` commands inspect, preview, and apply an existing item's collection routing. Give a reason based on the paper content, review the preview, then apply. Update `papers.md` with the real item key and collection paths only after readback confirms the write. On API failure, leave the row pending.

Zotero's local write authorization is granted in Zotero itself. Never read or expose browser profiles, passwords, cookies, or local API keys. Do not edit `zotero.sqlite`.
