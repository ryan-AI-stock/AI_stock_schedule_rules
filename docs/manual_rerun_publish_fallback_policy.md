# Manual Rerun Publish Fallback Policy

This policy covers `workflow_dispatch` recovery after Google OAuth / Drive
publish failures. It does not change scheduled-run gate behavior.

## Problem

When a Google refresh token expires, a scheduled report may finish analysis but
fail while updating the fixed Google Drive PDF. The token may be updated one or
more days later. A manual rerun at that later time must still be able to produce
and overwrite the fixed PDF, even when the action-day market data is incomplete
or does not match the originally requested date.

## Scheduled Runs

Scheduled runs stay conservative:

- use the shared gate `target_date`
- keep trading-day and data-completeness guards
- skip or fail closed when the required scheduled date cannot be verified
- never publish an incomplete report just because the workflow was scheduled

This policy must not turn scheduled runs into fail-open runs.

## Manual Rerun Contract

Manual `workflow_dispatch` recovery defaults to best-effort publish fallback:

- `manual_rerun=true`
- `require_exact_date=false` unless the user explicitly requests exact mode
- `requested_date` records the user input, gate target, or action-day request
- `actual_report_date` or `actual_signal_date` records the date actually used
  to build the PDF
- `fallback_reason` records why `actual_*_date` differs from `requested_date`
- the fixed Google Drive file should be overwritten when the PDF is generated,
  unless a validation flag such as `skip_public_upload=true` explicitly disables
  public publishing

If `requested_date` is missing or incomplete, the manual rerun should select the
latest complete reportable data date for that report type. Prefer the latest
complete date on or before `requested_date`; if the repo cannot safely evaluate
that bound, use the latest complete available date and log the limitation.

If no complete reportable data exists, the workflow should fail clearly or mark
the run blocked. It should not overwrite the fixed PDF with an incomplete report.

## Exact Mode

Exact mode is opt-in only:

- `require_exact_date=true`
- or repo-specific names such as `require_exact_report_date=true` /
  `require_exact_signal_date=true`

Only in exact mode may a manual rerun stop without producing a PDF because the
exact requested date is unavailable. The failure or skip reason must state that
exact mode was requested.

## Required Outputs

Downstream repos should expose these values in logs, GitHub outputs, report
manifest files, or equivalent audit artifacts:

- `manual_rerun`
- `requested_date`
- `actual_report_date` or `actual_signal_date`
- `require_exact_date`, `require_exact_report_date`, or
  `require_exact_signal_date`
- `fallback_reason`
- fixed Drive publish result

## Acceptance Scenario

At `2026-06-23 08:24 Asia/Taipei`, a user manually runs Backtest Lab Stock Pool
Observation. The requested or signal date is `2026-06-23`, but the latest common
complete price date is `2026-06-22`.

Expected behavior:

- `manual_rerun=true`
- `requested_date=2026-06-23`
- `require_exact_signal_date=false`
- `actual_signal_date=2026-06-22`
- `fallback_reason=requested_date_incomplete_latest_complete_data`
- generate the `2026-06-22` PDF
- overwrite the existing fixed Google Drive PDF

Unexpected behavior:

- no PDF generated only because `2026-06-23` data is incomplete
- publish skipped only because the action ran on `2026-06-23`
- silently using `2026-06-22` without logging requested and actual dates

## Downstream Implementation Notes

`AI_stock_market_daily`:

- manual rerun should fallback from requested `REPORT_DATE` to the latest
  complete daily stock data date when exact mode is not requested
- publish should overwrite the fixed daily Drive PDF

`AI_stock_market_weekly`:

- manual rerun should fallback to the latest complete weekly report target when
  exact mode is not requested
- existing scheduled weekly final-trading-day gate stays conservative

`AI_stock_rotation_radar`:

- manual `report_date` reruns should use target-date processed snapshots when
  available
- if the requested date is incomplete and exact mode is false, fallback to the
  latest complete processed report date and overwrite the fixed radar PDF

`AI_stock_backtest_lab`:

- Stock Pool Observation should map manual fallback into `actual_signal_date`
- Model Scorecard should map manual fallback into `actual_report_date`
- `require_exact_signal_date` / `require_exact_report_date` should default to
  false for manual recovery

## Healthcheck Status

The Phase 0 static healthcheck reports missing manual fallback fields as TODOs,
not failures. This keeps current downstream wiring checks useful while making
the manual recovery contract visible for the next implementation phase.
