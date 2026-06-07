# AI Stock Schedule Rules

Shared schedule rules and a small gate CLI for stock-report workflows under `ryan-AI-stock`.

## Purpose

This repo centralizes runtime schedule decisions for stock tools:

- daily reports run only on TWSE trading days after 15:00 Asia/Taipei.
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

Existing report repos should integrate this gate gradually:

- `AI_stock_market_daily`: add a low-risk daily gate before the report step.
- `AI_stock_backtest_lab`: add a low-risk daily gate before frozen strategy report generation.
- `AI_stock_rotation_radar`: already has a gate; align behavior and tests with this repo.
- `AI_stock_market_weekly`: already has a weekly final-trading-day gate; align behavior and tests with this repo.

Do not change report content, HTML/PDF templates, fixed Drive file IDs, LINE entrypoints, model formulas, or backtest results while integrating the gate.
