import logging

from openaleph_procrastinate.app import make_app
from openaleph_procrastinate.model import DatasetJob
from openaleph_procrastinate.tasks import task
from openaleph_procrastinate import defer

from ftm_translate.settings import Settings
from ftm_translate.exceptions import ProcessingException
from ftm_translate.logic import translate as _translate

settings = Settings()

log = logging.getLogger(__name__)
app = make_app(__loader__.name)

ORIGIN = "ftm-translate"
TEXT = "bodyText"


@task(app=app, retry=defer.tasks.translate.max_retries)
def translate(job: DatasetJob) -> None:
    with job.get_writer() as bulk:
        for entity in job.get_entities():
            for text in entity.get("bodyText"):
                try:
                    res = _translate(text)
                    if res is not None:
                        translated, language = res

                        entity.add("translatedText", translated)
                        entity.add("translatedLanguage", language)

                        bulk.put(entity)

                        defer.analyze(app, job.dataset, [entity], **job.context)
                except ProcessingException as e:
                    log.error(f"Transcription failed: {e}")
                finally:
                    # cleanup
                    pass
