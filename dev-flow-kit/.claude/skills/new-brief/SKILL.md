---
name: new-brief
description: Draft a Task Brief ({{DESIGN_AGENT}}→{{IMPL_AGENT}} handoff), running a reusable pre-flight checklist as a gate before emitting the AGENTS.md §1 brief format. Use when the user asks to write/draft a new brief or Task Brief, or to change an existing brief.
---

# new-brief — Task Brief drafter with a pre-flight gate

Drafts a Task Brief in the `AGENTS.md §1` format, but only after running a
reusable checklist that front-loads the checks which historically caused
multi-round review churn. This skill is the **executor**; the policy source of
truth is `AGENTS.md`. If they diverge, `AGENTS.md` wins — fix this skill rather
than acting on a stale copy.

Goal of the gate: land the brief in fewer review rounds (review-round count is
the project's leading quality indicator — `AGENTS.md §5.2`).

## 0. Pre-flight reading (Tier B)

Before drafting, read:

- `AGENTS.md §1` (Task Brief format) + `§3` (escalation rules) + `§4` (branch
  rules) + `§5` (Experience Externalization Discipline).
- The relevant `docs/<topic>_planning.md` for the phase/brief at hand, and
  `.claude/memory/STATUS.md` `## Phase` + `## Next Queue` for current priority.
- `.claude/memory/_index.md` + the most recent ~3 dated `YYYY-MM-DD.md` logs.
  `AGENTS.md §5.4` makes this mandatory: skipping the memory log re-introduces
  the "memory log skip → past-session trap recurs" anti-pattern.

If a required doc is stale or missing, surface that in the draft rather than
inventing context (documented recurring failure mode).

## 1. Reusable checklist (run before writing spec)

### 1a. Schema grounding  ⚠️ highest-yield
Every symbol, path, field name, operator, or config key you name in the brief
MUST be verified to exist in the implementation **by grep, not from memory**.
Value forms (e.g. an identifier format a producer emits) must match the real
producer's output — confusing them is a permanent "compiles but fails at
runtime" category. List the canonical files to grep for your domain here.

### 1b. Invariant scope
Keep any cross-cutting invariant (byte-identity, import-graph, idempotence)
narrowed to the layer that actually owns it. Do not over-require invariants;
never add one that would force a forbidden coupling (e.g. a network call or a
real VCS ref) into a path that the project's scope guard says must stay pure.

### 1c. Cross-doc consistency
- Reference other briefs/specs using their canonical framing verbatim.
- Any new entry point's exit codes / error contract must cite the project's
  documented policy; no silent success for usage / internal errors.
- **Zero repeated spec inside the brief**: pick one canonical location per
  spec, cross-reference elsewhere. After editing any spec table, grep the brief
  for the spec string and sync every occurrence.

### 1d. Sync-trigger audit
If the brief changes a table, a merge/fallback chain, an exit-code table, an
invariant scope, or a registry, a brief-wide grep audit is mandatory — each of
those propagates to acceptance fixtures / Goal statements / criteria rows.

### 1e. Domain-specific items (if applicable)
Add the checks that are specific to your project's surfaces here (e.g. CLI flag
= parser + consumption + provenance all defined, or it is dropped; a new
advisory needs a detectable, meaningful invalid pattern first to prevent false
positives).

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
- IN: <files or modules {{IMPL_AGENT}} may change>
- OUT: <files, behavior, or decisions {{IMPL_AGENT}} must not change>

## Allowed Dependencies (optional)
<deps {{IMPL_AGENT}} may add; if absent, new deps require escalation>

## Implementation Hints (optional)
<suggested approach, design references, existing patterns>

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
```

Make every Acceptance Criterion **verifiable** (a command, a test, or a
grep-able assertion). Target task size ≈ 0.5–2 days. Foreseeable blockers
should map to an `AGENTS.md §3` escalation trigger rather than a silent
assumption.

## 3. Closeout
Hand the brief to the user (it is paste-ready for {{IMPL_AGENT}}). Note any §1a
grep that surfaced a schema mismatch, any unresolved design decision the user
must settle, and any 5+ round dispute that should be externalized into
docs/tests per `AGENTS.md §5`.
