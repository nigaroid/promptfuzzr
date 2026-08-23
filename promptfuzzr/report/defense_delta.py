from __future__ import annotations

from promptfuzzr.models import TestCase, Verdict


def _success_rate_by(test_cases: list[TestCase], key: str) -> dict[str, tuple[int, int]]:
    counts: dict[str, list[int]] = {}
    for tc in test_cases:
        group = getattr(tc, key).value
        bucket = counts.setdefault(group, [0, 0])
        bucket[1] += 1
        if tc.verdict == Verdict.SUCCESS:
            bucket[0] += 1
    return {k: (v[0], v[1]) for k, v in counts.items()}


def _delta_table(baseline: dict[str, tuple[int, int]], comparison: dict[str, tuple[int, int]]) -> dict:
    table: dict[str, dict] = {}
    for group in sorted(set(baseline) | set(comparison)):
        b_succ, b_total = baseline.get(group, (0, 0))
        c_succ, c_total = comparison.get(group, (0, 0))
        b_rate = round(100 * b_succ / b_total, 1) if group in baseline and b_total else None
        c_rate = round(100 * c_succ / c_total, 1) if group in comparison and c_total else None
        delta = round(c_rate - b_rate, 1) if b_rate is not None and c_rate is not None else None
        table[group] = {
            "baseline_rate": b_rate,
            "baseline_n": b_total,
            "comparison_rate": c_rate,
            "comparison_n": c_total,
            "delta": delta,
        }
    return table


def compare_runs(baseline_test_cases: list[TestCase], comparison_test_cases: list[TestCase]) -> dict:
    overall_table = _delta_table(
        {"overall": (sum(1 for tc in baseline_test_cases if tc.verdict == Verdict.SUCCESS), len(baseline_test_cases))},
        {"overall": (sum(1 for tc in comparison_test_cases if tc.verdict == Verdict.SUCCESS), len(comparison_test_cases))},
    )

    return {
        "overall": overall_table["overall"],
        "by_technique": _delta_table(
            _success_rate_by(baseline_test_cases, "technique"),
            _success_rate_by(comparison_test_cases, "technique"),
        ),
        "by_delivery": _delta_table(
            _success_rate_by(baseline_test_cases, "delivery"),
            _success_rate_by(comparison_test_cases, "delivery"),
        ),
    }
