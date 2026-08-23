"""Export a run's results/report to table (rich), HTML (jinja2), or
JSON. All three take the same core inputs — test_cases, the coverage
matrix, and optionally a run_meta dict / defense-delta result — so the
CLI's report command can build those once and hand them to whichever
export function --fmt selected.
"""

from __future__ import annotations

import json
from pathlib import Path

from promptfuzzr.models import TestCase, Verdict


def export_table(
    test_cases: list[TestCase],
    coverage: dict,
    run_meta: dict | None = None,
    defense_delta: dict | None = None,
) -> None:
    """Print a rich table summary to stdout: run header, per-axis
    coverage, verdict breakdown, defense-delta (if provided), and the
    findings list with minimized_payload shown where available.
    """
    from rich.console import Console
    from rich.table import Table

    console = Console()

    if run_meta:
        console.print(
            f"[bold]Run {run_meta['run_id']}[/bold] — target: {run_meta['target_id']} — "
            f"started: {run_meta['started_at']}"
        )
    console.print()

    axis_table = Table(title="Coverage by axis")
    axis_table.add_column("Axis")
    axis_table.add_column("Exercised / Total")
    axis_table.add_column("%")
    for axis_name, data in coverage["per_axis"].items():
        axis_table.add_row(axis_name, f"{len(data['exercised'])} / {data['total']}", f"{data['pct']}%")
    console.print(axis_table)
    console.print(
        f"[dim]Full cross-product (technique x delivery x propagation x encoding): "
        f"{coverage['cross_product']['cells_exercised']} / {coverage['cross_product']['cells_possible']} "
        f"({coverage['cross_product']['pct']}%) — expect this to be small until mutation/multi-surface "
        f"runs are wired into `fuzz`; per-axis numbers above are the meaningful signal today.[/dim]"
    )
    console.print()

    verdict_table = Table(title="Verdicts")
    verdict_table.add_column("Verdict")
    verdict_table.add_column("Count")
    counts: dict[str, int] = {}
    for tc in test_cases:
        counts[tc.verdict.value] = counts.get(tc.verdict.value, 0) + 1
    for verdict_name in ("success", "fail", "error", "partial"):
        if verdict_name in counts:
            verdict_table.add_row(verdict_name, str(counts[verdict_name]))
    console.print(verdict_table)
    console.print()

    if defense_delta:
        delta_table = Table(title="Defense delta by technique (comparison - baseline, pct points)")
        delta_table.add_column("Technique")
        delta_table.add_column("Baseline")
        delta_table.add_column("Comparison")
        delta_table.add_column("Delta")
        for technique, row in sorted(defense_delta["by_technique"].items()):
            b = f"{row['baseline_rate']}%" if row["baseline_rate"] is not None else "—"
            c = f"{row['comparison_rate']}%" if row["comparison_rate"] is not None else "—"
            d = f"{row['delta']:+}pp" if row["delta"] is not None else "—"
            delta_table.add_row(technique, b, c, d)
        console.print(delta_table)
        console.print()

    findings_table = Table(title="Successful findings")
    findings_table.add_column("Technique")
    findings_table.add_column("Delivery")
    findings_table.add_column("Payload / Minimized")
    successes = [tc for tc in test_cases if tc.verdict == Verdict.SUCCESS]
    if not successes:
        console.print("[dim]No successful findings in this run.[/dim]")
        return
    for tc in successes:
        shown = tc.minimized_payload if tc.minimized_payload else tc.payload
        label = "[green](minimized)[/green] " if tc.minimized_payload else ""
        preview = shown if len(shown) <= 80 else shown[:77] + "..."
        findings_table.add_row(tc.technique.value, tc.delivery.value, label + preview)
    console.print(findings_table)


def export_json(
    test_cases: list[TestCase],
    coverage: dict,
    out_path: Path,
    run_meta: dict | None = None,
    defense_delta: dict | None = None,
) -> None:
    """Dump the full report — run metadata, coverage matrix,
    defense-delta (if given), and every test case — as one JSON file.
    Every field on TestCase is included (not just findings), so this
    is suitable as a raw data export for further analysis, not just a
    human-readable summary.
    """
    payload = {
        "run_meta": run_meta,
        "coverage": coverage,
        "defense_delta": defense_delta,
        "test_cases": [
            {
                "id": tc.id,
                "technique": tc.technique.value,
                "delivery": tc.delivery.value,
                "propagation": tc.propagation.value,
                "encoding": tc.encoding.value,
                "payload": tc.payload,
                "mutation_chain": tc.mutation_chain,
                "target_id": tc.target_id,
                "response_text": tc.response_text,
                "tool_calls": [
                    {
                        "tool_name": call.tool_name,
                        "arguments": call.arguments,
                        "authorized": call.authorized,
                        "order": call.order,
                    }
                    for call in tc.tool_calls
                ],
                "verdict": tc.verdict.value,
                "verdict_basis": tc.verdict_basis.value,
                "confidence": tc.confidence,
                "retry_count": tc.retry_count,
                "kill_chain_depth": tc.kill_chain_depth,
                "minimized_payload": tc.minimized_payload,
                "notes": tc.notes,
            }
            for tc in test_cases
        ],
    }
    Path(out_path).write_text(json.dumps(payload, indent=2))


_HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>promptfuzzr report{{ ' — ' + run_meta.run_id if run_meta else '' }}</title>
<style>
  body { font-family: -apple-system, sans-serif; max-width: 960px; margin: 2rem auto; color: #1a1a1a; }
  h1, h2 { border-bottom: 1px solid #ddd; padding-bottom: 0.3rem; }
  table { border-collapse: collapse; width: 100%; margin-bottom: 1.5rem; }
  th, td { border: 1px solid #ddd; padding: 0.4rem 0.7rem; text-align: left; font-size: 0.9rem; }
  th { background: #f5f5f5; }
  .success { color: #1a7f37; font-weight: 600; }
  .fail { color: #666; }
  .error { color: #b91c1c; }
  .dim { color: #888; font-size: 0.85rem; }
  .minimized { color: #1a7f37; font-weight: 600; }
  code { background: #f5f5f5; padding: 0.1rem 0.3rem; border-radius: 3px; }
</style>
</head>
<body>
<h1>promptfuzzr report</h1>
{% if run_meta %}
<p class="dim">Run <code>{{ run_meta.run_id }}</code> — target: {{ run_meta.target_id }} —
started: {{ run_meta.started_at }}{% if run_meta.finished_at %} — finished: {{ run_meta.finished_at }}{% endif %}</p>
{% endif %}

<h2>Coverage by axis</h2>
<table>
<tr><th>Axis</th><th>Exercised / Total</th><th>%</th></tr>
{% for axis_name, data in coverage.per_axis.items() %}
<tr><td>{{ axis_name }}</td><td>{{ data.exercised | length }} / {{ data.total }}</td><td>{{ data.pct }}%</td></tr>
{% endfor %}
</table>
<p class="dim">Full cross-product (technique x delivery x propagation x encoding):
{{ coverage.cross_product.cells_exercised }} / {{ coverage.cross_product.cells_possible }}
({{ coverage.cross_product.pct }}%) — expect this to be small until mutation/multi-surface runs
are wired into <code>fuzz</code>; per-axis numbers above are the meaningful signal today.</p>

<h2>Verdicts</h2>
<table>
<tr><th>Verdict</th><th>Count</th></tr>
{% for v, n in verdict_counts.items() %}
<tr><td class="{{ v }}">{{ v }}</td><td>{{ n }}</td></tr>
{% endfor %}
</table>

{% if defense_delta %}
<h2>Defense delta by technique (comparison &minus; baseline, percentage points)</h2>
<table>
<tr><th>Technique</th><th>Baseline</th><th>Comparison</th><th>Delta</th></tr>
{% for technique, row in defense_delta.by_technique.items() | sort %}
<tr>
  <td>{{ technique }}</td>
  <td>{{ (row.baseline_rate ~ '%') if row.baseline_rate is not none else '—' }}</td>
  <td>{{ (row.comparison_rate ~ '%') if row.comparison_rate is not none else '—' }}</td>
  <td>{{ ('%+gpp' % row.delta) if row.delta is not none else '—' }}</td>
</tr>
{% endfor %}
</table>
{% endif %}

<h2>Successful findings</h2>
{% if successes %}
<table>
<tr><th>Technique</th><th>Delivery</th><th>Payload</th></tr>
{% for tc in successes %}
<tr>
  <td>{{ tc.technique.value }}</td>
  <td>{{ tc.delivery.value }}</td>
  <td>
    {% if tc.minimized_payload %}<span class="minimized">(minimized)</span> {{ tc.minimized_payload }}
    {% else %}{{ tc.payload }}{% endif %}
  </td>
</tr>
{% endfor %}
</table>
{% else %}
<p class="dim">No successful findings in this run.</p>
{% endif %}

</body>
</html>
"""


def export_html(
    test_cases: list[TestCase],
    coverage: dict,
    out_path: Path,
    run_meta: dict | None = None,
    defense_delta: dict | None = None,
) -> None:
    """Render a single self-contained HTML file (inline CSS, no
    external assets) — the coverage matrix, verdict breakdown,
    defense-delta table (if given), and the findings list with
    minimized_payload highlighted where available.
    """
    import jinja2

    verdict_counts: dict[str, int] = {}
    for tc in test_cases:
        verdict_counts[tc.verdict.value] = verdict_counts.get(tc.verdict.value, 0) + 1

    template = jinja2.Template(_HTML_TEMPLATE)
    html = template.render(
        run_meta=run_meta,
        coverage=coverage,
        verdict_counts=verdict_counts,
        defense_delta=defense_delta,
        successes=[tc for tc in test_cases if tc.verdict == Verdict.SUCCESS],
    )
    Path(out_path).write_text(html)
