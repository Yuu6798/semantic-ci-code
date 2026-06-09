# Repository Layout

Full `src/` / `tests/` tree with per-module CSCI annotations. `CLAUDE.md`
keeps only a pointer here so the always-loaded policy doc stays lean; this
file carries the detail and is read on demand.

```text
src/semantic_ci_code/
  __init__.py            # legacy entrypoint (semantic-ci-code script)
  __main__.py
  config.py
  scope.py
  api_surface/           # Python public-symbol extractor (CSCI-5)
  cli/                   # CLI surface (Brief 4 / 4b / 4d / 5)
    main.py              # argparse entry; subparser for 10 subcommands
    commands/            # one module per subcommand
      observe.py
      compare.py
      check.py
      compile.py
      compile_repair.py  # Brief 5
      validate_plan.py   # Brief 5
    output/              # json / human / sarif / gh-actions formatters
    output_sarif.py
    output_gh_actions.py
    init_command.py      # Brief 4d
    git_runtime.py       # detached worktree materialization
    code_state_cache.py  # CSCI-26 / 27
    target_loader.py
    delta_overlay.py     # files_touched / loc_delta from git numstat
  compiler/              # target.yaml -> CompiledTarget (CSCI-12)
    target_compiler.py
    templates.py         # change_kind template constraints
    path_schema.py       # PR #58 compile-time path validation
  complexity/            # cyclomatic / cognitive (CSCI-7)
  delta/                 # CodeStateDelta (CSCI-11)
  domain/                # state_schema (CodeState root)
  effects/               # effect_db + AST visitor (CSCI-2 / 3 / 4 / 29)
  evaluator/             # constraint evaluator (CSCI-13)
    operators.py
    path_resolver.py
  framework/             # modality-agnostic (TargetSVP, ConstraintKind)
  imports/               # CSCI-6
  module_graph/          # CSCI-8
  pipeline/              # extract_python_code_state (CSCI-10)
  repair/                # RepairPlan emitter (CSCI-14)
  repair_compiler/       # Brief 5: Adapter Protocol + adapters
    core.py
    types.py
    risk_summary.py
    adapters/
      claude_code.py
      cursor.py
      codex.py
      markdown.py
  schemas/               # JSON Schema artifacts
  ssp/                   # Semantic Security Protocol v0.1 (Brief 7)
    models.py            # Pydantic v2 models (SensorOutput, Finding, SSPDelta, etc.)
    fingerprint.py       # SAST 5-element + SCA 3-element canonical fingerprint
    python_profile.py    # AST normalization for SAST normalized_text
    delta.py             # compute_delta + ordinal assignment
    verdict.py           # per-sensor + aggregate verdict
  test_surface/          # CSCI-9
tests/
  cli/                   # CLI integration tests
  compiler/              # CSCI-12
  delta/                 # CSCI-11
  evaluator/             # CSCI-13
  pipeline/              # CSCI-10
  repair/                # CSCI-14
  repair_compiler/       # Brief 5
  ssp/                   # SSP models, fingerprint, delta, verdict tests
  discipline/            # AGENTS.md §5.5 discipline rules as CI checks
  fixtures/              # hand-built before/after trees + expected verdicts
docs/                    # see the Design Documents table in CLAUDE.md
experiments/             # observation-only reproductions (out of core scope)
.claude/memory/          # session memory (handoff source of truth)
```
