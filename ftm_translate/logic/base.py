from typing import Generator, Iterable

from anystore.logging import get_logger
from followthemoney import E, EntityProxy
from ftmq.types import Entities

from ftm_translate.exceptions import ProcessingException
from ftm_translate.settings import Engine, Settings

log = get_logger(__name__)

settings = Settings()


def extract_text(e: EntityProxy) -> Generator[str, None, None]:
    if e.schema.is_a("Pages"):
        # we stored in indexText
        yield from e.get("indexText")
    else:
        yield from e.get("bodyText")


def translate(
    text: str,
    source_lang: str,
    target_lang: str = settings.target_language,
    engine: Engine = settings.engine,
) -> str | None:

    engine = engine or settings.engine

    if engine == "argos":
        from ftm_translate.logic.argos import translate_argos

        return translate_argos(text, source_lang, target_lang)
    if engine == "apertium":
        from ftm_translate.logic.apertium import translate_apertium

        return translate_apertium(text, source_lang, target_lang)
    raise ProcessingException(f"Unsupported engine: `{engine}`")


def translate_entity(
    entity: E,
    source_lang: str,
    target_lang: str = settings.target_language,
    engine: Engine = settings.engine,
) -> E:
    _translated = False
    _should_translate = False
    for text in extract_text(entity):
        _should_translate = True
        res = translate(text, source_lang, target_lang, engine)
        if res is not None:
            entity.add("translatedText", res)
            entity.add("translatedLanguage", target_lang)
            _translated = True
    if not _translated and _should_translate:
        log.warn(
            "Couldn't translate entity!",
            entity=entity.id,
            source_lang=source_lang,
            target_lang=target_lang,
        )
    return entity


def translate_entities(
    entities: Iterable[E],
    source_lang: str,
    target_lang: str = settings.target_language,
    engine: Engine = settings.engine,
) -> Entities:
    for entity in entities:
        try:
            yield translate_entity(entity, source_lang, target_lang, engine)
        except ProcessingException as e:
            log.error(f"Translation failed for `{entity.id}`: {e}")
