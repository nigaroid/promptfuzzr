## Installation

```bash
git clone https://github.com/nigaroid/promptfuzzr.git
cd promptfuzzr
pip install -e ".[dev]"
```

The package installs the `promptfuzzr` command. The module form is also available:

```bash
python -m promptfuzzr.cli <command>
```

Check the CLI with:

```bash
promptfuzzr --help
```

## 1. Inspect the corpus

```bash
promptfuzzr seeds list
promptfuzzr seeds list --corpus-dir path/to/other/seeds
promptfuzzr seeds show instr-override-001
```

`list` prints each seed's id, technique, and tags. `show` prints the seed's full `base_text`.

## 2. Preview mutations

```bash
promptfuzzr mutate "ignore previous instructions" --count 3
promptfuzzr mutate instr-override-001 --count 5
```

This is preview-only. There is no `--mutate` flag on `fuzz`; real runs send each seed's raw `base_text` unmutated. Currently only `--axis encoding` is accepted, and it runs all implemented mutators together: encoding transforms, fake-delimiter/fake-user-turn wrapping, synonym substitution, and field-splitting.

## 3. Run a fuzzing campaign

```bash
promptfuzzr fuzz --config config/promptfuzzr.yaml
```

Example output:

```text
Ran 26 test cases — 3 successful.
Results stored in /home/<user>/.promptfuzzr/db/promptfuzzr.db
```

For a first real-target run, set `max_retries: 1` or `2`.

## 4. Inspect findings

```bash
promptfuzzr findings
promptfuzzr findings --verdict fail
promptfuzzr findings --verdict error
promptfuzzr findings --run-id <uuid>
```

The default shows successful findings from the most recent run. Each result includes verdict, id, technique, delivery, propagation, kill-chain depth, actual tool calls, payload preview, and response preview.

Check `error` results early. A run dominated by `error` generally indicates a configuration, provider, endpoint, or response-shape problem rather than a defensive success.

## 5. Minimize a finding

```bash
promptfuzzr minimize <finding-id> --config config/promptfuzzr.yaml
```

Minimization replays candidate payloads against a freshly built target, so it consumes real target/API calls. Use the same configuration that produced the finding. `--verify-retries` defaults to `2` and helps account for non-deterministic targets.

Only `single_shot` findings can currently be minimized.

## 6. Generate reports

```bash
promptfuzzr report <run-id>
promptfuzzr report <run-id> --fmt json --out report.json
promptfuzzr report <run-id> --fmt html --out report.html
promptfuzzr report <run-id> --compare-run-id <other-run-id>
```

Reports include run metadata, coverage by technique/delivery/propagation/encoding, verdict breakdown, and successful findings. Comparison mode adds a per-technique defense-delta table.

A positive comparison delta means the comparison run had a higher success rate than the baseline. A technique exercised by only one run is shown as `—`.

## Remote agent workflow

A remote target can expose an OpenAI-compatible `/v1/chat/completions` endpoint. Configure:

```yaml
agent_endpoint: http://localhost:7003
```

When `agent_endpoint` is set, it takes precedence over `model_provider`, `model_name`, and `target_profile`.

### DVAA reference target

```bash
docker run -d --name dvaa -p 9000:9000 -p 7001-7023:7001-7023 opena2a/dvaa:latest
```

Useful reference bots include SecureBot, HelperBot, LegacyBot, RAGBot, and MemoryBot. Run a hardened control alongside the bot under test to help distinguish real findings from over-triggering by the judge.

## Local OpenAI-compatible router

Set:

```yaml
model_provider: openai_compat
model_name: <model id exposed by your router>
```

Then configure:

```bash
export OPENAI_COMPAT_API_KEY="your key"
export OPENAI_COMPAT_BASE_URL="http://localhost:PORT/v1"
```

Before a real campaign, verify that the target produces actual structured tool calls. See [TROUBLESHOOTING.md](TROUBLESHOOTING.md#tool-calling-check).
