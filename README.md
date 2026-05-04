# semantic-ci-code

Semantic CI Code Edition is a deterministic semantic CI layer for code changes.
It compares observed code semantics against a declared `target.yaml` intent and
returns stable JSON or human-readable repair guidance.

It is not a linter, type checker, test runner, or LLM-as-judge service.

## Install

```bash
pip install -e ".[dev]"
semantic-ci --version
```

The legacy `semantic-ci-code` entrypoint is still available and unchanged.

## Quick Start

Create a minimal `target.yaml`:

```yaml
intent: add user profile endpoint
change:
  primary_kind: feature
```

Inspect a package without judging it:

```bash
semantic-ci observe --package-root src/semantic_ci_code --format json
```

Compare two local directories:

```bash
semantic-ci compare --baseline-dir /tmp/base --candidate-dir /tmp/candidate --target target.yaml
```

Check a git change against `origin/main`:

```bash
semantic-ci check --target target.yaml
```

Check staged changes before committing:

```bash
semantic-ci pre-commit --target target.yaml
```

Dry-compile a target file:

```bash
semantic-ci compile --target target.yaml --format human
```

## Documentation

- [CLI Usage](docs/cli_usage.md) - subcommands, flags, target discovery, and output formats
- [Exit Codes](docs/exit_codes.md) - CI-facing exit code contract
- [JSON Output Schema](docs/json_schema.md) - `schema_version="1"` envelopes
- [Code Semantic CI Design](docs/code_semantic_ci_design.md) - Code Edition v0.1 design spec
- [AGENTS.md](AGENTS.md) - Claude x Codex task handoff protocol
- [CLAUDE.md](CLAUDE.md) - repository-level agent operating policy

## Development

```bash
ruff check .
ruff format --check .
pytest -q
```

## License

MIT. Revisit before a commercial or source-available release if the product policy changes.
