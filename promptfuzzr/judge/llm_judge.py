from __future__ import annotations

from promptfuzzr.models import TestCase, Verdict


class LlmJudge:
    basis = "llm_judge"

    def __init__(self, judge_model_id: str):
        self.judge_model_id = judge_model_id

    def evaluate(self, test_case: TestCase) -> tuple[Verdict, float]:
        raise NotImplementedError("TODO(phase 5): call judge model with a fixed prompt template")
