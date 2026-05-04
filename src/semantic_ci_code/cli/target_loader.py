from __future__ import annotations

from pathlib import Path

from semantic_ci_code.compiler import CompiledTarget, compile_target_svp


class TargetUsageError(Exception):
    """Target YAML discovery or loading failed due to CLI input."""


class AmbiguousTargetError(TargetUsageError):
    """Both supported implicit target locations exist."""


def discover_target(explicit: str | None, *, cwd: Path) -> Path:
    root = cwd.resolve()
    if explicit is not None:
        path = Path(explicit)
        if not path.is_absolute():
            path = root / path
        path = path.resolve()
        if not path.exists():
            raise TargetUsageError(f"target file not found: {path}")
        if not path.is_file():
            raise TargetUsageError(f"target path is not a file: {path}")
        return path

    root_yaml = root / "target.yaml"
    dotted_yaml = root / ".semantic-ci" / "target.yaml"
    has_root = root_yaml.exists()
    has_dotted = dotted_yaml.exists()
    if has_root and has_dotted:
        raise AmbiguousTargetError(
            "ambiguous target.yaml location: both ./target.yaml and "
            "./.semantic-ci/target.yaml exist; use --target."
        )
    if has_root:
        return root_yaml
    if has_dotted:
        return dotted_yaml
    raise TargetUsageError(
        "target.yaml not found; tried ./target.yaml and ./.semantic-ci/target.yaml. Use --target."
    )


def load_compiled_target(path: Path) -> CompiledTarget:
    yaml_text = path.read_text(encoding="utf-8")
    return compile_target_svp(yaml_text, filename=str(path))
