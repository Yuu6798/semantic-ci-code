# semantic-ci-code

> **This is not a linter. This is not a type checker. This is not a test runner.**
>
> Semantic CI Code Edition is a deterministic semantic CI layer for validating
> whether a code change matches its declared intent.

## Current Status

Bootstrap scaffold. The repository now defines the Code Edition boundary, Python
package layout, CI, and development workflow. Product behavior is still design-first.

## Scope

Semantic CI Code Edition compares:

- declared change intent
- expected code state
- baseline code state
- observed code state

It emits a semantic diff plus repair instructions for the next generator pass.

Out of scope:

- replacing linters, type checkers, or test runners
- LLM-as-judge behavior
- API-key services
- the music PoC implementation

## Setup

```bash
pip install -e ".[dev]"
```

## Development

```bash
ruff check .
pytest -q
python -m semantic_ci_code
```

## Project Structure

```text
src/semantic_ci_code/        # Python package
tests/                       # pytest suite
docs/                        # design documents
.github/workflows/ci.yml     # ruff + pytest CI
```

## Documentation

- [Code Semantic CI Design](docs/code_semantic_ci_design.md) - Code Edition v0.1 design spec
- [AGENTS.md](AGENTS.md) - Claude x Codex task handoff protocol
- [CLAUDE.md](CLAUDE.md) - repository-level agent operating policy

## Appendix

並列エージェント運用におけるオーケストレーター盲点の観測事例（core scope 外の応用観測）: [Multi-Agent Orchestration Audit Gap](docs/multi_agent_audit_case.md)。

## License

MIT. Revisit before a commercial or source-available release if the product policy changes.
