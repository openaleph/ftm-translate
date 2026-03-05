from followthemoney.namespace import Namespace
from followthemoney.proxy import EntityProxy
from followthemoney.util import make_entity_id
from ftmq.store.fragments import get_fragments
from openaleph_procrastinate import defer
from openaleph_procrastinate.app import make_app
from openaleph_procrastinate.model import DatasetJob
from openaleph_procrastinate.settings import OpenAlephSettings
from openaleph_procrastinate.tasks import task

from ftm_translate.exceptions import ProcessingException
from ftm_translate.logic.base import translate_entity
from ftm_translate.settings import Settings
from ftm_translate.util import dehydrate_entity

settings = Settings()
openaleph_settings = OpenAlephSettings()

app = make_app(__loader__.name)
sqlalchemy_pool = {
    "pool_size": openaleph_settings.db_pool_size,
    "max_overflow": openaleph_settings.db_pool_size,
}

ORIGIN = "ftm-translate"
# FTMQ BulkLoader default size = 1000
QUERY_LIMIT = 1000
ORIGIN = "translate"


@task(
    app=app,
    retry=defer.tasks.translate.max_retries,
    tracer_uri=openaleph_settings.redis_url,
)
def translate(job: DatasetJob) -> None:
    to_defer: list[EntityProxy] = []
    ftm_dataset = job.payload["context"]["ftmstore"]
    ns = Namespace(job.context["namespace"])
    store = get_fragments(
        ftm_dataset,
        origin="ingest",
        database_uri=openaleph_settings.fragments_uri,
        **sqlalchemy_pool,
    )
    fragment_name = f"translation_{settings.target_language}"
    with job.get_writer(origin=ORIGIN) as bulk:
        for entity in job.load_entities():
            # abort early if source language isn't set
            source_lang = entity.first("detectedLanguage") or settings.source_language
            if source_lang is None:
                raise ProcessingException("No source language detected.")

            if entity.schema.is_a("Pages"):
                # We want to translate the Page entities (children). To look
                # them up in the ftm store, we assume their IDs in batches
                # instead of doing a json lookup for parent property which is
                # way too expensive.
                current_page = 1
                parent = EntityProxy.from_dict({"id": entity.id, "schema": "Pages"})
                while True:
                    # generate Page entities IDs:
                    page_batch = range(current_page, current_page + QUERY_LIMIT)
                    page_ids = (
                        make_entity_id(entity.id, p, key_prefix=ftm_dataset)
                        for p in page_batch
                    )
                    # apply correct namespace
                    page_ids = list(map(ns.sign, page_ids))
                    # get at most QUERY_LIMIT Page entities with
                    # origin = "ingest" from the store
                    pages_found = False
                    ix = 1
                    for ix, fragment in enumerate(  # noqa: B007
                        store.fragments(page_ids, "default"), 1
                    ):
                        pages_found = True
                        page = EntityProxy.from_dict(fragment)
                        try:
                            translated = translate_entity(page, source_lang)
                            if translated.has("translatedText"):
                                # add translated Page to store
                                bulk.put(dehydrate_entity(translated), fragment_name)
                                # store translated text in parent for full-text search
                                parent.add(
                                    "indexText", translated.get("translatedText")
                                )
                                # defer page entity to index stage
                                to_defer.append(page)
                        except Exception as e:
                            job.log.error(f"Translation failed: {e}", entity_id=page.id)

                    if pages_found:
                        # signal the indexer that this is translated text:
                        index_text = "\n".join(parent.get("indexText"))
                        parent.set("indexText", f"__translation__ {index_text}")
                        # write parent fragment to store
                        bulk.put(parent, fragment=fragment_name)
                        # defer parent entity to index stage
                        to_defer.append(entity)
                    else:
                        # there are no Page entities with origin = ingest
                        job.log.error(
                            "Translation failed. No ingest Page fragments found",
                            entity_id=entity.id,
                        )

                    # stop if no more Page entities
                    if ix <= QUERY_LIMIT:
                        break

            else:
                try:
                    # all other Documents, easy
                    translated = translate_entity(entity, source_lang)
                    if translated is not None:
                        bulk.put(dehydrate_entity(translated), fragment_name)
                        to_defer.append(translated)
                except ProcessingException as e:
                    job.log.error(f"Translation failed: {e}", entity_id=entity.id)

    if to_defer:
        defer.index(app, job.dataset, to_defer, **job.context)
