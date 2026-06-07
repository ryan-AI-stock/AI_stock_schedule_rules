import unittest
from datetime import date, datetime, timedelta, timezone

from stock_schedule_rules.gate import evaluate_gate, fetch_twse_trading_dates, load_rules


TAIPEI = timezone(timedelta(hours=8))


class GateTests(unittest.TestCase):
    def setUp(self):
        self.rules = load_rules()
        self.trading_dates = {
            date(2026, 6, 1),
            date(2026, 6, 2),
            date(2026, 6, 3),
            date(2026, 6, 4),
            date(2026, 6, 5),
        }

    def test_daily_runs_on_trading_day_after_15(self):
        decision = evaluate_gate(
            self.rules,
            "daily",
            datetime(2026, 6, 5, 15, 0, tzinfo=TAIPEI),
            self.trading_dates,
        )

        self.assertTrue(decision.should_run)
        self.assertEqual(decision.target_date, "2026-06-05")

    def test_daily_retries_previous_trading_day_until_next_window_opens(self):
        before_15 = evaluate_gate(
            self.rules,
            "daily",
            datetime(2026, 6, 5, 14, 59, tzinfo=TAIPEI),
            self.trading_dates,
        )
        weekend = evaluate_gate(
            self.rules,
            "daily",
            datetime(2026, 6, 6, 15, 0, tzinfo=TAIPEI),
            self.trading_dates,
        )

        self.assertTrue(before_15.should_run)
        self.assertEqual(before_15.target_date, "2026-06-04")
        self.assertEqual(before_15.reason, "retry_previous_trading_day_until_success")
        self.assertTrue(weekend.should_run)
        self.assertEqual(weekend.target_date, "2026-06-05")
        self.assertEqual(weekend.reason, "retry_previous_trading_day_until_success")

    def test_daily_respects_retry_until_success_false(self):
        self.rules["profiles"]["daily"]["retry_until_success"] = False

        before_15 = evaluate_gate(
            self.rules,
            "daily",
            datetime(2026, 6, 5, 14, 59, tzinfo=TAIPEI),
            self.trading_dates,
        )
        weekend = evaluate_gate(
            self.rules,
            "daily",
            datetime(2026, 6, 6, 15, 0, tzinfo=TAIPEI),
            self.trading_dates,
        )

        self.assertFalse(before_15.should_run)
        self.assertEqual(before_15.reason, "before_run_after")
        self.assertFalse(weekend.should_run)
        self.assertEqual(weekend.reason, "not_trading_day")

    def test_daily_skips_before_first_open_window(self):
        decision = evaluate_gate(
            self.rules,
            "daily",
            datetime(2026, 6, 1, 14, 59, tzinfo=TAIPEI),
            self.trading_dates,
        )

        self.assertFalse(decision.should_run)
        self.assertEqual(decision.reason, "before_run_after")

    def test_calendar_unavailable_skips_without_failure(self):
        decision = evaluate_gate(
            self.rules,
            "daily",
            datetime(2026, 6, 5, 15, 0, tzinfo=TAIPEI),
            None,
        )

        self.assertFalse(decision.should_run)
        self.assertEqual(decision.reason, "calendar_unavailable")

    def test_manual_dispatch_bypasses_gate(self):
        decision = evaluate_gate(
            self.rules,
            "daily",
            datetime(2026, 6, 6, 10, 0, tzinfo=TAIPEI),
            None,
            manual_dispatch=True,
            force_run=True,
        )

        self.assertTrue(decision.should_run)
        self.assertEqual(decision.reason, "manual_dispatch_bypass")

    def test_weekly_runs_on_last_trading_day(self):
        decision = evaluate_gate(
            self.rules,
            "weekly",
            datetime(2026, 6, 5, 15, 0, tzinfo=TAIPEI),
            self.trading_dates,
        )

        self.assertTrue(decision.should_run)
        self.assertEqual(decision.target_date, "2026-06-05")

    def test_weekly_runs_thursday_when_friday_is_holiday(self):
        trading_dates = self.trading_dates - {date(2026, 6, 5)}
        decision = evaluate_gate(
            self.rules,
            "weekly",
            datetime(2026, 6, 4, 15, 0, tzinfo=TAIPEI),
            trading_dates,
        )

        self.assertTrue(decision.should_run)
        self.assertEqual(decision.target_date, "2026-06-04")

    def test_twse_non_json_returns_none(self):
        self.assertIsNone(fetch_twse_trading_dates(2026, fetcher=lambda _url: "<html>not json</html>"))


if __name__ == "__main__":
    unittest.main()
