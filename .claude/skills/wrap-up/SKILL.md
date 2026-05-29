---
name: wrap-up
description: Persist a session-end reflection into .claude/memory and run the memory-hygiene sweep for the semantic-ci-code repo. Use when the user signals the session is ending — e.g. 「今日はここまで」「今日は終わり」「セッション終了」「また明日」「お疲れ様」「done for today」「that's all」 — or runs /wrap-up manually.
---

# wrap-up — session memory persistence + hygiene sweep

Executes the session-end procedure defined in `CLAUDE.md` § Session Memory
「終了時ルール (自動トリガー)」 and § Archive policy. This skill is the
**executor**; `CLAUDE.md` is the **policy source of truth**. If this file
and `CLAUDE.md` ever diverge, `CLAUDE.md` wins — fix this skill rather than
acting on the stale copy.

Run it confirmation-free when a trigger phrase fires (that is the documented
contract), but still surface what you changed at the end.

## Why this is a skill, not prose

The procedure has a hard ordering and a hard gate that散文では構造的に
保証されない:

- **step 4 (`次の発行順序` sweep) must run before step 5 (`直近 merged`
  compaction)** — a single pass that moves completed entries into 直近
  merged *then* re-evaluates the 5-cap (PR #92 review).
- **step 8 (`python -m pytest tests/discipline/`) must run before any direct push** —
  the `.claude/memory/` main-push exception is post-hoc-only, so a discipline
  violation turns main red directly instead of being blocked by PR CI.

Walk the steps in order. Do not skip the gates.

## Procedure

### 1. Save the reflection
Write the session reflection to `.claude/memory/YYYY-MM-DD.md` (today =
the `currentDate` from context). If the file already exists for today,
append a new `## Session N` section instead of overwriting.

Use the conventional section layout (see `CLAUDE.md` § サマリーの構成):
**コンテキスト / 設計判断 / 成功パターン / 修正・訂正 / 工程サマリー (table) /
成果物 / 次セッションへの引き継ぎ / メモ**.

### 2. Append the index entry
Add **one 1–2 line row** to `.claude/memory/_index.md` using the existing
table columns: `| Date | PR / commit | Outcome | Detail |`. The Detail cell
is the dated filename (e.g. `2026-05-29.md`). Keep each cell ≤ 500 chars —
this is enforced by `tests/discipline/test_index_md_entry_compactness.py`.
Do NOT essay-ify the entry; full narrative lives in the dated file.

### 3. Archive dated logs older than 30 days
Move any `YYYY-MM-DD.md` older than 30 days into
`.claude/memory/archive/YYYY-MM/`, preserving the original text verbatim
(zero information loss). Rewrite its `_index.md` row to a 1-line summary +
archive path. Update `.claude/memory/archive/INDEX.md`.

### 4. Sweep `STATUS.md` 次の発行順序  ⚠️ before step 5
In `.claude/memory/STATUS.md` § `## 次の発行順序`, remove any Brief / CSCI /
D# item that has been **completed/merged**, converting it into a new entry
under `## 直近 merged`. Enforced by
`tests/discipline/test_status_md_next_queue_no_completed.py`.

### 5. Compact `STATUS.md` 直近 merged
Keep only the most recent **5** entries inline under `## 直近 merged`.
Move the overflow (oldest first) to the end of
`.claude/memory/archive/STATUS_MERGED_LOG.md`, verbatim.

### 6. Check `STATUS.md ## Phase` is a single paragraph
`## Phase` must be exactly **one** canonical paragraph. If you added a new
paragraph, delete the old one — do not leave both. Enforced by
`tests/discipline/test_status_md_phase_single_paragraph.py`.

### 7. Externalize 5+ round disputes
If any spec/ambiguity took **5+ rounds** of review or 壁打ち this session,
confirm its resolution is encoded in docs/tests. If not, externalize it now.
This is the core of Experience Externalization and is intentionally a
checklist item, not a test (a round-count test is a fragile proxy — see
`tests/discipline/README.md`). If a `CLAUDE.md` / `AGENTS.md` update is
warranted, propose it to the user.

### 8. Verify discipline tests, then push  ⚠️ gate
Run:

```bash
python -m pytest tests/discipline/ -q --no-cov
```

Use `python -m pytest`, not bare `pytest`: a bare `pytest` on `$PATH` can
resolve to an interpreter without the `pytest-cov` plugin, making `--no-cov`
an unrecognized argument and the gate error out spuriously. `python -m`
pins the invocation to the active environment's pytest.

All tests in `tests/discipline/` MUST pass before pushing. A failure means
drift remains from steps 4–6 — fix the offending file and re-run; do NOT
push red. Only `.claude/memory/` changes may go direct to main (the memory
exception); everything else still needs a feature branch + PR.

## Closeout
After pushing, give the user a short summary: which memory files changed,
any archive moves, the discipline-test result, and any 5+ round item you
externalized or are proposing to encode.
