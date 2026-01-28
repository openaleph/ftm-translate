from typing import Optional

import typer
from anystore.cli import ErrorHandler
from anystore.logging import configure_logging
from anystore.io import smart_read
from ftmq.io import smart_read_proxies, smart_write_proxies
from rich.console import Console
from typing_extensions import Annotated

from ftm_translate import __version__
from ftm_translate import logic
from ftm_translate.settings import Settings

settings = Settings()
cli = typer.Typer(no_args_is_help=True)
console = Console(stderr=True)


class Opts:
    IN = typer.Option("-", "-i", help="Input uri (file, http, s3...)")
    OUT = typer.Option("-", "-o", help="Output uri (file, http, s3...)")
    LANGUAGE = typer.Option(settings.target_language, "-l", help="Target language code")
    SOURCE_LANGUAGE = typer.Option(None, "-s", help="Source language code")


@cli.callback(invoke_without_command=True)
def cli_main(
    version: Annotated[Optional[bool], typer.Option(..., help="Show version")] = False,
    show_settings: Annotated[
        Optional[bool], typer.Option("--settings", help="Show current settings")
    ] = False,
):
    if version:
        print(__version__)
        raise typer.Exit()
    if show_settings:
        console.print(Settings())

    configure_logging()


@cli.command("text")
def translate_text(
    input_uri: str = Opts.IN,
    language: str = Opts.LANGUAGE,
    source_language: Optional[str] = Opts.SOURCE_LANGUAGE,
):
    """Translate a text string and print the result."""
    with ErrorHandler():
        text = smart_read(input_uri, mode="r")
        res = logic.translate(text, language=language, source_language=source_language)
        if res is not None:
            translated, lang = res
            console.print(translated)
        else:
            raise typer.Exit(1)


@cli.command("entities")
def translate_entities(
    input_uri: str = Opts.IN,
    output_uri: str = Opts.OUT,
    language: str = Opts.LANGUAGE,
    source_language: Optional[str] = Opts.SOURCE_LANGUAGE,
):
    """Translate FTM entities from an input stream.

    Reads FollowTheMoney entities, translates their `bodyText` property,
    and writes the updated entities to the output.

    Example:
        ftm-translate translate-entities -i entities.ftm.json -o translated.ftm.json
    """
    with ErrorHandler():
        proxies = smart_read_proxies(input_uri)
        translated = logic.translate_entities(
            proxies, language=language, source_language=source_language
        )
        smart_write_proxies(output_uri, translated)
