from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class Delivery(str, Enum):
    DIRECT = "direct"
    WEBPAGE = "webpage"
    EMAIL = "email"
    FILE = "file"
    REPO_COMMENT = "repo_comment"
    CALENDAR = "calendar"
    TOOL_OUTPUT = "tool_output"
    TOOL_SCHEMA = "tool_schema"
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
    SCHEMA_POISONING = "schema_poisoning"


class Verdict(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAIL = "fail"
    ERROR = "error"


class VerdictBasis(str, Enum):
    ACTION_OUTCOME = "action_outcome"
    HEURISTIC = "heuristic"
    LLM_JUDGE = "llm_judge"


@dataclass
class ToolCallRecord:
    tool_name: str
    arguments: dict
    authorized: bool
    order: int
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class PayloadSeed:
    id: str
    technique: Technique
    base_text: str
    tags: list[str] = field(default_factory=list)


@dataclass
class TestCase:
    __test__ = False

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

    kill_chain_depth: int = 0

    minimized_payload: str | None = None
    notes: str = ""
