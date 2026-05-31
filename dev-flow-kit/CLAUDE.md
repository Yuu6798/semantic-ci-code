# CLAUDE.md — {{PROJECT_NAME}}

This file defines the repository-level operating policy for {{DESIGN_AGENT}} and
related agent workflows. Keep product details in `docs/<topic>.md` and keep
task-handoff format rules in `AGENTS.md`.

## Project Overview

{{PROJECT_NAME}} — {{PROJECT_TAGLINE}}.

<!-- Replace this section with a short product description and any hard scope
guards (what this project is NOT, and any inviolable invariants such as
determinism, no network calls, etc.). Scope guards stated here are the
invariants {{IMPL_AGENT}} must escalate on under AGENTS.md §3.5. -->

## Current Status

The day-to-day project status (current phase, recent merged PRs, and the active
next-issue queue) lives in `.claude/memory/STATUS.md` so this policy doc stays
stable while the snapshot can be edited freely.

- Live status: `.claude/memory/STATUS.md`
- Per-session log: `.claude/memory/_index.md` + the dated `YYYY-MM-DD.md` files

## Required Reading Before Editing

{{DESIGN_AGENT}} (and any agent acting in this repository) MUST consult these
before taking any action that changes the repo. Reading load is **tiered** to
keep startup attention budget bounded. Read up to the tier that matches your
task scope.

### Tier A — Always required at startup

1. **This file (`CLAUDE.md`)** — repository policy and operating contract.
2. **`.claude/memory/STATUS.md` `## Phase` (1 paragraph) + `## Next Queue`** —
   current project state + active next-issue queue.
3. **`.claude/memory/_index.md` — the most recent ~5 entries** (1–2 line index
   form; essay entries are a bloat anti-pattern).
4. **`AGENTS.md` §1–§4** — Message Flow + Task Brief / Completion Summary format
   + Escalation Rules + Branch Rules.

Skipping Tier A and inventing context from scratch is a documented recurring
failure mode. If a Tier A doc is stale or incomplete, surface that in the
response rather than acting without it.

### Tier B — Required before drafting a new brief

1. **`AGENTS.md` §5 Experience Externalization Discipline** — principle +
   anti-pattern list + enforcement map.
2. **The relevant `docs/<topic>_planning.md` section** for the brief/phase.

### Tier C — On-demand for the specific task

- Full read of the relevant planning doc.
- The most recent ~3 dated session logs (`.claude/memory/YYYY-MM-DD.md`).
- The design spec section relevant to the surface you are changing.

### Tier D — Debug / archeology only

- `.claude/memory/archive/` — compacted historical session logs.
- Dated session logs older than 30 days.

## Tech Stack

- Language / runtime: {{LANG_RUNTIME}}
- Install: `{{INSTALL_CMD}}`
- Lint: `{{LINT_CMD}}`
- Test: `{{TEST_CMD}}`

## Workflow

This repository separates design and implementation (see `AGENTS.md`):

- {{DESIGN_AGENT}}: design, specification, review judgment, phase planning.
- {{IMPL_AGENT}}: implementation, tests, PR creation, Completion Summary.
- User: final approval and handoff trigger.

Default cycle:

1. {{DESIGN_AGENT}} issues a Task Brief using `AGENTS.md`.
2. User gives the brief to {{IMPL_AGENT}}.
3. {{IMPL_AGENT}} implements on `{{IMPL_BRANCH_PREFIX}}<topic>`, runs checks, and
   prepares a PR with a Completion Summary.
4. User shares the PR back to {{DESIGN_AGENT}}.
5. {{DESIGN_AGENT}} reviews and either approves, requests repair, or emits the
   next brief.

## Coding Conventions

- Keep behavior deterministic: the same input should produce the same output.
- Add dependencies only when allowed by the active brief.
- Prefer structured parsing over ad hoc string manipulation.
- Keep the README concise; move detailed design into `docs/`.

## Session Memory (persistent-memory workflow)

Long-running design conversations are recorded in `.claude/memory/` so that
later sessions can resume without losing context.

### Mechanism

- Location: `.claude/memory/`
- Files: `YYYY-MM-DD.md` (if multiple sessions land on one day, append a
  `## Session N` section to the same file).
- Index: `_index.md` holds one 1–2 line row per session.

### Startup rule

1. Read `_index.md` (recent entries) at the start of a session to recover prior
   decisions.
2. Dive into the most recent ~3 summaries as needed.
3. Answer questions about past design decisions from the memory first.

### Session-end rule (auto-trigger)

When the user signals intent to end the session, immediately run the wrap-up
procedure (no confirmation needed). The `.claude/skills/wrap-up` skill is the
**executor**; this section is the **policy source of truth**. If they diverge,
this file wins.

Trigger phrases (examples): "that's all", "done for today", "let's stop here",
"see you tomorrow", "wrap up", or the manual `/wrap-up`.

Wrap-up steps (the skill walks these in order; do not skip the gates):

1. **Save the reflection** to `.claude/memory/YYYY-MM-DD.md` (new file, or a new
   `## Session N` section if today already exists). Use the conventional
   layout: Context / Design decisions / What worked / Corrections / Process
   table / Deliverables / Handoff to next session / Notes.
2. **Append the index entry** — one 1–2 line row to `_index.md`
   (`| Date | PR / commit | Outcome | Detail |`). Keep cells compact.
3. **Archive dated logs older than 30 days** into `.claude/memory/archive/`,
   preserving the original text verbatim; rewrite the `_index.md` row to a
   1-line summary + archive path; update `archive/INDEX.md`.
4. **Sweep `STATUS.md` `## Next Queue`** — remove any item that has been
   completed/merged, converting it into a new `## 直近 merged` / `## Recently
   merged` entry. ⚠️ Run this **before** step 5.
5. **Compact `STATUS.md` recently-merged** — keep only the most recent 5 entries
   inline; move overflow (oldest first) to `archive/STATUS_MERGED_LOG.md`.
6. **Check `STATUS.md ## Phase` is a single paragraph** — if you added a new
   paragraph, delete the old one.
7. **Externalize 5+ round disputes** — if any spec took 5+ rounds of review this
   session, confirm its resolution is encoded in docs/tests; if not, do it now.
   Propose any `CLAUDE.md` / `AGENTS.md` update warranted.
8. **Verify discipline tests, then push** ⚠️ gate — run
   `{{DISCIPLINE_TEST_CMD}}`. All `tests/discipline/` tests MUST pass before
   pushing. Only `.claude/memory/` changes may go direct to `{{DEFAULT_BRANCH}}`
   (the memory exception); everything else still needs a feature branch + PR.

### Archive policy (compaction TTL)

| Artifact | TTL | Destination |
|---|---|---|
| dated session log `YYYY-MM-DD.md` | 30 days | `archive/YYYY-MM/` (verbatim) |
| `_index.md` row | same | rewritten to 1-line summary + archive path |
| `STATUS.md` recently-merged entry | beyond the most recent 5 | `archive/STATUS_MERGED_LOG.md` |
| `STATUS.md` next-queue completed entry | at merge time | converted to a recently-merged entry |

### Git Workflow exception

The `.claude/memory/` operational logs are the **only** exception to the
"feature branch + PR" rule and may be pushed directly to `{{DEFAULT_BRANCH}}`.
Because this path is post-hoc only (no PR CI to block a bad push), the wrap-up
discipline-test gate (step 8) MUST be run before every direct memory push.

## Experience Externalization

AI development (design agent / implementation agent / parallel agents) does not
inherit tacit knowledge across sessions. The only way to keep results
reproducible is to force experience into **explicit artifacts**: docs (planning
/ spec / guides), tests (invariant tests, producer-spec contract tests),
checklists (the brief-drafting checklist), and pattern catalogs. Experience
kept as an individual's or agent's "feel" does not work in AI development.

The detailed three-tier classification, the review-round-count principle, the
maintenance practice, and the anti-pattern list live in
`AGENTS.md` § Experience Externalization Discipline. Read it verbatim before
drafting a new brief or introducing a new architectural pattern.
