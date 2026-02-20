import logging

from banal import ensure_list
from followthemoney import model
from ftmq.store.fragments import get_fragments
from ftmq.store.fragments.utils import safe_fragment
from followthemoney.proxy import EntityProxy
from ftmq.store.fragments.loader import BulkLoader
from followthemoney.namespace import Namespace
from openaleph_procrastinate import defer
from openaleph_procrastinate.app import make_app
from openaleph_procrastinate.model import DatasetJob
from openaleph_procrastinate.tasks import task
from openaleph_procrastinate.settings import OpenAlephSettings

from ftm_translate.exceptions import ProcessingException
from ftm_translate.logic.base import translate_entity
from ftm_translate.settings import Settings
from ftm_translate.util import filter_text

settings = Settings()
openaleph_settings = OpenAlephSettings()

log = logging.getLogger(__name__)
app = make_app(__loader__.name)
sqlalchemy_pool = {
    "pool_size": openaleph_settings.db_pool_size,
    "max_overflow": openaleph_settings.db_pool_size,
}

ORIGIN = "ftm-translate"
# FTMQ BulkLoader default size = 1000
QUERY_LIMIT = 1000
ORIGIN = "translate"


def emit_entity_fragment(parent: EntityProxy, texts: list[str], child: EntityProxy, ns: Namespace, bulk: BulkLoader) -> EntityProxy:
    texts = [t for t in ensure_list(texts) if filter_text(t)]
    if len(texts):
        entity_fragment = model.make_entity(parent.schema)
        entity_fragment.id = parent.id
        entity_fragment.add("indexText", texts)
        ns.apply(entity_fragment)
        bulk.put(entity_fragment, fragment=safe_fragment(child.id))
        return entity_fragment

@task(app=app, retry=defer.tasks.translate.max_retries)
def translate(job: DatasetJob) -> None:
    to_defer: list[EntityProxy] = []
    with job.get_writer(origin=ORIGIN) as bulk:
        for entity in job.load_entities():
            # abort early if source language isn't set
            source_lang = (entity.first("detectedLanguage") or settings.source_language)
            if source_lang is None:
                    raise ProcessingException("No source language detected.")

            if entity.schema.is_a("Pages"):
                current_page = 1
                accumulate_done = False
                while not accumulate_done:
                    # create Page entities with origin = translate
                    schema = model.get("Page")
                    dataset = job.payload["context"]["ftmstore"]
                    ns = Namespace(job.context["namespace"])
                    # create Page entities
                    translated_entities: list[EntityProxy] = [model.make_entity(schema, key_prefix=dataset) for idx in range(current_page, current_page+QUERY_LIMIT)]
                    #  create Page entity IDs
                    for idx, page_entity in zip(range(current_page, current_page+QUERY_LIMIT), translated_entities):
                        page_entity.make_id(entity.id, idx)
                    # apply namespace to Page entity IDs
                    translated_entities: list[EntityProxy] = [ns.apply(page_entity) for page_entity in translated_entities]
                    # get at most QUERY_LIMIT Page entities with origin = "ingest" from the store
                    # these will be the source of the bodyText for translations
                    store = get_fragments(dataset, "ingest", database_uri=openaleph_settings.fragments_uri, **sqlalchemy_pool)
                    page_entity_ids: list[str] = [page_entity.id for page_entity in translated_entities]
                    ingest_page_raw: list[dict] = list(store.fragments(page_entity_ids))
                    ingest_page_entities = []

                    for entity_dict in ingest_page_raw:
                        try:
                            ingest_page_entities.append(EntityProxy.from_dict(entity_dict))
                        except Exception as e:
                            log.error(f"Failed to retrieve Page entity: {entity_dict["id"]}")
                            continue
                    
                    # there are no Page entities with origin = ingest
                    if not len(ingest_page_entities):
                        log.error(f"Transcription failed. No ingest fragments found")

                    translated_texts = []
                    for source_entity, translated_entity in zip(ingest_page_entities, translated_entities):
                        try:
                            translated_entity = translate_entity(source_entity, translated_entity, entity.id, source_lang)
                            if translated_entity is not None:
                                bulk.put(translated_entity)
                                translated_texts.append(translated_entity.first("translatedText"))
                                # emit a Pages fragment with the translatedText copied into indexText
                                # to allow full text search across the translated text
                                fragment = emit_entity_fragment(entity, translated_texts, translated_entity, ns, bulk)
                                # queue both the Page entity and the Pages fragment for indexing
                                to_defer.append(translated_entity)
                                to_defer.append(fragment)
                        except ProcessingException as e:
                            log.error(f"Transcription failed: {e}")
                        
                    if len(ingest_page_entities) <= QUERY_LIMIT:
                        accumulate_done = True
                    else:
                        current_page += QUERY_LIMIT
                else:
                    try:
                        # the source_entity and translated_entity are the same in the case of
                        # Documents that aren't Pages entities
                        translated_entity = translate_entity(entity, entity, entity.id, source_lang)
                        if translated_entity is not None:
                            bulk.put(translated_entity)
                            to_defer.append(translated_entity)
                    except ProcessingException as e:
                        log.error(f"Transcription failed: {e}")
            # write any left-over entities to the store
            bulk.flush()
    if to_defer:
        defer.index(app, job.dataset, to_defer, **job.context)
