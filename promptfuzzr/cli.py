from __future__ import annotations

from pathlib import Path

import typer

app = typer.Typer(help="promptfuzzr — mutation-based prompt injection fuzzer")

seeds_app = typer.Typer(help="Inspect the payload corpus")
app.add_typer(seeds_app, name="seeds")


_DEFAULT_CORPUS = Path(__file__).parent / "corpus" / "seeds"


@seeds_app.command("list")
def seeds_list(
    corpus_dir: Path = typer.Option(_DEFAULT_CORPUS, help="Seed corpus directory"),
) -> None:
    from promptfuzzr.corpus.loader import load_seeds

    seeds = load_seeds(corpus_dir)
    if not seeds:
        typer.echo(f"No seeds found in {corpus_dir}")
        raise typer.Exit(1)
    for seed in sorted(seeds, key=lambda s: (s.technique.value, s.id)):
        tags = f" [{', '.join(seed.tags)}]" if seed.tags else ""
        typer.echo(f"{seed.id:28s} {seed.technique.value:32s}{tags}")


@seeds_app.command("show")
def seeds_show(
    seed_id: str = typer.Argument(..., help="Seed id, e.g. instr-override-001"),
    corpus_dir: Path = typer.Option(_DEFAULT_CORPUS),
) -> None:
    from promptfuzzr.corpus.loader import load_seeds

    for seed in load_seeds(corpus_dir):
        if seed.id == seed_id:
            typer.echo(f"id:        {seed.id}")
            typer.echo(f"technique: {seed.technique.value}")
            typer.echo(f"tags:      {', '.join(seed.tags) if seed.tags else '(none)'}")
            typer.echo("--- base_text ---")
            typer.echo(seed.base_text)
            return
    typer.echo(f"Seed '{seed_id}' not found in {corpus_dir}")
    raise typer.Exit(1)


@app.command()
def mutate(
    seed: str = typer.Argument(..., help="Seed id from the corpus, or raw payload text"),
    axis: str = typer.Option("encoding", help="Axis to mutate: encoding | delivery | propagation"),
    count: int = typer.Option(10, help="Number of variants to generate"),
) -> None:
    from promptfuzzr.corpus.loader import load_seeds
    from promptfuzzr.mutate.encode import EncodeMutator
    from promptfuzzr.mutate.fake_delimiter import FakeDelimiterMutator
    from promptfuzzr.mutate.fake_user_turn import FakeUserTurnMutator
    from promptfuzzr.mutate.split import SplitMutator
    from promptfuzzr.mutate.synonym import SynonymMutator

    seed_text = seed
    resolved_id = "(raw text)"
    for candidate in load_seeds(_DEFAULT_CORPUS):
        if candidate.id == seed:
            seed_text = candidate.base_text
            resolved_id = candidate.id
            break

    if axis != "encoding":
        typer.echo(f"Axis '{axis}' is not implemented yet — only 'encoding' is wired (Phase 2).")
        raise typer.Exit(1)

    mutators = [
        EncodeMutator(),
        FakeDelimiterMutator(),
        FakeUserTurnMutator(),
        SynonymMutator(),
        SplitMutator(),
    ]

    shown = 0
    for mutator in mutators:
        variants = mutator.mutate(seed_text, count=count)
        for i, variant in enumerate(variants):
            shown += 1
            label = f"{mutator.name}#{i + 1}"
            typer.echo(f"--- {label} ---")
            if isinstance(variant, dict):
                for field_name, chunk in variant.items():
                    typer.echo(f"  [{field_name}] {chunk}")
            else:
                typer.echo(variant)
            if shown >= count * len(mutators):
                break
    typer.echo(f"\n{shown} variants generated from {resolved_id} (axis={axis}).")


def _build_target(run_config):
    if run_config.agent_endpoint:
        from promptfuzzr.targets.remote_agent import RemoteAgentTarget, probe_endpoint

        if not probe_endpoint(run_config.agent_endpoint):
            raise typer.BadParameter(
                f"agent_endpoint '{run_config.agent_endpoint}' is not reachable — "
                f"is the container/agent running?"
            )
        return RemoteAgentTarget(endpoint=run_config.agent_endpoint)

    from promptfuzzr.targets.agent_harness import (
        AgentHarnessTarget,
        AnthropicModelClient,
        OpenAICompatibleModelClient,
    )

    if run_config.target_profile == "vulnerable":
        from promptfuzzr.targets.agent_harness import VulnerableAgentModelClient

        typer.secho(
            "WARNING: target_profile=vulnerable — using the deterministic "
            "positive-control target, NOT a real model. Results validate the "
            "fuzzer's own success-detection pipeline; they say nothing about "
            "real-world attack success rates. Do not report these numbers as "
            "findings.",
            fg=typer.colors.YELLOW,
            err=True,
        )
        model_client = VulnerableAgentModelClient()
    elif run_config.model_provider == "anthropic":
        model_client = AnthropicModelClient(model=run_config.model_name)
    elif run_config.model_provider == "openai_compat":
        model_client = OpenAICompatibleModelClient(model=run_config.model_name)
    else:
        raise typer.BadParameter(
            f"model_provider '{run_config.model_provider}' not recognized — "
            f"use 'anthropic' or 'openai_compat'"
        )

    return AgentHarnessTarget(model_client=model_client)


@app.command()
def fuzz(
    config: Path = typer.Option(..., "--config", help="RunConfig YAML path, e.g. config/lab.example.yaml"),
) -> None:
    from promptfuzzr.config import RunConfig
    from promptfuzzr.orchestrator.engine import run_corpus
    from promptfuzzr.storage.paths import get_db_path

    run_config = RunConfig.from_yaml(config)

    if not run_config.agent_endpoint and run_config.target_id != "lab_agent":
        raise typer.BadParameter(
            f"target_id '{run_config.target_id}' is not wired up yet — "
            f"use 'lab_agent' locally, or set agent_endpoint for a remote target"
        )

    if run_config.authority_policy is None:
        raise typer.BadParameter(
            "authority_policy is required in the config — the action_outcome "
            "judge has nothing to compare tool calls against without it. "
            "See config/lab.example.yaml."
        )

    if run_config.agent_endpoint:
        typer.echo(f"Targeting remote agent at {run_config.agent_endpoint}")

    target = _build_target(run_config)
    results = run_corpus(run_config, target)

    successes = sum(1 for r in results if r.verdict.value == "success")
    typer.echo(f"Ran {len(results)} test cases — {successes} successful.")
    typer.echo(f"Results stored in {get_db_path()}")


@app.command()
def findings(
    run_id: str = typer.Option(None, help="Run id to filter by; defaults to the most recent run"),
    verdict: str = typer.Option("success", help="Filter by verdict: success | partial | fail | error"),
) -> None:
    from promptfuzzr.storage.db import init_db, load_most_recent_run_id, load_test_cases

    conn = init_db()
    if not run_id:
        run_id = load_most_recent_run_id(conn)
        if run_id is None:
            typer.echo("No runs in the database yet — run `promptfuzzr fuzz` first.")
            raise typer.Exit(1)

    cases = load_test_cases(conn, run_id, verdict=verdict)
    if not cases:
        typer.echo(f"No test cases with verdict '{verdict}' in run {run_id}.")
        return

    for tc in cases:
        typer.echo(f"[{tc.verdict.value}] {tc.id}")
        typer.echo(f"  technique: {tc.technique.value} | delivery: {tc.delivery.value} | "
                   f"propagation: {tc.propagation.value} | depth: {tc.kill_chain_depth}")
        tools_used = sorted({c.tool_name for c in tc.tool_calls})
        typer.echo(f"  tools called: {', '.join(tools_used) if tools_used else '(none)'}")
        payload_preview = " ".join(tc.payload.split())[:120]
        typer.echo(f"  payload: {payload_preview}")
        if tc.response_text:
            resp_preview = " ".join(tc.response_text.split())[:120]
            typer.echo(f"  response: {resp_preview}")
        typer.echo("")
    typer.echo(f"{len(cases)} finding(s) in run {run_id}")


@app.command()
def minimize(
    finding_id: str = typer.Argument(..., help="TestCase id of a successful finding"),
    config: Path = typer.Option(
        ..., "--config", help="The SAME RunConfig YAML the finding was produced with"
    ),
    verify_retries: int = typer.Option(
        2, help="Re-checks per candidate before concluding it doesn't reproduce (non-determinism hedge)"
    ),
) -> None:
    from promptfuzzr.config import RunConfig
    from promptfuzzr.judge.action_outcome import ActionOutcomeJudge
    from promptfuzzr.minimize.ddmin import minimize_test_case
    from promptfuzzr.models import Verdict
    from promptfuzzr.storage.db import init_db, load_test_case_by_id, save_test_case

    run_config = RunConfig.from_yaml(config)

    if run_config.authority_policy is None:
        raise typer.BadParameter(
            "authority_policy is required in the config — the action_outcome "
            "judge has nothing to compare tool calls against without it."
        )

    conn = init_db()
    result = load_test_case_by_id(conn, finding_id)
    if result is None:
        typer.echo(f"No test case with id '{finding_id}' found in the database.")
        raise typer.Exit(1)
    test_case, run_id = result

    if test_case.verdict != Verdict.SUCCESS:
        typer.echo(
            f"Test case {finding_id} has verdict '{test_case.verdict.value}', not "
            f"'success' — only a successful finding has anything to minimize."
        )
        raise typer.Exit(1)

    target = _build_target(run_config)
    action_judge = ActionOutcomeJudge(run_config.authority_policy)

    typer.echo(f"Original payload ({len(test_case.payload)} chars):")
    typer.echo(f"  {test_case.payload!r}")
    typer.echo("Minimizing (this replays candidates against the target — may take a while)...")

    try:
        minimized = minimize_test_case(
            test_case, target, action_judge=action_judge, verify_retries=verify_retries
        )
    except NotImplementedError as exc:
        typer.echo(str(exc))
        raise typer.Exit(1)
    except RuntimeError as exc:
        typer.echo(str(exc))
        raise typer.Exit(1)

    save_test_case(conn, run_id, test_case)

    typer.echo("")
    typer.echo(f"Minimized payload ({len(minimized)} chars):")
    typer.echo(f"  {minimized!r}")
    reduction_pct = 100 * (1 - len(minimized) / max(1, len(test_case.payload)))
    typer.echo(f"Reduced by {reduction_pct:.0f}% — saved back to the database.")


@app.command()
def report(
    run_id: str = typer.Argument(..., help="Run id to report on"),
    fmt: str = typer.Option("table", help="table | html | json"),
    compare_run_id: str = typer.Option(
        None, help="Optional second run id — adds a defense-delta comparison table (this run vs. that one)"
    ),
    out: Path = typer.Option(
        None, help="Output file path for html/json (defaults to report.<fmt> in the current directory)"
    ),
) -> None:
    from promptfuzzr.report.coverage import build_coverage_matrix
    from promptfuzzr.report.defense_delta import compare_runs
    from promptfuzzr.report.export import export_html, export_json, export_table
    from promptfuzzr.storage.db import init_db, load_run_meta, load_test_cases

    if fmt not in ("table", "html", "json"):
        raise typer.BadParameter(f"fmt '{fmt}' not recognized — use table, html, or json")

    conn = init_db()
    run_meta = load_run_meta(conn, run_id)
    if run_meta is None:
        typer.echo(f"No run with id '{run_id}' found in the database.")
        raise typer.Exit(1)

    test_cases = load_test_cases(conn, run_id)
    if not test_cases:
        typer.echo(f"Run '{run_id}' has no test cases.")
        raise typer.Exit(1)

    coverage = build_coverage_matrix(test_cases)

    defense_delta = None
    if compare_run_id:
        compare_meta = load_run_meta(conn, compare_run_id)
        if compare_meta is None:
            typer.echo(f"--compare-run-id '{compare_run_id}' not found in the database.")
            raise typer.Exit(1)
        compare_cases = load_test_cases(conn, compare_run_id)
        defense_delta = compare_runs(test_cases, compare_cases)
        typer.echo(f"Comparing {run_id} (baseline) against {compare_run_id} (comparison)...")

    if fmt == "table":
        export_table(test_cases, coverage, run_meta=run_meta, defense_delta=defense_delta)
        return

    out_path = out or Path(f"report.{fmt}")
    if fmt == "html":
        export_html(test_cases, coverage, out_path, run_meta=run_meta, defense_delta=defense_delta)
    else:
        export_json(test_cases, coverage, out_path, run_meta=run_meta, defense_delta=defense_delta)
    typer.echo(f"Report written to {out_path}")


if __name__ == "__main__":
    app()
