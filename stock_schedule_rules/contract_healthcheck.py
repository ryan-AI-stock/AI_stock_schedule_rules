"""Static downstream workflow contract checks for schedule-rule adopters."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class WorkflowRule:
    path: str
    required: tuple[str, ...]
    any_of: tuple[tuple[str, ...], ...] = ()
    optional: bool = False


@dataclass(frozen=True)
class RepoRule:
    repo_id: str
    directory: str
    workflows: tuple[WorkflowRule, ...]
    directory_candidates: tuple[str, ...] = ()


EXPECTED_REPOS: tuple[RepoRule, ...] = (
    RepoRule(
        repo_id="DAILY_STOCK",
        directory="AI_stock_market_daily",
        workflows=(
            WorkflowRule(
                path=".github/workflows/daily_run.yml",
                required=(
                    "repository: ryan-AI-stock/AI_stock_schedule_rules",
                    "python -m stock_schedule_rules.gate",
                    "steps.schedule-gate.outputs.should_run",
                    "steps.schedule-gate.outputs.target_date",
                    "REPORT_DATE",
                    "workflow_dispatch",
                ),
            ),
        ),
    ),
    RepoRule(
        repo_id="WEEKLY_STOCK",
        directory="AI_stock_market_weekly",
        workflows=(
            WorkflowRule(
                path=".github/workflows/weekly_run.yml",
                required=(
                    "repository: ryan-AI-stock/AI_stock_schedule_rules",
                    "SCHEDULE_RULES_PATH",
                    "steps.schedule-gate.outputs.should_run",
                    "workflow_dispatch",
                    "force_run",
                ),
            ),
        ),
    ),
    RepoRule(
        repo_id="SECTOR_RADAR",
        directory="AI_stock_rotation_radar",
        directory_candidates=("AI_stock_rotation_radar_latest", "AI_stock_rotation_radar"),
        workflows=(
            WorkflowRule(
                path=".github/workflows/generate-report.yml",
                required=(
                    "repository: ryan-AI-stock/AI_stock_schedule_rules",
                    "SCHEDULE_RULES_PATH",
                    "python -m rotation_radar.schedule_gate",
                    "steps.report-date.outputs.target_date",
                    "report_date",
                    "workflow_dispatch",
                ),
            ),
        ),
    ),
    RepoRule(
        repo_id="BACKTEST_LAB",
        directory="AI_stock_backtest_lab",
        workflows=(
            WorkflowRule(
                path=".github/workflows/model_scorecard_report.yml",
                required=(
                    "repository: ryan-AI-stock/AI_stock_schedule_rules",
                    "python -m stock_schedule_rules.gate",
                    "steps.schedule-gate.outputs.should_run",
                    "steps.schedule-gate.outputs.target_date",
                    "report_date",
                    "workflow_dispatch",
                ),
            ),
            WorkflowRule(
                path=".github/workflows/stock_pool_observation.yml",
                required=(
                    "repository: ryan-AI-stock/AI_stock_schedule_rules",
                    "python -m stock_schedule_rules.gate",
                    "steps.schedule-gate.outputs.should_run",
                    "steps.schedule-gate.outputs.target_date",
                    "signal_date",
                    "workflow_dispatch",
                ),
            ),
            WorkflowRule(
                path=".github/workflows/frozen_strategy_daily_report.yml",
                required=(
                    "repository: ryan-AI-stock/AI_stock_schedule_rules",
                    "python -m stock_schedule_rules.gate",
                    "steps.schedule-gate.outputs.should_run",
                    "steps.schedule-gate.outputs.target_date",
                    "signal_date",
                    "workflow_dispatch",
                ),
                optional=True,
            ),
        ),
    ),
)


def check_root(root: Path, repo_rules: Iterable[RepoRule] = EXPECTED_REPOS) -> dict:
    repos = [_check_repo(root, rule) for rule in repo_rules]
    return {
        "ok": all(repo["ok"] for repo in repos),
        "root": str(root),
        "repos": repos,
    }


def _check_repo(root: Path, rule: RepoRule) -> dict:
    candidates = rule.directory_candidates or (rule.directory,)
    repo_path = _first_existing_repo(root, candidates)
    if not repo_path.exists():
        return {
            "repo_id": rule.repo_id,
            "directory": rule.directory,
            "directory_candidates": list(candidates),
            "ok": False,
            "missing_repo": True,
            "workflows": [],
        }

    workflows = [_check_workflow(repo_path, workflow) for workflow in rule.workflows]
    required_workflows = [item for item in workflows if not item.get("optional")]
    return {
        "repo_id": rule.repo_id,
        "directory": repo_path.name,
        "directory_candidates": list(candidates),
        "ok": all(item["ok"] for item in required_workflows)
        and all(item["ok"] for item in workflows if item.get("exists")),
        "missing_repo": False,
        "workflows": workflows,
    }


def _check_workflow(repo_path: Path, rule: WorkflowRule) -> dict:
    workflow_path = repo_path / rule.path
    if not workflow_path.exists():
        return {
            "path": rule.path,
            "ok": bool(rule.optional),
            "exists": False,
            "optional": rule.optional,
            "missing": [] if rule.optional else ["workflow_file"],
            "missing_any_of": [],
        }

    text = workflow_path.read_text(encoding="utf-8")
    missing = [needle for needle in rule.required if needle not in text]
    missing_any_of = [
        list(group)
        for group in rule.any_of
        if not any(needle in text for needle in group)
    ]
    return {
        "path": rule.path,
        "ok": not missing and not missing_any_of,
        "exists": True,
        "optional": rule.optional,
        "missing": missing,
        "missing_any_of": missing_any_of,
    }


def _first_existing_repo(root: Path, candidates: Iterable[str]) -> Path:
    for directory in candidates:
        path = root / directory
        if path.exists():
            return path
    return root / next(iter(candidates))


def _print_text_report(result: dict) -> None:
    status = "PASS" if result["ok"] else "FAIL"
    print(f"contract healthcheck: {status} root={result['root']}")
    for repo in result["repos"]:
        repo_status = "PASS" if repo["ok"] else "FAIL"
        print(f"- {repo['repo_id']} ({repo['directory']}): {repo_status}")
        if repo.get("missing_repo"):
            print("  missing repo directory")
            continue
        for workflow in repo["workflows"]:
            workflow_status = "PASS" if workflow["ok"] else "FAIL"
            optional = " optional" if workflow.get("optional") else ""
            exists = "" if workflow.get("exists") else " missing"
            print(f"  - {workflow['path']}:{optional}{exists} {workflow_status}")
            for missing in workflow.get("missing", []):
                print(f"    missing: {missing}")
            for group in workflow.get("missing_any_of", []):
                print(f"    missing any of: {', '.join(group)}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check downstream workflow wiring against the schedule contract."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("work"),
        help="Directory containing downstream repo checkouts. Defaults to ./work.",
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args(argv)

    result = check_root(args.root)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        _print_text_report(result)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
