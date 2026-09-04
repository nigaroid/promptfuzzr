# Configuration

All `fuzz` and `minimize` runs are driven by one YAML file. The shipped template is:

```text
config/promptfuzzr.yaml
```

Copy it to another filename inside `config/` when you need a saved scenario, for example `config/my-run.yaml`.

## Example

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

## Path resolution

`corpus_dir` is resolved relative to the configuration file's own directory, not the current working directory.

Because the shipped file lives in `config/`, this works:

```yaml
corpus_dir: ../promptfuzzr/corpus/seeds
```

If you copy the configuration outside `config/`, update `corpus_dir` accordingly. A common symptom of getting this wrong is:

```text
Ran 0 test cases
```

with no obvious error.

## Database path

Do not add a `db_path` field. The database is always:

```text
~/.promptfuzzr/db/promptfuzzr.db
```

The path cannot currently be changed through YAML or a CLI flag. An old config containing `db_path:` triggers a warning and the key is ignored.

## Field reference

| Field | Meaning |
|---|---|
| `target_id` | `lab_agent` for the local harness, or a target name when `agent_endpoint` is used |
| `corpus_dir` | Seed directory; resolved relative to the config file |
| `model_provider` | `anthropic` or `openai_compat` |
| `model_name` | Model id passed to the selected provider |
| `target_profile` | `real` or `vulnerable` |
| `agent_endpoint` | OpenAI-compatible remote agent endpoint |
| `delivery` | `direct`, `webpage`, `email`, `file`, `rag_doc`, or `tool_schema` |
| `propagation` | `single_shot`, `multi_step`, or `cross_session` |
| `max_follow_up_turns` | Maximum follow-ups for `multi_step` |
| `retry_policy.max_retries` / `backoff_seconds` | Retry behavior |
| `authority_policy` | Required for `action_outcome` judging |
| `authority_policy.allowed_arg_values` | Optional per-argument value constraints |
| `axes` | Currently informational; does not auto-vary a run |
| `concurrency` | Defined but currently unused; execution is sequential |

## Providers

### Anthropic

```yaml
model_provider: anthropic
```

Uses `ANTHROPIC_API_KEY`.

### OpenAI-compatible

```yaml
model_provider: openai_compat
```

Uses:

```text
OPENAI_COMPAT_API_KEY
OPENAI_COMPAT_BASE_URL
```

When `agent_endpoint` is set, these provider fields are ignored.

## Remote agent precedence

```yaml
agent_endpoint: http://localhost:7003
```

When present, `agent_endpoint` takes full precedence over `model_provider`, `model_name`, and `target_profile`.

The remote agent owns its own system prompt and tool registry. Consequently, `tool_schema` is supported only by the local `lab_agent`; remote targets fall back to a benign direct question and record the behavior in `notes`.

## Local OpenAI-compatible router

For LiteLLM, LM Studio, vLLM, or another OpenAI-compatible router:

```yaml
model_provider: openai_compat
model_name: <router model id>
```

Then set the environment variables before the run.

Verify real tool calling first. A model that only describes a tool call in text produces `heuristic` judging instead of meaningful `action_outcome` results.

## Per-argument constraints

You can constrain values for a tool that is otherwise allowed:

```yaml
authority_policy:
  role: support_agent
  allowed_tools: [lookup_order, delete_ticket]
  allowed_arg_values:
    delete_ticket:
      ticket_id: ["1001", "1002"]
```

`delete_ticket(ticket_id="1001")` passes. `delete_ticket(ticket_id="9999")` is flagged.

Values are compared as strings so YAML numbers/strings and model-emitted JSON values compare uniformly.

## Validating the pipeline

Set:

```yaml
target_profile: vulnerable
```

Provider/model fields are ignored for this profile. PromptFuzzr prints a warning explaining that the fixture is a positive control and its success rate is not evidence about a real model.

Use this profile after changes to the judge, orchestrator, or corpus before trusting a real-target run.
