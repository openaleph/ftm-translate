from followthemoney import E
from ftmq.util import make_entity


def dehydrate_entity(entity: E) -> E:
    """Make translation fragment"""
    data = {
        "id": entity.id,
        "schema": entity.schema.name,
        "caption": entity.caption,
        "properties": {
            "translatedText": entity.get("translatedText"),
            "translatedLanguage": entity.get("translatedLanguage"),
        },
    }
    return make_entity(data, entity.__class__)
