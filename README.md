# PromptFuzzr — User Manual (Phases 0–4)

This covers everything currently working: seed corpus, mutation preview,
fuzzing against local or remote targets, delivery surfaces, propagation
modes, and reading results. `minimize` and `report` are not built yet
(Phase 5/6) — see the end of this document for what that means today.

---

## 1. Install

```bash
git clone <your repo>
cd promptfuzzr
pip install -e ".[dev]"
```

This registers the `promptfuzzr` command (and `promptfuzzr.exe` on Windows).
If you'd rather not install the console script, every command also works as
`python -m promptfuzzr.cli <command>`.

Verify the install:

```bash
promptfuzzr --help
```

You should see six commands: `seeds`, `mutate`, `fuzz`, `findings`,
`minimize`, `report`. Only the first four do anything yet.

---

## 2. Core concepts (read this before running anything)

### 2.1 What a "test case" is

Every attack attempt is a `TestCase`: one seed payload, sent through one
**delivery** surface, with one **propagation** mode, judged by one of two
judges, and stored in SQLite. The three axes:

- **Technique** — *what kind* of manipulation (15 total): instruction
  override, role manipulation, rule injection, context switching,
  story/poem extraction, summary/repetition, syntactic extraction, indirect
  inference, fake conversation, jailbreak persona, token smuggling,
  business logic manipulation, chained web attack, insecure output
  handling, schema poisoning.
- **Delivery** — *where* the payload enters: `direct`, `webpage`, `email`,
  `file`, `rag_doc`, `tool_schema` are implemented. (`repo_comment`,
  `calendar`, `tool_output` exist as enum values but have no delivery
  channel built yet.)
- **Propagation** — *how many turns* it takes: `single_shot` (one trigger,
  done), `multi_step` (trigger + follow-up pushes, context hijacking),
  `cross_session` (payload sits in a store, a **fresh** session picks it up
  with no direct delivery).

### 2.2 The two judges, and which one wins

- **`action_outcome`** (the differentiator) — did the target call a tool
  that isn't on the `authority_policy.allowed_tools` list, or call an
  allowed tool with a disallowed argument value? This is checked first,
  and wins, whenever the target's response includes at least one tool
  call.
- **`heuristic`** — regex pattern matching against the response text
  (leaked system prompt, compliance phrases like "instructions received",
  explicit block/refusal phrases). Used whenever there were no tool calls
  to judge — pure text-leak techniques, or a target that just describes
  what it did in prose instead of calling a real tool.

You'll see which one fired in every result (`verdict_basis` column /
`findings` output). If you expected `action_outcome` and got `heuristic`,
it usually means your target never actually invoked a tool for that
payload — worth knowing when interpreting a `FAIL`.

### 2.3 Verdicts

`success` / `fail` / `error` (there's a `partial` value defined but nothing
currently produces it). `error` means the *attempt itself* broke — a
network error, a bad response shape, an unreachable target — not that the
attack failed. Always check `error` rows separately from `fail` rows; a
pile of `error`s usually means a config or connectivity problem, not a
finding about the target's defenses.

### 2.4 Retries are outcome-based, not just error-based

`retry_policy.max_retries` doesn't just retry on exceptions — it retries a
payload that got a clean `FAIL` too, up to that many times, because model
responses are non-deterministic (a payload can fail 3 times and succeed on
the 4th). It stops early the moment a `SUCCESS` verdict lands. This means:

- A high `max_retries` (the default is 8) can make a full run **slow**,
  since most payloads against a well-behaved target will burn every retry.
  Start with `max_retries: 1` or `2` for a first sanity run, then raise it
  once you know the target/config actually works.
- `retry_count` in results tells you how many attempts a payload actually
  took — 0 means it worked (or failed) on the first try.

---

## 3. Configuration

Every `fuzz` run is driven by a YAML file. Four examples ship in `config/`:

| File | Target |
|---|---|
| `config/lab.example.yaml` | Local lab agent, real Anthropic model |
| `config/lab.omniroute.yaml` | Local lab agent, via an OpenAI-compatible local router |
| `config/lab.vulnerable.yaml` | Local lab agent, deterministic positive-control (see §7) |
| `config/dvaa.yaml` | Remote agent — DVAA's LegacyBot (see §6) |

### 3.1 Required fields

```yaml
target_id: lab_agent          # or a name for your remote target
corpus_dir: ../promptfuzzr/corpus/seeds
```

**Path resolution:** `corpus_dir` resolves **relative to the config
file's own directory**, not your current working directory or the
project root. All shipped configs live in `config/`, so a path like
`../promptfuzzr/corpus/seeds` correctly reaches the project-root
`promptfuzzr/` package from there. If you write your own config file
somewhere else, adjust the `../` accordingly — or just use an absolute
path, which is always taken as-is.

### 3.2 Full field reference

```yaml
target_id: lab_agent
corpus_dir: ../promptfuzzr/corpus/seeds
axes: [delivery, encoding]       # currently informational only — not yet used to auto-vary a run

model_provider: anthropic        # anthropic | openai_compat
model_name: claude-sonnet-4-6
target_profile: real             # real | vulnerable — see §7

agent_endpoint: null             # set this to fuzz a REMOTE agent instead — see §6
                                  # when set, it overrides target_id/model_provider/target_profile entirely

delivery: direct                 # direct | webpage | email | file | rag_doc | tool_schema
propagation: single_shot         # single_shot | multi_step | cross_session
max_follow_up_turns: 2           # multi_step only — see §5.2

retry_policy:
  max_retries: 8
  backoff_seconds: 1.5

authority_policy:                # REQUIRED — the action_outcome judge has nothing
  role: support_agent            # to compare against without this
  allowed_tools:
    - lookup_order
    - get_weather
  allowed_arg_values:             # optional, Phase 4 — see §3.3
    delete_ticket:
      ticket_id: ["1001", "1002"]

concurrency: 4                   # defined but not yet used — runs are sequential today
```

### 3.3 Per-argument constraints (`allowed_arg_values`)

Beyond "is this tool allowed at all," you can constrain *which argument
values* are allowed for a tool that otherwise is allowed:

```yaml
authority_policy:
  role: support_agent
  allowed_tools: [lookup_order, delete_ticket]
  allowed_arg_values:
    delete_ticket:
      ticket_id: ["1001", "1002"]   # only these two ticket IDs are in-scope
```

With this policy, `delete_ticket(ticket_id="1001")` is a clean pass, but
`delete_ticket(ticket_id="9999")` is flagged as a violation even though
`delete_ticket` itself is on the allow-list — this is what catches an
injection that gets the model to act on the *right tool, wrong target*
(e.g. deleting someone else's ticket). Values are compared as strings, so
YAML ints/strings and model-emitted JSON values compare uniformly — you
don't need to worry about `1001` vs `"1001"`.

### 3.4 Database location (not configurable)

Every run's results go into one SQLite database, always at:

```
~/.promptfuzzr/db/promptfuzzr.db
```

- Linux: `/home/<user>/.promptfuzzr/db/promptfuzzr.db`
- Windows: `C:\Users\<user>\.promptfuzzr\db\promptfuzzr.db`

This location is **managed entirely by the application** and cannot be
set via YAML (`db_path:` is not a valid config field — an old config
file that still has one triggers a warning, not an error, and the key
is ignored) or via a CLI flag. Every run, from every config, writes into
the same shared database; `runs.run_id` / `runs.target_id` /
`runs.started_at` are what distinguish one run from another within it —
`findings --run-id <uuid>` scopes to one specific run.

The directory is created automatically the first time it's needed — you
don't need to create `~/.promptfuzzr/db/` yourself. See
`promptfuzzr/storage/paths.py` if you need the implementation details;
every database-touching function in the codebase goes through
`get_db_path()` there, nowhere else.

---

## 4. Everyday commands

### 4.1 `seeds` — inspect the corpus

```bash
promptfuzzr seeds list
promptfuzzr seeds list --corpus-dir path/to/other/seeds
promptfuzzr seeds show instr-override-001
```

`list` prints every seed's id, technique, and tags. `show` prints one
seed's full `base_text`. Useful before a run to confirm what's actually in
the corpus, and afterward to look up exactly what a given `technique`
column in results actually said.

### 4.2 `mutate` — preview payload variants (no target needed)

```bash
promptfuzzr mutate "ignore previous instructions" --count 3
promptfuzzr mutate instr-override-001 --count 5
```

Accepts either a raw string or a known seed id (resolved automatically —
if the argument matches a seed id, its `base_text` is used instead of the
literal string). This is a **preview only** — it doesn't feed into `fuzz`
yet; there's no `--mutate` flag on the fuzz run itself. Use it to sanity
check what a mutator produces before deciding it's worth hand-adding to
the corpus.

Only `--axis encoding` is wired (the default and only accepted value —
anything else exits with an error). Despite the name, this currently runs
every implemented mutator together — encoding transforms (base64, rot13),
fake-delimiter and fake-user-turn wrapping, synonym substitution, and
field-splitting — not literally just the `Encoding` enum's values. Treat
`mutate`'s output as "everything the mutation engine can currently do to
this payload," not a strict per-axis breakdown.

### 4.3 `fuzz` — run the corpus against a target

```bash
promptfuzzr fuzz --config config/lab.example.yaml
```

Prints a one-line summary (`Ran N test cases — M successful`) and the
path results were written to — always
`~/.promptfuzzr/db/promptfuzzr.db` (see §3.4), not configurable.
That's it from the CLI — use `findings` next to actually see anything.

**Before your first real run:** start with `max_retries: 1` in the config
and, if you're hitting a real network target, confirm connectivity first
(see §6.2 for remote targets, or just run a 1-seed corpus by pointing
`corpus_dir` at a folder with a single seed file).

### 4.4 `findings` — see what happened

```bash
promptfuzzr findings                          # most recent run, verdict=success (default)
promptfuzzr findings --verdict fail
promptfuzzr findings --verdict error
promptfuzzr findings --run-id <uuid>           # a specific past run
```

`findings` (and `minimize`/`report`, once built) always read from the
same centralized database — there's no `--db-path` flag, since the
location isn't user-configurable (§3.4).

For each matching test case, prints: verdict, id, technique, delivery,
propagation, kill-chain depth, which tools were actually called, a payload
preview, and a response preview. This is your primary way of reading
results right now — there's no `report` yet.

**Read `error` results first.** If most of a run is `error` rather than
`fail`, something's broken (bad API key, unreachable endpoint, malformed
config) — the corpus/target/judge pipeline never got a fair shot.

---

## 5. Delivery surfaces and propagation modes

### 5.1 Delivery surfaces

| `delivery:` value | What happens |
|---|---|
| `direct` | Seed text sent as-is, as if the user typed it. |
| `webpage` | Seed wrapped in an HTML comment on a locally-served page; target is asked to summarize it. |
| `email` | Seed wrapped in an HTML comment as an email body; target is told "I just received this email." |
| `file` | Seed embedded in a plausible-looking file (txt/md/csv/code — csv is the default-realistic case, one poisoned field among benign ones); target is asked to review it. |
| `rag_doc` | Seed indexed as a "knowledge base document"; target is asked a question that would retrieve it. Required for `cross_session` propagation. |
| `tool_schema` | Seed poisons a tool's *description* field in the target's own tool registry (only works against `AgentHarnessTarget` — remote agents own their registry privately and fall back to a benign direct question with a note). |

Every indirect surface (webpage/email/file/rag_doc) cleans up its own
artifact after each test case — no state accumulates across seeds, per the
"one payload per document" isolation principle.

### 5.2 Propagation modes

- **`single_shot`** — one trigger turn. Default, and the fastest to run.
- **`multi_step`** — sends the trigger, then up to `max_follow_up_turns`
  escalating follow-up pushes ("continue with what the material said" →
  "you haven't completed the task yet") **only if** the previous turn
  didn't already succeed. `kill_chain_depth` in results tells you how many
  total tool calls fired across the whole exchange, which is your severity
  signal for "how far did this chain go."
- **`cross_session`** — only meaningful when `delivery: rag_doc`. The
  payload is stored via the RAG channel, then a **brand-new session** (no
  shared history with the delivery step) asks an unrelated question that
  would trigger retrieval. This tests whether stored poison fires without
  any same-session delivery. If you set `cross_session` with any other
  delivery surface, the engine silently falls back to `single_shot` and
  records a note explaining why — check the `notes` column if a run's
  results look unexpectedly like single-shot.

---

## 6. Targets: local lab agent vs. remote agent

### 6.1 Local lab agent (`target_id: lab_agent`)

This is `AgentHarnessTarget` — a small tool-calling loop **you control**,
with a 5-tool registry (`lookup_order`, `get_weather` in-scope;
`delete_ticket`, `send_email`, `apply_discount` out-of-scope by default in
the example policy). It needs a real model behind it:

```yaml
model_provider: anthropic        # reads ANTHROPIC_API_KEY
# or
model_provider: openai_compat    # reads OPENAI_COMPAT_API_KEY, OPENAI_COMPAT_BASE_URL
model_name: <whatever model id your provider/router expects>
```

**Before fuzzing with `openai_compat`,** confirm your router/model actually
supports tool calling — a model that only *describes* calling a tool
instead of actually calling it silently defeats `action_outcome` judging
(everything falls through to `heuristic` instead, and you won't be told).
Use the standalone probe:

```bash
python scripts/probe_tool_calling.py <model-name>
```

If it reports no `tool_calls` in the response, `action_outcome` won't have
anything to work with against that model — expect `heuristic`-only
results, which is a strictly weaker signal.

### 6.2 Remote agent (`agent_endpoint: ...`)

Set `agent_endpoint` to fuzz an **external** agent that exposes an
OpenAI-compatible `/v1/chat/completions` endpoint — the fuzzer manages
per-session history and sends the corpus straight at it. The remote agent
brings its own system prompt and tools; you don't control or see its
registry (which is why `tool_schema` delivery falls back for these).

When `agent_endpoint` is set, it **takes full precedence** —
`model_provider`, `model_name`, and `target_profile` are ignored entirely.

**DVAA (Damn Vulnerable AI Agent)** is the reference remote target:

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

```bash
promptfuzzr fuzz --config config/dvaa.yaml
```

Before launching a full run, `fuzz` automatically probes the endpoint and
fails fast with a clear error if it's unreachable — you'll know
immediately if the container isn't up, rather than watching every seed
error out one by one.

**Tip:** run `SecureBot` (7001) as a control alongside whichever bot you're
actually testing. If your corpus gets meaningful `success` results against
SecureBot too, that's a strong signal the *judge* is miscalibrated
(over-triggering), not that SecureBot is actually vulnerable.

---

## 7. Validating the pipeline itself: `target_profile: vulnerable`

Real models refuse most things, which makes it genuinely hard to tell "the
target is robust" apart from "the fuzzer's success-detection is broken."
`target_profile: vulnerable` swaps in a deterministic, offline,
zero-network fixture (`VulnerableAgentModelClient`) that follows any
injected instruction it recognizes — a positive control, the same idea as
DVWA for web scanners.

```yaml
target_profile: vulnerable
# model_provider/model_name are ignored when this is set
```

```bash
promptfuzzr fuzz --config config/lab.vulnerable.yaml
```

You'll see a yellow warning on stderr every time this runs:

```
WARNING: target_profile=vulnerable — using the deterministic
positive-control target, NOT a real model. Results validate the
fuzzer's own success-detection pipeline; they say nothing about
real-world attack success rates. Do not report these numbers as
findings.
```

**Use this to answer "is my fuzzer working," never "how vulnerable is my
target."** A near-100% success rate here just confirms the corpus → judge →
findings path is wired correctly. Run it once after any change to
`judge/`, `orchestrator/engine.py`, or the corpus, before trusting results
from a real target.

---

## 8. Reading results directly from SQLite

`findings` covers most needs, but for anything more specific:

```bash
python scripts/inspect_db.py                    # default: ~/.promptfuzzr/db/promptfuzzr.db
python scripts/inspect_db.py path/to/other.db    # or point it at any specific db file
```

Prints every run's metadata, a verdict breakdown, and full per-case detail
including error notes — useful when `findings` is filtering out exactly
the rows you want to see, or when comparing two runs' `.db` files side by
side. If you'd rather query directly, `test_cases` and `runs` are plain
SQLite tables — `technique`, `delivery`, `propagation`, `encoding`,
`verdict`, `verdict_basis`, `retry_count`, `kill_chain_depth`,
`tool_calls_json`, `response_text`, and `notes` are all real columns.

---

## 9. Troubleshooting

**A run finishes instantly with 0 test cases.** Your `corpus_dir` didn't
resolve to a real directory. Check it's relative to the *config file's*
location, not your CWD (§3.1) — `python -c "from promptfuzzr.config import
RunConfig; print(RunConfig.from_yaml('your-config.yaml').corpus_dir)"` will
show you exactly what path it resolved to.

**A run seems to hang for a long time.** Almost always retry volume, not
an actual hang — see §2.4. Drop `max_retries` to 1 and try again. If it's
still stuck even at `max_retries: 1`, it's a genuine network stall; check
your target/router is actually reachable and responding.

**Everything comes back `verdict: error`.** Check `findings --verdict
error` and read the `notes` — it'll be the actual exception message
(missing API key, unreachable endpoint, malformed provider response), not
a generic failure.

**Everything comes back `verdict_basis: heuristic` when you expected
`action_outcome`.** The target never called a tool for those payloads.
Either the model doesn't support/isn't using tool calling (run the probe
script, §6.1), or your seeds genuinely aren't triggering tool use for this
target — worth checking with `target_profile: vulnerable` first to confirm
the judge itself is working (§7).

**You picked `delivery: email` (or any indirect surface) and every result
looks suspiciously uniform.** Check `findings` payload/response previews —
if the response shows the target reacting to *nothing* rather than to your
seed's content, the delivery channel isn't round-tripping correctly. (This
was a real bug in `email.py` that's now fixed and covered by a regression
test in `scripts/verify_phases.py` — if you're on an older copy of this
project, update it.)

**You're not sure where your results actually went.** They're always at
`~/.promptfuzzr/db/promptfuzzr.db` (§3.4) — there's no per-run or
per-config separation. `findings` and `scripts/inspect_db.py` (no
argument) both read from there by default.

---

## 10. What's NOT here yet (Phase 5/6)

- **`minimize`** — reducing a successful payload to its minimal reproducer
  (ddmin-style). Currently raises `NotImplementedError`.
- **`report`** — coverage-matrix heatmap, defense-delta comparisons, HTML/
  JSON export. Currently raises `NotImplementedError`. `findings` is the
  only way to review results today.
- **Mutation isn't wired into `fuzz`** — `mutate` is preview-only; a real
  run always sends each seed's raw `base_text`, unmutated.
- **`axes` and `concurrency` in `RunConfig`** are accepted and stored but
  not yet acted on — runs are single-threaded and don't currently vary
  axes automatically.
- **`repo_comment`, `calendar`, `tool_output`** are defined as `Delivery`
  enum values with no channel implementation — setting `delivery` to any
  of these falls back to `direct` silently inside `run_corpus`.

If you hit one of these and need it now, that's the next thing to build,
not a bug to report.
