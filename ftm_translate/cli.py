from typing import Optional

import typer
from anystore.cli import ErrorHandler
from anystore.io import smart_read, smart_write
from anystore.logging import configure_logging
from ftmq.io import smart_read_proxies, smart_write_proxies
from rich.console import Console
from typing_extensions import Annotated

from ftm_translate import __version__, logic
from ftm_translate.settings import Engine, Settings

settings = Settings()
cli = typer.Typer(no_args_is_help=True)
console = Console(stderr=True)


class Opts:
    IN = typer.Option("-", "-i", help="Input uri (file, http, s3...)")
    OUT = typer.Option("-", "-o", help="Output uri (file, http, s3...)")
    SOURCE_LANGUAGE = typer.Option(
        settings.source_language, "-s", help="Source language code"
    )
    TARGET_LANGUAGE = typer.Option(
        settings.target_language, "-t", help="Target language code"
    )
    ENGINE = typer.Option(
        settings.engine, "-e", help="Translation engine (argos, apertium)"
    )


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
    output_uri: str = Opts.OUT,
    source_language: Optional[str] = Opts.SOURCE_LANGUAGE,
    target_language: str = Opts.TARGET_LANGUAGE,
    engine: Engine = Opts.ENGINE,
):
    """Translate a text string and print the result."""
    with ErrorHandler():
        if source_language is None:
            raise typer.BadParameter("Source language (-s) is required")
        text = smart_read(input_uri, mode="r")
        res = logic.translate(text, source_language, target_language, engine)
        if res is not None:
            smart_write(output_uri, res)


@cli.command("entities")
def translate_entities(
    input_uri: str = Opts.IN,
    output_uri: str = Opts.OUT,
    source_language: Optional[str] = Opts.SOURCE_LANGUAGE,
    target_language: str = Opts.TARGET_LANGUAGE,
    engine: Engine = Opts.ENGINE,
):
    """Translate FTM entities from an input stream.

    Reads FollowTheMoney entities, translates their `bodyText` property,
    and writes the updated entities to the output.

    Example:
        ftm-translate entities -i entities.ftm.json -o translated.ftm.json -s de
    """
    with ErrorHandler():
        if source_language is None:
            raise typer.BadParameter("Source language (-s) is required")
        proxies = smart_read_proxies(input_uri)
        translated = logic.translate_entities(
            proxies, source_language, target_lang=target_language, engine=engine
        )
        smart_write_proxies(output_uri, translated)
