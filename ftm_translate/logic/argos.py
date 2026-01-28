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

from ftm_translate.exceptions import ProcessingException  # noqa: E402
from ftm_translate.logic.translator import Translator  # noqa: E402
from ftm_translate.settings import Settings  # noqa: E402

settings = Settings()


class ArgosTranslator(Translator):
    engine = "argos"

    def _ensure_pair(self) -> bool:
        """Ensure the language pair is installed, downloading if necessary."""
        installed_languages = argostranslate.translate.get_installed_languages()
        source_langs = [
            lang for lang in installed_languages if lang.code == self.source_lang
        ]
        target_langs = [
            lang for lang in installed_languages if lang.code == self.target_lang
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
            if pkg.from_code == self.source_lang and pkg.to_code == self.target_lang
        ]

        if not matching:
            raise ProcessingException(
                f"No Argos package available for `{self.source_lang}` -> `{self.target_lang}`"
            )

        package = matching[0]
        download_path = package.download()
        argostranslate.package.install_from_path(download_path)
        return True

    def _translate(self, text: str) -> str:
        """Translate text using Argos."""
        installed_languages = argostranslate.translate.get_installed_languages()
        source_langs = [
            lang for lang in installed_languages if lang.code == self.source_lang
        ]
        target_langs = [
            lang for lang in installed_languages if lang.code == self.target_lang
        ]

        if not source_langs:
            raise ProcessingException(
                f"Argos source language `{self.source_lang}` is not installed"
            )
        if not target_langs:
            raise ProcessingException(
                f"Argos target language `{self.target_lang}` is not installed"
            )

        source = source_langs[0]
        target = target_langs[0]
        translation = source.get_translation(target)

        if translation is None:
            raise ProcessingException(
                f"No Argos translation from `{self.source_lang}` to `{self.target_lang}`"
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
