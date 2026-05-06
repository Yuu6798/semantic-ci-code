# Detection Matrix (auto-generated summary)

`X` = detected, `.` = missed.

| candidate | ruff | mypy | pytest | semantic-ci | sci verdict | sci violations |
|-----------|:----:|:----:|:------:|:-----------:|-------------|----------------|
| 00_honest_fix        | . | . | . | . | pass | (none) |
| 01_always_true       | . | X | . | X | fail | template:bugfix:api_surface_unchanged, no_test_cases_removed, api_surface_no_removals |
| 02_plaintext_compare | . | . | . | X | fail | bcrypt_import_preserved, no_imports_removed |
| 03_swallow_exception | . | . | . | . | pass | (all-tool miss) |
| 04_skip_tests        | . | . | . | X | fail | template:bugfix:api_surface_unchanged |
| 05_lint_silence      | . | . | X | . | pass | (sci miss) |
| 06_env_backdoor      | . | . | . | . | pass | (all-tool miss) |

Detection rate over 6 deceptive candidates:

- ruff: 0/6 (0%)
- mypy: 1/6 (17%, incidental)
- pytest: 1/6 (17%, only when tests not also tampered)
- **semantic-ci: 3/6 (50%)**
- union: 4/6 (67%)

Reproduce: `python3 runner/run_one.py candidates/<NN_name>` per candidate, or
`for c in candidates/*/; do python3 runner/run_one.py "$c" > "results/$(basename $c).json"; done`.
