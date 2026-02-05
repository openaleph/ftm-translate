import logging

from followthemoney.proxy import EntityProxy
from openaleph_procrastinate import defer
from openaleph_procrastinate.app import make_app
from openaleph_procrastinate.model import DatasetJob
from openaleph_procrastinate.tasks import task

from ftm_translate.exceptions import ProcessingException
from ftm_translate.logic.base import translate_entity
from ftm_translate.settings import Settings

settings = Settings()

log = logging.getLogger(__name__)
app = make_app(__loader__.name)

ORIGIN = "ftm-translate"
TEXT = "bodyText"


@task(app=app, retry=defer.tasks.translate.max_retries)
def translate(job: DatasetJob) -> None:
    to_defer: list[EntityProxy] = []
    with job.get_writer() as bulk:
        for entity in job.get_entities():
            try:
                source_lang = (
                    entity.first("detectedLanguage") or settings.source_language
                )
                if source_lang is None:
                    raise ProcessingException("No source language detected.")
                translated_entity = translate_entity(entity, source_lang)
                if translated_entity is not None:
                    bulk.put(translate_entity)
                    to_defer.append(translated_entity)
            except ProcessingException as e:
                log.error(f"Transcription failed: {e}")
    if to_defer:
        defer.index(app, job.dataset, to_defer, **job.context)
