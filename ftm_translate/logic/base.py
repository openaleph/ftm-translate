from typing import TypeAlias, Generator, Iterable

from anystore.logging import get_logger
from followthemoney import E

from ftm_translate.exceptions import ProcessingException
from ftm_translate.settings import Engine, Settings
from ftm_translate.util import dehydrate_entity

log = get_logger(__name__)

settings = Settings()

TranslationResult: TypeAlias = tuple[str, str]  # text, lang


def translate(
    text: str,
    language: str | None = settings.target_language,
    source_language: str | None = None,
    engine: Engine | None = settings.engine,
) -> TranslationResult | None:
    from ftm_translate.logic.apertium import translate_apertium
    from ftm_translate.logic.argos import translate_argos

    language = language or settings.target_language
    engine = engine or settings.engine

    if engine == "argos":
        return translate_argos(text, language, source_language)
    if engine == "apertium":
        return translate_apertium(text, language, source_language)
    raise ProcessingException(f"Unsupported engine: `{engine}`")


def translate_entity(
    entity: E,
    language: str | None = settings.target_language,
    source_language: str | None = None,
    engine: Engine | None = settings.engine,
    dehydrate: bool | None = False,
) -> E | None:
    _translated = False
    for text in entity.get("bodyText"):
        res = translate(text, language=language, source_language=source_language, engine=engine)
        if res is not None:
            translated, lang = res
            entity.add("translatedText", translated)
            entity.add("translatedLanguage", lang)
            _translated = True
    if _translated:
        if dehydrate:
            entity = dehydrate_entity(entity)
        return entity
    return None


def translate_entities(
    entities: Iterable[E],
    language: str | None = settings.target_language,
    source_language: str | None = None,
    engine: Engine | None = settings.engine,
    dehydrate: bool | None = False,
) -> Generator[E, None, None]:
    for entity in entities:
        try:
            result = translate_entity(
                entity,
                language=language,
                source_language=source_language,
                engine=engine,
                dehydrate=dehydrate,
            )
            if result is not None:
                yield result
        except ProcessingException as e:
            log.error(f"Translation failed for `{entity.id}`: {e}")
