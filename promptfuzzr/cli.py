"""CLI entrypoint. Registered as the `promptfuzzr` console script in
pyproject.toml.

Commands map directly to the phases in roadmap.md:
  seeds     -> Phase 1 (payload corpus)
  mutate    -> Phase 2 (mutation engine, previewed with no target needed)
  fuzz      -> Phase 3/4 (delivery + orchestration + judge — the actual attack run)
  findings  -> Phase 4/5 (quick list of successes, no formatting)
  minimize  -> Phase 5 (ddmin-style reducer)
  report    -> Phase 6 (coverage matrix, defense-delta, full export)
"""

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
    """List available payload seeds by technique."""
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
    """Show the full text and metadata for one seed."""
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
    """Preview mutated variants of a seed payload. No target required —
    useful for sanity-checking a mutator before spending a fuzz run on it.
    """
    from promptfuzzr.corpus.loader import load_seeds
    from promptfuzzr.mutate.encode import EncodeMutator
    from promptfuzzr.mutate.fake_delimiter import FakeDelimiterMutator
    from promptfuzzr.mutate.fake_user_turn import FakeUserTurnMutator
    from promptfuzzr.mutate.split import SplitMutator
    from promptfuzzr.mutate.synonym import SynonymMutator

    # Resolve the argument: a known seed id wins, otherwise treat it as raw text.
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
            # split returns dicts of field->chunk; stringify the rest
            if isinstance(variant, dict):
                for field_name, chunk in variant.items():
                    typer.echo(f"  [{field_name}] {chunk}")
            else:
                typer.echo(variant)
            if shown >= count * len(mutators):
                break
    typer.echo(f"\n{shown} variants generated from {resolved_id} (axis={axis}).")


@app.command()
def fuzz(
    config: Path = typer.Option(..., "--config", help="RunConfig YAML path, e.g. config/lab.example.yaml"),
) -> None:
    """Run the corpus against the configured target and store every
    result. See config.py's `delivery`/`propagation` fields for which
    surfaces and modes are available.

    Supports: the local lab_agent (via AgentHarnessTarget, with
    target_profile real|vulnerable and model_provider
    anthropic|openai_compat), and remote agents under test that expose
    an OpenAI-compatible endpoint (via agent_endpoint, e.g. DVAA).
    """
    from promptfuzzr.config import RunConfig
    from promptfuzzr.orchestrator.engine import run_corpus
    from promptfuzzr.storage.paths import get_db_path
    from promptfuzzr.targets.agent_harness import (
        AgentHarnessTarget,
        AnthropicModelClient,
        OpenAICompatibleModelClient,
    )

    run_config = RunConfig.from_yaml(config)

    # Remote agents (DVAA etc.) bring their own identity; the local
    # harness check only applies to non-endpoint runs.
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
        # External agent under test (e.g. DVAA) — no local model client;
        # the remote target owns its own system prompt and tools.
        from promptfuzzr.targets.remote_agent import RemoteAgentTarget, probe_endpoint

        if not probe_endpoint(run_config.agent_endpoint):
            raise typer.BadParameter(
                f"agent_endpoint '{run_config.agent_endpoint}' is not reachable — "
                f"is the container/agent running?"
            )
        typer.echo(f"Targeting remote agent at {run_config.agent_endpoint}")
        results = run_corpus(run_config, RemoteAgentTarget(endpoint=run_config.agent_endpoint))
        successes = sum(1 for r in results if r.verdict.value == "success")
        typer.echo(f"Ran {len(results)} test cases — {successes} successful.")
        typer.echo(f"Results stored in {get_db_path()}")
        return

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

    target = AgentHarnessTarget(model_client=model_client)
    results = run_corpus(run_config, target)

    successes = sum(1 for r in results if r.verdict.value == "success")
    typer.echo(f"Ran {len(results)} test cases — {successes} successful.")
    typer.echo(f"Results stored in {get_db_path()}")


@app.command()
def findings(
    run_id: str = typer.Option(None, help="Run id to filter by; defaults to the most recent run"),
    verdict: str = typer.Option("success", help="Filter by verdict: success | partial | fail | error"),
) -> None:
    """Quick list of test cases matching a verdict — check progress
    mid-run without generating a full report.
    """
    from promptfuzzr.storage.db import init_db, load_test_cases

    conn = init_db()
    if not run_id:
        row = conn.execute("SELECT run_id FROM runs ORDER BY started_at DESC LIMIT 1").fetchone()
        if row is None:
            typer.echo("No runs in the database yet — run `promptfuzzr fuzz` first.")
            raise typer.Exit(1)
        run_id = row[0]

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
) -> None:
    """Reduce a successful payload to a minimal reproducer."""
    raise NotImplementedError("TODO(phase 5): wire into minimize/ddmin.py")


@app.command()
def report(
    run_id: str = typer.Argument(..., help="Run id to report on"),
    fmt: str = typer.Option("table", help="table | html | json"),
) -> None:
    """Full report: coverage matrix, defense-delta, and findings with
    minimized reproducers where available.
    """
    raise NotImplementedError("TODO(phase 6): wire into report/")


if __name__ == "__main__":
    app()
