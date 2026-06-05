# Roadmap

`semantic-ci-code` is intentionally **pre-release**. This file records what
"stable" means here and why we have not promised it yet. For the live project
state (current phase, active queue), see
[`.claude/memory/STATUS.md`](.claude/memory/STATUS.md).

## Why no stable release yet

The value of a semantic CI layer is a *stable contract*: once external CI
pipelines pin our JSON envelope, exit codes, and verdict policy, changing them
becomes a breaking change for every consumer. Those surfaces are still moving —
the JSON envelope is at `schema_version="6"`, having already gone through five
revisions. Promising stability now would lock in decisions we are still
refining, which is an expensive mistake for a foundational tool. So we keep the
project explicitly experimental until the surfaces below settle.

There is no tagged or published release. The `0.1.0` string in `pyproject.toml`
is a development placeholder, not a stability promise.

## Surfaces that may still break

| Surface | Where it lives | Canonical doc |
|---|---|---|
| JSON output envelope (`schema_version`) | `compare` / `check` / `compile` output | [docs/json_schema.md](docs/json_schema.md) |
| CLI exit codes | every subcommand | [docs/exit_codes.md](docs/exit_codes.md) |
| Verdict / judgement policy | constraint evaluator, templates | [docs/code_semantic_ci_design.md](docs/code_semantic_ci_design.md) |

## Exit criteria for a stable (tagged) release

We will tag a stable release only when all of the following hold:

- **Schema stability** — the JSON `schema_version` is unchanged across **three
  consecutive briefs** (no envelope churn). The conservative threshold is
  deliberate: cutting too early is exactly the risk this roadmap exists to
  avoid.
- **Exit-code stability** — the exit-code policy in
  [docs/exit_codes.md](docs/exit_codes.md) is unchanged over the same window.
- **Known-findings closure** — every D-class finding in the
  [Dogfooding Findings Tracker](docs/dogfooding_findings_tracker.md) is either
  resolved or explicitly waived with a recorded rationale. (Currently 5 of 7
  resolved; D6 and D7 open.)

## Out of scope for now

Distribution channels (PyPI, a GitHub Action, semver `1.0`) are **deferred**.
They are a small technical task, but are intentionally sequenced after the
ecosystem-level validation work; see the Frozen / Deferred section of
[`.claude/memory/STATUS.md`](.claude/memory/STATUS.md). This roadmap is about
credibility and legibility, not distribution.
