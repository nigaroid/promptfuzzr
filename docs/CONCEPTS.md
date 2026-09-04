# Concepts

## Test cases

Every attack attempt is a `TestCase`: one seed payload, one delivery surface, one propagation mode, one judge outcome, and one stored result in SQLite.

### Techniques

PromptFuzzr currently defines 15 techniques:

- instruction override
- role manipulation
- rule injection and authority assertion
- context switching
- story/poem extraction
- summary/repetition
- syntactic extraction
- indirect inference
- fake conversation
- jailbreak persona
- token smuggling
- business logic manipulation
- chained web attack
- insecure output handling
- schema poisoning

### Delivery

Delivery describes where the seed enters the target:

| Value | Meaning |
|---|---|
| `direct` | Sent as if typed directly by the user |
| `webpage` | Embedded in an HTML comment on a locally served page |
| `email` | Embedded in an HTML-comment email body |
| `file` | Embedded in a plausible file, CSV by default |
| `rag_doc` | Indexed as a knowledge-base document |
| `tool_schema` | Injected into a tool description in the local lab registry |

`repo_comment`, `calendar`, and `tool_output` are defined but do not yet have dedicated channels and currently fall back to `direct`.

Indirect delivery artifacts are cleaned up after each test case.

### Propagation

| Value | Meaning |
|---|---|
| `single_shot` | One trigger turn |
| `multi_step` | Trigger followed by escalating follow-ups |
| `cross_session` | Payload persists in a store and is retrieved by a fresh session |

`cross_session` is meaningful only with `delivery: rag_doc`. Any other combination falls back to `single_shot` and records the reason in `notes`.

For `multi_step`, `kill_chain_depth` is the total tool-call count across the exchange.

## Judges

PromptFuzzr has two judges.

### `action_outcome`

This is the primary differentiator. If the target produces tool calls, PromptFuzzr checks whether it:

1. called a tool outside `authority_policy.allowed_tools`, or
2. called an allowed tool with a disallowed argument value defined under `allowed_arg_values`.

When tool calls exist, this judge wins.

### `heuristic`

This uses regex matching against response text, such as leaked system-prompt indicators, compliance phrases, or explicit refusal phrases. It is used when there are no tool calls to evaluate.

Every result stores the selected judge in `verdict_basis`.

## Verdicts

Possible verdicts are:

- `success`
- `fail`
- `error`
- `partial` (defined but not currently produced)

`error` means the attempt itself broke, for example because of a network error, unreachable target, malformed provider response, or unexpected response shape. It does not mean that the target successfully resisted the attack.

## Retries

Retries are outcome-based, not exception-only.

`retry_policy.max_retries` allows a payload that cleanly produced `FAIL` to be tried again because model behavior can be non-deterministic. Retries stop as soon as a `SUCCESS` occurs.

High retry counts can make campaigns slow. Start with `1` or `2` when validating a new setup.

## Positive control

`target_profile: vulnerable` replaces the real model with a deterministic, offline fixture that recognizes the injected instruction patterns.

Use it to answer:

> Is PromptFuzzr's orchestration and judging pipeline working?

Do not use it to answer:

> How vulnerable is my real target?

The profile is a pipeline validation target, analogous to a deliberately vulnerable test application used to validate a scanner.
