"""Command-line interface for agent-memory-probe.

Usage:
    python -m agent_memory_probe probe --cases builtin --out report.json
    python -m agent_memory_probe probe --cases my-cases.json --out report.json

Exit code is 0 when every canary stays contained and 1 when any
canary resurfaces or influences an answer. A usage or file error
exits with code 2.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .probes import builtin_cases, load_cases, run_all


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agent-memory-probe",
        description=(
            "Probe whether planted content in a memory store resurfaces "
            "in a later session of a mock agent."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)
    probe = sub.add_parser(
        "probe", help="run probe cases against the mock agent"
    )
    probe.add_argument(
        "--cases",
        default="builtin",
        help="path to a JSON cases file, or 'builtin' (default: builtin)",
    )
    probe.add_argument(
        "--out",
        default="report.json",
        help="path to write the JSON report to (default: report.json)",
    )
    return parser


def format_summary(report: dict) -> str:
    summary = report["summary"]
    lines = [
        "agent-memory-probe results",
        f"total: {summary['total']}  passed: {summary['passed']}  "
        f"failed: {summary['failed']}",
        "",
    ]
    for case in report["cases"]:
        lines.append(
            f"{case['verdict']} {case['id']} ({case['class']}): "
            f"resurfaced={case['resurfaced']} "
            f"influenced={case['influenced']}"
        )
    lines.append("")
    if summary["failed"]:
        lines.append(
            f"{summary['failed']} canary(s) resurfaced or influenced an "
            "answer in the mock agent."
        )
    else:
        lines.append("All canaries stayed contained in the mock agent.")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command != "probe":
        return 2
    try:
        cases = builtin_cases() if args.cases == "builtin" else load_cases(args.cases)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"error: cannot load cases: {exc}", file=sys.stderr)
        return 2
    report = run_all(cases)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(format_summary(report))
    print(f"\nJSON report written to {out_path}")
    return 1 if report["summary"]["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
