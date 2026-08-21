"""Defense-delta reporting: run the same corpus against a target with a
mitigation toggled on vs. off, report the bypass-rate delta rather than
a raw success rate. See roadmap.md Phase 6 and the general-hardening
list in section 5 for the mitigations to compare against.

TODO(phase 6): implement compare_runs(baseline_run_id, mitigated_run_id)
-> per-technique/per-encoding delta table.
"""

from __future__ import annotations


def compare_runs(baseline_test_cases: list, mitigated_test_cases: list) -> dict:
    raise NotImplementedError("TODO(phase 6): compute success-rate delta by technique/encoding")
