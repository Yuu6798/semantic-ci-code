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
- `test_d_class_status_sync.py`: public project-status documents must match the
  canonical D-class tracker before claiming registry closure.
- `test_dogfood_dual_case.py`: each registered case/verdict-matrix dogfood
  report must demonstrate both PASS and FAIL in its `Verdict` column (column
  parsed, not free prose), so a dogfooding pass cannot evidence detection
  power one-sidedly.
- `test_pr_body_dogfood_disclosure.py`: PR bodies must disclose dogfooding
  status. `Status: performed` requires command/result/evidence, and
  `Status: skipped` requires an explicit reason. GitHub Actions enforces the
  same rule in a trusted `pull_request_target` workflow that does not execute
  PR-controlled code.
- `test_claude_md_line_cap.py`: `CLAUDE.md` must stay ≤ 300 lines. It is
  always-loaded policy (per-turn fixed cost + instruction-following risk past
  ~150-200 lines), so reference detail (the `src/` tree, the session-memory
  procedure) is offloaded to `docs/repository_layout.md` and the wrap-up skill,
  leaving pointers in `CLAUDE.md`. Enforced via the wrap-up gate (step 8).

Phase 6 closeout (`docs/archive/doc_refactor_planning.md`): the schema-grep and
dual-case dogfood candidates landed as the two tests above. The
round-count-to-encoding candidate was **retired** rather than encoded as a
test -- review-round count exists only as hand-written prose, so any test is a
fragile proxy that cannot detect the very "encode forgotten" case it targets,
and adding it would re-trigger the framework-self-bloat paradox the doc
refactor fought. Its intent (externalize 5+ round disputes) instead lives as a
wrap-up checklist item in the wrap-up skill (`.claude/skills/wrap-up/SKILL.md`
step 7).
