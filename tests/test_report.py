"""Tests for report/ — coverage matrix, defense-delta, and export.
No network/target needed: all three modules operate on plain TestCase
lists built in-memory, so these are pure logic tests.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from promptfuzzr.models import Delivery, Encoding, Propagation, Technique, TestCase, Verdict


def _tc(technique, delivery=Delivery.DIRECT, verdict=Verdict.FAIL, minimized_payload=None, payload="p"):
    return TestCase(
        id=f"tc-{technique.value}-{verdict.value}-{id(object())}",
        technique=technique,
        delivery=delivery,
        propagation=Propagation.SINGLE_SHOT,
        encoding=Encoding.PLAIN,
        payload=payload,
        verdict=verdict,
        minimized_payload=minimized_payload,
    )


# ---------------------------------------------------------------------------
# coverage.py
# ---------------------------------------------------------------------------


def test_coverage_per_axis_counts_distinct_values_only():
    from promptfuzzr.report.coverage import build_coverage_matrix

    cases = [
        _tc(Technique.INSTRUCTION_OVERRIDE),
        _tc(Technique.INSTRUCTION_OVERRIDE),  # duplicate technique -> still counts as 1 exercised value
        _tc(Technique.ROLE_MANIPULATION),
    ]
    matrix = build_coverage_matrix(cases)

    assert matrix["total_cases"] == 3
    assert set(matrix["per_axis"]["technique"]["exercised"]) == {"instruction_override", "role_manipulation"}
    assert matrix["per_axis"]["technique"]["total"] == len(list(Technique))
    assert matrix["per_axis"]["delivery"]["exercised"] == ["direct"]


def test_coverage_cross_product_matches_full_enum_sizes():
    from promptfuzzr.report.coverage import build_coverage_matrix

    matrix = build_coverage_matrix([_tc(Technique.INSTRUCTION_OVERRIDE)])
    expected = len(list(Technique)) * len(list(Delivery)) * len(list(Propagation)) * len(list(Encoding))
    assert matrix["cross_product"]["cells_possible"] == expected
    assert matrix["cross_product"]["cells_exercised"] == 1


def test_coverage_empty_test_cases_does_not_crash():
    from promptfuzzr.report.coverage import build_coverage_matrix

    matrix = build_coverage_matrix([])
    assert matrix["total_cases"] == 0
    assert matrix["per_axis"]["technique"]["exercised"] == []
    assert matrix["per_axis"]["technique"]["pct"] == 0.0


# ---------------------------------------------------------------------------
# defense_delta.py
# ---------------------------------------------------------------------------


def test_defense_delta_computes_correct_rates_and_direction():
    from promptfuzzr.report.defense_delta import compare_runs

    baseline = [
        _tc(Technique.INSTRUCTION_OVERRIDE, verdict=Verdict.SUCCESS),
        _tc(Technique.INSTRUCTION_OVERRIDE, verdict=Verdict.SUCCESS),
        _tc(Technique.INSTRUCTION_OVERRIDE, verdict=Verdict.FAIL),
        _tc(Technique.INSTRUCTION_OVERRIDE, verdict=Verdict.FAIL),
    ]
    comparison = [
        _tc(Technique.INSTRUCTION_OVERRIDE, verdict=Verdict.FAIL),
        _tc(Technique.INSTRUCTION_OVERRIDE, verdict=Verdict.FAIL),
        _tc(Technique.INSTRUCTION_OVERRIDE, verdict=Verdict.FAIL),
        _tc(Technique.INSTRUCTION_OVERRIDE, verdict=Verdict.FAIL),
    ]
    result = compare_runs(baseline, comparison)

    row = result["by_technique"]["instruction_override"]
    assert row["baseline_rate"] == 50.0
    assert row["comparison_rate"] == 0.0
    assert row["delta"] == -50.0  # mitigation reduced success rate


def test_defense_delta_group_present_in_only_one_side_is_none_not_zero():
    from promptfuzzr.report.defense_delta import compare_runs

    baseline = [_tc(Technique.INSTRUCTION_OVERRIDE, verdict=Verdict.FAIL)]
    comparison = [_tc(Technique.ROLE_MANIPULATION, verdict=Verdict.SUCCESS)]
    result = compare_runs(baseline, comparison)

    # Only in baseline -> comparison side is None (never tested), not 0.
    assert result["by_technique"]["instruction_override"]["comparison_rate"] is None
    assert result["by_technique"]["instruction_override"]["delta"] is None
    # Only in comparison -> baseline side is None (never tested), not 0.
    assert result["by_technique"]["role_manipulation"]["baseline_rate"] is None
    assert result["by_technique"]["role_manipulation"]["delta"] is None


def test_defense_delta_real_zero_percent_is_distinct_from_absent():
    """A technique tested with zero successes must show 0.0, not None —
    only genuinely UNTESTED groups get None.
    """
    from promptfuzzr.report.defense_delta import compare_runs

    baseline = [_tc(Technique.INSTRUCTION_OVERRIDE, verdict=Verdict.FAIL)]
    comparison = [_tc(Technique.INSTRUCTION_OVERRIDE, verdict=Verdict.FAIL)]
    result = compare_runs(baseline, comparison)

    row = result["by_technique"]["instruction_override"]
    assert row["baseline_rate"] == 0.0
    assert row["comparison_rate"] == 0.0
    assert row["delta"] == 0.0


def test_defense_delta_overall_aggregates_across_all_techniques():
    from promptfuzzr.report.defense_delta import compare_runs

    baseline = [
        _tc(Technique.INSTRUCTION_OVERRIDE, verdict=Verdict.SUCCESS),
        _tc(Technique.ROLE_MANIPULATION, verdict=Verdict.FAIL),
    ]
    comparison = [_tc(Technique.INSTRUCTION_OVERRIDE, verdict=Verdict.FAIL)]
    result = compare_runs(baseline, comparison)

    assert result["overall"]["baseline_rate"] == 50.0
    assert result["overall"]["baseline_n"] == 2
    assert result["overall"]["comparison_rate"] == 0.0
    assert result["overall"]["comparison_n"] == 1


# ---------------------------------------------------------------------------
# export.py
# ---------------------------------------------------------------------------


def test_export_json_round_trips_all_fields(tmp_path):
    from promptfuzzr.models import ToolCallRecord
    from promptfuzzr.report.coverage import build_coverage_matrix
    from promptfuzzr.report.export import export_json

    tc = _tc(Technique.SCHEMA_POISONING, verdict=Verdict.SUCCESS, minimized_payload="short")
    tc.tool_calls = [ToolCallRecord(tool_name="send_email", arguments={"to": "x"}, authorized=False, order=1)]
    coverage = build_coverage_matrix([tc])

    out = tmp_path / "report.json"
    export_json([tc], coverage, out, run_meta={"run_id": "r1", "target_id": "lab_agent"})

    loaded = json.loads(out.read_text())
    assert loaded["run_meta"]["run_id"] == "r1"
    assert loaded["coverage"]["total_cases"] == 1
    assert len(loaded["test_cases"]) == 1
    assert loaded["test_cases"][0]["minimized_payload"] == "short"
    assert loaded["test_cases"][0]["tool_calls"][0]["tool_name"] == "send_email"


def test_export_json_works_with_no_run_meta_or_delta(tmp_path):
    from promptfuzzr.report.coverage import build_coverage_matrix
    from promptfuzzr.report.export import export_json

    cases = [_tc(Technique.INSTRUCTION_OVERRIDE)]
    coverage = build_coverage_matrix(cases)
    out = tmp_path / "report.json"

    export_json(cases, coverage, out)  # no run_meta, no defense_delta — must not crash
    loaded = json.loads(out.read_text())
    assert loaded["run_meta"] is None
    assert loaded["defense_delta"] is None


def test_export_html_contains_expected_sections(tmp_path):
    from promptfuzzr.report.coverage import build_coverage_matrix
    from promptfuzzr.report.export import export_html

    cases = [
        _tc(Technique.ROLE_MANIPULATION, verdict=Verdict.SUCCESS, minimized_payload="short trigger"),
        _tc(Technique.INSTRUCTION_OVERRIDE, verdict=Verdict.FAIL),
    ]
    coverage = build_coverage_matrix(cases)
    out = tmp_path / "report.html"

    export_html(cases, coverage, out, run_meta={"run_id": "r1", "target_id": "lab_agent", "started_at": "now"})

    html = out.read_text()
    assert "<html>" in html
    assert "r1" in html
    assert "Coverage by axis" in html
    assert "short trigger" in html
    assert "(minimized)" in html


def test_export_html_no_successes_shows_empty_state(tmp_path):
    from promptfuzzr.report.coverage import build_coverage_matrix
    from promptfuzzr.report.export import export_html

    cases = [_tc(Technique.INSTRUCTION_OVERRIDE, verdict=Verdict.FAIL)]
    coverage = build_coverage_matrix(cases)
    out = tmp_path / "report.html"

    export_html(cases, coverage, out)
    assert "No successful findings" in out.read_text()


def test_export_table_runs_without_crashing_no_successes(capsys):
    from promptfuzzr.report.coverage import build_coverage_matrix
    from promptfuzzr.report.export import export_table

    cases = [_tc(Technique.INSTRUCTION_OVERRIDE, verdict=Verdict.FAIL)]
    coverage = build_coverage_matrix(cases)

    export_table(cases, coverage)  # should print and return cleanly, no exception
    captured = capsys.readouterr()
    assert "Coverage by axis" in captured.out
