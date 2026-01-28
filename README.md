[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit)](https://github.com/pre-commit/pre-commit)
[![Coverage Status](https://coveralls.io/repos/github/openaleph/ftm-translate/badge.svg?branch=main)](https://coveralls.io/github/openaleph/ftm-translate?branch=main)

# ftm-translate

Local translations for [FollowTheMoney Documents](https://followthemoney.tech/explorer/schemata/Document/).

Translates `bodyText` and stores results in `translatedText` and `translatedLanguage` properties.

## Installation

    pip install ftm-translate[argos]   # or [apertium]

[Apertium requires system installation.](https://wiki.apertium.org/wiki/Install_Apertium_core_using_packaging)

## Configuration

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `FTM_TRANSLATE_ENGINE` | `argos` | Translation engine (`argos` or `apertium`) |
| `FTM_TRANSLATE_SOURCE_LANGUAGE` | - | Source language (ISO 639-1) |
| `FTM_TRANSLATE_TARGET_LANGUAGE` | `en` | Target language (ISO 639-1) |

## CLI Usage

    ftm-translate --help

Translate entities:

    ftm-translate entities -i entities.json -o translated.json -s de -t en
    ftm-translate entities -i https://data.example.org/entities.ftm.json -s de

Translate text:

    echo "Hallo Welt" | ftm-translate text -s de -t en
    ftm-translate text -i input.txt -o output.txt -s de -e apertium

Options: `-s` source, `-t` target (default: en), `-e` engine, `-i` input, `-o` output.

## OpenAleph Worker

To integrate in [OpenAleph](https://openaleph.org) ingest pipeline using [openaleph-procrastinate](https://openaleph.org/docs/lib/openaleph-procrastinate/):

Install dependencies:

    pip install ftm-translate[openaleph]

Run the worker:

    PROCRASTINATE_APP=ftm_translate.tasks.app procrastinate worker -q translate

Queue name: `translate`
Task identifier: `ftm_translate.tasks.translate`

## Acknowledgements

This is inspired by the preliminary work by and valuable knowledge exchange with the [International Consortium of Investigative Journalists](http://icij.org/) whose tech team built [ES Translator](https://icij.github.io/es-translator/).

## License

`ftm-translate`, (C) 2026 [Data and Research Center – DARC](https://dataresearchcenter.org)

Licensed under AGPLv3+. See [NOTICE](./NOTICE) and [LICENSE](./LICENSE).
