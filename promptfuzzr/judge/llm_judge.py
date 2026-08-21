"""Secondary judge: uses an LLM to evaluate "did the attack succeed?"
given (payload, response). Slower and costs tokens; run after the
heuristic pre-filter as a confirmation/disambiguation step.

TODO(phase 5): implement evaluate() with a fixed judge prompt template;
cache judgments per (payload_hash, response_hash) to avoid re-spending
on retries.
"""

from __future__ import annotations

from promptfuzzr.models import TestCase, Verdict


class LlmJudge:
    basis = "llm_judge"

    def __init__(self, judge_model_id: str):
        self.judge_model_id = judge_model_id

    def evaluate(self, test_case: TestCase) -> tuple[Verdict, float]:
        raise NotImplementedError("TODO(phase 5): call judge model with a fixed prompt template")
