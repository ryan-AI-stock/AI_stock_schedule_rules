# Ridge Prospective Shadow Schedule Contract

This contract covers the Backtest Lab vNext Ridge prospective shadow hook:

```text
.github/workflows/vnext-ridge-prospective-shadow.yml
```

It is a shadow prediction hook only. It must not become a formal daily report,
Drive/PDF publisher, or trade-decision workflow.

## Runtime Boundary

The workflow is allowed to append prospective shadow predictions only when all
of these are true:

- the shared schedule gate confirms a Taiwan official market open day
- the workflow maps the shared gate `target_date` to the decision date for
  scheduled runs
- exact current Layer0-4 `primary80` source package exists for that decision
  date
- freshness checks pass
- corporate-action guard passes

If the market is closed, including typhoon closure or holiday, the workflow
should skip successfully.

If the market is open but exact current Layer0-4 data, freshness, or
corporate-action guard is missing, the workflow must hard block. It must not
carry forward an older Layer0-4 package.

## Required Isolation

The hook must remain isolated from formal systems:

- no PDF generation
- no Google Drive publish
- no formal daily report update
- no trade decision update
- no overwrite of prior predictions
- no promotion to formal or formal-ready status

Prediction output is append-only. Outcome evaluation must wait until the 10TD
or 20TD maturity window is complete and then write a separate evaluation ledger.
The evaluator must not rewrite or overwrite the original prediction ledger.

## Required Audit Flags

Readiness or ledger artifacts for this hook must keep these flags false:

- `formal_model_changed=false`
- `trade_decision_changed=false`
- `active_in_trade_decision=false`
- `report_changed=false`

The hook must also expose:

- `not_live_rule=true`
- `carried_scope_allowed=false`
- `ready_for_first_prospective_prediction`
- latest exact Layer0-4 source package date

## Current Governance Decision

The Core handoff for `TASK-BACKTEST-CORE-VNEXT-P3-RIDGE-PROSPECTIVE-SHADOW-CONTRACT-001`
reports that the hook exists, but first live prediction remains blocked until
Radar/Data provides the current exact Layer0-4 source package.

Schedule governance must not treat the hook as live-ready merely because the
workflow file exists. The workflow must first satisfy the shared schedule gate
contract and the exact-current source package contract.

## Downstream Healthcheck

`python -m stock_schedule_rules.contract_healthcheck --root work` checks this
hook as a Backtest Lab downstream workflow. A missing shared schedule gate is a
contract failure, not a TODO, because this hook has a `schedule:` trigger.
