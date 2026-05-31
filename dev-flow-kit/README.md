# dev-flow-kit — portable agent development-flow scheme

A repo-agnostic, copy-into-place kit that ports the **design / implementation
separation scheme** and the **session-end protocol** (plus the session-memory
workflow, drafting/wrap-up skills, web-session bootstrap hook, and the
discipline tests that enforce memory hygiene) out of one repository so they can
be reused in another (e.g. the *quantum* repository).

This kit is the generalized form of the workflow battle-tested in
`semantic-ci-code`. Everything here is intentionally stripped of that repo's
domain specifics (its product schema, brief IDs, security protocol, etc.) and
parameterized with `{{PLACEHOLDER}}` tokens you fill in once.

## What you get

| Pillar | Files | What it does |
|---|---|---|
| **Design/impl split** | `AGENTS.md` | Two-agent handoff protocol: a *design* agent owns briefs + review judgment, an *implementation* agent owns code/tests/PRs. Defines the Task Brief ⇄ Completion Summary message format, escalation rules, branch rules, and the experience-externalization discipline. |
| **Repo policy** | `CLAUDE.md` | The operating contract: tiered required-reading, the session-memory workflow, and the session-end ("wrap-up") rules. Ties the other pillars together. |
| **Session-end protocol** | `.claude/skills/wrap-up/SKILL.md` + `.claude/memory/*` | The executable, ordered procedure that persists a session reflection, sweeps the status tracker, archives old logs on a TTL, and runs the discipline gate before any push. |
| **Brief drafter** | `.claude/skills/new-brief/SKILL.md` | A pre-flight checklist gate that front-loads the checks which historically caused multi-round review churn, then emits a paste-ready Task Brief. |
| **Web bootstrap** | `.claude/hooks/session-start.sh` + `.claude/settings.json` | Installs deps at session start so lint/test/discipline gates work in remote (web) sessions. |
| **Discipline tests** | `tests/discipline/*` | Turn the recurring memory-hygiene anti-patterns into CI failures (single-paragraph status, no completed items left in the queue, compact index cells). |

## Why this shape

AI-driven development does not inherit tacit knowledge across sessions: the
design agent has no long-term memory, the implementation agent only sees a
per-PR review trail, and the operator's accumulated judgment evaporates between
sessions unless it is written down. The only thing that survives is what you
**force into explicit artifacts** — docs, tests, checklists, and a structured
memory log. This kit is that forcing function, packaged for reuse.

## How to port it into the quantum repo

1. **Copy the tree.** From this kit, copy into the target repo root:
   - `CLAUDE.md`, `AGENTS.md`
   - `.claude/` (settings, hooks, skills, memory skeleton)
   - `tests/discipline/` (place it at `<repo>/tests/discipline/` — the tests
     resolve the repo root as `Path(__file__).resolve().parents[2]`, so this
     exact location matters).

2. **Fill the placeholders.** Search the copied files for `{{` and replace
   every token. The full list:

   | Placeholder | Meaning | Example |
   |---|---|---|
   | `{{PROJECT_NAME}}` | Repo / product name | `quantum` |
   | `{{PROJECT_TAGLINE}}` | One-line description | `Quantum circuit simulator` |
   | `{{DESIGN_AGENT}}` | The design agent | `Claude Code` |
   | `{{IMPL_AGENT}}` | The implementation agent | `Codex` |
   | `{{TASK_UNIT}}` | Your unit-of-work label | `ticket` / `CSCI` / `issue` |
   | `{{INSTALL_CMD}}` | One-shot dependency install | `python -m pip install -e ".[dev]"` / `npm ci` |
   | `{{LINT_CMD}}` | Lint command | `ruff check .` / `npm run lint` |
   | `{{TEST_CMD}}` | Full test command | `pytest -q` / `npm test` |
   | `{{DISCIPLINE_TEST_CMD}}` | The pre-push discipline gate | `python -m pytest tests/discipline/ -q --no-cov` |
   | `{{DESIGN_BRANCH_PREFIX}}` | Design branch prefix | `claude/` |
   | `{{IMPL_BRANCH_PREFIX}}` | Impl branch prefix | `codex/` |
   | `{{DEFAULT_BRANCH}}` | Mainline branch | `main` |
   | `{{LANG_RUNTIME}}` | Language/runtime line | `Python 3.11+` / `Node 20+` |

3. **Configure the discipline tests.** Edit `tests/discipline/_config.py` so the
   heading names + completion markers match your `STATUS.md` / `_index.md`
   language (the defaults use English headings; swap them if your tracker is in
   another language). Then run `{{DISCIPLINE_TEST_CMD}}` — it should pass
   against the shipped memory skeleton.

4. **Seed the memory.** Replace the placeholder rows in
   `.claude/memory/STATUS.md` and `.claude/memory/_index.md` with your real
   first entries. Keep `## Phase` to a single paragraph and `_index.md` cells
   compact — the discipline tests enforce both.

5. **Adapt the bootstrap hook.** If the target repo is not Python, replace the
   `{{INSTALL_CMD}}` body of `.claude/hooks/session-start.sh`. The remote-only
   guard (`CLAUDE_CODE_REMOTE`) and the "keep install chatter out of model
   context" pattern are language-agnostic — keep them.

6. **Wire CI (optional but recommended).** Add a CI step that runs
   `{{DISCIPLINE_TEST_CMD}}` so the hygiene rules are enforced on PRs, not only
   at wrap-up time.

## What this kit deliberately omits

- Product/domain code, schemas, and any brief/spec content specific to the
  source repo.
- The source repo's domain-specific discipline tests (e.g. JSON-schema-version
  sync, dogfooding dual-case checks). Only the **generic** memory-hygiene tests
  are generalized; re-derive domain ones in the target repo.
- A package installer. This is a copy-and-adapt template, not a dependency.

## Source

Generalized from `semantic-ci-code` (the UGH-ecosystem code domain). The
empirical basis for "externalize experience into artifacts" is recorded in that
repo's `AGENTS.md §5` (review-round count dropping to 0 after the recurring
traps were encoded into tests + checklists).
