# Repair Brief: CSCI-47 follow-up — security gate composition semantics (PR #127)

## Context

PR #127 (CSCI-47 / Phase G-3) review で **security policy gate と default
severity floor の合成セマンティクスに footgun** が見つかった。原案 brief (AC C
step4/5) が「合成」を曖昧にしていた spec hole 由来。本 repair で安全側
セマンティクスに直し、回帰テストで pin する。CI は green のままなので **既存
挙動を壊さず** (既存テスト全件は新セマンティクスでも pass する) gate ロジックの
み差し替える repair。

対象は `src/semantic_ci_code/suite/security.py` の `_has_user_gate` /
`_status_for_added` / `_violates_user_policy` 周辺のみ。schema / evaluator /
sensor / framework は変更しない。

## Defect (現状の挙動)

`_status_for_added` は user gate (`severity.not_in` / `max_count` /
`deny_added`) が **1 つでも** あると default severity floor (`_FAIL_SEVERITIES`)
を **丸ごと skip** する。結果:

- `findings.added.max_count: 10` だけ宣言 → candidate が **critical** 新規
  finding を 1 件追加しても `1 > 10` が False で **`pass`** (floor が消える)
- `rules.deny_added: [sql-injection]` だけ宣言 → 他ルールの **high/critical**
  新規 finding がすり抜ける

= 「gate を**追加**したつもり」が severity floor を**暗黙で無効化**する。

## Required Semantics (安全側に修正)

post-suppression の added findings に対し、**以下の OR でいずれか True なら当該
判定対象は `fail`**:

1. **severity gate**: 各 added finding の severity が
   - `findings.added.severity.not_in` が **指定されていれば** その集合に属する
   - **未指定なら** default floor `_FAIL_SEVERITIES` に属する
   (= `not_in` を書いた時だけ floor を置換。書かなければ floor は残る)
2. **count gate**: `findings.added.max_count` 指定時、added 件数 > max_count
3. **rule gate**: `rules.deny_added` 指定時、SAST finding の `rule_id` が集合に属する

`max_count` / `deny_added` は floor を**置換せず加算**される。これにより
「count cap だけ / deny だけ」を足しても severity floor は維持される。

`policy is None` または該当 sub-block が全て None の場合は従来どおり floor のみ。

## P2 論点 (Codex 判断に委ねる): max_count の集計単位

現状 `max_count` は **sensor 単位** (`_status_for_added` が per-sensor 呼び出し)
で評価される。`max_count: 2` で semgrep 2件 + pip-audit 2件 = 計4件でも各
センサー 2 件なので pass になる。**ユーザー直感は「全スキャナ合計で最大 N」**
の可能性が高い。

- **推奨**: `max_count` を **全センサー合算の added 総数** で評価する
  (severity gate / rule gate は引き続き per-finding 判定で良い)。
- ただし実装コスト・既存集約構造との整合を見て **per-sensor 維持** を選ぶ場合は、
  その判断理由を Completion Summary に明記し、後述 docs にも per-sensor である旨を
  記載すること。
- どちらを採っても、選んだ単位を**テストで固定**する (下記 AC)。

## Acceptance Criteria

- [ ] `_status_for_added` (または相当ロジック) を上記 Required Semantics に
      修正。`severity.not_in` 未指定時は default floor が**残る**こと。
- [ ] `max_count` / `deny_added` は severity gate を置換せず **OR 加算** される。
- [ ] **回帰テスト追加** (現状 footgun を捕捉する、現行コードで fail するテスト):
  - `max_count: 10` のみ宣言 + candidate に **critical** 新規 finding 1件
    → `fail` (floor 維持の証明)
  - `rules.deny_added: ["sql-injection"]` のみ宣言 + candidate に **high** 新規
    finding (rule_id は deny 集合外) → `fail` (floor 維持の証明)
  - `severity.not_in: [high, critical]` 指定 + **medium** added → `pass`
    (not_in 指定時は floor 置換、既存テスト相当を維持)
  - `severity.not_in: [high, critical]` 指定 + **high** added → `fail`
  - `deny_added` + 該当 rule_id の **info** finding → `fail` (rule gate 加算)
- [ ] **max_count 集計単位を確定しテストで固定**: global total を採るなら
      2センサー合算で max_count 超過 → `fail` のテスト。per-sensor 維持なら
      その旨を pin するテスト。
- [ ] 既存テスト (`tests/suite/test_security.py` 他) **全件 green** のまま
      (新セマンティクスは既存ケースを壊さない)。

## P3 nits (同 PR 内で一緒に対応、任意だが推奨)

- [ ] **default drift set の二重定義解消**: `suite/security.py:_DEFAULT_DRIFT_FIELDS`
      を `sensor.delta.DEFAULT_DRIFT_FIELDS` 再利用に寄せるか、
      `_drift_fields_for_scanner(None) == _drift_fields_for_scanner(ScannerPolicy())`
      を test で固定 (片方編集時の drift を検出可能にする)。
- [ ] **private import の解消**: `from ...sensor.models import _FAIL_SEVERITIES`
      が underscore-private を跨いでいる。`sensor.models` 側で public alias
      (例 `FAIL_SEVERITIES`) を export して suite はそれを使う。`_FAIL_SEVERITIES`
      は後方互換 alias として残して可。

## Scope

- IN: `src/semantic_ci_code/suite/security.py`、`tests/suite/test_security.py`
      (回帰テスト追加)、P3 対応時のみ `src/semantic_ci_code/sensor/models.py`
      (public alias export) + `src/semantic_ci_code/suite/security.py`
- OUT: schema / `framework/` / `evaluator/` / `sensor/delta.py` のロジック変更、
      CLI、出力、SuiteVerdict 集約 (`combine_verdict` は変更不要)

## Allowed Dependencies

なし (新規依存禁止)。

## Done When

- All acceptance criteria checked
- `ruff check .` / `ruff format --check .` pass
- `python -m pytest -q` pass
- `python scripts/regen_schemas.py --check` pass (schema 不変の確認)
- PR #127 に追記コミット (同ブランチ `codex/csci-47-suite-evaluator`)、
  Completion Summary に「footgun 修正 + max_count 集計単位の選択と理由」を明記
