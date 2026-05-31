# tests/discipline

Executable checks for the memory-hygiene rules in `AGENTS.md §5.4`. These turn
recurring discipline anti-patterns into CI failures:

- `test_status_phase_single_paragraph.py`: `.claude/memory/STATUS.md` `## Phase`
  must stay one canonical paragraph (replace it on a phase change; never append
  a second one).
- `test_status_next_queue_no_completed.py`: completed items must not remain as
  active markers in the next-queue section — they belong in recently-merged.
- `test_index_entry_compactness.py`: `.claude/memory/_index.md` table cells must
  stay compact, with details moved into dated session logs.

## Placement

These tests resolve the repo root as `Path(__file__).resolve().parents[2]`
(see `_config.py`). Keep them at **`<repo>/tests/discipline/`** so that path
math is correct.

## Configuration

`_config.py` holds every repo/language-specific constant: the memory file
paths, the `STATUS.md` heading names, the completion-marker substrings, any
narrative sub-headings to skip, and the max index-cell length. Adapt those to
your tracker's language; the test logic itself is language-agnostic.

## Run

```bash
{{DISCIPLINE_TEST_CMD}}
```

Pin the invocation to the active environment (e.g. `python -m pytest`) so a
stray interpreter on `$PATH` cannot make the gate error out spuriously. This is
the same gate `wrap-up` step 8 runs before any direct memory push.

## What was intentionally NOT generalized

The source repo also had domain-specific discipline tests (e.g. a JSON-schema
version-sync check and a dogfood dual-case check). Those depend on that repo's
product and were left out. Re-derive equivalents for your own domain — the
pattern (turn a recurring anti-pattern into a parsed, fixture-backed test) is
the reusable part. Note also: a "review-round count" check was deliberately
*not* encoded as a test, because round count exists only as hand-written prose
and any test would be a fragile proxy that cannot detect the very "encode
forgotten" case it targets. That rule lives as a `wrap-up` checklist item
instead.

## Fixtures

Each parser is backed by both a positive fixture (a file that should pass) —
the live memory files — and negative fixtures under `fixtures/` that the parser
must reject, so the parser itself cannot silently rot into a no-op.
