"""Payload-splitting mutator (Phase 2).

Splits a seed payload into N fragments intended for N separate
delivery fields (e.g. first_name / last_name / company), such that no
single fragment trips a naive per-field keyword filter but the target
recombines them at read time (e.g. rendering all form fields into one
prompt/document). Output shape differs from other mutators — returns
list[dict[field_name, fragment]] rather than list[str]; this mirrors
that divergence explicitly via a distinct method name (`split`) in
addition to satisfying the shared `mutate` name for registry lookup.
"""

from __future__ import annotations


# Default field-name sets to distribute fragments across. Different
# sets model different real-world multi-field surfaces (a signup form
# vs. a support ticket vs. a CSV upload) — pick whichever list has
# enough slots for the requested fragment count.
_FIELD_NAME_SETS: list[list[str]] = [
    ["first_name", "last_name", "company", "notes"],
    ["ticket_subject", "ticket_body", "ticket_tags"],
    ["address_line_1", "address_line_2", "city", "postal_code", "country"],
]


def _split_into_chunks(text: str, n: int) -> list[str]:
    """Split text into n roughly-even word-boundary chunks (n >= 1)."""
    words = text.split()
    if n <= 1 or len(words) <= 1:
        return [text]
    n = min(n, len(words))
    chunk_size = -(-len(words) // n)  # ceil division
    chunks = [
        " ".join(words[i : i + chunk_size]) for i in range(0, len(words), chunk_size)
    ]
    return chunks


def _fields_for(n: int) -> list[str]:
    for field_set in _FIELD_NAME_SETS:
        if len(field_set) >= n:
            return field_set[:n]
    # fall back to generic numbered fields if nothing fits
    return [f"field_{i + 1}" for i in range(n)]


class SplitMutator:
    name = "split"

    def mutate(self, seed_text: str, count: int = 10) -> list[dict[str, str]]:
        """Return up to `count` fragmentations of seed_text, each a
        dict mapping a field name to its fragment. Fragment counts
        range from 2 up to (count + 1), each using a plausible
        field-name set of matching size, so a single call surfaces
        several different granularities of split to test against.
        """
        if not seed_text or not seed_text.strip():
            return []

        words = seed_text.split()
        max_fragments = min(len(words), max(2, count + 1))

        variants: list[dict[str, str]] = []
        seen: set[tuple[str, ...]] = set()
        for n in range(2, max_fragments + 1):
            chunks = _split_into_chunks(seed_text, n)
            if len(chunks) < 2:
                continue
            key = tuple(chunks)
            if key in seen:
                continue
            seen.add(key)
            field_names = _fields_for(len(chunks))
            variants.append(dict(zip(field_names, chunks)))
            if len(variants) >= count:
                break
        return variants[:count]
