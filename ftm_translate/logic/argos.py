import logging
import os

# Suppress verbose logging from argostranslate and its dependencies
for _logger_name in ("argostranslate", "argostranslate.utils", "stanza"):
    _logger = logging.getLogger(_logger_name)
    _logger.setLevel(logging.ERROR)
    _logger.propagate = False
    _logger.addHandler(logging.NullHandler())

from functools import cache  # noqa: E402

import argostranslate.package  # noqa: E402
import argostranslate.translate  # noqa: E402
from rigour.langs import iso_639_alpha2  # noqa: E402

# Patch stanza to skip re-downloading resources.json when it already exists
# locally. Without this, stanza always tries to fetch the resource index from
# GitHub, which breaks offline / air-gapped containers.
try:
    import stanza.pipeline.core as _stanza_core  # noqa: E402

    _orig_download_resources_json = _stanza_core.download_resources_json

    def _download_resources_json_if_needed(*args, **kwargs):
        model_dir = (
            args[0] if args else kwargs.get("model_dir", _stanza_core.DEFAULT_MODEL_DIR)
        )
        filepath = kwargs.get("resources_filepath") or os.path.join(
            model_dir, "resources.json"
        )
        if os.path.exists(filepath):
            return
        return _orig_download_resources_json(*args, **kwargs)

    _stanza_core.download_resources_json = _download_resources_json_if_needed
except ImportError:
    pass

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
        # Fast filesystem-only check via installed packages (avoids creating
        # Translation objects which may trigger lazy network calls).
        installed_packages = argostranslate.package.get_installed_packages()
        if any(
            pkg.from_code == self.source_alpha2 and pkg.to_code == self.target_alpha2
            for pkg in installed_packages
        ):
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
