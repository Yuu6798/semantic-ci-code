# Dogfooding Report — Scale & Security (2026-06-07)

This report records a dogfooding pass with two distinct objectives, run
across three external public Python repositories
(`BerriAI/litellm`, `langchain-ai/langgraph`, `pdm-project/pdm`):

1. **Scale / large-function robustness** — does the core engine produce a
   well-formed verdict on large diffs and large aggregated functions?
2. **Security observation** — does the SSP sensor layer (SAST = Semgrep,
   SCA = pip-audit) catch real merged-then-fixed vulnerabilities, and
   where does it structurally fall short?

Core engine path for every scale/random case:

```bash
semantic-ci check \
  --baseline-rev <sha>^ --candidate-rev <sha> \
  --target <yaml> --package-root <pkg> --format json
```

SSP path for every security case:

```bash
semantic-ci ssp scan --sensor {semgrep,pip-audit} \
  --baseline-dir <tree> --candidate-dir <tree> \
  [--config <ruleset>] [--package-root <p>]
```

The pass is organised as **three sub-passes**: Pass 1 (5 scale cases,
目標アリ with a randomized constraint surface, seed `20260607`), Pass 2
(5 random-sampling cases, generic 0-constraint target, extractor
robustness only), and Pass 3 (5 security cases incl. 2 real
vulnerabilities). All commits exercised are **MERGED on main**.

## Scope framing (read before the matrices)

Per `CLAUDE.md` Scope guard and `docs/code_semantic_ci_design.md §23.3`,
the engine derives a verdict from the **declared** `target.yaml`, not
from the author's true intent or the PR's merge outcome. Every FAIL
below was on a **merged** commit. **This is not a false-positive rate.**
A FAIL means "this change is not a behavior/API-preserving refactor under
the declared constraint" — which is true for all four FAIL cases; they
merged because they were legitimate features or intentional public-surface
changes, not because the verdict was wrong. To measure whether FAIL
tracks *human rejection* you need actually-closed PRs or intent-matched
targets; the prior pass
(`docs/dogfooding_real_pr_complexity.md`) did exactly that with a closed
langgraph PR (#3700). This pass deliberately trades that for **scale and
constraint randomization**, so verdict×intent×outcome alignment is only
expected on the API-preserving case (#2).

## Pass 1 — Large-scale / large-function (目標アリ, randomized constraint, seed 20260607)

Constraint surface drawn at random per case from the seed; the draw
yielded `api_surface` 4/5 and `template_refactor` 1/5. Complexity and
effects constraints were added as a **supplementary run** on the three
litellm large-function commits (recorded in the Δcyc/Δcog/effects column).

| # | Repo / commit / PR | Constraint (seed-drawn) | Scale | Verdict | Wall | Tool judgment |
|---:|---|---|---|---|---|---|
| 1 | `BerriAI/litellm` `216c68db04` (#29582 fix(gemini) googleSearch+tools, `main.py`) | template_refactor | 9 files / +274 | FAIL | 11s (warm) | Correct — feature-shaped change fails the refactor template (api added=2 / removed=2). Supplementary: complexity Δcyc +15 / Δcog +12 → FAIL; effects → satisfied |
| 2 | `BerriAI/litellm` `d5d6b26a72` (#28720 fix bedrock streaming hot-path perf, `streaming_handler.py`) | api_surface | 4 files / +1141 / -51 | PASS | 100s (cold) | Correct **non-vacuous** PASS — large perf refactor preserves public API; complexity Δcyc +3 / Δcog +4 (change *detected*, so not vacuous); effects satisfied |
| 3 | `BerriAI/litellm` `95015de733` (#28898 feat claude code goal mode, `utils.py`) | api_surface | 20 files / +1036 / -185 | FAIL | 100s | Correct — feature adds 3 public symbols. Supplementary complexity Δcyc +49 / Δcog +46 → FAIL (huge function file aggregated correctly); effects satisfied |
| 4 | `langchain-ai/langgraph` `8c4e698c` (#5252 solidify public/private differentiations) | api_surface | 89 files / +4094 / -4088 | FAIL | 6s | Correct — mass public→private rename → api added=254 / removed=260 detected. Largest single input; extractor computed a 514-symbol surface delta without issue |
| 5 | `pdm-project/pdm` `5397cc96` (#3797 fix use existing pyproject.toml) | api_surface | 4 files / +264 / -25 | FAIL | 6s | Correct — api added=3 / removed=1 |

Verdict×intent×outcome fully align only on **#2** (perf fix, API
preserved → PASS → merged) = the extractor sweet spot. The other four
FAILs are correct against the declared strict refactor/preservation
constraint but were merged as legitimate feature / intentional-surface
changes (see scope framing above).

**Performance.** Cold full-litellm extraction ≈ 103s; warm
(`CodeState` cache) ≈ 11s for the same input. The cache is materially
effective for repeated CI on the same tree.

## Pass 2 — Random sampling (extraction robustness, generic 0-constraint target)

Goal: extractor robustness only — no crash, no timeout, well-formed
`CodeState` and diff. The target is the generic 0-constraint skeleton, so
every case is a PASS by construction; the signal is whether extraction
**completes cleanly**.

| Repo / commit | Description | `--package-root` | Scale | Wall | Extraction |
|---|---|---|---|---|---|
| `BerriAI/litellm` `f047b1571e` | otel 401 | `litellm/integrations` | 7 files / +128 / -7 | 15s | clean |
| `BerriAI/litellm` `51769a8ede` | fal_ai image-gen feature | `litellm/llms` | 6 files / +313 / -1 | 31s | clean |
| `BerriAI/litellm` `4ec4ab99d0` | mcp per-server env vars | `litellm/proxy` | 37 files / +5951 / -110 | 35s | clean (largest LOC input) |
| `pdm-project/pdm` `9015fbfc` | tomlkit parse-on-write | `src/pdm` | 21 files / +134 / -91 | 6s | clean |
| `pdm-project/pdm` `fcc8372b` | skip same-version candidates | `src/pdm` | 2 files / +7 / -6 | 6s | clean |

All 5 cases: extraction succeeded, **no crash, no timeout, well-formed
JSON**, including the +5951 LOC `litellm/proxy` change.

## Pass 3 — Security (SSP: SAST = Semgrep, SCA = pip-audit)

> **VALIDITY WARNING — SAST sub-pass was network-blocked.** Every Semgrep
> registry ruleset (`p/security-audit`, `p/secrets`, `p/python`) returned
> **HTTP 403 from semgrep.dev** under this environment's network policy
> ("Failed to download configuration from
> https://semgrep.dev/c/p/security-audit HTTP 403" + "invalid configuration
> file found"). Consequently **Semgrep scanned 0 paths with 0 loaded
> rules** — the "0 findings" results are `0-rules × 0-files`, i.e.
> meaningless. **The SAST detection results in this Pass are NOT VALID as a
> capability measurement.** The claim that pattern SAST "misses" the SSRF /
> business-logic vulnerabilities could **not be tested in this run**; it
> remains an a-priori hypothesis (Phase H rationale), not an empirical
> result of this pass. The SCA (pip-audit) sub-pass is unaffected and was
> separately positive-controlled (see below).

**Setup note.** Semgrep was installed in an isolated venv (a
debian-managed PyJWT blocked a global install); pip-audit was
pre-installed. SAST registry rulesets (`p/security-audit` + `p/secrets` +
`p/python`) were **attempted but unreachable** (HTTP 403, see validity
warning above), so no real rules ever loaded.

Two **real vulnerabilities** were selected from litellm git history —
each was MERGED unnoticed and later manually fixed, so the parent of each
fix commit (`<fix>^`) is the vulnerable merged state. **This selection is
independent of any scanner**: the evidence that these vulns existed and
were merged unnoticed comes from the fix commits and their commit-message
descriptions, not from a SAST run. This is the one empirically solid
security finding of the pass — *real vulnerabilities do get merged
unnoticed and only later fixed by hand*:

- `BerriAI/litellm` `f1d07c13e5` — *"fix: block SSRF fields in RAG
  ingest vector_store config"*. **SSRF**:
  `aws_sts_endpoint` / `aws_web_identity_token` /
  `aws_bedrock_runtime_endpoint` supplied in
  `ingest_options.vector_store` were passed into boto3 STS client
  construction; any authenticated caller could redirect `AssumeRole` to
  an attacker-controlled server → instance-profile credential theft.
  File: `litellm/proxy/rag_endpoints/endpoints.py`.
- `BerriAI/litellm` `b95130eb32` — *"fix: block client-side pricing
  injection via request body"*. Client-supplied
  `CustomPricingLiteLLMParams` (`input_cost_per_token`, etc.) forwarded
  to `register_model()` → permanently mutates the shared global
  `litellm.model_cost` for **all** users.

### SAST results (Semgrep) — NOT VALID (registry 403, 0 rules loaded)

The table below is retained only to record what was attempted. **Every
"0" is `0-rules × 0-files`** because the registry rulesets returned HTTP
403 and Semgrep scanned 0 paths — see the validity warning at the top of
this Pass. **None of these rows demonstrate a SAST blind spot**; they
demonstrate only that the registry was unreachable.

| Target | "Findings" | Status |
|---|---|---|
| SSRF vulnerable parent (`f1d07c13e5^`, `endpoints.py`) | 0 (0 rules / 0 paths) | NOT VALID — Semgrep never ran with real rules (403) |
| mcp PR `4ec4ab99` touched files (incl. `key_management_endpoints.py`) | 0 (0 rules / 0 paths) | NOT VALID — same 403 |
| otel PR `f047b157` touched files | 0 (0 rules / 0 paths) | NOT VALID — same 403 |

Whether pattern SAST would detect the business-logic SSRF / pricing
injection therefore **remains untested in this run**. It is an a-priori
expectation (the basis for Phase H), not an observation produced here. To
test it for real, a future pass needs a network policy that allows
`semgrep.dev` (or a fully-local equivalent of the registry rules).

**SSP product path — WIRING SMOKE TEST ONLY.** Running `ssp scan --sensor
semgrep` on the SSRF vuln→fix pair with a curated 10-rule **local**
ruleset (no 403, because it is local) returned `aggregate_verdict =
pass`, exit 0, clean envelope. This confirms only that the **product
wiring is healthy** — the local 10-rule set contained **no SSRF or
business-logic rule**, so the `0` / `pass` result says **nothing about
detection capability**. It is not evidence that the vuln is undetectable;
it is evidence that the CLI → adapter → envelope path works end-to-end.
(Authoring note: a curated-ruleset YAML parse error — a colon inside a JWT
`options` dict pattern — had to be quoted/simplified. The semgrep adapter
requires a **local** ruleset file; registry shorthands (`p/...`) are
rejected by design for determinism.)

### SCA results (pip-audit) — VALID (vuln DB reachable, positive-controlled)

Unlike the SAST sub-pass, SCA worked: the pip-audit vulnerability database
was reachable in this environment, confirmed by an explicit **positive
control**.

| Target | Result |
|---|---|
| **Positive control**: `jinja2==2.11.2` (known-vulnerable) | **5 known CVEs** detected (PYSEC-2021-66, CVE-2024-22195, CVE-2024-34064, CVE-2024-56326, CVE-2025-27516) — confirms the vuln DB is reachable and the sensor reports real hits |
| Direct audit of litellm's 12 declared deps (53 resolved incl. transitive) | **0 known vulnerabilities** — a **real negative** (not a silent failure, given the positive control above): clean core dependency tree |
| SSP product path `ssp scan --sensor pip-audit` on litellm worktrees | `status = unknown` / `aggregate_verdict = unknown` / **exit 3** (auto-discovery gap → D8) |

Because the `jinja2==2.11.2` positive control returned its 5 CVEs, the
litellm "0 known vulnerabilities" is a credible true negative, not a
silently-broken scan.

**Root cause of the `unknown`.** SSP SCA auto-discovery
(`_requirements_file` in `src/semantic_ci_code/cli/commands/ssp.py`) only
looks for `requirements.txt` at repo root; the `--locked` fallback only
accepts `pylock.toml` / requirements lockfiles. litellm (PEP 621
pyproject-only) and pdm (`pdm.lock`) declare deps in formats the sensor
does not recognise → `pip-audit --locked .` errors *"no lockfiles
found"* → empty JSON → the adapter degrades to `unknown`. This is
**correct graceful degradation** per the SSP verdict precedence
(`unknown > fail > pass`) — there is **no silent false PASS** — but it is
a real usability gap (registered as a D# below).

## Headline / conclusion

**Scale & robustness.** 16 runs total (5 scale + 5 random + 3 litellm
supplementary complexity/effects + 3 effects), **0 crashes, 0 timeouts,
100% well-formed JSON**. The largest inputs were handled cleanly:
langgraph 89 files / 514-symbol surface delta; `litellm/proxy` +5951
LOC; a huge `utils.py` correctly aggregated to Δcyclomatic +49. The
`CodeState` cache cut a repeat extraction from cold ≈103s to warm ≈11s.
**Conclusion: the engine functions on large-scale / large-function
inputs.**

**Security.** The empirically supported findings of this pass are:

1. **Real vulnerabilities get merged unnoticed.** Two genuine litellm
   vulns (SSRF `f1d07c13e5`, pricing injection `b95130eb32`) were merged
   on main and only later fixed by hand — established from git history /
   commit messages, **independent of any scanner**.
2. **SCA works and litellm's core deps are clean.** pip-audit found 0
   known vulnerabilities across litellm's 12 declared (53 resolved) deps,
   and a `jinja2==2.11.2` positive control returned 5 CVEs, so the 0 is a
   **real negative**, not a silent failure.
3. **SCA auto-discovery gap (D8).** SSP SCA does not recognise modern
   dependency declarations (PEP 621 pyproject, `pdm.lock`), degrading to
   `unknown` (exit 3) — correct graceful degradation, but a real
   usability gap and a fixable `semantic-ci` defect.

**Not demonstrated in this pass (untested here).** Whether deterministic
pattern SAST misses the SSRF / business-logic vulns **could not be tested**:
the Semgrep registry rulesets were network-blocked (HTTP 403, 0 rules
loaded, 0 paths scanned). The "pattern SAST misses logic vulns" position
therefore remains the **a-priori motivation** for Phase H (LLM security
scout layer, `docs/llm_sensor_adapter_planning.md`, CSCI-50〜54) —
*"the LLM is a scout, not a judge"* — but this pass does **not**
empirically validate that blind spot. Redoing the SAST sub-pass requires a
network policy that allows `semgrep.dev` or a fully-local equivalent of the
registry rules.

**SSP product wiring is healthy.** The CLI → adapter → envelope path
produced clean envelopes and correct `unknown` degradation in every run
(the semgrep run with a local ruleset was a wiring smoke test only). So
the limitation surfaced here is in **SCA dependency-source discovery**
(D8) and in the **test environment's network policy** (the 403 that
blocked SAST), not in the SSP protocol itself.

## Reproduction

Per the Engine Contract (`CLAUDE.md`), each case is reconstructible from
public git history plus the inline `target.yaml` below; trees are not
committed. Base SHA is `<head>^` for every case.

### Per-case reproduction inputs

| # | Sub-pass | Repo | Source ref | Base SHA | Head SHA | `--package-root` |
|---:|---|---|---|---|---|---|
| 1 | scale | `BerriAI/litellm` | PR #29582 | `216c68db04^` | `216c68db04` | `litellm` |
| 2 | scale | `BerriAI/litellm` | PR #28720 | `d5d6b26a72^` | `d5d6b26a72` | `litellm` |
| 3 | scale | `BerriAI/litellm` | PR #28898 | `95015de733^` | `95015de733` | `litellm` |
| 4 | scale | `langchain-ai/langgraph` | PR #5252 | `8c4e698c^` | `8c4e698c` | `libs/langgraph/langgraph` |
| 5 | scale | `pdm-project/pdm` | PR #3797 | `5397cc96^` | `5397cc96` | `src/pdm` |
| 6 | random | `BerriAI/litellm` | otel 401 | `f047b1571e^` | `f047b1571e` | `litellm/integrations` |
| 7 | random | `BerriAI/litellm` | fal_ai image-gen | `51769a8ede^` | `51769a8ede` | `litellm/llms` |
| 8 | random | `BerriAI/litellm` | mcp per-server env | `4ec4ab99d0^` | `4ec4ab99d0` | `litellm/proxy` |
| 9 | random | `pdm-project/pdm` | tomlkit parse-on-write | `9015fbfc^` | `9015fbfc` | `src/pdm` |
| 10 | random | `pdm-project/pdm` | skip same-version | `fcc8372b^` | `fcc8372b` | `src/pdm` |
| 11 | security (SSRF) | `BerriAI/litellm` | `f1d07c13e5` fix | `f1d07c13e5^` | `f1d07c13e5` | `litellm/proxy` |
| 12 | security (pricing) | `BerriAI/litellm` | `b95130eb32` fix | `b95130eb32^` | `b95130eb32` | `litellm/proxy` |

### `target.yaml` skeletons

```yaml
# generic (Pass 2 random sampling — 0 constraints, robustness only)
intent: extraction robustness sampling
change:
  primary_kind: refactor
constraints: []
```

```yaml
# api_surface (Pass 1 cases 2-5)
intent: preserve public API surface
change:
  primary_kind: refactor
constraints:
  - id: api_surface_unchanged
    kind: state
    target: api_surface_public
    operator: equals_baseline
    severity: hard
    unknown_policy: fail
```

```yaml
# complexity (Pass 1 supplementary on the 3 litellm large-function commits)
intent: complexity should not increase
change:
  primary_kind: refactor
constraints:
  - id: cyc_no_increase
    kind: delta
    target: complexity_delta.cyclomatic
    operator: less_than_or_equal
    expected: 0
    severity: hard
    unknown_policy: fail
  - id: cog_no_increase
    kind: delta
    target: complexity_delta.cognitive
    operator: less_than_or_equal
    expected: 0
    severity: soft
    unknown_policy: warn
```

```yaml
# effects (Pass 1 supplementary)
intent: side-effect set preserved
change:
  primary_kind: refactor
constraints:
  - id: effects_preserved
    kind: delta
    target: effect_changes
    operator: equals
    expected:
      added: []
      removed: []
    severity: hard
    unknown_policy: fail
```

```yaml
# template_refactor (Pass 1 case 1) — bare template, no user constraints
change:
  primary_kind: refactor
```

### Security reproduction

> **403 limitation (must read before redoing the SAST sub-pass).** In this
> environment, all `semgrep.dev` registry rulesets (`p/security-audit`,
> `p/secrets`, `p/python`) returned **HTTP 403**, so Semgrep loaded 0 rules
> and scanned 0 paths. To redo the SAST sub-pass as a real capability test,
> run it under a network policy that allows `semgrep.dev`, **or** vendor a
> fully-local equivalent of those registry rules (the local ruleset used
> here was only a 10-rule wiring smoke test with no SSRF / logic rule). The
> SCA sub-pass below is unaffected.

```bash
# SAST: registry rulesets p/security-audit + p/secrets + p/python
# NOTE: returned HTTP 403 in this environment (0 rules loaded) — needs a
# network policy allowing semgrep.dev, or a fully-local ruleset, to be valid.
semantic-ci ssp scan --sensor semgrep \
  --baseline-dir <f1d07c13e5^ tree> --candidate-dir <f1d07c13e5 tree> \
  --config <local-ruleset.yml> --package-root litellm/proxy
# SSRF case repro pair: f1d07c13e5^ vs f1d07c13e5,
# file litellm/proxy/rag_endpoints/endpoints.py

# SCA
semantic-ci ssp scan --sensor pip-audit \
  --baseline-dir <tree> --candidate-dir <tree> --package-root litellm
# SCA positive control (confirms the vuln DB is reachable):
#   pip-audit on jinja2==2.11.2 → 5 CVEs (PYSEC-2021-66, CVE-2024-22195,
#   CVE-2024-34064, CVE-2024-56326, CVE-2025-27516)
```

The semgrep adapter requires a **local** ruleset file; `p/...` registry
shorthands are rejected by design for determinism (run them through
`semgrep` directly, or vendor the rules into a local YAML).

## Tracking

Findings classification (hazard D# vs observation) for this pass and all
prior passes is consolidated in
**`docs/dogfooding_findings_tracker.md`**. This pass registered:

- **D8** (SCA auto-discovery gap, 未解決) — `_requirements_file` ignores
  PEP 621 pyproject / `poetry.lock` / `pdm.lock`, so modern dependency
  declarations degrade to `unknown`. A genuine, fixable `semantic-ci`
  defect.
- **F6** (SAST logic-vuln blindspot) — **UNTESTED HYPOTHESIS in this
  pass**, not a demonstrated observation: the Semgrep registry rulesets
  returned HTTP 403, so Semgrep never ran with real rules (0 rules / 0
  paths). The expectation that pattern SAST misses semantic / business-logic
  vulns remains an a-priori limitation cross-linked to Phase H
  (`docs/llm_sensor_adapter_planning.md`) as **motivation**, not as an
  empirical result. Observation-only line (not a D#). To convert it into a
  demonstrated observation, redo the SAST sub-pass under a network policy
  allowing `semgrep.dev` or with a fully-local equivalent ruleset.

Do not re-tabulate D-class status inside this report; update the tracker
when D8 status changes.
