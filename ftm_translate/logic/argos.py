import argostranslate.translate

from ftm_translate.exceptions import ProcessingException
from ftm_translate.logic.base import TranslationResult


def translate_argos(
    text: str, language: str, source_language: str | None = None
) -> TranslationResult | None:
    installed_languages = argostranslate.translate.get_installed_languages()

    target_langs = [l for l in installed_languages if l.code == language]
    if not target_langs:
        raise ProcessingException(
            f"Argos target language `{language}` is not installed"
        )
    target_lang = target_langs[0]

    if source_language:
        source_langs = [l for l in installed_languages if l.code == source_language]
        if not source_langs:
            raise ProcessingException(
                f"Argos source language `{source_language}` is not installed"
            )
        translation = source_langs[0].get_translation(target_lang)
        if translation is None:
            raise ProcessingException(
                f"No Argos translation from `{source_language}` to `{language}`"
            )
        result = translation.translate(text)
        return result, language

    # No source language specified: try all installed languages
    for lang in installed_languages:
        if lang.code == language:
            continue
        translation = lang.get_translation(target_lang)
        if translation is not None:
            result = translation.translate(text)
            if result and result != text:
                return result, language

    raise ProcessingException(
        f"No Argos translation pair found for target `{language}`"
    )
