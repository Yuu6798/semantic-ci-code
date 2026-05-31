# AGENTS.md — {{DESIGN_AGENT}} × {{IMPL_AGENT}} Handoff Protocol

This repository uses a **design / implementation split**. {{DESIGN_AGENT}} owns
design briefs and review judgment. {{IMPL_AGENT}} owns implementation, tests,
and PR preparation. The user triggers handoff between them.

Both agents should read this file before starting repository work.

## Message Flow

```text
{{DESIGN_AGENT}} -> Task Brief -> User -> {{IMPL_AGENT}}
{{DESIGN_AGENT}} <- Completion Summary <- User <- PR URL <- {{IMPL_AGENT}}
```

Agents do not need to communicate directly. The user moves the structured
messages between them.

## 1. Task Brief: {{DESIGN_AGENT}} to {{IMPL_AGENT}}

{{DESIGN_AGENT}} should issue tasks in this format so the user can paste them
directly into {{IMPL_AGENT}}. Target task size is roughly 0.5 to 2 days.

````markdown
# Task Brief: <ID> - <short title>

## Phase
<design phase or document reference>

## Goal
<1-2 sentences defining completion>

## Acceptance Criteria
- [ ] Verifiable condition 1
- [ ] Verifiable condition 2

## Scope
- IN: <files or modules {{IMPL_AGENT}} may change>
- OUT: <files, behavior, or decisions {{IMPL_AGENT}} must not change>

## Allowed Dependencies (optional)
<Dependencies {{IMPL_AGENT}} may add. If absent, new dependencies require escalation.>

## Implementation Hints (optional)
<Suggested approach, design references, existing patterns>

## Required Outputs
- Branch name: `{{IMPL_BRANCH_PREFIX}}<topic>`
- PR title: <Conventional Commits style>
- Expected files changed: <list>
- Required tests: <test expectations>

## Done When
- All acceptance criteria are checked
- `{{LINT_CMD}}` passes
- `{{TEST_CMD}}` passes
- PR body starts with a Completion Summary
````

## 2. Completion Summary: {{IMPL_AGENT}} to {{DESIGN_AGENT}}

{{IMPL_AGENT}} should place this at the top of the PR body.

````markdown
# Completion Summary: <Task ID>

## Phase
<copied from Task Brief>

## What Changed
- <high-level change 1>
- <high-level change 2>

## Acceptance Criteria Status
- [x] Condition 1 - <evidence>
- [ ] Condition 2 - <reason if incomplete>

## Tests
- Added: <test names or count>
- Result: <pass / fail / skipped>

## Files Changed
<git diff --stat equivalent>

## Deviations from Brief
<None, or list deviations>

## Open Questions / Deferred
<Questions for {{DESIGN_AGENT}} or next phase>

## Next Handoff
<What {{DESIGN_AGENT}} should review next>
````

## 3. Escalation Rules

{{IMPL_AGENT}} should stop and report a blocked Completion Summary when:

1. Acceptance criteria are technically impossible.
2. The brief requires an unstated design decision.
3. Existing tests fail in a way that suggests a behavior regression.
4. A new dependency is needed but not listed in Allowed Dependencies.
5. The implementation would violate a core invariant of the project (e.g.
   determinism, auditability, or any "do not do X" guard stated in `CLAUDE.md`).

## 4. Branch Rules

- {{DESIGN_AGENT}} design branches: `{{DESIGN_BRANCH_PREFIX}}<topic>`
- {{IMPL_AGENT}} implementation branches: `{{IMPL_BRANCH_PREFIX}}<topic>`
- Direct changes on `{{DEFAULT_BRANCH}}` are reserved for explicit
  user-approved exceptions (see `CLAUDE.md` § Session Memory for the one
  standing exception: `.claude/memory/` operational logs).

## 5. Experience Externalization Discipline

Required reading **before drafting any new Task Brief** or **introducing a new
architectural pattern**.

### 5.1 Principle

AI development does not inherit tacit knowledge across sessions: the design
agent has no long-term memory, the implementation agent sees only a per-PR
review trail, and the operator's judgment is lost between sessions unless it is
written down. The only way to keep results reproducible is to force experience
into **explicit artifacts** (docs / tests / checklists / pattern catalogs).
"Veteran intuition" locked inside an individual or agent does not work in AI
development. The constraint that the design agent forgets paradoxically acts as
a **forced externalization discipline**.

### 5.2 Review Round Count as Leading Quality Indicator

Track how many review rounds a PR takes to land. It is the cheapest leading
indicator of brief quality.

| Round | Interpretation | Action |
|---|---|---|
| **0** | Brief discipline worked; inviolate predicates were explicit; producer output shapes were grep-verified. | None (base case). |
| **1–3** | Light follow-up; reinforcing a specific point. | Acceptable if resolved within the round. |
| **5–10** | A spec section that was ambiguous in the brief surfaced. | Encode that spec into docs/tests — mandatory. |
| **10+** | The brief skipped the §1 (new-brief) checklist / left an invariant implicit / did not verify producer shapes. | Do the "never let this trap recur" encoding work in a follow-up commit or the next brief. |

Empirical base case from the source repo: two PRs took 16 and 13 rounds chasing
the same ambiguity; once that ambiguity was encoded into contract tests +
architecture invariants + a drafting checklist, the next several PRs landed in
**0 rounds**. That causal chain is the reason this discipline exists.

### 5.3 Three-Tier Externalization (by artifact portability)

| Tier | Type | Primary artifacts |
|---|---|---|
| 1 (codified) | portable to any repo | `CLAUDE.md` / `AGENTS.md` / architecture-invariant tests / brief-drafting checklist / the AskUserQuestion N-option trade-off pattern |
| 2 (repo-specific) | reusable within the same domain | planning docs / authoring guides / contract tests / case studies |
| 3 (session-tacit) | partially inherited by re-reading memory | `.claude/memory/STATUS.md` / `_index.md` / dated `YYYY-MM-DD.md` logs |

### 5.4 Practice / Anti-Pattern / Enforcement

Read each rule along three axes: the **practice** (do this), the
**anti-pattern** (what goes wrong), and the **enforcement** (what catches it).

| Practice | Anti-Pattern | Enforcement |
|---|---|---|
| Read the memory log + recent dated entries before drafting a brief. | Skipping the memory log → re-triggering a trap from a past session. | `CLAUDE.md` § Required Reading (Tier A) |
| Verify every symbol/path/field named in a brief against the implementation by grep, not from memory. | Writing a validator from assumption → a permanent "compiles but fails at runtime" trap. | `new-brief` skill §1 + producer-shape sync tests |
| Run the full drafting checklist regardless of task size. | "It's a short brief, skip the checklist." | `new-brief` skill |
| Demonstrate both a FAIL case and a PASS case when validating a gate. | One PASS case only → a no-op gate looks like it works. | domain dual-case test |
| Use AskUserQuestion with 3–4 trade-off options for genuine decisions. | A bare yes/no question → user decision latency. | (pattern catalog) |
| After a 5+ round review, encode the ambiguous spec into docs/tests post-merge. | Fixing only within the round → the trail lives only in chat and is never re-read. | `wrap-up` skill step 7 (checklist item, not a test — round count is a fragile proxy) |
| Sweep `STATUS.md` next-queue the moment a PR merges (remove completed entries). | "Later" → stale entries accumulate. | `tests/discipline/test_status_next_queue_no_completed.py` |
| Keep `STATUS.md` `## Phase` to one paragraph. | Append a new paragraph + leave the old one. | `tests/discipline/test_status_phase_single_paragraph.py` |
| Keep `_index.md` cells short (a 1–2 line summary). | Essay-sized cells → the index bloats. | `tests/discipline/test_index_entry_compactness.py` |

### 5.5 Cross-Reference

- `CLAUDE.md` § Experience Externalization (light pointer back here) +
  § Required Reading (the Tier A/B/C/D load order).
- `.claude/skills/new-brief/SKILL.md` (the drafting checklist executor).
- `.claude/skills/wrap-up/SKILL.md` (the session-end executor).

## Related Documents

- `CLAUDE.md` — repository policy and workflow summary.
