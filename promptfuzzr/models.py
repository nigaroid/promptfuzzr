"""Core data models shared across the corpus, mutation, orchestration,
judge, and reporting layers.

These are the load-bearing types referenced throughout roadmap.md — get
the shape of ToolCallRecord / TestCase right early (Phase 0) since the
action-outcome judge and minimizer both depend on it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class Delivery(str, Enum):
    DIRECT = "direct"
    WEBPAGE = "webpage"
    EMAIL = "email"
    FILE = "file"
    REPO_COMMENT = "repo_comment"
    CALENDAR = "calendar"
    TOOL_OUTPUT = "tool_output"
    TOOL_SCHEMA = "tool_schema"  # first-class differentiator surface
    RAG_CORPUS = "rag_corpus"


class Propagation(str, Enum):
    SINGLE_SHOT = "single_shot"
    MULTI_STEP = "multi_step"
    CROSS_SESSION = "cross_session"


class Encoding(str, Enum):
    PLAIN = "plain"
    FAKE_DELIMITER = "fake_delimiter"
    FAKE_USER_TURN = "fake_user_turn"
    INVISIBLE_UNICODE = "invisible_unicode"
    BASE64 = "base64"
    ROT13 = "rot13"
    HEX = "hex"
    LEETSPEAK = "leetspeak"
    NON_ENGLISH = "non_english"
    SPLIT = "split"


class Technique(str, Enum):
    INSTRUCTION_OVERRIDE = "instruction_override"
    ROLE_MANIPULATION = "role_manipulation"
    RULE_INJECTION_AUTHORITY = "rule_injection_authority"
    CONTEXT_SWITCHING = "context_switching"
    STORY_POEM_EXTRACTION = "story_poem_extraction"
    SUMMARY_REPETITION = "summary_repetition"
    SYNTACTIC_EXTRACTION = "syntactic_extraction"
    INDIRECT_INFERENCE = "indirect_inference"
    FAKE_CONVERSATION = "fake_conversation"
    JAILBREAK_PERSONA = "jailbreak_persona"
    TOKEN_SMUGGLING = "token_smuggling"
    BUSINESS_LOGIC_MANIPULATION = "business_logic_manipulation"
    CHAINED_WEB_ATTACK = "chained_web_attack"
    INSECURE_OUTPUT_HANDLING = "insecure_output_handling"
    SCHEMA_POISONING = "schema_poisoning"  # first-class differentiator technique


class Verdict(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAIL = "fail"
    ERROR = "error"


class VerdictBasis(str, Enum):
    ACTION_OUTCOME = "action_outcome"  # primary — see judge/action_outcome.py
    HEURISTIC = "heuristic"
    LLM_JUDGE = "llm_judge"


@dataclass
class ToolCallRecord:
    """One observed tool invocation during a target run.

    `authorized` is a placeholder at record time (default False) — it
    is NOT set by the target adapter or orchestrator. The single source
    of truth for authorization is judge/action_outcome.py, which
    compares `tool_name` against the session's AuthorityPolicy at judge
    time and returns a verdict. The judge is read-only: it does not
    mutate this field. Treat this value as meaningless until a verdict
    has been computed; don't rely on it directly elsewhere.
    """

    tool_name: str
    arguments: dict
    authorized: bool
    order: int
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class PayloadSeed:
    """A single entry loaded from corpus/seeds/*.yaml."""

    id: str
    technique: Technique
    base_text: str
    tags: list[str] = field(default_factory=list)


@dataclass
class TestCase:
    """One point in the delivery x propagation x encoding x technique
    space, plus its execution result. See roadmap.md section 2 for the
    full rationale.
    """

    id: str
    technique: Technique
    delivery: Delivery
    propagation: Propagation
    encoding: Encoding
    payload: str
    mutation_chain: list[str] = field(default_factory=list)

    target_id: str = ""
    response_text: str | None = None
    tool_calls: list[ToolCallRecord] = field(default_factory=list)

    verdict: Verdict = Verdict.ERROR
    verdict_basis: VerdictBasis = VerdictBasis.HEURISTIC
    confidence: float = 0.0
    retry_count: int = 0

    # Phase 4 severity metric (roadmap section 3): how many chained tool
    # calls the agent executed before the chain broke. For single-shot
    # cases this is just len(tool_calls); for multi-step propagation it's
    # the cumulative count across all turns of the session.
    kill_chain_depth: int = 0

    minimized_payload: str | None = None
    notes: str = ""
