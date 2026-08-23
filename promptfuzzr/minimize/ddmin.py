from __future__ import annotations

import re

from typing import Callable
from promptfuzzr.judge.action_outcome import ActionOutcomeJudge
from promptfuzzr.judge.heuristic import HeuristicJudge
from promptfuzzr.models import Propagation, TestCase, ToolCallRecord, Verdict, VerdictBasis
from promptfuzzr.orchestrator.engine import (
    compose_trigger_prompt,
    deliver_payload,
    get_channel,
)


def chunk_payload(payload: str, granularity: str = "sentence") -> list[str]:
    if granularity not in ("sentence", "word", "char"):
        raise ValueError(f"unknown granularity '{granularity}' — use sentence, word, or char")

    if payload == "":
        return []

    if granularity == "char":
        return list(payload)

    if granularity == "word":
        return re.findall(r"\s+|\S+", payload)

    chunks = re.findall(r"[^.!?]*[.!?]+\s*|[^.!?]+$", payload)
    return chunks if chunks else [payload]


def ddmin(chunks: list[str], verify_fn: Callable[[list[str]], bool]) -> list[str]:
    if len(chunks) < 2:
        return chunks

    n = 2
    while True:
        subset_size = max(1, len(chunks) // n)
        subsets = [chunks[i : i + subset_size] for i in range(0, len(chunks), subset_size)]

        reduced = False
        offset = 0
        for subset in subsets:
            start, end = offset, offset + len(subset)
            complement = chunks[:start] + chunks[end:]
            if len(complement) < len(chunks) and verify_fn(complement):
                chunks = complement
                n = max(n - 1, 2)
                reduced = True
                break
            offset = end

        if not reduced:
            if n >= len(chunks):
                break
            n = min(n * 2, len(chunks))

    return chunks


def minimize_test_case(
    test_case: TestCase,
    target,
    action_judge: ActionOutcomeJudge | None = None,
    heuristic_judge: HeuristicJudge | None = None,
    verify_retries: int = 2,
) -> str:
    if test_case.verdict != Verdict.SUCCESS:
        raise ValueError(
            f"cannot minimize test case {test_case.id}: verdict is "
            f"'{test_case.verdict.value}', not 'success' — only a successful "
            f"finding has anything meaningful to reduce."
        )
    if test_case.propagation != Propagation.SINGLE_SHOT:
        raise NotImplementedError(
            f"cannot minimize test case {test_case.id}: propagation is "
            f"'{test_case.propagation.value}'. Only single_shot is supported — "
            f"see the scope-boundary note at the top of this module for why "
            f"multi_step/cross_session minimization isn't a well-defined drop-in "
            f"extension of this algorithm."
        )

    heuristic_judge = heuristic_judge or HeuristicJudge()
    delivery_channel = get_channel(test_case.delivery)
    stats = {"verify_calls": 0}

    def judge_snapshot(response_text: str, tool_calls: list[ToolCallRecord]) -> Verdict:
        snapshot = TestCase(
            id=test_case.id,
            technique=test_case.technique,
            delivery=test_case.delivery,
            propagation=test_case.propagation,
            encoding=test_case.encoding,
            payload="",
            response_text=response_text,
            tool_calls=tool_calls,
        )
        if action_judge is not None and tool_calls:
            verdict, _ = action_judge.evaluate(snapshot)
            return verdict
        verdict, _ = heuristic_judge.evaluate(snapshot)
        return verdict

    def verify_once(candidate_text: str) -> bool:
        stats["verify_calls"] += 1
        if candidate_text == "":
            return False  # an empty payload can never be a valid reproducer

        session_id = f"minimize-{test_case.id}-{stats['verify_calls']}"
        reference = deliver_payload(candidate_text, test_case.delivery, target, delivery_channel)
        try:
            if test_case.delivery.value in ("direct", "tool_schema"):
                prompt = compose_trigger_prompt(test_case.delivery, candidate_text, "")
            else:
                content = delivery_channel.read_content(reference)
                prompt = compose_trigger_prompt(test_case.delivery, candidate_text, content)

            target.reset_session(session_id)
            response_text, tool_calls = target.send(prompt, session_id=session_id)
            return judge_snapshot(response_text, tool_calls) == Verdict.SUCCESS
        finally:
            try:
                delivery_channel.cleanup(reference)
            except Exception:
                pass

    def verify_fn(candidate_chunks: list[str]) -> bool:
        candidate_text = "".join(candidate_chunks)
        for _ in range(max(1, verify_retries)):
            if verify_once(candidate_text):
                return True
        return False

    if not verify_fn(chunk_payload(test_case.payload, "char")):
        raise RuntimeError(
            f"test case {test_case.id} did not reproduce during minimization "
            f"(tried {verify_retries} time(s)) — the original payload may no "
            f"longer trigger a SUCCESS verdict against this target/config. "
            f"Nothing was minimized."
        )

    current_text = test_case.payload
    for granularity in ("sentence", "word", "char"):
        chunks = chunk_payload(current_text, granularity)
        if len(chunks) < 2:
            continue
        reduced_chunks = ddmin(chunks, verify_fn)
        current_text = "".join(reduced_chunks)

    test_case.minimized_payload = current_text
    return current_text
