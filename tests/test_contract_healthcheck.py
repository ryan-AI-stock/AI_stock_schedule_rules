import tempfile
import unittest
from pathlib import Path

from stock_schedule_rules.contract_healthcheck import (
    EXPECTED_REPOS,
    RepoRule,
    WorkflowRule,
    check_root,
)


DAILY_WORKFLOW = """
on:
  schedule:
  workflow_dispatch:
jobs:
  report:
    steps:
      - uses: actions/checkout@v4
        with:
          repository: ryan-AI-stock/AI_stock_schedule_rules
      - run: PYTHONPATH=schedule_rules python -m stock_schedule_rules.gate --profile daily
      - if: steps.schedule-gate.outputs.should_run == 'true'
        env:
          REPORT_DATE: ${{ steps.schedule-gate.outputs.target_date || '' }}
"""


class ContractHealthcheckTests(unittest.TestCase):
    def test_valid_repo_passes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workflow = root / "AI_stock_market_daily" / ".github" / "workflows" / "daily_run.yml"
            workflow.parent.mkdir(parents=True)
            workflow.write_text(DAILY_WORKFLOW, encoding="utf-8")
            rule = RepoRule(
                repo_id="DAILY_STOCK",
                directory="AI_stock_market_daily",
                workflows=EXPECTED_REPOS[0].workflows,
            )

            result = check_root(root, (rule,))

        self.assertTrue(result["ok"])
        self.assertTrue(result["repos"][0]["workflows"][0]["ok"])

    def test_missing_target_date_mapping_fails(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workflow = root / "AI_stock_market_daily" / ".github" / "workflows" / "daily_run.yml"
            workflow.parent.mkdir(parents=True)
            workflow.write_text(
                DAILY_WORKFLOW.replace("steps.schedule-gate.outputs.target_date", "github.run_id"),
                encoding="utf-8",
            )
            rule = RepoRule(
                repo_id="DAILY_STOCK",
                directory="AI_stock_market_daily",
                workflows=EXPECTED_REPOS[0].workflows,
            )

            result = check_root(root, (rule,))

        self.assertFalse(result["ok"])
        self.assertIn(
            "steps.schedule-gate.outputs.target_date",
            result["repos"][0]["workflows"][0]["missing"],
        )

    def test_missing_optional_workflow_does_not_fail_repo(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            repo = root / "sample"
            repo.mkdir()
            rule = RepoRule(
                repo_id="SAMPLE",
                directory="sample",
                workflows=(
                    WorkflowRule(
                        path=".github/workflows/manual.yml",
                        required=("python -m stock_schedule_rules.gate",),
                        optional=True,
                    ),
                ),
            )

            result = check_root(root, (rule,))

        self.assertTrue(result["ok"])
        self.assertFalse(result["repos"][0]["workflows"][0]["exists"])

    def test_missing_repo_fails(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            result = check_root(
                Path(temp_dir),
                (
                    RepoRule(
                        repo_id="DAILY_STOCK",
                        directory="AI_stock_market_daily",
                        workflows=EXPECTED_REPOS[0].workflows,
                    ),
                ),
            )

        self.assertFalse(result["ok"])
        self.assertTrue(result["repos"][0]["missing_repo"])

    def test_directory_candidates_prefer_first_existing_repo(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            old_workflow = root / "old_daily" / ".github" / "workflows" / "daily_run.yml"
            old_workflow.parent.mkdir(parents=True)
            old_workflow.write_text("on:\n  schedule:\n", encoding="utf-8")
            new_workflow = root / "new_daily" / ".github" / "workflows" / "daily_run.yml"
            new_workflow.parent.mkdir(parents=True)
            new_workflow.write_text(DAILY_WORKFLOW, encoding="utf-8")
            rule = RepoRule(
                repo_id="DAILY_STOCK",
                directory="old_daily",
                directory_candidates=("new_daily", "old_daily"),
                workflows=EXPECTED_REPOS[0].workflows,
            )

            result = check_root(root, (rule,))

        self.assertTrue(result["ok"])
        self.assertEqual(result["repos"][0]["directory"], "new_daily")


if __name__ == "__main__":
    unittest.main()
