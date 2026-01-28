from typing import TypeAlias
from ftm_translate.exceptions import ProcessingException
from ftm_translate.settings import Engine, Settings

settings = Settings()

TranslationResult: TypeAlias = tuple[str, str]  # text, lang


def translate(
    text: str,
    language: str | None = settings.target_language,
    source_language: str | None = None,
    engine: Engine | None = settings.engine,
) -> TranslationResult | None:
    language = language or settings.target_language
    engine = engine or settings.engine

    if engine == "argos":
        return _translate_argos(text, language, source_language)
    if engine == "apertium":
        return _translate_apertium(text, language, source_language)
    raise ProcessingException(f"Unsupported engine: `{engine}`")


def _translate_apertium(
    text: str, language: str, source_language: str | None = None
) -> TranslationResult | None: ...


def _translate_argos(
    text: str, language: str, source_language: str | None = None
) -> TranslationResult | None: ...
