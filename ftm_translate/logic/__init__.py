from ftm_translate.logic.apertium import translate_apertium
from ftm_translate.logic.argos import translate_argos
from ftm_translate.logic.base import (
    translate,
    translate_entities,
    translate_entity,
)

__all__ = [
    "translate",
    "translate_apertium",
    "translate_argos",
    "translate_entities",
    "translate_entity",
]
