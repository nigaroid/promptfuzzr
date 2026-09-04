# Configuration

Every `fuzz`/`minimize` run is driven by one YAML file:
`config/promptfuzzr.yaml`. This is the only template shipped — every
scenario below is a small, explicit change to specific fields in it, not a
separate file. Copy it if you want a saved variant (e.g.
`config/my-run.yaml`), but **keep the copy inside `config/`** — see the
path-resolution note below.

```yaml
target_id: lab_agent
corpus_dir: ../promptfuzzr/corpus/seeds

model_provider: anthropic
model_name: claude-sonnet-4-6
target_profile: real

agent_endpoint: null
delivery: direct
propagation: single_shot
max_follow_up_turns: 2

retry_policy:
  max_retries: 3
  backoff_seconds: 1.5

authority_policy:
  role: support_agent
  allowed_tools:
    - lookup_order
    - get_weather
  allowed_arg_values: {}

axes: [delivery, encoding]
concurrency: 4
```

As shipped, this points at the local lab agent (see [Scenario: remote
agent](#scenario-remote-agent) for the alternative) using a real Anthropic
model — the scenario needing the fewest moving parts (no Docker, no local
router).

## Path resolution — read this before copying the file anywhere

`corpus_dir` resolves **relative to the config file's own directory**, not
your current working directory. The shipped file lives in `config/`, so
`../promptfuzzr/corpus/seeds` correctly reaches the project root's
`promptfuzzr/` package from there.

**If you copy this file outside `config/`, you must adjust `corpus_dir`**
(add/remove `../` segments, or switch to an absolute path) — otherwise the
run silently finds zero seeds and reports `Ran 0 test cases` with no
error. This is the single most common way to get a confusingly empty run;
if that happens, check this first (see also
[TROUBLESHOOTING.md](TROUBLESHOOTING.md)).

`db_path` is deliberately **not** a field here at all — the database
location is managed entirely by the application, always at
`~/.promptfuzzr/db/promptfuzzr.db`. It can't be set via YAML or a CLI flag.
An old config file with a leftover `db_path:` key triggers a warning
(the key is ignored, not silently accepted).

## Field reference

| Field | Meaning |
|---|---|
| `target_id` | `lab_agent` for the local harness, or a name for a remote agent when `agent_endpoint` is set |
| `corpus_dir` | seed directory — see [Path resolution](#path-resolution--read-this-before-copying-the-file-anywhere) |
| `model_provider` | `anthropic` (reads `ANTHROPIC_API_KEY`) or `openai_compat` (reads `OPENAI_COMPAT_API_KEY`, `OPENAI_COMPAT_BASE_URL`) — ignored if `agent_endpoint` or `target_profile: vulnerable` is set |
| `model_name` | model id passed to whichever provider |
| `target_profile` | `real` (default) or `vulnerable` — see [Scenario: validating the pipeline itself](#scenario-validating-the-pipeline-itself) |
| `agent_endpoint` | set to fuzz a remote OpenAI-compatible agent instead of the local harness — see [Scenario: remote agent](#scenario-remote-agent) |
| `delivery` | `direct` \| `webpage` \| `email` \| `file` \| `rag_doc` \| `tool_schema` — see [CONCEPTS.md](CONCEPTS.md#delivery-surfaces) |
| `propagation` | `single_shot` \| `multi_step` \| `cross_session` — see [CONCEPTS.md](CONCEPTS.md#propagation-modes) |
| `max_follow_up_turns` | `multi_step` only |
| `retry_policy.max_retries` / `.backoff_seconds` | see [CONCEPTS.md](CONCEPTS.md#retries-are-outcome-based-not-just-error-based) |
| `authority_policy` | **required** — the `action_outcome` judge has nothing to compare against without it |
| `authority_policy.allowed_arg_values` | optional per-argument constraints — see [Per-argument constraints](#per-argument-constraints) |
| `axes` | currently informational only — not yet used to auto-vary a run |
| `concurrency` | defined but not yet used — runs are sequential |

## Per-argument constraints

Beyond "is this tool allowed at all," constrain *which argument values* are
allowed for a tool that otherwise is:

```yaml
authority_policy:
  role: support_agent
  allowed_tools: [lookup_order, delete_ticket]
  allowed_arg_values:
    delete_ticket:
      ticket_id: ["1001", "1002"]
```

`delete_ticket(ticket_id="1001")` passes; `delete_ticket(ticket_id="9999")`
is flagged even though `delete_ticket` itself is allowed — this catches an
injection that gets the model to act on the *right tool, wrong target*.
Values compare as strings, so YAML ints/strings and model-emitted JSON
values compare uniformly.

## Scenario: remote agent

Fuzz an external agent that exposes an OpenAI-compatible
`/v1/chat/completions` endpoint. Change:

```yaml
agent_endpoint: http://localhost:7003
```

When `agent_endpoint` is set, it **takes full precedence** —
`model_provider`, `model_name`, and `target_profile` are ignored entirely.
The remote agent brings its own system prompt and tools; you don't control
its registry, which is why `tool_schema` delivery falls back to a benign
direct question against remote targets.

**DVAA (Damn Vulnerable AI Agent)** is a good reference target:

```bash
docker run -d --name dvaa -p 9000:9000 -p 7001-7023:7001-7023 opena2a/dvaa:latest
```

| Agent | Port | Profile |
|---|---|---|
| SecureBot | 7001 | HARDENED — control, should resist |
| HelperBot | 7002 | WEAK — overly eager follower |
| LegacyBot | 7003 | CRITICAL — everything exploitable |
| RAGBot | 7005 | WEAK — injectable knowledge base |
| MemoryBot | 7007 | VULNERABLE — context/memory poisoning |

`fuzz` probes the endpoint before running and fails fast with a clear
error if it's unreachable — you'll know immediately if the container isn't
up. Run SecureBot alongside whichever bot you're actually testing as a
control: if your corpus gets meaningful successes against SecureBot too,
that's a sign the judge is over-triggering, not that SecureBot is
vulnerable.

See also [DEMO.md](DEMO.md) for a full walkthrough against LegacyBot.

## Scenario: local target via an OpenAI-compatible router

For a local router (LiteLLM proxy, LM Studio, vLLM's OpenAI server, etc.)
instead of the Anthropic API. Change:

```yaml
model_provider: openai_compat
model_name: <whatever model id your router exposes>
```

And set environment variables before running:

```bash
export OPENAI_COMPAT_API_KEY="your key"       # or a placeholder for local-only routers
export OPENAI_COMPAT_BASE_URL="http://localhost:PORT/v1"
```

**Before relying on this for a real run, confirm tool calling actually
works** — see [USAGE.md](USAGE.md#confirming-tool-calling-support-before-a-real-run).
A model that only *describes* calling a tool instead of actually calling it
silently defeats `action_outcome` judging; every case falls through to
`heuristic` instead, and nothing tells you that happened unless you check
`verdict_basis`.

## Scenario: validating the pipeline itself

Real models refuse most things, which makes it hard to tell "the target is
robust" apart from "the fuzzer's success-detection is broken."
`target_profile: vulnerable` swaps in a deterministic, offline,
zero-network fixture that follows any injected instruction it recognizes —
a positive control, the same idea as DVWA for web scanners. Change:

```yaml
target_profile: vulnerable
```

`model_provider`/`model_name` are ignored when this is set. Every run
prints a yellow warning to stderr:

```
WARNING: target_profile=vulnerable — using the deterministic
positive-control target, NOT a real model. Results validate the
fuzzer's own success-detection pipeline; they say nothing about
real-world attack success rates. Do not report these numbers as
findings.
```

**Use this to answer "is my fuzzer working," never "how vulnerable is my
target."** Run it once after any change to `promptfuzzr/judge/`,
`promptfuzzr/orchestrator/engine.py`, or the corpus, before trusting
results from a real target.
