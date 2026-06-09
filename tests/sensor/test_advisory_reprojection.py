from __future__ import annotations

from semantic_ci_code.domain.state_schema import APISurfaceEntry, CodeState, RenameEntry
from semantic_ci_code.sensor.advisory import compute_advisory_reprojection

from .helpers import llm_finding


def _code_state(*entries: APISurfaceEntry) -> CodeState:
    return CodeState(api_surface=entries)


def _site(
    fqn: str = "src.app.handler",
    *,
    decorators: tuple[str, ...] = (),
    kind: str = "function",
) -> APISurfaceEntry:
    return APISurfaceEntry(
        fqn=fqn,
        kind=kind,
        visibility="public",
        decorators=decorators,
    )


def test_absence_anchor_with_baseline_guard_is_added():
    finding = llm_finding(
        finding_class="missing-authz",
        anchor_kind="absence",
        expected_property="requires authorization guard",
    )
    baseline = _code_state(_site(decorators=("login_required",)))

    result = compute_advisory_reprojection((finding,), baseline)

    assert result.added == (finding,)
    assert result.pre_existing == ()


def test_absence_anchor_without_baseline_guard_is_pre_existing():
    finding = llm_finding(
        finding_class="missing-authz",
        anchor_kind="absence",
        expected_property="requires authorization guard",
    )
    baseline = _code_state(_site(decorators=()))

    result = compute_advisory_reprojection((finding,), baseline)

    assert result.added == ()
    assert result.pre_existing == (finding,)


def test_absence_guard_match_uses_decorator_leaf():
    finding = llm_finding(
        finding_class="missing-authz",
        anchor_kind="absence",
        expected_property="requires authorization guard",
    )
    baseline = _code_state(_site(decorators=("auth.login_required",)))

    result = compute_advisory_reprojection((finding,), baseline)

    assert result.added == (finding,)
    assert result.pre_existing == ()


def test_absence_anchor_checks_enclosing_class_guard():
    finding = llm_finding(
        finding_class="missing-authz",
        module_path="src/views.py",
        qualified_name="src.views.Users.get",
        anchor_kind="absence",
        expected_property="requires authorization guard",
    )
    baseline = _code_state(
        _site(fqn="src.views.Users", kind="class", decorators=("login_required",)),
        _site(fqn="src.views.Users.get", decorators=()),
    )

    result = compute_advisory_reprojection((finding,), baseline)

    assert result.added == (finding,)
    assert result.pre_existing == ()


def test_absence_anchor_without_enclosing_class_guard_is_pre_existing():
    finding = llm_finding(
        finding_class="missing-authz",
        module_path="src/views.py",
        qualified_name="src.views.Users.get",
        anchor_kind="absence",
        expected_property="requires authorization guard",
    )
    baseline = _code_state(
        _site(fqn="src.views.Users", kind="class", decorators=()),
        _site(fqn="src.views.Users.get", decorators=()),
    )

    result = compute_advisory_reprojection((finding,), baseline)

    assert result.added == ()
    assert result.pre_existing == (finding,)


def test_presence_anchor_is_always_added_fallback():
    finding = llm_finding(
        finding_class="ssrf",
        anchor_kind="presence",
        expected_property="",
    )
    baseline = _code_state(_site(decorators=("login_required",)))

    result = compute_advisory_reprojection((finding,), baseline)

    assert result.added == (finding,)
    assert result.pre_existing == ()


def test_unknown_absence_class_is_added_recall_first():
    finding = llm_finding(
        finding_class="missing-rate-limit",
        anchor_kind="absence",
        expected_property="requires rate limiting",
    )
    baseline = _code_state(_site(decorators=()))

    result = compute_advisory_reprojection((finding,), baseline)

    assert result.added == (finding,)
    assert result.pre_existing == ()


def test_unresolved_absence_site_is_added_recall_first():
    finding = llm_finding(
        finding_class="missing-authz",
        anchor_kind="absence",
        expected_property="requires authorization guard",
        qualified_name="src.app.missing",
    )
    baseline = _code_state(_site(fqn="src.app.handler", decorators=()))

    result = compute_advisory_reprojection((finding,), baseline)

    assert result.added == (finding,)
    assert result.pre_existing == ()


def test_rename_map_prevents_pre_existing_absence_from_becoming_added():
    finding = llm_finding(
        finding_class="missing-authz",
        module_path="src/renamed.py",
        qualified_name="src.renamed.handler",
        anchor_kind="absence",
        expected_property="requires authorization guard",
    )
    baseline = _code_state(_site(fqn="src.original.handler", decorators=()))
    renames = (RenameEntry(old_path="src/original.py", new_path="src/renamed.py"),)

    with_renames = compute_advisory_reprojection((finding,), baseline, renames=renames)
    without_renames = compute_advisory_reprojection((finding,), baseline)

    assert with_renames.added == ()
    assert with_renames.pre_existing == (finding,)
    assert without_renames.added == (finding,)
    assert without_renames.pre_existing == ()


def test_rename_map_handles_repo_relative_paths_with_package_root_prefix():
    finding = llm_finding(
        finding_class="missing-authz",
        module_path="src/pkg/renamed.py",
        qualified_name="pkg.renamed.handler",
        anchor_kind="absence",
        expected_property="requires authorization guard",
    )
    baseline = _code_state(_site(fqn="pkg.original.handler", decorators=()))
    renames = (RenameEntry(old_path="src/pkg/original.py", new_path="src/pkg/renamed.py"),)

    with_renames = compute_advisory_reprojection((finding,), baseline, renames=renames)
    without_renames = compute_advisory_reprojection((finding,), baseline)

    assert with_renames.added == ()
    assert with_renames.pre_existing == (finding,)
    assert without_renames.added == (finding,)
    assert without_renames.pre_existing == ()


def test_reprojection_output_is_sorted_by_canonical_id():
    later = llm_finding(
        finding_class="missing-authz",
        anchor_kind="absence",
        expected_property="requires authorization guard",
        ordinal=1,
    )
    earlier = llm_finding(
        finding_class="missing-authz",
        anchor_kind="absence",
        expected_property="requires authorization guard",
        ordinal=0,
    )
    baseline = _code_state(_site(decorators=("login_required",)))

    result = compute_advisory_reprojection((later, earlier), baseline)

    assert result.added == tuple(sorted((earlier, later), key=lambda item: item.canonical_id))
