# Target Authoring Surface

`target.yaml` is the declared intent that the Validator surface evaluates a
candidate against. This document fixes the design contract for **how that file
gets produced**, so future implementation work (`init --recipe`, `target-doctor`,
`target-catalog`, and any later LLM-assisted path) can be built without
re-litigating provenance, surface boundaries, or the verdict-vs-authoring split.

The boundary is established in `docs/code_semantic_ci_design.md §23.3` and
§23.3.1. This document is the **Authoring surface's implementation-side
counterpart**: it states what authoring may do, what it must not do, and how
multiple authoring paths coexist without leaking into the verdict.

## A. Hand-written is one path among several

`target.yaml` is **not required to be hand-written**. The engine takes the
compiled target as ground truth and does not care how it was produced. The
authoring difficulty users hit when writing `target.yaml` from scratch
(see `docs/target_yaml_guide.md` D1〜D5) is an implementation gap on the
Authoring surface, not a property of the engine. Closing that gap is what
Brief 8 implements.

## B. The three deterministic authoring paths

Three paths are in scope for Brief 8. All are completely deterministic — no
LLM, no network, no API key (see §E):

| Path | Subcommand | Inputs | Brief 8 CSCI |
|---|---|---|---|
| **Recipe + structured sources** | `semantic-ci init --recipe <id> [--from-pr-body / --from-labels / --from-commits / --from-issue]` | recipe ID + user-provided text or git metadata | CSCI-42 |
| **Catalog reference** | `semantic-ci target-catalog [--format json] [--kind <k>] [--target-path <p>]` | nothing (reads built-in registry); intended for AI assistants and IDE extensions producing `target.yaml` from machine-readable schema | CSCI-44 |
| **Hand-written** | `semantic-ci init` (plain scaffold), then user edit | empty skeleton from existing `TARGET_TEMPLATE` | already in repo, unchanged |

`semantic-ci target-doctor` (CSCI-43) is the Advisor surface that audits a
target file regardless of which authoring path produced it. It does not
generate `target.yaml` and never participates in the verdict.

The plain `semantic-ci init` (no `--recipe`) keeps its current scaffold output
byte-for-byte — Brief 8 does not change the existing `TARGET_TEMPLATE`.

## C. LLM-assisted authoring is out of scope for Brief 8

LLM-driven generation (PR body summarisation, recipe inference, freeform
intent → `target.yaml`) is **deferred to Brief 8b**. It is not introduced in
Brief 8. The reason is the same one that keeps LLMs out of the Validator
surface: a verdict that depends on a non-deterministic generator is not
auditable.

Concretely, Brief 8 must satisfy INV-4 ("no-LLM / no-network"):
no subcommand added or modified in this brief may import `httpx`, `requests`,
`openai`, `anthropic`, or any other network / LLM client
(`docs/brief_8_planning.md §5.2`). The import-graph test
`tests/architecture/test_surface_isolation.py` (CSCI-43) enforces this.

When Brief 8b adds an LLM-assisted path, the new path lives in the Authoring
surface only, must produce output that compiles like any other `target.yaml`,
and must not relax INV-1 / INV-2 / INV-3.

## D. Every path lands at the same verdict entry

All authoring paths converge on the same handoff: a compiled `TargetSVP` that
the Validator surface treats as ground truth.

```
authoring-time (verdict 不参加)        ┃   verdict-time (Validator, §23.1)
                                       ┃
recipe + sources ─┐                    ┃
catalog reference ┼─▶ target.yaml ──▶  ┃ ─▶ check / compare / compile-repair
hand-written ─────┘   (declared        ┃    validate-plan
                       intent +        ┃
                       provenance)     ┃
target-doctor (Advisor, audits) ──────/
```

The provenance of the file — which generator path produced it, what recipe ID
was used, what PR body fragment seeded a constraint — is recorded under
`authorship.generation_metadata` for traceability on generator paths
(`init --recipe --from-*`), but the evaluator never reads it. Plain `init`
scaffold and hand-written targets do not populate `generation_metadata` at
all. INV-3 (Provenance non-participation) in
`docs/brief_8_planning.md §5.2` requires that mutating `generation_metadata`
leaves evaluator-derived fields (`verdict`, `repair_plan`, `summary`)
byte-identical.

## E. Authoring / Advisor / Provenance surfaces are not reachable from the evaluator

The verdict-bearing modules — `evaluator/`, `compiler/`, `pipeline/`,
`repair/`, and the verdict subcommand handlers `check` / `compare` must not
import the new Authoring or target-audit modules (`init --recipe`,
`target-doctor`, `target-catalog`).

The Advisor surface itself is **explicitly exempt** from this isolation rule.
`compile-repair` and `validate-plan` are Advisor subcommands; their adapter
renderers in `repair_compiler/adapters/*` intentionally include
`authorship.generation_metadata` (`format_generation_metadata`) so the
downstream generator sees how the target was produced. That is the existing
contract called out as an INV-1 exception in
`docs/brief_8_planning.md §5.2` (the `validate-plan` envelope and the verdict
envelope's `target_authorship` field are reflected, not quarantined).

Brief 8 fixes the isolation structurally:

- **INV-2 (Surface isolation)**: the transitive import closure of
  `cli/commands/check.py` (and the other verdict-path command handlers
  `compare.py`) does not contain `init`, `target-doctor`,
  `target-catalog`, or any new `authoring/` module. `cli/main.py` subparser
  registration is excluded — it is a dispatcher concern, not a
  verdict-semantic one. `compile-repair` / `validate-plan` and
  `repair_compiler/` are not on the verdict path and are not gated by INV-2.
- **INV-1 (Verdict bytes invariant)**: the JSON fields the evaluator decides
  (`verdict`, `repair_plan`, `summary`) remain byte-identical across Brief 8.
  Two narrow exceptions are documented in `docs/brief_8_planning.md §5.2`:
  the existing `target_authorship` field on the verdict envelope, and the
  whole `validate-plan` envelope (which is itself an Advisor output that
  intentionally renders `generation_metadata`).
- **INV-3 (Provenance non-participation)**: arbitrary edits to
  `authorship.generation_metadata` do not move the evaluator-derived fields,
  even though Advisor renderers reflect that metadata into their output.

`docs/code_semantic_ci_design.md §23.3.1` lists the four surfaces (Validator /
Authoring / Provenance / Advisor) and pins that adapters and repair compilers
**render** declared intent — they do not rewrite its semantics. The same
rule applies to recipes: a recipe expands `change.primary_kind` and user input
into a `target.yaml`, but the resulting file is then frozen as declared intent
before any verdict runs.

## F. Candidate-derived expectations are not implemented; `candidate_code_used: false` whenever provenance metadata is populated

Deriving an expectation from the candidate code under review — for example,
auto-generating `api_surface_delta.added` to match whatever the candidate
actually added — is a tautology that produces vacuous PASS verdicts. Brief 8
**does not implement candidate-derived expectations** and does not introduce a
`--allow-candidate-derived-expectations` flag (see `R2` in
`docs/brief_8_planning.md §11`; the argparse spec test fixes flag non-existence).

`authorship.generation_metadata` is populated only on generator paths
(`init --recipe --from-*` today; any future Brief 8b LLM path would have to
populate the same block). Plain `semantic-ci init` and hand-written targets
do not get a `generation_metadata` block at all — that block is absent rather
than set, which preserves the byte-for-byte `TARGET_TEMPLATE` invariant
(`docs/brief_8_planning.md §2.4`). Whenever `generation_metadata` is
populated, the recorded `candidate_code_used` is **always `false`** in this
brief. A future brief that legitimately introduces candidate-aware
expectations (if such a path is ever shown to be safe) would have to
negotiate the boundary against §23.3 first; until then the field is a fixed
sentinel, not a switch.

## Cross References

- `docs/code_semantic_ci_design.md §23.1` — engine input contract; state
  provenance neutrality
- `docs/code_semantic_ci_design.md §23.3` — Responsibility Boundary
  (Adherence, not Correctness)
- `docs/code_semantic_ci_design.md §23.3.1` — Adjacent surfaces table
  (Validator / Authoring / Provenance / Advisor)
- `docs/brief_8_planning.md` — CSCI-41〜44 split, §5.2 INV-1〜INV-5
- `docs/target_yaml_guide.md` — practical hand-authoring guide; D1/D3/D4
  hazards are mechanised by `target-doctor` (CSCI-43)
- `docs/cli_usage.md` — Authoring subcommands section (CSCI-42〜44 land
  their subcommands here)
- `docs/exit_codes.md` — `target-doctor` exit code policy
  (advisory presence does not change the verdict; usage / engine errors
  still use the global 2 / 3 / 4 policy)
- `docs/json_schema.md` — `advisory-2` and `catalog-1` envelopes
