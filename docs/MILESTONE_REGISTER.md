# RAGForge Milestone Register

This register records the milestone gates and deferred work used to plan M2 and
the transition to M3.

## M0 — Build and package

**Exit gate:** CI builds a wheel in a clean environment, installs that wheel with
its declared runtime dependencies, and imports `ragforge`, `ragforge.parsing`,
and `ragforge.chunking` successfully.

## M1 — Repository ingestion

**Close-out status: implementation and local verification complete.**

### M1-T01 — Snapshot manifest and stable identity

- The manifest includes a sorted per-file inventory, exact-byte size and SHA-256,
  processed/skip status, explicit stable repository ID, and ingestion-config
  hash. The snapshot ID hashes canonical JSON of those inputs and schema version.
- Checkout paths, timestamps, source URIs, and enumeration order are excluded.
- Local ingestion requires callers to supply `repository_id`; there is no
  directory-name fallback.
- Regression tests verify repeatability, path independence, identity and config
  separation, content changes, empty repositories, creation order, and oversized
  skip metadata.

### M1-T04 — GitHub repository source

- `resolve_github` accepts canonical HTTPS GitHub owner/repository URLs and a
  full 40-character commit SHA only. It fetches that exact SHA, verifies both
  `FETCH_HEAD` and detached `HEAD`, and records canonical `github:owner/repo`
  identity and the resolved commit.
- Live verification on 2026-11-07 resolved
  `alan2207/bulletproof-react` at
  `9506629ed003a561c6627735480cce4994244bb4`; resolver metadata and `git
  rev-parse HEAD` matched. Unit tests cover unsupported URLs, moving refs,
  invalid SHAs, fetch failure, and resolved-SHA mismatch.
- ZIP repository identity is `zip:<sha256>` over canonical JSON containing
  sorted normalized file paths, exact sizes, and SHA-256 content hashes. Archive
  filesystem location/name, compression metadata, directory entries, and entry
  order do not contribute. The normalized member paths do contribute. The
  resolver computes per-file hashes while extracting in bounded blocks, after
  validating paths and archive limits.

### M1-T10 — Snapshot diff

- `diff_snapshots` reports added, removed, and modified files in normalized
  path order; identical manifests produce no changes. Cross-repository diffs
  are rejected.
- Tests cover all change types, file metadata/status changes, ordering, and the
  identical-snapshot case.

### M1-T11 — Streaming ingestion API

- `iter_ingestion` yields per-file documents or explicit skip events in sorted
  path order, followed by a completion event with manifest and aggregate counts.
- Document contents are not accumulated; only the current file and compact
  per-file manifest metadata are retained. Per-file reads remain bounded by the
  configured file-size limit; oversized files are hashed in bounded blocks and
  emitted as skips.
- Tests cover incremental consumption, deterministic output and manifest,
  oversized skips, and a read error followed by continued processing.

### M1 verification evidence

- ZIP regressions: `pytest tests/integration/ingestion/test_zip_ingestion.py -q`
  — **20 passed**, including path/name independence, archive-order independence,
  changed-content identity, unsafe paths, limits, and cleanup.
- Local and manifest regressions — **17 passed**; M2 golden, symbol/overload,
  and byte-coverage regressions — **21 passed**.
- Full suite: `pytest -q` — **143 passed**.
- Ruff: `ruff check src tests ingestion` — passed.
- Mypy: parsing/chunking (26 files) and ingestion (14 files) — no issues.
- Clean build: isolated `python -m build` produced wheel and sdist.
- Fresh-environment install/import: wheel installed with declared dependencies;
  `ragforge`, `ragforge.ingestion`, `ragforge.parsing`, and
  `ragforge.chunking` imported from site-packages outside the source checkout.
- `git diff --check` passed.

Known limitations: local repository identity is caller-assigned and must be
managed by the caller. ZIP repository identity represents the normalized archive
file tree, so repackaging the same tree is stable, while any changed archive file
entry changes the repository identity. Streaming keeps one compact manifest
entry per discovered file in memory so it can emit the final content-addressed
manifest; document contents are not retained. Repository scanning intentionally
excludes configured directories, hidden paths, unsupported extensions, and
symlinks.

## M2 — Parsing and structure-aware chunking

**M2-T13 validation scope:** validate at least one real repository per supported
language: Python, JavaScript, TypeScript, TSX, and Java. Record repository
revision, source-file accounting, parser errors, span integrity, determinism,
and chunk-size distributions.

**Exit gate:** all language golden fixtures pass; leaf and residue chunks cover
every source byte exactly once; repeated runs produce byte-identical output;
malformed files are reported and do not stop other files; symbol keys remain
stable across body edits and overloads remain distinct; CI runs static type
checks.

### Run B.1 validation record

- Python: the RAGForge source repository smoke test covers its 45 `.py` source
  files with exact byte coverage and deterministic repeat output.
- TypeScript and TSX: 175 `.ts` and 241 `.tsx` files from
  [`alan2207/bulletproof-react`](https://github.com/alan2207/bulletproof-react),
  revision `9506629ed003a561c6627735480cce4994244bb4`.
- Java: 50 `.java` files from
  [`spring-projects/spring-petclinic`](https://github.com/spring-projects/spring-petclinic),
  revision `500158f732419217507c7656904b8e6aa1bcc0d6`.
- JavaScript baseline: 24 `.js` and `.jsx` files from the previously validated
  local project.
- Each checked out revision processed every discovered source file without
  skips. All spans, byte coverage, and repeated-run comparisons passed.
- Malformed `.js`, `.ts`, `.tsx`, and `.java` examples reported parser errors,
  produced fallback chunks, and did not prevent neighboring valid files from
  being processed.
- Clean wheel installation and imports were verified in a fresh virtual
  environment. CI repeats build, install, and import checks on every run.

M1 close-out remains a required milestone before M3 begins.

## M3 — Evaluation foundation

- **M3-T01:** `evaluation/repositories.json` pins three varied repositories by
  full Git commit SHA, records source-file counts and language coverage, and
  marks the familiar RAGForge repository. Each `snapshot_id` is the SHA-256 of
  the normalized repository URL and commit SHA. The two external checkout
  revisions were verified against their recorded commits.
- **M3-T02:** `schemas/gold_set.schema.json` defines the JSONL question record;
  `ragforge.evaluation.gold_set` validates line-range or symbol spans and loads
  JSONL while rejecting malformed records and duplicate question IDs.

M3-T03 and later tasks remain open. No retrieval baseline or metric work is
included in this step.
