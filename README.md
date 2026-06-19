# AI Stock Schedule Rules

Shared schedule rules and a small gate CLI for stock-report workflows under `ryan-AI-stock`.

## Purpose

This repo centralizes runtime schedule decisions for stock tools:

- daily reports run only on TWSE trading days after 15:00 Asia/Taipei.
- daily reports do not have a hard same-day cutoff; downstream repos should keep retrying and stop duplicate output with their own completed-report checks.
- weekly reports run after the actual final TWSE trading day of the week.
- monthly and quarterly profiles are defined for future report tools.
- TWSE calendar failures must not make GitHub Actions fail at the gate.
- manual dispatch / force-run flows can bypass the gate.

Google Sheets remains the project-management source of truth. Runtime workflows should read this versioned repo instead of calling Google Sheets during GitHub Actions.

## CLI

```powershell
python -m stock_schedule_rules.gate --profile daily --github-output $env:GITHUB_OUTPUT
```

The CLI writes:

- `should_run=true|false`
- `target_date=YYYY-MM-DD`
- `period_type=daily|weekly|monthly|quarterly`
- `reason=...`

## Integration Policy

Downstream report repos should keep their workflow integration aligned with
the runtime contract in
[`docs/downstream_runtime_contract.md`](docs/downstream_runtime_contract.md).

Current expected integrations:

- `AI_stock_market_daily`: scheduled daily gate, with `target_date` passed as
  `REPORT_DATE`.
- `AI_stock_market_weekly`: scheduled weekly gate, with `SCHEDULE_RULES_PATH`
  passed to report generation.
- `AI_stock_rotation_radar`: scheduled daily gate, with manual `report_date`
  override preserved.
- `AI_stock_backtest_lab`: scheduled daily gate for scorecard and stock-pool
  observation reports, with manual input overrides preserved.

Do not change report content, HTML/PDF templates, fixed Drive file IDs, LINE entrypoints, model formulas, or backtest results while integrating the gate.
