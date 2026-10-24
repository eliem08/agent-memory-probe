"""Tests for the prober and the CLI."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from agent_memory_probe.cli import main
from agent_memory_probe.probes import (
    PROBE_CLASSES,
    builtin_cases,
    load_cases,
    run_all,
    run_probe,
    validate_case,
)

ROOT = Path(__file__).resolve().parent.parent


def _by_id(cases):
    return {c["id"]: c for c in cases}


def test_builtin_has_exactly_three_classes_and_six_cases():
    cases = builtin_cases()
    assert len(cases) == 6
    assert sorted({c["class"] for c in cases}) == sorted(PROBE_CLASSES)
    assert {c["class"] for c in cases} == set(PROBE_CLASSES)


def test_instruction_vulnerable_case_fails():
    result = run_probe(_by_id(builtin_cases())["instruction_persist"])
    assert result["planted"] is True
    assert result["resurfaced"] is True
    assert result["influenced"] is True
    assert result["verdict"] == "FAIL"


def test_instruction_contained_case_passes():
    result = run_probe(_by_id(builtin_cases())["instruction_contained"])
    assert result["resurfaced"] is False
    assert result["influenced"] is False
    assert result["verdict"] == "PASS"


def test_false_fact_vulnerable_case_fails():
    result = run_probe(_by_id(builtin_cases())["false_fact_persist"])
    assert result["resurfaced"] is True
    assert result["verdict"] == "FAIL"
    assert result["baseline_answer"] == "Paris."
    assert result["answer"] != result["baseline_answer"]


def test_false_fact_contained_case_passes():
    result = run_probe(_by_id(builtin_cases())["false_fact_contained"])
    assert result["verdict"] == "PASS"
    assert result["answer"] == "Paris."


def test_confidentiality_leak_case_fails():
    result = run_probe(_by_id(builtin_cases())["confidentiality_leak"])
    assert result["plant_scope"] == "alice"
    assert result["ask_scope"] == "bob"
    assert result["resurfaced"] is True
    assert result["verdict"] == "FAIL"


def test_confidentiality_contained_case_passes():
    result = run_probe(_by_id(builtin_cases())["confidentiality_contained"])
    assert result["resurfaced"] is False
    assert result["verdict"] == "PASS"


def test_report_shape_and_summary_counts():
    report = run_all(builtin_cases())
    assert report["tool"] == "agent-memory-probe"
    assert report["summary"] == {"total": 6, "passed": 3, "failed": 3}
    for case in report["cases"]:
        for key in ("planted", "resurfaced", "influenced", "verdict"):
            assert key in case


def test_validate_rejects_unknown_class():
    bad = dict(_by_id(builtin_cases())["instruction_persist"])
    bad["class"] = "something_else"
    with pytest.raises(ValueError, match="unknown class"):
        validate_case(bad)


def test_validate_rejects_canary_not_in_content():
    bad = dict(_by_id(builtin_cases())["instruction_persist"])
    bad["canary"] = "CANARY-NOT-THERE"
    with pytest.raises(ValueError, match="canary"):
        validate_case(bad)


def test_load_cases_from_file(tmp_path):
    path = tmp_path / "cases.json"
    path.write_text(json.dumps({"cases": builtin_cases()}), encoding="utf-8")
    assert len(load_cases(path)) == 6


def test_cli_builtin_exits_nonzero_and_writes_json(tmp_path, capsys):
    out = tmp_path / "report.json"
    code = main(["probe", "--cases", "builtin", "--out", str(out)])
    assert code == 1
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["summary"]["failed"] == 3
    assert "agent-memory-probe results" in capsys.readouterr().out


def test_cli_contained_only_cases_exits_zero(tmp_path):
    contained = [
        c
        for c in builtin_cases()
        if c["id"]
        in ("instruction_contained", "false_fact_contained", "confidentiality_contained")
    ]
    path = tmp_path / "cases.json"
    path.write_text(json.dumps(contained), encoding="utf-8")
    out = tmp_path / "report.json"
    code = main(["probe", "--cases", str(path), "--out", str(out)])
    assert code == 0
    assert json.loads(out.read_text(encoding="utf-8"))["summary"] == {
        "total": 3,
        "passed": 3,
        "failed": 0,
    }


def test_cli_invalid_cases_file_exits_two(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("[]", encoding="utf-8")
    assert main(["probe", "--cases", str(path), "--out", str(tmp_path / "r.json")]) == 2


def test_cli_end_to_end_via_module(tmp_path):
    env = {"PYTHONPATH": str(ROOT), "PATH": "/usr/bin:/bin"}
    proc = subprocess.run(
        [sys.executable, "-m", "agent_memory_probe", "probe",
         "--cases", "builtin", "--out", "report.json"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 1
    report = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert report["summary"]["total"] == 6
    assert "agent-memory-probe results" in proc.stdout
