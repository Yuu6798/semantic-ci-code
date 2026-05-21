# tests/discipline

Executable checks for discipline rules in `AGENTS.md` section 5.5.

These tests turn recurring memory-hygiene anti-patterns into CI failures:

- `test_status_md_phase_single_paragraph.py`: `.claude/memory/STATUS.md`
  `## Phase` must stay one canonical paragraph.
- `test_status_md_next_queue_no_completed.py`: completed Brief / CSCI /
  D# items must not remain as active markers in `## 次の発行順序`.
- `test_index_md_entry_compactness.py`: `.claude/memory/_index.md` table
  cells must stay compact (500 chars or less), with details moved into dated
  session logs.

Future hardening candidates from `docs/doc_refactor_planning.md` Phase 6:

- schema-grep check for producer-output-shape grounding
- dual-case dogfood check requiring both fail and pass cases
- round-count-to-encoding check for specs clarified during long reviews
