"""Unit tests for minimize/ddmin.py. Use a fake verify_fn (no live
target) that succeeds only when specific known-required chunks are
present, to confirm ddmin converges to the expected minimal set.

TODO(phase 5): implement once ddmin() lands.
"""

import pytest


@pytest.mark.skip(reason="TODO(phase 5): implement once ddmin.py lands")
def test_ddmin_converges_to_minimal_chunk_set():
    ...
