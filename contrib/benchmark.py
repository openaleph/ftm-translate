#!/usr/bin/env python
# flake8: noqa: B008
"""
Benchmark script comparing Argos and Apertium translation engines.

Usage:
    python contrib/benchmark.py
    python contrib/benchmark.py -s de -t en -n 5
    python contrib/benchmark.py -e argos -m sentences

Fetches random Wikipedia articles for realistic text samples.
Use -m sentences to split into sentences (requires nltk).

Requires engines to be installed:
    pip install ftm-translate[argos]
    # and/or apertium system installation

For sentence mode:
    pip install nltk
"""

import json
import statistics
import time
import urllib.parse
import urllib.request
from enum import StrEnum
from typing import Optional

import typer
from rich.console import Console

# Wikipedia API endpoints per language
WIKIPEDIA_API = "https://{lang}.wikipedia.org/w/api.php"
USER_AGENT = "ftm-translate-benchmark/1.0 (https://github.com/openaleph/ftm-translate)"

cli = typer.Typer(no_args_is_help=True)
console = Console(stderr=True)


class Mode(StrEnum):
    full = "full"
    sentences = "sentences"


def wiki_request(url: str) -> dict:
    """Make a Wikipedia API request with proper User-Agent."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_random_articles(lang: str, count: int = 10) -> list[dict]:
    """Fetch random Wikipedia articles with their text content."""
    api_url = WIKIPEDIA_API.format(lang=lang)

    # Get random article titles
    params = {
        "action": "query",
        "format": "json",
        "list": "random",
        "rnnamespace": "0",
        "rnlimit": str(count),
    }
    url = f"{api_url}?{'&'.join(f'{k}={v}' for k, v in params.items())}"
    data = wiki_request(url)

    titles = [item["title"] for item in data["query"]["random"]]

    # Fetch article extracts
    articles = []
    for title in titles:
        params = {
            "action": "query",
            "format": "json",
            "titles": urllib.parse.quote(title),
            "prop": "extracts",
            "explaintext": "1",
            "exsectionformat": "plain",
            "exchars": "5000",
        }
        url = f"{api_url}?{'&'.join(f'{k}={v}' for k, v in params.items())}"
        data = wiki_request(url)

        pages = data["query"]["pages"]
        for page in pages.values():
            extract = page.get("extract", "").strip()
            if extract and len(extract) > 100:
                articles.append({"title": page["title"], "text": extract})

    return articles


def split_into_sentences(texts: list[str], lang: str) -> list[str]:
    """Split texts into sentences using nltk."""
    try:
        import nltk
    except ImportError:
        raise RuntimeError("nltk is required for sentence mode: pip install nltk")

    # Ensure punkt tokenizer data is available
    try:
        nltk.data.find("tokenizers/punkt_tab")
    except LookupError:
        nltk.download("punkt_tab", quiet=True)

    sentences = []
    for text in texts:
        for sent in nltk.sent_tokenize(text, language=_nltk_lang(lang)):
            sent_text = sent.strip()
            if sent_text and len(sent_text) > 10:
                sentences.append(sent_text)

    return sentences


def _nltk_lang(lang: str) -> str:
    """Map ISO 639-1 language codes to nltk language names."""
    lang_map = {
        "de": "german",
        "en": "english",
        "es": "spanish",
        "fr": "french",
        "it": "italian",
        "pt": "portuguese",
        "nl": "dutch",
        "pl": "polish",
        "ru": "russian",
        "cs": "czech",
        "da": "danish",
        "et": "estonian",
        "fi": "finnish",
        "el": "greek",
        "no": "norwegian",
        "sl": "slovene",
        "sv": "swedish",
        "tr": "turkish",
    }
    return lang_map.get(lang, "english")


def get_translator(engine: str, source_lang: str, target_lang: str):
    """Get cached translator instance."""
    if engine == "argos":
        from ftm_translate.logic.argos import make_translator

        return make_translator(source_lang, target_lang)
    elif engine == "apertium":
        from ftm_translate.logic.apertium import make_translator

        return make_translator(source_lang, target_lang)
    else:
        raise ValueError(f"Unknown engine: {engine}")


def benchmark_engine(
    engine: str,
    texts: list[str],
    source_lang: str,
    target_lang: str,
    rounds: int = 3,
) -> dict:
    """Benchmark a translation engine."""
    times: list[float] = []
    results: list[str] = []
    errors: list[str] = []
    total_chars = sum(len(t) for t in texts)

    # Get cached translator
    translator = get_translator(engine, source_lang, target_lang)

    for round_num in range(rounds):
        round_start = time.perf_counter()

        for text in texts:
            try:
                result = translator.translate(text)
                if round_num == 0 and result:
                    results.append(result)
            except Exception as e:
                if round_num == 0:
                    errors.append(str(e))
                    results.append(f"[ERROR: {e}]")

        elapsed = time.perf_counter() - round_start
        times.append(elapsed)

    return {
        "engine": engine,
        "rounds": rounds,
        "texts": len(texts),
        "total_chars": total_chars,
        "total_time_avg": statistics.mean(times),
        "total_time_std": statistics.stdev(times) if len(times) > 1 else 0,
        "chars_per_sec": total_chars / statistics.mean(times),
        "sources": texts,
        "results": results,
        "errors": errors,
    }


def print_results(results: dict, mode: Mode) -> None:
    """Print benchmark results."""
    console.print(f"\n[bold]{results['engine'].upper()}[/bold]")
    unit = "sentences" if mode == Mode.sentences else "texts"
    console.print(
        f"  {unit.capitalize()}:     {results['texts']} ({results['total_chars']} chars)"
    )
    console.print(
        f"  Time (avg):     {results['total_time_avg']:.3f}s ± {results['total_time_std']:.3f}s"
    )
    console.print(f"  Throughput:     {results['chars_per_sec']:.0f} chars/sec")

    if results["errors"]:
        console.print(f"  [red]Errors: {len(results['errors'])}[/red]")

    if results["results"] and results["sources"]:
        console.print("\n  Samples:")
        for i in range(min(3, len(results["results"]))):
            original = str(results["sources"][i])[:200].replace("\n", " ")
            translated = str(results["results"][i])[:200].replace("\n", " ")
            console.print(f"\n    [{i + 1}] Original:")
            console.print(f"        [dim]{original}...[/dim]")
            console.print(f"    [{i + 1}] Translated:")
            console.print(f"        [dim]{translated}...[/dim]")


@cli.command()
def run(
    source: str = typer.Option("de", "-s", "--source", help="Source language"),
    target: str = typer.Option("en", "-t", "--target", help="Target language"),
    num_articles: int = typer.Option(
        10, "-n", "--num-articles", help="Number of Wikipedia articles to fetch"
    ),
    rounds: int = typer.Option(3, "-r", "--rounds", help="Number of rounds"),
    mode: Mode = typer.Option(
        Mode.full, "-m", "--mode", help="Translation mode: full text or sentences"
    ),
    engines: Optional[list[str]] = typer.Option(
        None, "-e", "--engine", help="Engines to benchmark (default: both)"
    ),
):
    """Benchmark translation engines with random Wikipedia articles."""
    if engines is None:
        engines = ["argos", "apertium"]

    console.print(f"[bold]Benchmark: {source} → {target} ({mode})[/bold]")
    console.print(f"Fetching {num_articles} random Wikipedia articles...", end="")

    try:
        articles = fetch_random_articles(source, num_articles)
        total_chars = sum(len(a["text"]) for a in articles)
        console.print(f" [green]got {len(articles)} ({total_chars} chars)[/green]")
    except Exception as e:
        console.print(f" [red]failed: {e}[/red]")
        raise typer.Exit(1)

    if not articles:
        console.print("[red]No articles fetched[/red]")
        raise typer.Exit(1)

    # Prepare texts based on mode
    texts = [a["text"] for a in articles]

    if mode == Mode.sentences:
        console.print("Splitting into sentences...", end="")
        try:
            texts = split_into_sentences(texts, source)
            total_chars = sum(len(t) for t in texts)
            console.print(
                f" [green]{len(texts)} sentences ({total_chars} chars)[/green]"
            )
        except RuntimeError as e:
            console.print(f" [red]failed: {e}[/red]")
            raise typer.Exit(1)

    console.print(f"Rounds: {rounds}")

    all_results = []

    for engine in engines:
        console.print(f"\nRunning {engine}...", end="")
        try:
            results = benchmark_engine(engine, texts, source, target, rounds)
            all_results.append(results)
            console.print(" [green]done[/green]")
            print_results(results, mode)
        except Exception as e:
            console.print(f" [red]failed: {e}[/red]")

    if len(all_results) == 2:
        console.print("\n[bold]Comparison[/bold]")
        a, b = all_results
        ratio = a["chars_per_sec"] / b["chars_per_sec"]
        faster = a["engine"] if ratio > 1 else b["engine"]
        slower = b["engine"] if ratio > 1 else a["engine"]
        factor = max(ratio, 1 / ratio)
        console.print(
            f"  [green]{faster}[/green] is {factor:.1f}x faster than [yellow]{slower}[/yellow]"
        )


if __name__ == "__main__":
    cli()
