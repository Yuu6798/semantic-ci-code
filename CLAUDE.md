# CLAUDE.md - semantic-ci-code

This file defines the repository-level operating policy for Claude Code and related
agent workflows. Keep product details in `docs/<topic>.md` and keep task handoff
format rules in `AGENTS.md`.

## Project Overview

Semantic CI Code Edition is a deterministic semantic CI layer for code changes.
It compares declared change intent, expected code state, baseline code state, and
observed code state, then emits a semantic diff plus repair instructions.

Scope guard:

- This is not a linter.
- This is not a type checker.
- This is not a test runner.
- This is not an LLM-as-judge service.

The product exists to catch intent drift in generated or manually edited pull
requests while remaining deterministic and auditable.

## Tech Stack

- Language: Python 3.11+
- Build: setuptools with src layout
- Models: Pydantic v2
- Config: PyYAML
- Lint: ruff
- Test: pytest
- CI: GitHub Actions
- License: MIT until explicitly changed

## Workflow

This repository separates design and implementation:

- Claude Code: design, specification, review judgment, phase planning
- Codex: implementation, tests, PR creation, Completion Summary
- User: final approval and handoff trigger

Default cycle:

1. Claude issues a Task Brief using `AGENTS.md`.
2. User gives the brief to Codex.
3. Codex implements on `codex/<topic>`, runs checks, and prepares a PR with a
   Completion Summary.
4. User shares the PR back to Claude.
5. Claude reviews and either approves, requests repair, or emits the next brief.

## Repository Layout

```text
src/semantic_ci_code/
  __init__.py
  __main__.py
  config.py
  scope.py
tests/
docs/
  code_semantic_ci_design.md
```

## Design Documents

| Document | Purpose |
|---|---|
| `docs/code_semantic_ci_design.md` | Code Edition v0.1 design: 3-state RPE, state schema, constraints, repair loop |

When adding a new `docs/<topic>.md`, update this table and the README documentation list.

## Commands

```bash
pip install -e ".[dev]"
ruff check .
pytest -q
python -m semantic_ci_code
```

## Coding Conventions

- Keep behavior deterministic: same input should produce the same output.
- Do not introduce LLM calls, API keys, network services, or vendor coupling without an
  explicit Task Brief decision.
- Add dependencies only when they are allowed by the active brief.
- Prefer typed Pydantic models for state, constraint, diff, and repair data.
- Prefer structured parsing over ad hoc string manipulation.
- Keep README concise; move detailed design into `docs/`.
