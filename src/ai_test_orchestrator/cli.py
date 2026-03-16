"""
CLI entry point for the AI Test Orchestrator.

Usage:
    python -m ai_test_orchestrator --scenario path/to/scenario.yaml --adapter module.path:ClassName
    ai-test-orchestrator --scenario path/to/scenario.yaml --adapter module.path:ClassName
"""

from __future__ import annotations

import argparse
import importlib
import json
import logging
import sys
from pathlib import Path

from .invariant_checker import InvariantChecker
from .narrative_judge import NarrativeJudge
from .report import console_summary
from .runner import ScenarioRunner, load_scenario


def _import_adapter(spec: str):
    """Import an adapter class from a 'module.path:ClassName' spec."""
    if ":" not in spec:
        raise ValueError(f"Adapter spec must be 'module.path:ClassName', got: {spec}")
    module_path, class_name = spec.rsplit(":", 1)
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


def _import_invariants(spec: str) -> list:
    """Import invariant checks from a 'module.path' spec (must have get_checks() function)."""
    module = importlib.import_module(spec)
    if hasattr(module, "get_checks"):
        return module.get_checks()
    return []


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ai-test-orchestrator",
        description="Run AI-driven end-to-end test scenarios against a system under test.",
    )
    parser.add_argument(
        "--scenario",
        required=True,
        nargs="+",
        help="Path(s) to YAML scenario file(s)",
    )
    parser.add_argument(
        "--adapter",
        required=True,
        help="SUT adapter class: 'module.path:ClassName'",
    )
    parser.add_argument(
        "--invariants",
        help="Module providing invariant checks: 'module.path' (must have get_checks())",
    )
    parser.add_argument(
        "--seed",
        type=int,
        help="Override scenario seed",
    )
    parser.add_argument(
        "--output-dir",
        default="test_results",
        help="Directory for reports and transcripts (default: test_results)",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Halt on first CRITICAL invariant failure",
    )
    parser.add_argument(
        "--json-report",
        help="Path to write JSON report",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable debug logging",
    )

    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    logger = logging.getLogger(__name__)

    # Import adapter
    adapter_cls = _import_adapter(args.adapter)

    # Import invariants
    checks = []
    if args.invariants:
        checks = _import_invariants(args.invariants)

    all_reports = []
    exit_code = 0

    for scenario_path in args.scenario:
        scenario = load_scenario(scenario_path)

        # Override seed if specified
        if args.seed is not None:
            scenario.seed = args.seed
        if args.fail_fast:
            scenario.fail_fast = True

        logger.info(
            "Starting scenario '%s' (system=%s, seed=%s)",
            scenario.name,
            scenario.system,
            scenario.seed if scenario.seed is not None else "none",
        )

        sut = adapter_cls()
        checker = InvariantChecker(checks=checks or None, fail_fast=scenario.fail_fast)
        judge = NarrativeJudge() if scenario.enable_narrative_judge else None

        runner = ScenarioRunner(
            sut=sut,
            scenario=scenario,
            checker=checker,
            judge=judge,
            transcript_dir=args.output_dir,
        )

        report = runner.run()
        all_reports.append(report)

        print(console_summary(report))

        if report.verdict.value == "fail":
            exit_code = 1

    # Write combined JSON report
    if args.json_report:
        report_data = [r.to_dict() for r in all_reports]
        Path(args.json_report).write_text(
            json.dumps(report_data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"\nJSON report: {args.json_report}")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
