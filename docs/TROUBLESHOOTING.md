# Troubleshooting

## The run finishes instantly with 0 test cases

Most often, `corpus_dir` does not resolve to the actual seed directory. This is especially common after copying the config outside `config/`.

Check the resolved path:

```bash
python3 -c "from promptfuzzr.config import RunConfig; print(RunConfig.from_yaml('your-config.yaml').corpus_dir)"
```

## The run seems to hang

First reduce retry volume:

```yaml
retry_policy:
  max_retries: 1
```

A high retry count can make a campaign look stuck because most payloads against a robust target may consume every retry.

If `max_retries: 1` still stalls, investigate network connectivity and the target/router itself.

## Every case is `verdict: error`

Run:

```bash
promptfuzzr findings --verdict error
```

Read the `notes` field. It contains the relevant exception or failure detail, such as a missing API key, unreachable endpoint, or malformed provider response.

## Everything is `verdict_basis: heuristic`

`action_outcome` requires actual structured tool calls. If the model returns prose such as "I would call get_weather" rather than a real tool call, PromptFuzzr has nothing to evaluate at the action level.

First check whether the model/router supports tools, then test the `vulnerable` positive-control profile to verify the judging pipeline.

## Tool-calling check

Before a real OpenAI-compatible run, try a small direct API call with a single test tool:

```bash
python3 -c "
import os, openai
client = openai.OpenAI(
    api_key=os.environ.get('OPENAI_COMPAT_API_KEY', 'not-needed'),
    base_url=os.environ.get('OPENAI_COMPAT_BASE_URL'),
)
resp = client.chat.completions.create(
    model='<your model id>',
    max_tokens=256,
    messages=[{'role': 'user', 'content': \"What's the weather in Paris?\"}],
    tools=[{'type': 'function', 'function': {
        'name': 'get_weather',
        'description': 'Get current weather for a city.',
        'parameters': {
            'type': 'object',
            'properties': {'city': {'type': 'string'}},
            'required': ['city']
        }
    }}],
)
message = resp.choices[0].message
print('tool_calls:', message.tool_calls)
print('WORKS' if message.tool_calls else 'NO TOOL CALLS — action_outcome judging will not have anything to work with')
"
```

## `minimize` reports a propagation error

Only `single_shot` findings can currently be minimized. `multi_step` and `cross_session` findings require a different notion of minimality because the surrounding interaction is not contained entirely in the seed payload.

## You cannot find your results

The SQLite database is always:

```text
~/.promptfuzzr/db/promptfuzzr.db
```

Past runs are separated by `run_id`, `target_id`, and `started_at`.
