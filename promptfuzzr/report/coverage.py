from __future__ import annotations

from promptfuzzr.models import Delivery, Encoding, Propagation, Technique, TestCase

_AXES = {
    "technique": Technique,
    "delivery": Delivery,
    "propagation": Propagation,
    "encoding": Encoding,
}


def build_coverage_matrix(test_cases: list[TestCase]) -> dict:
    per_axis: dict[str, dict] = {}
    for axis_name, enum_cls in _AXES.items():
        seen = {getattr(tc, axis_name).value for tc in test_cases}
        total = len(list(enum_cls))
        per_axis[axis_name] = {
            "exercised": sorted(seen),
            "total": total,
            "pct": round(100 * len(seen) / total, 1) if total else 0.0,
        }

    cells_possible = 1
    for enum_cls in _AXES.values():
        cells_possible *= len(list(enum_cls))

    distinct_tuples = {
        (tc.technique.value, tc.delivery.value, tc.propagation.value, tc.encoding.value)
        for tc in test_cases
    }

    return {
        "total_cases": len(test_cases),
        "per_axis": per_axis,
        "cross_product": {
            "cells_exercised": len(distinct_tuples),
            "cells_possible": cells_possible,
            "pct": round(100 * len(distinct_tuples) / cells_possible, 3) if cells_possible else 0.0,
        },
    }
