from ftm_translate.logic.base import TranslationResult


def translate_apertium(
    text: str, language: str, source_language: str | None = None
) -> TranslationResult | None: ...
