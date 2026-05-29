# tests/discipline

Executable checks for discipline rules in `AGENTS.md` section 5.5.

These tests turn recurring discipline anti-patterns into CI failures:

- `test_status_md_phase_single_paragraph.py`: `.claude/memory/STATUS.md`
  `## Phase` must stay one canonical paragraph.
- `test_status_md_next_queue_no_completed.py`: completed Brief / CSCI /
  D# items must not remain as active markers in `## 次の発行順序`.
- `test_index_md_entry_compactness.py`: `.claude/memory/_index.md` table
  cells must stay compact (500 chars or less), with details moved into dated
  session logs.
- `test_json_schema_version_sync.py`: every CLI envelope `schema_version`
  constant (the producer) must match its documented value in
  `docs/json_schema.md` (producer-output-shape grounding).
- `test_dogfood_dual_case.py`: each `docs/dogfooding_*.md` report must
  demonstrate both PASS and FAIL verdict directions, so a dogfooding pass
  cannot evidence detection power one-sidedly.

Phase 6 closeout (`docs/doc_refactor_planning.md`): the schema-grep and
dual-case dogfood candidates landed as the two tests above. The
round-count-to-encoding candidate was **retired** rather than encoded as a
test -- review-round count exists only as hand-written prose, so any test is a
fragile proxy that cannot detect the very "encode forgotten" case it targets,
and adding it would re-trigger the framework-self-bloat paradox the doc
refactor fought. Its intent (externalize 5+ round disputes) instead lives as a
wrap-up checklist item in `CLAUDE.md` 終了時ルール.
