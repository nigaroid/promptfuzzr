"""Export a run's results/report to table (rich), HTML (jinja2), or
JSON.

TODO(phase 6): implement export_table(), export_html(), export_json(),
dispatched from cli.py::report based on the --fmt flag. HTML export
should render the coverage matrix and defense-delta table alongside a
findings list with minimized_payload shown for each success.
"""

from __future__ import annotations

from promptfuzzr.models import TestCase


def export_table(test_cases: list[TestCase]) -> None:
    raise NotImplementedError("TODO(phase 6): print a rich table summary")


def export_html(test_cases: list[TestCase], out_path: str) -> None:
    raise NotImplementedError("TODO(phase 6): render a jinja2 HTML report")


def export_json(test_cases: list[TestCase], out_path: str) -> None:
    raise NotImplementedError("TODO(phase 6): dump test_cases as JSON")
