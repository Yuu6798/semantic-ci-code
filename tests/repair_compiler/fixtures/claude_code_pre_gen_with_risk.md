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

## Risk Areas
- "require_missing_api"

## Forbidden Zones
- {"constraint_id": "lock_api_surface", "operator": "equals_baseline", "source": "user", "target": "api_surface"}

## Required Additions
- {"constraint_id": "require_missing_api", "expected": "pkg.profile", "operator": "includes_all", "source": "user", "target": "api_surface"}

## Template Implications
- "template:refactor:api_surface_unchanged"
