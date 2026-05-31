---
name: wrap-up
description: Persist a session-end reflection into .claude/memory and run the memory-hygiene sweep. Use when the user signals the session is ending — e.g. "that's all", "done for today", "let's stop here", "see you tomorrow", "wrap up" — or runs /wrap-up manually.
---

# wrap-up — session memory persistence + hygiene sweep

Executes the session-end procedure defined in `CLAUDE.md` § Session Memory
"Session-end rule" and § Archive policy. This skill is the **executor**;
`CLAUDE.md` is the **policy source of truth**. If this file and `CLAUDE.md`
ever diverge, `CLAUDE.md` wins — fix this skill rather than acting on the stale
copy.

Run it confirmation-free when a trigger phrase fires (that is the documented
contract), but still surface what you changed at the end.

## Why this is a skill, not prose

The procedure has a hard ordering and a hard gate that free-form prose cannot
structurally guarantee:

- **step 4 (next-queue sweep) must run before step 5 (recently-merged
  compaction)** — a single pass that moves completed entries into the
  recently-merged list *then* re-evaluates the 5-cap.
- **step 8 (the discipline-test gate) must run before any direct push** — the
  `.claude/memory/` direct-push exception is post-hoc-only, so a discipline
  violation turns `{{DEFAULT_BRANCH}}` red directly instead of being blocked by
  PR CI.

Walk the steps in order. Do not skip the gates.

## Procedure

### 1. Save the reflection
Write the session reflection to `.claude/memory/YYYY-MM-DD.md` (today = the
`currentDate` from context). If the file already exists for today, append a new
`## Session N` section instead of overwriting.

Use the conventional section layout (see `CLAUDE.md`): **Context / Design
decisions / What worked / Corrections / Process table / Deliverables / Handoff
to next session / Notes**.

### 2. Append the index entry
Add **one 1–2 line row** to `.claude/memory/_index.md` using the existing table
columns: `| Date | PR / commit | Outcome | Detail |`. The Detail cell is the
dated filename (e.g. `2026-05-29.md`). Keep each cell within the limit enforced
by `tests/discipline/test_index_entry_compactness.py`. Do NOT essay-ify the
entry; the full narrative lives in the dated file.

### 3. Archive dated logs older than 30 days
Move any `YYYY-MM-DD.md` older than 30 days into `.claude/memory/archive/YYYY-MM/`,
preserving the original text verbatim (zero information loss). Rewrite its
`_index.md` row to a 1-line summary + archive path. Update
`.claude/memory/archive/INDEX.md`.

### 4. Sweep `STATUS.md` next-queue  ⚠️ before step 5
In `.claude/memory/STATUS.md` § `## Next Queue`, remove any item that has been
**completed/merged**, converting it into a new entry under the recently-merged
section. Enforced by `tests/discipline/test_status_next_queue_no_completed.py`.

### 5. Compact `STATUS.md` recently-merged
Keep only the most recent **5** entries inline. Move the overflow (oldest
first) to the end of `.claude/memory/archive/STATUS_MERGED_LOG.md`, verbatim.

### 6. Check `STATUS.md ## Phase` is a single paragraph
`## Phase` must be exactly **one** canonical paragraph. If you added a new
paragraph, delete the old one — do not leave both. Enforced by
`tests/discipline/test_status_phase_single_paragraph.py`.

### 7. Externalize 5+ round disputes
If any spec/ambiguity took **5+ rounds** of review this session, confirm its
resolution is encoded in docs/tests. If not, externalize it now. This is the
core of Experience Externalization and is intentionally a checklist item, not a
test (a round-count test is a fragile proxy that cannot detect the very "encode
forgotten" case it targets). If a `CLAUDE.md` / `AGENTS.md` update is
warranted, propose it to the user.

### 8. Verify discipline tests, then push  ⚠️ gate
Run:

```bash
{{DISCIPLINE_TEST_CMD}}
```

Pin the invocation to the active environment (e.g. `python -m pytest`, not bare
`pytest`) so a stray interpreter on `$PATH` cannot make the gate error out
spuriously.

All tests in `tests/discipline/` MUST pass before pushing. A failure means
drift remains from steps 4–6 — fix the offending file and re-run; do NOT push
red. Only `.claude/memory/` changes may go direct to `{{DEFAULT_BRANCH}}` (the
memory exception); everything else still needs a feature branch + PR.

## Closeout
After pushing, give the user a short summary: which memory files changed, any
archive moves, the discipline-test result, and any 5+ round item you
externalized or are proposing to encode.
