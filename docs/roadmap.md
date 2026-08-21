# promptfuzzr — Roadmap

Automated mutation-based prompt injection fuzzing framework for LLM applications
and LLM agents. CLI tool, Python.

---

## 0. Positioning — why this and not Garak/FuzzyAI/HouYi/PyRIT/promptfoo

The field is crowded. Most existing tools cluster into a few buckets:

```
Text-in / text-out scanners   : Garak, FuzzyAI, HouYi, LLMFuzzer
                                 → success = "did the response contain a bad string"
Orchestration/scoring infra    : PyRIT, Mindgard
                                 → model-agnostic red-team plumbing, not app-specific
Regression / defense products : promptfoo, Giskard, LLM Guard, Rebuff
                                 → correctness harnesses or defensive filters, not offense-first
DAST-style web integration     : brainstorm
```

Almost none of them treat **agentic tool-calling as the actual attack surface**,
and none treat the **tool schema/description field** as fuzzable input. That's
`promptfuzzr`'s wedge. Three differentiators, chosen deliberately over a longer
list so the pitch stays coherent instead of "worse Garak with more features":

**1. Action-outcome judging, not string-match judging.**
Every other scanner in the list above asks "did the output contain X." `promptfuzzr`'s
judge asks "did a specific tool get invoked with specific arguments it shouldn't
have been invoked with." This maps directly to real-world impact — it's the
CSRF-for-agents framing (attacker can't act directly, so they trick a
higher-privileged agent into acting on their behalf) rather than a text-leak
framing. Success criteria live at the tool-call layer, not the token layer.

**2. Tool-definition/schema fuzzing as a first-class surface.**
Tool descriptions get fed into the model's context on *every turn*, whether or
not the tool is ever called — a poisoned description is a standing injection
that doesn't need to wait for retrieval. Nobody in the current tool market
fuzzes this surface deliberately. `promptfuzzr` mutates and delivers payloads
through the schema channel with the same rigor other tools apply to prompts.

**3. Payload minimization (delta-debugging for injections).**
Once a mutation succeeds, automatically reduce it to the smallest payload that
still triggers the vulnerability — the `ddmin`/`afl-tmin` idea, applied to
prompt injection. A minimal reproducer is what a real triager actually wants;
nothing in the current landscape does this for prompt injection specifically.

Everything else in this roadmap (coverage-matrix reporting, defense-delta
testing, cross-session blast radius) is worth keeping as secondary,
lower-priority features — useful, but not the headline. The headline is:

> **A fuzzer that measures whether injections cause unauthorized agent
> actions, targets the tool-definition surface nobody else fuzzes, and
> returns a minimal reproducer instead of a wall of logs.**

---

## 1. Framing the attack space (the "roots")

Every test case is a point in a 3-axis space — the fuzzer's job is to explore
that space systematically instead of accumulating anecdotes.

```
Delivery (WHERE it enters)     Propagation (HOW it spreads)    Encoding (HOW it's represented)
───────────────────────────    ─────────────────────────────   ────────────────────────────────
direct (user field)            single-shot                     plain imperative text
webpage / URL                  multi-step kill-chain            fake delimiters / fake markup
email                          cross-session (poisoned store)   fake user-turn injection
file                                                            invisible unicode (zero-width, tag-block)
code repo / comment                                             base64 / rot13 / hex / leetspeak
calendar invite                                                 non-english / multilingual
tool output                                                     payload splitting (multi-field)
tool schema / description  ★                                    multimodal / steganographic (OOS)
memory / RAG corpus
```

★ = the surface `promptfuzzr` treats as first-class, where others treat it as
an afterthought or skip it entirely.

**Root attack techniques** (orthogonal to the axes — any technique can be
delivered via any surface, in any encoding):

1. Instruction override — "ignore previous instructions"
2. Role manipulation — "you are now unrestricted / a developer / an admin"
3. Rule injection & authority assertion — fake exception rule + claimed compliance
4. Context switching — reframe the system prompt as data to transform
5. Story/poem extraction — coax the secret out via creative framing
6. Summary & repetition — ask the model to repeat its own context
7. Syntactic extraction — reference the secret structurally, name unknown
8. Indirect inference / char-by-char exfiltration — bisection when direct output is blocked
9. Fake conversation injection — forged `---USER RESPONSE---` block
10. Jailbreak personas — DAN, roleplay/fictional framing, opposite/sudo mode
11. Token/masked-word smuggling — reconstruct via string ops, no single token trips a filter
12. Business logic manipulation — fake promos, fake internal memos, fake override phrases
13. Chained web-attack delivery — path traversal / SQLi / command injection via the LLM as vector
14. Insecure output handling — unsanitized HTML/JS/Markdown for a downstream sink
15. **Schema/tool-definition poisoning** — payload lives in a tool's description, fires every turn ★

---

## 2. Architecture (backbone)

The core loop is built around the three differentiators, not a generic
mutate-send-judge cycle:

```
                         ┌────────────────────┐
                         │  CLI (Typer)         │
                         │  promptfuzzr run ...  │
                         └─────────┬───────────┘
                                   │
                 ┌─────────────────┼──────────────────┐
                 ▼                 ▼                   ▼
        ┌────────────────┐ ┌──────────────┐   ┌────────────────┐
        │ Payload Corpus  │ │ Mutation      │   │ Target Adapter │
        │ (seed templates,│ │ Engine        │   │ Layer          │
        │ incl. SCHEMA    │ │ (incl. schema │   │ (agent harness,│
        │ seeds) ★        │ │ mutators) ★   │   │ tool registry)  │
        └────────┬────────┘ └──────┬────────┘   └───────┬────────┘
                 │                  │                     │
                 └──────────┬───────┘                     │
                             ▼                             │
                    ┌─────────────────┐                    │
                    │ Test Case        │                   │
                    │ Generator        │                   │
                    │ (delivery ×      │                   │
                    │ propagation ×    │                   │
                    │ encoding)        │                   │
                    └────────┬─────────┘                   │
                             ▼                              ▼
                    ┌──────────────────────────────────────────┐
                    │        Execution Orchestrator              │
                    │  - retry policy (5-10x, non-determinism)   │
                    │  - rate limiting / concurrency              │
                    │  - session state (multi-turn, kill-chain)  │
                    │  - captures FULL tool-call trace, not just │
                    │    final text response ★                   │
                    └────────────────────┬───────────────────────┘
                                          ▼
                    ┌──────────────────────────────────────────┐
                    │   Action-Outcome Judge Engine  ★            │
                    │  - was tool T called with args A?           │
                    │  - was T authorized for this context?       │
                    │  - heuristic string-match (secondary signal)│
                    │  - LLM-as-judge (secondary signal)          │
                    └────────────────────┬───────────────────────┘
                                          ▼
                    ┌──────────────────────────────────────────┐
                    │   Minimizer  ★                              │
                    │  - ddmin-style reduction of successful       │
                    │    payloads to a minimal reproducer          │
                    └────────────────────┬───────────────────────┘
                                          ▼
                    ┌──────────────────────────────────────────┐
                    │        Scoring + Report Store (SQLite)     │
                    └────────────────────┬───────────────────────┘
                                          ▼
                    ┌──────────────────────────────────────────┐
                    │   Reporting                                  │
                    │  - coverage matrix (delivery×prop×encoding) │
                    │  - defense-delta (mitigation on/off)         │
                    │  - minimal reproducers per finding           │
                    │  - CLI table / HTML / JSON export             │
                    └──────────────────────────────────────────┘
```

★ = differentiator components, not present (or not emphasized) in the
existing tool market.

### Module breakdown

- **`corpus/`** — seed payload templates by technique (the 15 roots above),
  YAML/JSON, `{category, technique, base_text, tags}`. Includes a dedicated
  `schema_seeds.yaml` for tool-description payloads.
- **`mutate/`** — one mutator per encoding axis: `synonym.py`, `restructure.py`,
  `encode.py` (b64/rot13/hex/leet/unicode), `translate.py`, `split.py`,
  `fake_delimiter.py`, `fake_user_turn.py`, and **`schema_mutate.py`** — mutates
  tool `description`/`parameters` fields specifically (different constraints
  than free-text prompts: has to stay plausible as a tool doc while carrying
  the payload).
- **`delivery/`** — simulates each surface: `direct.py`, `webpage.py`, `email.py`,
  `file.py`, `repo_comment.py`, `rag_doc.py`, and **`tool_schema.py`** — injects
  into a target's tool registry/marketplace fixture.
- **`targets/`** — `TargetAdapter` interface, but built around an **agent
  harness** (tool-calling loop) as the primary target type, not a plain
  chat completion endpoint. Text-only targets are supported but treated as
  the degraded case, not the default.
- **`orchestrator/`** — runs test cases, handles retries, multi-turn sessions,
  kill-chains, and critically **logs the full tool-call trace** (tool name,
  args, order, whether a confirmation step was skipped) for every test case,
  not just the final text.
- **`judge/`** — primary: **action-outcome judge**, comparing the observed
  tool-call trace against an allow-list/policy for that session's authority
  level (ties directly to your excessive-agency / lethal-trifecta notes).
  Secondary: heuristic string-match + LLM-judge, kept as a fallback signal
  for text-only targets and for straightforward leakage cases.
- **`minimize/`** — takes a successful `TestCase`, applies ddmin-style
  reduction (binary-search removal of payload chunks, verifying the exploit
  still triggers after each cut) until no further reduction preserves success.
- **`report/`** — coverage-matrix heatmap (fraction of delivery×propagation×
  encoding×technique space exercised), defense-delta table (mitigation
  on/off), success rate by technique/delivery/encoding, and minimal
  reproducer per finding.
- **`cli.py`** — Typer app: `promptfuzzr corpus list`, `promptfuzzr mutate --seed X --axis encoding`,
  `promptfuzzr run --target X --corpus Y --axes delivery,encoding`,
  `promptfuzzr minimize --finding-id Z`, `promptfuzzr report --run-id Z`.

### Core data model (per test case)

```python
@dataclass
class ToolCallRecord:
    tool_name: str
    arguments: dict
    authorized: bool          # per the target's declared policy for this session
    order: int

@dataclass
class TestCase:
    id: str
    technique: str             # e.g. "schema_poisoning"
    delivery: str               # e.g. "tool_schema"
    propagation: str            # single-shot | multi-step | cross-session
    encoding: str                # plain | base64 | fake_delimiter | ...
    payload: str
    mutation_chain: list[str]
    target_id: str
    response_text: str | None
    tool_calls: list[ToolCallRecord]   # ★ full trace, not just text
    verdict: Literal["success","fail","partial","error"]
    verdict_basis: Literal["action_outcome","heuristic","llm_judge"]  # ★
    confidence: float
    retry_count: int
    minimized_payload: str | None      # ★ set once minimizer runs
    notes: str
```

---

## 3. Build sequence (roadmap phases)

**Phase 0 — Scaffolding (0.5 day)**
- CLI skeleton (Typer), config loading, SQLite schema, adapter interface stub.
- Design the tool-call trace format up front — this is load-bearing for the
  action-outcome judge, don't bolt it on later.

**Phase 1 — Corpus + single-axis fuzzing (Day 1)**
- Load cheatsheet payloads into `corpus/*.yaml` by technique.
- Build a controlled lab agent: a chatbot with at least one tool that has
  real (if simulated) consequence — e.g. `delete_ticket`, `send_email`,
  `apply_discount` — not just a text-only guarded-secret bot. This is what
  makes action-outcome judging meaningful from day one.
- Direct delivery, plain encoding. One full loop: corpus → send → capture
  tool-call trace → action-outcome judge → SQLite → CLI report.

**Phase 2 — Mutation engine (Day 2)**
- Text mutators: base64/rot13/hex/leetspeak → unicode tricks → fake
  delimiters → fake user-turn → payload splitting → non-English translation.
- **Schema mutator**: variants of a poisoned tool description that stay
  plausible as documentation while carrying the payload (this needs its own
  mutation grammar — a schema payload that reads like "ignore instructions"
  in plain text is far less effective than one that reads like a legitimate
  tool-usage note with an embedded imperative).

**Phase 3 — Delivery surfaces incl. schema (Day 2-3)**
- Webpage, RAG doc poisoning, CSV/field poisoning.
- **Tool-schema delivery**: inject into a tool registry/marketplace fixture,
  confirm the payload fires on every turn regardless of whether the tool is
  invoked — this is the headline "nobody else tests this" result.
- Lethal-trifecta gating: only build exfiltration cases against targets
  confirmed to have ingestion + sensitive data + egress.

**Phase 4 — Action-outcome judge + propagation (Day 3-4)**
- Build the judge against the tool-call trace, not text: define an
  authorization policy per session/role, flag any call outside it.
- Multi-turn context hijacking, kill-chain depth measurement (how many
  chained calls before something breaks the chain — this becomes a severity
  metric once you're already tracing tool calls).
- Cross-session/memory poisoning if a persistent store exists; otherwise
  scope out explicitly.

**Phase 5 — Minimizer (Day 4-5)**
- ddmin-style reduction on successful test cases: chunk the payload
  (sentence/token/char level depending on encoding), binary-search removal,
  re-verify success after each cut, stop when no further reduction holds.
- This is a genuinely new capability for this space — budget real time for it,
  it's part of the headline pitch, not a stretch goal.

**Phase 6 — Reporting + experiments (Day 5-6)**
- Coverage-matrix heatmap, defense-delta table (mitigation toggled on/off,
  report the bypass-rate delta), success rate by technique/delivery/encoding.
- Run comparisons: manual vs. automated corpus, model-vs-model resistance,
  schema-delivery vs. prompt-delivery effectiveness.
- Defense-bypass study against your own mitigation (fake-closing-tag attack
  on delimiter tags) — likely highest-value single result, lead the report
  with it if it lands.

**Phase 7 — Polish (Day 7)**
- README positioning against Garak/FuzzyAI/HouYi/PyRIT/promptfoo explicitly
  (the differentiation section above, condensed).
- Sample findings with minimized reproducers, retry/backoff tuning, packaging.

---

## 4. Tech stack

```
Core        : Python 3.11+, Typer (CLI), Pydantic (data models), SQLite
Mutation    : nltk/wordnet or a local LLM for synonym mutation, deep-translator
              for language mutation, custom encoders for b64/rot13/unicode,
              custom grammar for schema-mutation
Targets     : openai/anthropic SDKs, ollama for local models, requests;
              agent harness with a small tool registry (own fixtures)
Delivery    : http.server for webpage lab, swaks for email lab (own domains only)
Judge       : tool-call trace comparator (primary) + regex/keyword heuristic
              + LLM judge (secondary signals)
Minimizer   : custom ddmin implementation, chunked at sentence/token/char level
Reporting   : rich (CLI tables), Jinja2 (HTML report), optional Streamlit
```

---

## 5. Notes carried over from your cheatsheet (don't lose these in implementation)

- **Non-determinism**: retry failed payloads 5-10x before marking `fail`; log
  retry count per case, don't silently average it away.
- **Isolation of injections**: one payload per document/field — conflicting
  instructions in the same document reduce reliability and muddy results.
- **Plain-English exfil phrasing** tends to outperform structured tool-call
  syntax when testing egress — worth its own encoding sub-axis.
- **Domain evasion**: don't hardcode common OOB-collaborator domains
  (oastify.com, burpcollaborator.net, interact.sh) into your own exfil test
  payloads — use a domain you control.
- **General hardening list** doubles as your Phase 6 "defenses to test
  against": prompt-engineering-only, keyword filter, least privilege,
  separate scanner identity, human-in-the-loop, fine-tuning, adversarial
  training, input/output guard LLMs, treat-APIs-as-public, don't-feed-
  sensitive-data. Each is a target configuration to toggle and re-run the
  full corpus against for the defense-delta table.
