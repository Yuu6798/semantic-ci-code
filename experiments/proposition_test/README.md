# Proposition Test: deceptive-fix detection

This experiment measures how well each of `ruff`, `mypy`, `pytest`, and
`semantic-ci compare` detects **deceptive bug fixes** — changes that claim
to fix a bug but actually weaken security or evade tests.

## Layout

```
proposition_test/
├── REPORT.md                    main report (Japanese, with matrix + analysis)
├── target.yaml                  declared intent + custom constraints
├── baseline/authpkg/            "pre-fix" code (correct implementation)
├── candidates/
│   ├── 00_honest_fix/           legitimate fix (control)
│   ├── 01_always_true/          deception #1 — body returns True
│   ├── 02_plaintext_compare/    deception #2 — bcrypt removed, plaintext ==
│   ├── 03_swallow_exception/    deception #3 — except: return True
│   ├── 04_skip_tests/           deception #4 — broken impl + skipped tests
│   ├── 05_lint_silence/         deception #5 — # noqa / # type: ignore
│   └── 06_env_backdoor/         deception #6 — os.environ backdoor
├── runner/
│   └── run_one.py               runs all 4 tools on one candidate, emits JSON
└── results/
    ├── matrix.md                detection matrix summary
    └── *.json                   raw per-candidate detection data
```

## Reproduce

From this directory:

```bash
# Run one candidate:
python3 runner/run_one.py candidates/03_swallow_exception

# Run all and save:
for c in candidates/*/; do
  python3 runner/run_one.py "$c" > "results/$(basename $c).json"
done
```

The run requires `bcrypt`, `pytest`, `mypy`, `ruff`, and the `semantic-ci`
CLI all installed against the *same* Python interpreter. Easiest:

```bash
pip install -e ".[dev]"        # from repo root, gives semantic-ci
pip install bcrypt pytest mypy ruff
```

Then run via `python3 -m pytest` etc. (the runner does this automatically).

## Headline result

|             | ruff | mypy | pytest | semantic-ci |
|-------------|:----:|:----:|:------:|:-----------:|
| detected /6 | 0    | 1    | 1      | **3**       |

`03_swallow_exception` and `06_env_backdoor` slip past **all four** tools.
See `REPORT.md` for the full per-candidate analysis and improvement notes.
