# Downstream Runtime Contract

This repo is the runtime source of truth for stock-report scheduling. Downstream
GitHub Actions should checkout `ryan-AI-stock/AI_stock_schedule_rules` at run
time and use the gate output instead of reading Google Sheets.

## Required Workflow Shape

- Scheduled stock-report workflows must run the shared gate before report
  generation.
- Daily-style workflows should call:

```powershell
python -m stock_schedule_rules.gate --profile daily --github-output $env:GITHUB_OUTPUT
```

- Weekly workflows should either call the shared CLI with the weekly profile or
  load `schedule_rules.json` through `SCHEDULE_RULES_PATH` while preserving the
  same final-trading-day behavior.
- A scheduled workflow must stop report generation when `should_run` is not
  `true`.
- Downstream repos remain responsible for duplicate-output protection, fixed
  Drive file handling, data completeness checks, and report-specific validation.

## Date Output Contract

- `target_date` is the canonical gate output for the intended Taiwan market
  date.
- `AI_stock_market_daily` should pass `target_date` into report generation as
  `REPORT_DATE`.
- `AI_stock_rotation_radar` should use its report-date step output as
  `report_date` / `target_date` for report generation and publish steps.
- `AI_stock_backtest_lab` workflows may map `target_date` into domain-specific
  names such as `report_date` or `signal_date`, but the mapping should be
  explicit in the workflow.
- Manual input dates must override the gate date only inside
  `workflow_dispatch` flows.

## Bypass And Validation Boundaries

- `workflow_dispatch` and explicit `force_run`/validation modes must remain
  usable for recovery and manual verification.
- Manual bypass should not weaken scheduled-run completeness checks unless the
  downstream repo explicitly documents that verification mode.
- TWSE calendar fetch failures should not fail the workflow at the gate; the
  gate should fail closed by emitting `should_run=false` with a clear reason.
- The shared schedule repo must not store or log downstream secrets.

## Health Check Evidence To Keep Current

When auditing downstream health, verify both static workflow wiring and recent
live Action runs:

- workflow checkout of `ryan-AI-stock/AI_stock_schedule_rules`
- gate invocation or `SCHEDULE_RULES_PATH` use
- `should_run` guard before report generation
- explicit mapping from `target_date` to downstream date variables
- successful recent scheduled runs, or a documented non-code infrastructure
  blocker

Phase 0 static workflow checks can be run from this repo with:

```powershell
python -m stock_schedule_rules.contract_healthcheck --root work
```

This prototype checks local downstream workflow files only. Live GitHub Actions
evidence still needs to be verified separately when doing a full audit.
