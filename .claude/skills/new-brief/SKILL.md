---
name: new-brief
description: Draft a Task Brief (Claude→Codex handoff) for the semantic-ci-code repo, running the reusable §15 brief-drafting checklist as a pre-flight gate before emitting the AGENTS.md §1 brief format. Use when the user asks to write/draft a new brief, a CSCI brief, or a Task Brief, or to change an existing brief.
---

# new-brief — Task Brief drafter with §15 pre-flight gate

Drafts a Task Brief in the `AGENTS.md §1` format, but only after running the
reusable core of the §15 brief-drafting checklist (distilled from 20 review
rounds, PR #73). This skill is the **executor**; the policy sources of truth
are `AGENTS.md` and `docs/brief_8_planning.md §15`. If they diverge from this
file, they win — fix this skill rather than acting on a stale copy.

Goal of the gate: front-load the checks that historically caused multi-round
review churn, so the brief lands in fewer rounds (review-round count is the
repo's leading quality indicator — `AGENTS.md §5.4`).

## 0. Pre-flight reading (Tier B)

Before drafting, read:

- `AGENTS.md §1` (Task Brief format) + `§3` (escalation rules) + `§4`
  (branch rules) + `§5` (Experience Externalization Discipline).
- `docs/brief_8_planning.md §15` (the full checklist — this skill encodes only
  its reusable core; consult the source for domain-specific items).
- The relevant `docs/<topic>_planning.md` for the phase/brief at hand, and
  `.claude/memory/STATUS.md` § Phase + § 次の発行順序 for current priority.
- `.claude/memory/_index.md` + the 直近 3 dated `YYYY-MM-DD.md` session logs.
  `AGENTS.md §5.5` makes this mandatory before brief drafting: skipping the
  memory log re-introduces the "memory log skip → 過去 session trap 再発生"
  anti-pattern, and this skill is the executor for every new brief.

If a required doc is stale or missing, surface that in the draft rather than
inventing context (documented recurring failure mode).

## 1. Reusable checklist (run before writing spec)

### 1a. Schema grounding — §15.1  ⚠️ highest-yield
Every path / operator / match_schema key / template constraint / delta field
you name in the brief MUST be verified to exist in the implementation by grep,
not from memory. Canonical files to grep (paths are repo-root relative; the
package lives under `src/`):

- `src/semantic_ci_code/domain/state_schema.py` (delta fields)
- `src/semantic_ci_code/evaluator/operators.py` (operator names + semantics)
- `src/semantic_ci_code/evaluator/evaluator.py` (template relaxation path)
- `src/semantic_ci_code/compiler/templates.py` (`TEMPLATE_CONSTRAINTS` dict — quote it verbatim)
- `src/semantic_ci_code/compiler/target_compiler.py` (`allow_changes` etc. policy hatches)
- `src/semantic_ci_code/compiler/path_schema.py` (path validation)
- `src/semantic_ci_code/framework/match_schema.py` (required / optional / forbidden keys)
- `src/semantic_ci_code/framework/target_svp.py` (field optionality / target-level keys)

Collection-constraint value forms must match the real delta producer's output
(e.g. `new_cases` uses `path::name`, not Python FQN — a permanent
compile-pass / evaluator-fail category if confused).

### 1b. Invariant scope — §15.6
Keep any byte-identical / import-graph invariant narrowed to the **semantic
layer**: compare only evaluator-derived fields (`verdict` / `repair_plan` /
`summary`). Exclude provenance/output-reflection surfaces
(`target_authorship`, `validate-plan.rendered`) — reflecting provenance is
their reason to exist. Do not over-require invariants; never add one that
would force a real git ref into the verdict path (`§23.1` neutrality — flag
as a violation if the work needs it).

### 1c. Cross-doc consistency — §15.7
- Reference other briefs using their canonical framing verbatim (e.g. SSP =
  "sibling protocol, does not change core verdict semantics").
- Any new subcommand's exit codes must cite `docs/exit_codes.md` (0/1/2/3/4);
  no silent success for usage / engine errors.
- **Zero repeated spec inside the brief**: pick one canonical location per
  spec, cross-ref elsewhere. After editing any spec table, grep the brief for
  the spec string and sync every occurrence.

### 1d. Sync-trigger audit — §15.8
If the brief changes any of these, a brief-wide grep audit is mandatory:
recipe table, merge/fallback chain, exit-code table, invariant scope, or a
registry (intent-declaring sections, advisory lists). Each propagates to
acceptance fixtures / Goal statements / R-rows.

### 1e. Domain-specific items — §15.2 / 15.3 / 15.4 / 15.5 (if applicable)
Only when the brief touches that surface:
- **Authoring intent (15.2)**: preserve explicit user input verbatim; force
  qualifiers via record match, not flat alias.
- **Source merge (15.3)**: validate recipe necessity after merge; no silent
  fallback/override across source-strength layers.
- **CLI flags (15.4)**: a new flag needs merge + consumption + provenance all
  defined, else drop it; a source flag needs its parser + `source_surface`
  entry.
- **Advisor (15.5)**: confirm a detectable, meaningful invalid pattern exists
  before adding an advisory (false-positive prevention).

## 2. Emit the brief (AGENTS.md §1 format)

```markdown
# Task Brief: <ID> - <short title>

## Phase
<design phase or document reference>

## Goal
<1-2 sentences defining completion>

## Acceptance Criteria
- [ ] Verifiable condition 1
- [ ] Verifiable condition 2

## Scope
- IN: <files or modules Codex may change>
- OUT: <files, behavior, or decisions Codex must not change>

## Allowed Dependencies (optional)
<deps Codex may add; if absent, new deps require escalation>

## Implementation Hints (optional)
<suggested approach, design references, existing patterns>

## Required Outputs
- Branch name: `codex/<topic>`
- PR title: <Conventional Commits style>
- Expected files changed: <list>
- Required tests: <test expectations>

## Done When
- All acceptance criteria are checked
- `ruff check .` passes
- `pytest -q` passes
- PR body starts with a Completion Summary
```

Make every Acceptance Criterion **verifiable** (a command, a test, or a
grep-able assertion). Target task size ≈ 0.5–2 days. Foreseeable blockers
should map to an `AGENTS.md §3` escalation trigger rather than a silent
assumption.

## 3. Closeout
Hand the brief to the user (it is paste-ready for Codex). Note any §15.1 grep
that surfaced a schema mismatch, any unresolved design decision the user must
settle, and any 5+ round dispute that should be externalized into docs/tests
per `AGENTS.md §5`.
