"""Unit tests for judge/. action_outcome tests should assert against a
fixed AuthorityPolicy + a fabricated tool_calls trace, no live target
needed.

TODO(phase 4): test ActionOutcomeJudge against authorized vs.
unauthorized ToolCallRecord traces.
TODO(phase 1): test HeuristicJudge pattern matching.
"""

import pytest


@pytest.mark.skip(reason="TODO(phase 4): implement once action_outcome.py lands")
def test_action_outcome_judge_flags_unauthorized_tool_call():
    ...
