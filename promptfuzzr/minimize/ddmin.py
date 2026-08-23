"""ddmin-style (delta-debugging) reduction of a successful TestCase
payload. Given a payload that triggered a SUCCESS verdict, binary-
search-remove chunks (sentence/word/char granularity, coarse-to-fine)
and re-verify against the SAME target/delivery/judge configuration
after each cut, keeping only cuts that preserve the SUCCESS verdict.

This is a real differentiator per roadmap.md section 0 — a minimal
reproducer is what a real triager actually wants; nothing else in the
prompt-injection fuzzing space does this.

Scope boundary (deliberate, not an oversight): only single_shot
propagation is supported. Minimizing a multi_step or cross_session
finding is a well-defined but substantially different problem — what
does "minimal" even mean for a multi-turn kill chain, when the
follow-up pushes are fixed template text, not part of the seed? Rather
than build something that quietly does the wrong thing,
minimize_test_case() raises a clear NotImplementedError for those
cases.
"""

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
    """Split payload into reducible chunks. The invariant
    "".join(chunk_payload(payload, g)) == payload holds for every
    granularity — ddmin only ever removes chunks, never reorders or
    edits them, so this invariant is what guarantees a reduced chunk
    list reconstructs to a valid substring/subsequence of the original
    text via plain concatenation, with no separate "how do I rejoin
    this" logic needed anywhere else.
    """
    if granularity not in ("sentence", "word", "char"):
        raise ValueError(f"unknown granularity '{granularity}' — use sentence, word, or char")

    if payload == "":
        return []

    if granularity == "char":
        return list(payload)

    if granularity == "word":
        # Alternating whitespace-run / non-whitespace-run chunks. This
        # (rather than "one word plus its trailing space") is what
        # makes the join invariant hold with no special-casing for
        # leading/trailing/repeated whitespace.
        return re.findall(r"\s+|\S+", payload)

    # sentence: each chunk is one sentence including its terminal
    # punctuation and any trailing whitespace; a final clause with no
    # terminal punctuation is captured by the second alternative.
    chunks = re.findall(r"[^.!?]*[.!?]+\s*|[^.!?]+$", payload)
    return chunks if chunks else [payload]


def ddmin(chunks: list[str], verify_fn: Callable[[list[str]], bool]) -> list[str]:
    """Classic delta-debugging minimization (Zeller & Hildebrandt,
    1999), operating on a list of chunks instead of program input
    bytes. verify_fn(candidate_chunks) -> True if the candidate (the
    concatenation of candidate_chunks) still reproduces the finding.

    Repeatedly partitions the current chunk list into n roughly-equal
    subsets and tries removing each one in turn; if any removal still
    reproduces, keep the reduction and back off toward n=2 (coarsest
    granularity, to find more big wins first); if none do, double the
    partition count (finer-grained removal attempts) up to n ==
    len(chunks), at which point every individual chunk has been tried
    and the result is 1-minimal.
    """
    if len(chunks) < 2:
        return chunks

    n = 2
    while True:
        subset_size = max(1, len(chunks) // n)
        subsets = [chunks[i : i + subset_size] for i in range(0, len(chunks), subset_size)]

        # Build each candidate complement by INDEX range, not by content
        # membership — a content-based "keep chunks not in this subset"
        # approach breaks silently on duplicate chunks (e.g. the same
        # repeated word appearing in two different subsets), since it
        # can't tell which occurrence to drop.
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
    """Full pipeline: sanity-check the finding still reproduces, then
    reduce sentence -> word -> char (coarse-to-fine cascade, each pass
    starting from the previous pass's output), re-verifying against the
    SAME delivery surface / target / judge configuration the original
    finding used. Sets test_case.minimized_payload as a side effect and
    returns the minimal payload string.

    action_judge/heuristic_judge should be constructed the SAME way the
    original run constructed them (same AuthorityPolicy) — the CLI's
    minimize command enforces this by requiring --config to point at
    the config that produced the finding. Passing a different policy
    would minimize against a different notion of "success" than the one
    that actually found this case, which would silently produce a
    reproducer for the wrong thing.

    verify_retries: how many times a single candidate is re-checked
    before concluding it does NOT reproduce. This exists because model
    responses are non-deterministic (roadmap.md section 5) — a single
    flaky non-reproduction during minimization would make ddmin treat a
    removable chunk as required, producing an unnecessarily large
    "minimal" result. Kept small by default since ddmin already calls
    verify_fn many times; each retry multiplies that cost further.
    """
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
        """Same verdict-precedence rule as orchestrator/engine.py's
        run_corpus: action_outcome wins whenever there are tool calls to
        evaluate; heuristic is the fallback. Kept in sync manually since
        this is the one piece of engine.py's judging logic not already
        extracted into a shared function — duplicating a 4-line rule is
        lower risk than adding another cross-module dependency for it.
        """
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

    # Sanity check: the ORIGINAL payload must itself still reproduce
    # before we trust anything ddmin concludes from removing pieces of
    # it. A payload that no longer reproduces at all (target/model
    # changed, or the original success was a one-off flake) should be a
    # clearly reported failure, not silently "minimized" to something
    # meaningless.
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
