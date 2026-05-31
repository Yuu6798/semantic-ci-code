# Project Status (live tracker)

This file is the live, daily-changing snapshot of the project: current phase,
recently merged PRs, and the next-issue queue. It lives in `.claude/memory/` so
the policy doc (`CLAUDE.md`) can stay stable while this file changes freely.

Update rules:

- This file may be edited directly on `{{DEFAULT_BRANCH}}` under the
  `.claude/memory/` exception (see `CLAUDE.md` § Session Memory → Git Workflow
  exception).
- After each merged PR or session wrap-up, refresh **Recently merged** and
  **Next Queue** here, and append a 1-line entry to `_index.md`.
- When an item is completed, move it from **Next Queue** to **Recently merged**.

---

## Phase

<!-- Exactly ONE paragraph. When the phase changes, replace this paragraph;
do not append a second one (enforced by tests/discipline). -->
Project bootstrap. The development-flow scheme (design/implementation split +
session-memory workflow + wrap-up protocol) has been ported in from
dev-flow-kit and is being adapted to {{PROJECT_NAME}}. No feature phase has
started yet; the next queue holds the first planned units of work.

## Recently merged

<!-- Keep only the most recent 5 entries inline; archive the overflow to
archive/STATUS_MERGED_LOG.md (oldest first). -->

_None yet._

## Next Queue

<!-- Active, not-yet-completed units of work. Remove an item the moment it
merges and convert it into a "Recently merged" entry. Do NOT leave completed
items here (enforced by tests/discipline). -->

- **Adapt the ported policy docs** to {{PROJECT_NAME}}: fill remaining
  `{{...}}` placeholders in `CLAUDE.md` / `AGENTS.md`.
- **Seed the first real Task Brief** for the initial feature.
