# RAGForge Milestone Register

This register records the milestone gates and deferred work used to plan M2 and
the transition to M3.

## M0 — Build and package

**Exit gate:** CI builds a wheel in a clean environment, installs that wheel with
its declared runtime dependencies, and imports `ragforge`, `ragforge.parsing`,
and `ragforge.chunking` successfully.

## M1 — Repository ingestion

M1 is not considered fully closed until the following deferred tasks are
completed before M3:

- **M1-T01:** snapshot manifest and stable snapshot identifiers.
- **M1-T04:** GitHub repository source.
- **M1-T10:** diff ingestion.
- **M1-T11:** streaming ingestion API.

Snapshot identifiers are the priority because M3 evaluation runs depend on
reproducible repository revisions.

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
