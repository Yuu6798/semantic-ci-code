# Plan Validation - Pre-Generation Guidance

**Intent**: validate profile endpoint plan
**Primary kind**: refactor
**Allowed secondary kinds**: (none)
**Generation metadata**: (none)

## Target Constraints
1. `lock_api_surface`
   - Kind: `delta`
   - Target: `api_surface`
   - Operator: `equals_baseline`
   - Expected: null
   - Severity: `hard`
   - Unknown policy: `fail`
2. `require_missing_api`
   - Kind: `state`
   - Target: `api_surface`
   - Operator: `includes_all`
   - Expected: ["pkg.profile"]
   - Severity: `hard`
   - Unknown policy: `fail`

**Implementation order**: fix every item under *Authoring Errors* in `target.yaml` first; only then implement against *Risk Areas* / *Forbidden Zones* / *Required Additions*.

## Authoring Errors
(none)

## Risk Areas
- require_missing_api

## Forbidden Zones
1. `lock_api_surface`
   - Source: `user`
   - Target: `api_surface`
   - Operator: `equals_baseline`

## Required Additions
1. `require_missing_api`
   - Source: `user`
   - Target: `api_surface`
   - Operator: `includes_all`
   - Expected: "pkg.profile"

## Template Implications
- template:refactor:api_surface_unchanged
