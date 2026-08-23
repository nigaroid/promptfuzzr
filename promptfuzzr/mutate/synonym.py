from __future__ import annotations

import re
from itertools import product


SYNONYMS: dict[str, list[str]] = {
    "ignore": ["disregard", "forget", "override", "discard", "bypass"],
    "reveal": ["disclose", "expose", "divulge", "share", "output"],
    "unrestricted": ["unrestrained", "unfiltered", "unlimited", "unconstrained"],
    "admin": ["administrator", "superuser", "root user", "system operator"],
    "always": ["invariably", "without exception", "every single time"],
    "before": ["prior to", "ahead of", "preceding"],
    "must": ["should", "need to", "are required to", "have to"],
    "previous": ["prior", "preceding", "earlier", "above"],
    "instructions": ["directives", "guidelines", "rules", "commands"],
    "system prompt": ["system message", "initial instructions", "configuration prompt"],
    "delete": ["remove", "erase", "wipe", "purge"],
    "override": ["bypass", "supersede", "circumvent", "disable"],
}

_TRIGGER_ORDER = sorted(SYNONYMS.keys(), key=len, reverse=True)


def _match_case(replacement: str, original: str) -> str:
    if original.isupper():
        return replacement.upper()
    if original[:1].isupper():
        return replacement[:1].upper() + replacement[1:]
    return replacement


class SynonymMutator:
    name = "synonym"

    def mutate(self, seed_text: str, count: int = 10) -> list[str]:
        if not seed_text:
            return []

        occupied: list[tuple[int, int]] = []
        hits: list[tuple[str, re.Match]] = []
        for trigger in _TRIGGER_ORDER:
            pattern = re.compile(rf"\b{re.escape(trigger)}\b", re.IGNORECASE)
            for m in pattern.finditer(seed_text):
                if any(not (m.end() <= s or m.start() >= e) for s, e in occupied):
                    continue  # overlaps an already-claimed span
                occupied.append((m.start(), m.end()))
                hits.append((trigger, m))

        if not hits:
            return []

        hits.sort(key=lambda h: h[1].start())

        variants: list[str] = []
        seen: set[str] = set()

        def add(candidate: str) -> None:
            if candidate != seed_text and candidate not in seen:
                seen.add(candidate)
                variants.append(candidate)

        for trigger, m in hits:
            for synonym in SYNONYMS[trigger]:
                replacement = _match_case(synonym, m.group(0))
                candidate = seed_text[: m.start()] + replacement + seed_text[m.end() :]
                add(candidate)
                if len(variants) >= count:
                    return variants

        if len(hits) > 1 and len(variants) < count:
            choice_lists = [SYNONYMS[trigger] for trigger, _ in hits]
            for combo in product(*choice_lists):
                pieces: list[str] = []
                cursor = 0
                for (trigger, m), synonym in zip(hits, combo):
                    pieces.append(seed_text[cursor : m.start()])
                    pieces.append(_match_case(synonym, m.group(0)))
                    cursor = m.end()
                pieces.append(seed_text[cursor:])
                add("".join(pieces))
                if len(variants) >= count:
                    break

        return variants[:count]
