[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit)](https://github.com/pre-commit/pre-commit)
[![Coverage Status](https://coveralls.io/repos/github/openaleph/ftm-translate/badge.svg?branch=main)](https://coveralls.io/github/openaleph/ftm-translate?branch=main)

# ftm-translate

Open-source, local translations for [FollowTheMoney Documents](https://followthemoney.tech/explorer/schemata/Document/).

It takes the input text and stores translations at the `translatedText` property.

## Usage

To start an [openaleph-procrastinate worker](https://github.com/openaleph/openaleph-procrastinate) that can execute transcription tasks, start the worker from the command line:

    PROCRASTINATE_APP=ftm_translate.tasks.app procrastinate worker -q translate

To defer tasks from other places, use `translate` as queue name and `ftm_translate.tasks.translate` as the task identifier. These values can also be imported from [openaleph-procrastinate.settings](https://github.com/openaleph/openaleph-procrastinate/blob/main/openaleph_procrastinate/settings.py).

## License and Copyright

`ftm-translate`, (C) 2026 [Data and Research Center – DARC](https://dataresearchcenter.org)

`ftm-translate` is licensed under the AGPLv3 or later license.

see [NOTICE](./NOTICE) and [LICENSE](./LICENSE)
