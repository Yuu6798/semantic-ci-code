# Contributing

Thanks for looking at `semantic-ci-code`. It is an experimental, pre-release
project (see [`ROADMAP.md`](ROADMAP.md)); contributions and review are welcome,
with the caveats below.

## How this repo is developed

Development uses a design / implementation split, documented in
[`AGENTS.md`](AGENTS.md):

- **Design, specification, and review** are owned by Claude Code and issued as
  Task Briefs.
- **Implementation, tests, and PRs** are owned by Codex on `codex/<topic>`
  branches.
- Repository policy lives in [`CLAUDE.md`](CLAUDE.md).

You do not need to use that loop to contribute, but it explains why most commits
are agent-authored and why Task Briefs and `.claude/memory/` exist.

## Dev setup

```bash
pip install -e ".[dev]"
ruff check .
ruff format --check .
pytest -q
```

`pytest` must pass, including the `tests/discipline/` suite, which enforces
repo-hygiene invariants.

## Pull requests

- Branch from `main`; use `codex/<topic>` (or `claude/<topic>` for design
  work). Direct pushes to `main` are reserved for the `.claude/memory/`
  exception described in [`CLAUDE.md`](CLAUDE.md).
- Start the PR body with a **Completion Summary** (template in
  [`AGENTS.md`](AGENTS.md) §2).
- CI enforces a dogfooding disclosure in the PR body
  (`.github/workflows/pr-body-discipline.yml`): state whether you ran
  `semantic-ci` on your own change and what it reported.

## Good first issues

Good entry points are the open D-class findings in the
[Dogfooding Findings Tracker](docs/dogfooding_findings_tracker.md): **D6**
(nested-function vacuous PASS) and **D7** (extract-method × cyclomatic authoring
advice) are both scoped, low-risk, and well-documented.
