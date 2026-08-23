"""Coverage-matrix reporting: what fraction of the delivery x
propagation x encoding x technique space was actually exercised in a
run, per roadmap.md's AFL-style coverage framing (a differentiator vs.
hit-counting scanners).

Design note: RunConfig currently fixes delivery/propagation/encoding
for an entire run — only `technique` varies across the corpus within
one run (mutation isn't wired into `fuzz` yet, see README.md section
10). That means a single top-line "cells exercised / 4-axis product"
percentage would look tiny and alarming for almost every real run,
even a thorough one, and would bury the genuinely useful signal. So
per-axis coverage (which values of EACH axis were seen, independent of
the others) is the primary output here; the full cross-product number
is included too, but as secondary context, not the headline.
"""

from __future__ import annotations

from promptfuzzr.models import Delivery, Encoding, Propagation, Technique, TestCase

_AXES = {
    "technique": Technique,
    "delivery": Delivery,
    "propagation": Propagation,
    "encoding": Encoding,
}


def build_coverage_matrix(test_cases: list[TestCase]) -> dict:
    """Returns:
    {
      "total_cases": int,
      "per_axis": {
        "technique":   {"exercised": [...values seen, sorted...], "total": 15, "pct": 93.3},
        "delivery":    {...},
        "propagation": {...},
        "encoding":    {...},
      },
      "cross_product": {
        "cells_exercised": int,   # distinct (technique, delivery, propagation, encoding) 4-tuples seen
        "cells_possible":  int,   # len(Technique) * len(Delivery) * len(Propagation) * len(Encoding)
        "pct": float,
      },
    }

    Coverage counts a value as "exercised" regardless of verdict —
    this measures what the fuzzer TRIED, not what succeeded. Success
    rate is a completely separate question, handled by
    defense_delta.py / export.py's findings summary, not conflated
    here.
    """
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
