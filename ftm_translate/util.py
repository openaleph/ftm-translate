from followthemoney import E, EntityProxy
from ftmq.util import make_entity
from normality import stringify


def get_lang_prop(entity: EntityProxy) -> str:
    """Get ftm property for translated language based on schema"""
    if entity.schema.name == "Page":
        return "translatedTextLanguage"
    return "translatedLanguage"


def dehydrate_entity(entity: E) -> E:
    """Make translation fragment"""
    lang_prop = get_lang_prop(entity)
    data = {
        "id": entity.id,
        "schema": entity.schema.name,
        "caption": entity.caption,
        "properties": {
            "translatedText": entity.get("translatedText"),
            lang_prop: entity.get(lang_prop),
        },
    }
    return make_entity(data, entity.__class__)


def filter_text(text):
    """Remove text strings not worth indexing for full-text search."""
    text = stringify(text)
    if text is None:
        return False
    if not len(text.strip()):
        return False
    try:
        # try to exclude numeric data from spreadsheets
        float(text)
        return False
    except Exception:
        pass
    # TODO: should we check there's any alphabetic characters in the
    # text to avoid snippets entirely comprised of non-text chars?
    return True
