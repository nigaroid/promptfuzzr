# PromptFuzzr

Mutation-based prompt injection fuzzing framework for LLM applications and
agents.

## Installation

```bash
git clone https://github.com/nigaroid/promptfuzzr.git
cd promptfuzzr
pip install -e ".[dev]"
```

This registers the `promptfuzzr` command (`promptfuzzr.exe` on Windows).
Every command also works as `python -m promptfuzzr.cli <command>` if you'd
rather not install the console script.

```bash
promptfuzzr --help
```

Six commands: `seeds`, `mutate`, `fuzz`, `findings`, `minimize`, `report`.
All six are fully implemented.

## Quick start

1. Read [docs/CONCEPTS.md](docs/CONCEPTS.md) for what a test case actually
   is (technique / delivery / propagation), how the two judges work, and
   what the verdicts mean.
2. Read [docs/CONFIGURATION.md](docs/CONFIGURATION.md) to set up
   `config/promptfuzzr.yaml` for your target (local lab agent, a remote
   agent, or a local OpenAI-compatible router).
3. Run the corpus and inspect results — see [docs/USAGE.md](docs/USAGE.md)
   for the full command reference (`seeds`, `mutate`, `fuzz`, `findings`,
   `minimize`, `report`) and how the results database works.
4. Follow [docs/DEMO.md](docs/DEMO.md) for a concrete ~5-minute end-to-end
   run against DVAA (Damn Vulnerable AI Agent).
5. Hit a snag? Check [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)
   first — most confusing outcomes (0 test cases, all-`error` runs,
   unexpected `verdict_basis`) have a one-line explanation there.

## Documentation map

| File | Covers |
|---|---|
| [docs/CONCEPTS.md](docs/CONCEPTS.md) | Test cases, techniques, delivery surfaces, propagation modes, judges, verdicts, retries |
| [docs/CONFIGURATION.md](docs/CONFIGURATION.md) | The YAML config file, path resolution, field reference, per-argument constraints, all target scenarios |
| [docs/USAGE.md](docs/USAGE.md) | Every CLI command, the results database, confirming tool-calling support |
| [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) | Common failure modes and what they actually mean |
| [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) | Running the test suite, development setup |
| [docs/DEMO.md](docs/DEMO.md) | A minimal real end-to-end run against DVAA's LegacyBot |

## Contributing

See [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) for running the test
suite and development setup.
