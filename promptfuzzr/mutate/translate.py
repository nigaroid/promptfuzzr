from __future__ import annotations


class TranslateMutator:
    name = "translate"

    LANGUAGES: list[str] = ["de", "es", "zh-CN", "tr", "az"]

    def __init__(self) -> None:
        self.last_languages_used: list[str] = []

    def mutate(self, seed_text: str, count: int = 10) -> list[str]:
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
                continue
            if not translated:
                continue
            variants.append(translated)
            languages_used.append(lang)

        self.last_languages_used = languages_used
        return variants[:count]
