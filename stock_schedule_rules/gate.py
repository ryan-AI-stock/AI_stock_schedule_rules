"""Shared trading-day schedule gate for stock report workflows."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Callable, Iterable


TAIPEI_TZ = timezone(timedelta(hours=8))
DEFAULT_RULES_PATH = Path(__file__).resolve().parents[1] / "schedule_rules.json"
TWSE_HOLIDAY_URL = "https://www.twse.com.tw/holidaySchedule/holidaySchedule?response=json"


@dataclass(frozen=True)
class GateDecision:
    should_run: bool
    target_date: str
    period_type: str
    reason: str

    def as_github_output(self) -> str:
        return "\n".join(
            (
                f"should_run={str(self.should_run).lower()}",
                f"target_date={self.target_date}",
                f"period_type={self.period_type}",
                f"reason={self.reason}",
            )
        )


def load_rules(path: Path = DEFAULT_RULES_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def evaluate_gate(
    rules: dict,
    profile_name: str,
    now_tw: datetime,
    trading_dates: set[date] | None,
    *,
    manual_dispatch: bool = False,
    force_run: bool = False,
) -> GateDecision:
    profile = rules["profiles"][profile_name]
    period_type = profile["period_type"]

    if manual_dispatch and (force_run or rules.get("manual_dispatch", {}).get("bypass_gate", True)):
        target = now_tw.date()
        return GateDecision(True, target.isoformat(), period_type, "manual_dispatch_bypass")

    if trading_dates is None:
        return GateDecision(False, "", period_type, "calendar_unavailable")

    current = now_tw.date()
    run_after = _parse_hhmm(profile.get("run_after", "15:00"))
    run_on = profile["run_on"]
    if run_on == "trading_day":
        current_window_open = now_tw.time() >= run_after
        target = _latest_open_daily_target(
            trading_dates,
            current,
            current_window_open=current_window_open,
            retry_until_success=bool(profile.get("retry_until_success", False)),
        )
        if target is None:
            reason = "before_run_after" if not current_window_open else "not_trading_day"
            return GateDecision(False, "", period_type, reason)
        if target == current:
            return GateDecision(True, target.isoformat(), period_type, "trading_day_after_run_after")
        return GateDecision(True, target.isoformat(), period_type, "retry_previous_trading_day_until_success")

    if now_tw.time() < run_after:
        return GateDecision(False, "", period_type, "before_run_after")

    if run_on == "last_trading_day_of_week":
        target = _last_trading_day_in_range(
            trading_dates,
            current - timedelta(days=current.weekday()),
            current + timedelta(days=6 - current.weekday()),
        )
        return _period_decision(current, target, period_type, "last_trading_day_of_week")

    if run_on == "last_trading_day_of_month":
        first = current.replace(day=1)
        next_month = (first.replace(day=28) + timedelta(days=4)).replace(day=1)
        target = _last_trading_day_in_range(trading_dates, first, next_month - timedelta(days=1))
        return _period_decision(current, target, period_type, "last_trading_day_of_month")

    if run_on == "last_trading_day_of_quarter":
        quarter_start_month = ((current.month - 1) // 3) * 3 + 1
        first = date(current.year, quarter_start_month, 1)
        after_quarter = (date(current.year, quarter_start_month, 28) + timedelta(days=95)).replace(day=1)
        while after_quarter.month % 3 != (quarter_start_month + 3) % 12:
            after_quarter = (after_quarter.replace(day=28) + timedelta(days=4)).replace(day=1)
        target = _last_trading_day_in_range(trading_dates, first, after_quarter - timedelta(days=1))
        return _period_decision(current, target, period_type, "last_trading_day_of_quarter")

    raise ValueError(f"Unsupported run_on: {run_on}")


def fetch_twse_trading_dates(year: int, fetcher: Callable[[str], str] | None = None) -> set[date] | None:
    fetcher = fetcher or _default_fetcher
    try:
        raw = fetcher(TWSE_HOLIDAY_URL)
        payload = json.loads(raw)
    except Exception:
        return None

    if not isinstance(payload, dict):
        return None

    holidays = _parse_holiday_dates(payload, year)
    return {
        day
        for day in _iter_dates(date(year, 1, 1), date(year, 12, 31))
        if day.weekday() < 5 and day not in holidays
    }


def _parse_holiday_dates(payload: dict, year: int) -> set[date]:
    rows = payload.get("data") or []
    fields = payload.get("fields") or []
    holiday_dates: set[date] = set()

    for row in rows:
        values = row if isinstance(row, list) else [row.get(field, "") for field in fields]
        for value in values:
            holiday_dates.update(_extract_dates_from_text(str(value), year))
    return holiday_dates


def _extract_dates_from_text(text: str, year: int) -> set[date]:
    found: set[date] = set()
    normalized = text.replace("年", "/").replace("月", "/").replace("日", "")
    parts = normalized.replace("-", "/").split("/")
    for idx in range(len(parts) - 1):
        try:
            month = int("".join(ch for ch in parts[idx] if ch.isdigit()))
            day = int("".join(ch for ch in parts[idx + 1] if ch.isdigit()))
            found.add(date(year, month, day))
        except ValueError:
            continue
    return found


def _period_decision(current: date, target: date | None, period_type: str, reason: str) -> GateDecision:
    if target is None:
        return GateDecision(False, "", period_type, "no_trading_day_in_period")
    if current == target:
        return GateDecision(True, target.isoformat(), period_type, reason)
    return GateDecision(False, "", period_type, f"not_{reason}")


def _last_trading_day_in_range(trading_dates: set[date], start: date, end: date) -> date | None:
    candidates = [day for day in trading_dates if start <= day <= end]
    return max(candidates) if candidates else None


def _latest_open_daily_target(
    trading_dates: set[date],
    current: date,
    *,
    current_window_open: bool,
    retry_until_success: bool,
) -> date | None:
    if not retry_until_success:
        return current if current_window_open and current in trading_dates else None
    latest_allowed = current if current_window_open else current - timedelta(days=1)
    candidates = [day for day in trading_dates if day <= latest_allowed]
    return max(candidates) if candidates else None


def _parse_hhmm(value: str) -> time:
    hour, minute = value.split(":", 1)
    return time(int(hour), int(minute))


def _iter_dates(start: date, end: date) -> Iterable[date]:
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def _default_fetcher(url: str) -> str:
    with urllib.request.urlopen(url, timeout=15) as response:
        return response.read().decode("utf-8")


def _parse_now(value: str | None) -> datetime:
    if value:
        return datetime.fromisoformat(value).astimezone(TAIPEI_TZ)
    return datetime.now(TAIPEI_TZ)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", choices=("daily", "weekly", "monthly", "quarterly"), required=True)
    parser.add_argument("--rules", type=Path, default=DEFAULT_RULES_PATH)
    parser.add_argument("--now")
    parser.add_argument("--manual-dispatch", action="store_true")
    parser.add_argument("--force-run", action="store_true")
    parser.add_argument("--github-output")
    args = parser.parse_args(argv)

    rules = load_rules(args.rules)
    now_tw = _parse_now(args.now)
    trading_dates = fetch_twse_trading_dates(now_tw.year)
    decision = evaluate_gate(
        rules,
        args.profile,
        now_tw,
        trading_dates,
        manual_dispatch=args.manual_dispatch,
        force_run=args.force_run,
    )
    print(json.dumps(decision.__dict__, ensure_ascii=False))
    if args.github_output:
        Path(args.github_output).write_text(decision.as_github_output() + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
