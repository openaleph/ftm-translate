import pytest
from followthemoney import model as ftm_model
from followthemoney.proxy import EntityProxy

from ftm_translate.logic.base import translate, translate_entity

SOURCE_TEXT = "Hallo, ich heiße Jane Doe und wohne in Berlin"
EXPECTED_TRANSLATION = "Hello, my name is Jane Doe and live in Berlin"


@pytest.fixture
def plaintext_entity():
    entity = EntityProxy(
        ftm_model.get("PlainText"), {"id": "test-doc-1", "schema": "PlainText"}
    )
    entity.add("bodyText", SOURCE_TEXT)
    return entity


def test_translate_text():
    result = translate(SOURCE_TEXT, source_lang="de", target_lang="en", engine="argos")
    assert result is not None
    assert result == EXPECTED_TRANSLATION


def test_translate_entity(plaintext_entity):
    entity = translate_entity(
        plaintext_entity, source_lang="de", target_lang="en", engine="argos"
    )
    translated_texts = entity.get("translatedText")
    assert len(translated_texts) == 1
    assert translated_texts[0] == EXPECTED_TRANSLATION
