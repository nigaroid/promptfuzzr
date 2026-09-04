# PromptFuzzr

Mutation-based prompt injection fuzzing framework for LLM applications and agents.

PromptFuzzr tests prompt-injection resilience across direct and indirect delivery surfaces, multiple propagation modes, and tool-use outcomes. Results are stored in SQLite and can be minimized and exported as reports.

## Quick start

### Install

```bash
git clone https://github.com/nigaroid/promptfuzzr.git
cd promptfuzzr
pip install -e ".[dev]"
```

This registers the `promptfuzzr` command (`promptfuzzr.exe` on Windows). Every command also works as `python -m promptfuzzr.cli <command>`.

```bash
promptfuzzr --help
```

### Run the shipped local configuration

```bash
promptfuzzr fuzz --config config/promptfuzzr.yaml
```

Start with `retry_policy.max_retries: 1` for a first sanity run. Results are stored at:

```text
~/.promptfuzzr/db/promptfuzzr.db
```

### Inspect results

```bash
promptfuzzr findings
promptfuzzr report <run-id>
```

### Validate the pipeline without a real model

Set:

```yaml
target_profile: vulnerable
```

This uses the deterministic offline positive-control target. It validates PromptFuzzr's own judging and orchestration; it does not measure a real target's security.

## Documentation

- [USAGE.md](docs/USAGE.md) — installation, commands, and common workflows
- [CONCEPTS.md](docs/CONCEPTS.md) — test cases, judges, verdicts, retries, delivery, and propagation
- [CONFIGURATION.md](docs/CONFIGURATION.md) — complete YAML field reference and scenario configuration
- [TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) — common failures and diagnostics
- [DEVELOPMENT.md](docs/DEVELOPMENT.md) — tests and development workflow

## Commands at a glance

| Command | Purpose |
|---|---|
| `seeds` | Inspect the seed corpus |
| `mutate` | Preview payload variants |
| `fuzz` | Execute the corpus against a target |
| `findings` | Inspect results |
| `minimize` | Reduce a finding to a minimal reproducer |
| `report` | Generate coverage, comparison, and export reports |

## Important behavior

- The shipped configuration lives at `config/promptfuzzr.yaml`.
- `corpus_dir` is resolved relative to the config file's directory.
- The database path is fixed at `~/.promptfuzzr/db/promptfuzzr.db`.
- `authority_policy` is required for meaningful `action_outcome` judging.
- `axes` is currently informational; `concurrency` is currently defined but runs are sequential.
- Only `single_shot` findings can currently be minimized.

## Development

```bash
pip install -e ".[dev]"
pytest tests/
```

See [DEVELOPMENT.md](docs/DEVELOPMENT.md) for the current test layout.
