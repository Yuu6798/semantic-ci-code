# AGENTS.md - Claude x Codex Handoff Protocol

This repository uses a design/implementation split. Claude Code owns design briefs
and review judgment. Codex owns implementation, tests, and PR preparation. The user
triggers handoff between them.

Both agents should read this file before starting repository work.

## Message Flow

```text
Claude -> Task Brief -> User -> Codex
Claude <- Completion Summary <- User <- PR URL <- Codex
```

Agents do not need to communicate directly. The user moves the structured messages
between them.

## 1. Task Brief: Claude to Codex

Claude should issue tasks in this format so the user can paste them directly into
Codex. Target task size is roughly 0.5 to 2 days.

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
- IN: <files or modules Codex may change>
- OUT: <files, behavior, or decisions Codex must not change>

## Allowed Dependencies (optional)
<Dependencies Codex may add to pyproject.toml. If absent, new dependencies require escalation.>

## Implementation Hints (optional)
<Suggested approach, design references, existing patterns>

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
````

## 2. Completion Summary: Codex to Claude

Codex should place this at the top of the PR body.

````markdown
# Completion Summary: <Task ID>

## Phase
<copied from Task Brief>

## What Changed
- <high-level change 1>
- <high-level change 2>
- <high-level change 3>

## Acceptance Criteria Status
- [x] Condition 1 - <evidence>
- [x] Condition 2 - <evidence>
- [ ] Condition 3 - <reason if incomplete>

## Tests
- Added: <test names or count>
- Result: <pass / fail / skipped>

## Files Changed
<git diff --stat equivalent>

## Deviations from Brief
<None, or list deviations>

## Open Questions / Deferred
<Questions for Claude or next phase>

## Next Handoff
<What Claude should review next>
````

## 3. Escalation Rules

Codex should stop and report a blocked Completion Summary when:

1. Acceptance criteria are technically impossible.
2. The brief requires an unstated design decision.
3. Existing tests fail in a way that suggests a behavior regression.
4. A new dependency is needed but not listed in Allowed Dependencies.
5. The implementation would violate determinism, auditability, no-LLM operation, or
   no-API-key operation.

## 4. Branch Rules

- Claude design branches: `claude/<topic>`
- Codex implementation branches: `codex/<topic>`
- Direct changes on `main` are reserved for explicit user-approved exceptions.

## Related Documents

- `CLAUDE.md` - repository policy and workflow summary
- `docs/code_semantic_ci_design.md` - product design specification
