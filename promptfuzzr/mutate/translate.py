"""Non-English / multilingual mutator (Phase 2).

Wraps deep-translator to produce variants in a rotating set of target
languages. Translation is network-dependent (calls an external
translation service), which breaks the "pure, no network calls"
contract other mutators follow — that's inherent to this axis, not an
oversight, so failures are handled gracefully rather than propagated:
if a language's translation call fails (offline sandbox, rate limit,
unsupported pair), that language is skipped and the run continues with
whichever languages succeeded, rather than aborting the whole mutator.

`self.last_languages_used` records the language code for each element
of the most recent `mutate()` return value, in the same order, so a
caller (e.g. the orchestrator building mutation_chain) can log which
language actually produced each variant for later per-language
success-rate reporting, without changing the list[str] return contract
that the Mutator protocol expects.
"""

from __future__ import annotations


class TranslateMutator:
    name = "translate"

    LANGUAGES: list[str] = ["de", "es", "zh-CN", "tr", "az"]

    def __init__(self) -> None:
        self.last_languages_used: list[str] = []

    def mutate(self, seed_text: str, count: int = 10) -> list[str]:
        """Return up to `count` translated variants, one per language
        in LANGUAGES (in order), skipping any language whose
        translation call fails. Import of deep_translator is deferred
        into this method so the package (and its network dependency)
        is only required when this specific mutator is actually used.
        """
        if not seed_text or not seed_text.strip():
            self.last_languages_used = []
            return []

        try:
            from deep_translator import GoogleTranslator
        except ImportError as exc:
            raise RuntimeError(
                "TranslateMutator requires the 'deep-translator' package "
                "(pip install deep-translator)"
            ) from exc

        variants: list[str] = []
        languages_used: list[str] = []

        for lang in self.LANGUAGES:
            if len(variants) >= count:
                break
            try:
                translated = GoogleTranslator(source="en", target=lang).translate(seed_text)
            except Exception:
                # Network unavailable, rate-limited, or unsupported
                # pair — skip this language rather than fail the whole
                # mutation run. Non-determinism here is expected and
                # handled the same way the orchestrator handles target
                # non-determinism (roadmap.md section 5): retry policy
                # lives at the orchestrator layer, not here.
                continue
            if not translated:
                continue
            variants.append(translated)
            languages_used.append(lang)

        self.last_languages_used = languages_used
        return variants[:count]
