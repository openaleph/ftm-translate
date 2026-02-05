import logging

# Suppress verbose logging from argostranslate and its dependencies
for _logger_name in ("argostranslate", "argostranslate.utils", "stanza"):
    _logger = logging.getLogger(_logger_name)
    _logger.setLevel(logging.ERROR)
    _logger.propagate = False
    _logger.addHandler(logging.NullHandler())

import argostranslate.package  # noqa: E402
import argostranslate.translate  # noqa: E402
from anystore.functools import weakref_cache as cache  # noqa: E402
from rigour.langs import iso_639_alpha2  # noqa: E402

from ftm_translate.exceptions import ProcessingException  # noqa: E402
from ftm_translate.logic.translator import Translator  # noqa: E402
from ftm_translate.settings import Settings  # noqa: E402

settings = Settings()


class ArgosTranslator(Translator):
    engine = "argos"

    @property
    def source_alpha2(self) -> str:
        return iso_639_alpha2(self.source_lang) or self.source_lang

    @property
    def target_alpha2(self) -> str:
        return iso_639_alpha2(self.target_lang) or self.target_lang

    def _ensure_pair(self) -> bool:
        """Ensure the language pair is installed, downloading if necessary."""
        installed_languages = argostranslate.translate.get_installed_languages()
        source_langs = [
            lang for lang in installed_languages if lang.code == self.source_alpha2
        ]
        target_langs = [
            lang for lang in installed_languages if lang.code == self.target_alpha2
        ]

        if source_langs and target_langs:
            source = source_langs[0]
            target = target_langs[0]
            if source.get_translation(target) is not None:
                return True

        # Try to download the package
        self.log.info("Downloading argos language pair ...")
        argostranslate.package.update_package_index()
        available_packages = argostranslate.package.get_available_packages()
        matching = [
            pkg
            for pkg in available_packages
            if pkg.from_code == self.source_alpha2 and pkg.to_code == self.target_alpha2
        ]

        if not matching:
            raise ProcessingException(
                "No Argos package available for ",
                f"`{self.source_alpha2}` -> `{self.target_alpha2}`",
            )

        package = matching[0]
        download_path = package.download()
        argostranslate.package.install_from_path(download_path)
        return True

    def _translate(self, text: str) -> str:
        """Translate text using Argos."""
        installed_languages = argostranslate.translate.get_installed_languages()
        source_langs = [
            lang for lang in installed_languages if lang.code == self.source_alpha2
        ]
        target_langs = [
            lang for lang in installed_languages if lang.code == self.target_alpha2
        ]

        if not source_langs:
            raise ProcessingException(
                f"Argos source language `{self.source_alpha2}` is not installed"
            )
        if not target_langs:
            raise ProcessingException(
                f"Argos target language `{self.target_alpha2}` is not installed"
            )

        source = source_langs[0]
        target = target_langs[0]
        translation = source.get_translation(target)

        if translation is None:
            raise ProcessingException(
                f"No Argos translation from `{self.source_alpha2}` to `{self.target_alpha2}`"
            )

        return translation.translate(text)


@cache
def make_translator(source_lang: str, target_lang: str) -> ArgosTranslator:
    """Get cached translator instance"""
    return ArgosTranslator(source_lang, target_lang)


def translate_argos(
    text: str, source_lang: str, target_lang: str = settings.target_language
) -> str | None:
    """Factory function for Argos translation."""
    translator = make_translator(source_lang, target_lang)

    try:
        return translator.translate(text)
    except ProcessingException as e:
        translator.log.error(str(e))
