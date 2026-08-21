"""Encoding mutators: base64, rot13, hex, leetspeak, invisible unicode.

TODO(phase 2): implement each as a small pure function, then a
composite EncodeMutator that can target either the whole payload or
just the sensitive substring, per roadmap.md section 5 notes on
output-guardrail bypass technique (character-insertion obfuscation).
"""

from __future__ import annotations
import base64
import codecs


def to_base64(text: str) -> str:
    return base64.b64encode(text.encode()).decode()


def to_rot13(text: str) -> str:
    return codecs.encode(text, "rot_13")


def to_hex(text: str) -> str:
    return text.encode().hex()


_LEET_TABLE = str.maketrans(
    {
        "a": "4", "A": "4",
        "e": "3", "E": "3",
        "i": "1", "I": "1",
        "o": "0", "O": "0",
        "s": "5", "S": "5",
        "t": "7", "T": "7",
        "l": "1", "L": "1",
        "g": "9", "G": "9",
    }
)


def to_leetspeak(text: str) -> str:
    """Simple character-substitution leetspeak (a->4, e->3, i->1, o->0,
    s->5, t->7, l->1, g->9). Deliberately not "full" leetspeak (no
    multi-char digraphs like |-|) — this axis is about slipping past a
    naive keyword filter while staying human-readable, not maximal
    obfuscation.
    """
    return text.translate(_LEET_TABLE)


def insert_invisible_unicode(text: str, marker: str = "\u200b") -> str:
    """Insert a zero-width character between every character.
    See roadmap.md Study 7 — measure whether this still works on the
    target *and* whether a naive strip-on-ingest defense neutralizes it.
    """
    if not text:
        return text
    return marker.join(list(text))


# A few other zero-width / invisible code points worth rotating through,
# beyond the default ZERO WIDTH SPACE — different defenses strip
# different subsets of these, so varying the marker is itself a useful
# encoding sub-axis.
_INVISIBLE_MARKERS = [
    "\u200b",  # zero width space
    "\u200c",  # zero width non-joiner
    "\u200d",  # zero width joiner
    "\ufeff",  # zero width no-break space (BOM)
]


class EncodeMutator:
    name = "encode"

    def mutate(self, seed_text: str, count: int = 10) -> list[str]:
        """Compose the encoders above into variants. Order is fixed
        (base64, rot13, hex, leetspeak, then one invisible-unicode
        variant per marker) so callers/tests can rely on positions;
        stops once `count` variants have been produced.
        """
        if not seed_text:
            return []

        candidates: list[str] = [
            to_base64(seed_text),
            to_rot13(seed_text),
            to_hex(seed_text),
            to_leetspeak(seed_text),
        ]
        for marker in _INVISIBLE_MARKERS:
            candidates.append(insert_invisible_unicode(seed_text, marker=marker))

        # de-dupe while preserving order (e.g. leetspeak may equal the
        # original for payloads with no substitutable characters)
        seen: set[str] = set()
        variants: list[str] = []
        for candidate in candidates:
            if candidate not in seen:
                seen.add(candidate)
                variants.append(candidate)
            if len(variants) >= count:
                break
        return variants[:count]
