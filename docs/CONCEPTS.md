# Concepts

## What a "test case" is

Every attack attempt is a `TestCase`: one seed payload, sent through one
**delivery** surface, with one **propagation** mode, judged by one of two
judges, and stored in SQLite.

- **Technique** — *what kind* of manipulation (15 total): instruction
  override, role manipulation, rule injection & authority assertion,
  context switching, story/poem extraction, summary/repetition, syntactic
  extraction, indirect inference, fake conversation, jailbreak persona,
  token smuggling, business logic manipulation, chained web attack,
  insecure output handling, schema poisoning.
- **Delivery** — *where* the payload enters. Implemented: `direct`,
  `webpage`, `email`, `file`, `rag_doc`, `tool_schema`. Defined but with no
  channel yet (falls back to `direct` if set): `repo_comment`, `calendar`,
  `tool_output`.
- **Propagation** — *how many turns* it takes: `single_shot` (one trigger,
  done), `multi_step` (trigger + escalating follow-up pushes), `cross_session`
  (payload sits in a store, a fresh session picks it up with no direct
  delivery — only meaningful with `delivery: rag_doc`).

## The two judges, and which one wins

- **`action_outcome`** (the differentiator) — did the target call a tool
  outside `authority_policy.allowed_tools`, or call an allowed tool with a
  disallowed argument value (`allowed_arg_values`)? Checked first, and wins,
  whenever the response includes at least one tool call.
- **`heuristic`** — regex pattern matching against the response text (leaked
  system prompt, compliance phrases, explicit refusal phrases). Used only
  when there were no tool calls to judge.

Every result records which judge fired (`verdict_basis`). If you expected
`action_outcome` and got `heuristic`, the target never actually invoked a
tool for that payload — see [USAGE.md](USAGE.md#confirming-tool-calling-support-before-a-real-run)
for how to check whether your model/router supports tool calling at all.

## Verdicts

`success` / `fail` / `error` (`partial` is defined but nothing currently
produces it). `error` means the *attempt itself* broke — network error, bad
response shape, unreachable target — not that the attack failed. A run
that's mostly `error` rather than `fail` usually means a config or
connectivity problem, not a finding about the target's defenses.

## Retries are outcome-based, not just error-based

`retry_policy.max_retries` retries a payload that got a clean `FAIL`, not
just one that raised an exception — model responses are non-deterministic,
so a payload can fail 3 times and succeed on the 4th. It stops the moment a
`SUCCESS` verdict lands. A high `max_retries` can make a run slow, since
most payloads against a well-behaved target burn every retry; start low (1
or 2) for a first sanity run.

## Delivery surfaces

| `delivery:` value | What happens |
|---|---|
| `direct` | Seed text sent as-is, as if the user typed it. |
| `webpage` | Seed wrapped in an HTML comment on a locally-served page; target asked to summarize it. |
| `email` | Seed wrapped in an HTML comment as an email body; target told "I just received this email." |
| `file` | Seed embedded in a plausible file (csv by default — one poisoned field among benign ones); target asked to review it. |
| `rag_doc` | Seed indexed as a "knowledge base document"; target asked a question that would retrieve it. Required for `cross_session`. |
| `tool_schema` | Seed poisons a tool's *description* field in the target's own registry — only works against the local `lab_agent`; remote agents fall back to a benign direct question with a note in `notes`. |

Every indirect surface cleans up its own artifact after each test case — no
state accumulates across seeds.

## Propagation modes

- **`single_shot`** — one trigger turn. Default, fastest.
- **`multi_step`** — sends the trigger, then up to `max_follow_up_turns`
  escalating follow-up pushes, only if the previous turn didn't already
  succeed. `kill_chain_depth` in results is the total tool-call count across
  the whole exchange — your severity signal.
- **`cross_session`** — only meaningful with `delivery: rag_doc`. Payload is
  stored, then a brand-new session (no shared history) asks an unrelated
  question that would trigger retrieval. Setting `cross_session` with any
  other delivery falls back to `single_shot` and records why in `notes`.
