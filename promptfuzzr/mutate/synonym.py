"""Synonym-replacement mutator (Phase 2).

Swaps trigger words/phrases in a seed for synonyms drawn from a small
static table (e.g. "ignore" -> "disregard" / "forget" / "override").
Deliberately NOT wired to nltk/wordnet or a network-backed LLM call:
the trigger vocabulary in this space is small and adversarially
specific ("ignore", "unrestricted", "admin"...), and a static table
keeps this mutator pure, offline, and deterministic per roadmap.md's
Phase 1 note ("keep mutators pure — no network calls").

Substitution is whole-word, case-preserving (matches the case pattern
of the original token: Title / UPPER / lower), and can hit multiple
trigger words in the same seed — each variant swaps one *occurrence
position* to a specific synonym, cycling through combinations until
`count` variants are produced or the space is exhausted.
"""

from __future__ import annotations

import re
from itertools import product


# One entry per trigger word. Keep synonym lists roughly interchangeable
# in register (all imperative, all plausible) so a substitution doesn't
# make the payload read as obviously mangled.
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

# Longer phrases first so we don't shadow-match a substring of them
# (e.g. "system prompt" before a lone "prompt" rule, if one existed).
_TRIGGER_ORDER = sorted(SYNONYMS.keys(), key=len, reverse=True)


def _match_case(replacement: str, original: str) -> str:
    """Best-effort: mirror the original token's case pattern onto the replacement."""
    if original.isupper():
        return replacement.upper()
    if original[:1].isupper():
        return replacement[:1].upper() + replacement[1:]
    return replacement


class SynonymMutator:
    name = "synonym"

    def mutate(self, seed_text: str, count: int = 10) -> list[str]:
        """Return up to `count` variants, each with one trigger-word
        occurrence swapped for a synonym. If multiple distinct trigger
        words are present, later variants combine swaps across all of
        them (one synonym choice per word) before repeating.
        """
        if not seed_text:
            return []

        # Find every (trigger, span) occurrence in the seed, longest
        # trigger phrases first so multi-word triggers aren't clobbered
        # by a shorter single-word rule matching inside them.
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

        # Build the single-swap variant list first (one trigger word
        # changed per variant, other occurrences left as-is) — this
        # covers the common "does this one lexical choice matter" case.
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

        # If there's room left and more than one distinct trigger word,
        # add combined-swap variants (every occurrence replaced at once)
        # by walking synonym choices for each trigger in lockstep.
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
