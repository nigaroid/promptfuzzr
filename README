# promptfuzzr

Mutation-based prompt injection fuzzing framework for LLM applications and
agents. See `docs/roadmap.md` (copy of the project roadmap) for the full
design rationale, attack taxonomy, and phased build plan.

## Quickstart (once implemented)

```bash
pip install -e ".[dev]"
promptfuzzr corpus list
promptfuzzr mutate --seed "ignore previous instructions" --axis encoding
promptfuzzr run --target lab_agent --corpus corpus/seeds --axes delivery,encoding
promptfuzzr report --run-id <id>
```

## Structure

```
promptfuzzr/
  cli.py            CLI entrypoint (Typer)
  config.py         run configuration, target/session settings
  models.py         core data classes: TestCase, ToolCallRecord, Verdict
  corpus/           seed payload templates + loader
  mutate/           one mutator module per encoding axis + schema mutator
  delivery/         one module per delivery surface (direct, webpage, rag_doc, tool_schema, ...)
  targets/          adapters: agent harness (primary), local model, hosted API
  orchestrator/      execution engine: retries, sessions, kill-chains
  judge/            action-outcome judge (primary), heuristic + LLM judge (secondary)
  minimize/         ddmin-style payload minimization
  storage/          SQLite persistence
  report/           coverage matrix, defense-delta, export
tests/
```

Status: scaffolding only — see inline `TODO(phase N)` markers for the
build sequence.
