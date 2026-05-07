# Repair Instructions

**Intent**: Add profile endpoint
**Verdict**: fail (fix_required: 1, suggested: 1, info: 1, unresolved: 1)

## Fix Required
1. **R_USER_VIOLATION** - User constraint hard_api violated: operator=equals, target=api_surface_public.
   - Constraint: `hard_api`
   - Kind: `delta`
   - Severity: `hard`
   - Target: `api_surface_public`
   - Operator: `equals`
   - Status: `violated`
   - Error code: `E_VIOLATION`
   - Observed: ["removed"]
   - Expected: []
   - Hint: address the constraint or update target.yaml if intent changed.

## Suggested
1. **R_USER_VIOLATION** - User constraint soft_effect violated: operator=equals, target=effect_changes.added.
   - Constraint: `soft_effect`
   - Kind: `delta`
   - Severity: `soft`
   - Target: `effect_changes.added`
   - Operator: `equals`
   - Status: `violated`
   - Error code: `E_VIOLATION`
   - Hint: address the constraint or update target.yaml if intent changed.

## Info
1. **R_USER_VIOLATION** - User constraint info_imports violated: operator=equals, target=imports_delta.added.
   - Constraint: `info_imports`
   - Kind: `delta`
   - Severity: `info`
   - Target: `imports_delta.added`
   - Operator: `equals`
   - Status: `violated`
   - Error code: `E_VIOLATION`
   - Hint: address the constraint or update target.yaml if intent changed.

## Unresolved
1. **R_UNSUPPORTED_OPERATOR** - changed_only_in: skipped in P1 (E_OPERATOR_UNSUPPORTED_P1); operator=changed_only_in, kind=delta.
   - Constraint: `changed_only_in`
   - Kind: `delta`
   - Severity: `hard`
   - Target: `api_surface`
   - Operator: `changed_only_in`
   - Status: `skipped`
   - Error code: `E_OPERATOR_UNSUPPORTED_P1`
   - Hint: address the constraint or update target.yaml if intent changed.
