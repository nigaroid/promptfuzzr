"""Coverage-matrix reporting: what fraction of the delivery x
propagation x encoding x technique space was actually exercised in a
run, per roadmap.md's AFL-style coverage framing (a differentiator vs.
hit-counting scanners).

TODO(phase 6): implement build_coverage_matrix(test_cases) returning a
structure suitable for both a CLI table (rich) and an HTML heatmap.
"""

from __future__ import annotations

from promptfuzzr.models import TestCase


def build_coverage_matrix(test_cases: list[TestCase]) -> dict:
    raise NotImplementedError("TODO(phase 6): tally axis combinations exercised vs. total space")
