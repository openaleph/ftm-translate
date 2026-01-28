import uuid
import json
import logging
import subprocess
from pathlib import Path

from openaleph_procrastinate.app import make_app
from openaleph_procrastinate.model import DatasetJob
from openaleph_procrastinate.tasks import task
from openaleph_procrastinate import defer
from followthemoney.proxy import EntityProxy

from ftm_translate.settings import Settings
from ftm_translate.exceptions import ProcessingException

settings = Settings()

log = logging.getLogger(__name__)
app = make_app(__loader__.name)

ORIGIN = "ftm-translate"


@task(app=app, retry=defer.tasks.translate.max_retries)
def translate(job: DatasetJob) -> None:
    for entity_file_reference in job.get_file_references():
        entity: EntityProxy = entity_file_reference.entity
        audio_only_path = None

        with entity_file_reference.get_localpath() as local_path:
            try:
                audio_only_path = get_audio_only_path(local_path)
                full_transcription = get_transcription_text(
                    audio_only_path, entity_file_reference.entity
                )

                entity.add("bodyText", full_transcription)

                with job.get_writer() as bulk:
                    bulk.put(entity)

                defer.analyze(app, job.dataset, [entity], **job.context)
            except ProcessingException as e:
                log.error(f"Transcription failed: {e}")
            finally:
                if audio_only_path:
                    _delete_temporary_file(audio_only_path)


def get_audio_only_path(file_path: Path) -> Path:
    Path(settings.data_root).mkdir(parents=True, exist_ok=True)

    tmp_filename = uuid.uuid4().hex
    audio_only_path = Path(settings.data_root) / tmp_filename
    audio_only_path = audio_only_path.with_suffix(".wav")

    # https://github.com/ggml-org/whisper.cpp?tab=readme-ov-file#quick-start
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        file_path,
        "-ar",
        "16000",
        "-ac",
        "1",
        "-c:a",
        "pcm_s16le",
        audio_only_path,
    ]

    try:
        subprocess.run(
            cmd,
            timeout=int(settings.whisper_timeout),
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.STDOUT,
        )
    except subprocess.CalledProcessError as e:
        raise ProcessingException(e)

    if not audio_only_path.is_file():
        raise ProcessingException("Audio extraction failed.")

    return audio_only_path


def get_transcription_text(file_path: Path, entity: EntityProxy) -> str:
    model = settings.whisper_model
    models_path = Path(settings.whisper_model_root)

    output_path = Path(settings.data_root) / file_path.parts[-1].split(".")[0]

    cmd = [
        settings.whisper_executable,
        "-m",
        models_path / model,
        "-f",
        file_path,
        "-oj",
        "-of",
        output_path,
        "-l",
        # "auto" sometimes translates audio in an unintended language
        settings.whisper_language,
    ]

    try:
        log.info(cmd)
        subprocess.run(
            cmd,
            timeout=int(settings.whisper_timeout),
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.STDOUT,
        )
    except subprocess.CalledProcessError as e:
        raise e

    output_path = output_path.with_suffix(".json")
    if not output_path.is_file():
        raise ProcessingException(
            f"Transcription failed. This file type might be unsupported: {file_path.parts[-1]}."
        )

    with open(output_path, "r") as f:
        transcription_dict = json.loads(f.read())

    transcription_intervals = transcription_dict.get("transcription")
    if transcription_intervals:
        full_transcription = ""
        for interval in transcription_intervals:
            full_transcription += f"[{interval['timestamps']['from']} -> {interval['timestamps']['to']}] {interval['text'].strip()}"
        return full_transcription
    else:
        _delete_temporary_file(output_path)
        raise ProcessingException(
            f"Transcription failed, no output in file {output_path}."
        )

    _delete_temporary_file(output_path)


def _delete_temporary_file(file_path: Path):
    if not file_path.is_file():
        return

    Path.unlink(file_path)
