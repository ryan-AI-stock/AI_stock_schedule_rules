# TWSE Calendar Fallback Policy

This is a Phase 0 policy proposal. It documents fallback options for TWSE
calendar fetch failures. It does not change the live gate behavior.

## Current Policy

Scheduled runs fail closed when the TWSE calendar is unavailable or returns a
non-JSON response:

- `should_run=false`
- `target_date=""`
- `reason=calendar_unavailable`
- workflow exits successfully at the gate instead of failing the job

Manual recovery remains available through `workflow_dispatch` and explicit
`force_run` / validation paths.

## Options

### Option A: Keep Fail-Closed For Scheduled Runs

Scheduled runs do not generate reports when the calendar cannot be verified.

Pros:

- avoids producing reports on TWSE holidays, typhoon closures, or other special
  closures
- keeps the shared gate conservative and easy to reason about
- avoids pushing uncertainty into downstream report logic

Risks:

- a transient TWSE endpoint issue can delay a valid report cycle
- repeated endpoint failures require manual verification or dispatch
- downstream observers may see skipped runs without a new report until recovery

Recommended status: keep as the default shared gate policy.

### Option B: Cached Calendar Fallback

Use a previously validated TWSE calendar snapshot when the live endpoint fails.
If no validated cache exists for the year, continue to fail closed.

Pros:

- reduces false skips caused by temporary non-JSON or redirect responses
- keeps scheduled runs conservative when there is no trustworthy cache
- can be tested without changing downstream workflow contracts

Risks:

- stale cache may miss newly announced closures
- cache creation and refresh need an audit trail
- cache provenance must be visible in logs and gate output

Recommended status: candidate Phase 1. Implement only with tests, a visible
`reason` such as `calendar_cache_fallback`, and a freshness limit.

### Option C: Weekday Fallback

When TWSE calendar is unavailable, treat normal weekdays as trading days.

Pros:

- minimizes missed reports when the calendar endpoint is temporarily down
- simple to implement

Risks:

- can produce reports on holidays or emergency closures
- can create misleading `target_date` decisions
- weakens the guarantee that scheduled runs only execute on verified TWSE
  trading days

Recommended status: not recommended for unattended scheduled runs.

### Option D: Manual Fail-Open Only

Keep scheduled runs fail-closed, but let `workflow_dispatch` / `force_run`
bypass the calendar after a human has chosen to recover or validate a run.

Pros:

- preserves conservative automation
- provides a practical recovery path for SECTOR_RADAR and other downstream
  reports
- keeps manual historical `report_date` flows separate from live quote refresh
  risk

Risks:

- requires a human to notice and trigger recovery
- manual flows must keep their own target-date data guards

Recommended status: already aligned with the current contract and should remain.

## Recommendation

Do not change the shared gate behavior in Phase 0. Keep scheduled runs
fail-closed on `calendar_unavailable`, and use manual dispatch for recovery.

For Phase 1, consider a cached-calendar fallback only if TWSE endpoint
instability causes repeated valid-report delays. That implementation should:

- require a validated yearly calendar cache
- emit an explicit fallback reason
- cap cache age or require cache provenance
- keep manual dispatch and downstream completeness checks intact
- add tests for non-JSON live responses, missing cache, stale cache, and valid
  cache fallback
