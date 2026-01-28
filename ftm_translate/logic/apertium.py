import subprocess
from tempfile import NamedTemporaryFile

from anystore.functools import weakref_cache as cache
from rigour.langs import iso_639_alpha3

from ftm_translate.exceptions import ProcessingException
from ftm_translate.logic.translator import Translator
from ftm_translate.settings import Settings

settings = Settings()


class ApertiumNotInstalledError(ProcessingException):
    pass


@cache
def get_installed_pairs() -> list[str]:
    """Get list of locally installed Apertium language pairs."""
    try:
        result = subprocess.run(
            ["apertium", "-l"],
            capture_output=True,
            text=True,
            check=True,
        )
        return [
            pair.strip() for pair in result.stdout.strip().split("\n") if pair.strip()
        ]
    except FileNotFoundError:
        raise ApertiumNotInstalledError()


class ApertiumTranslator(Translator):
    engine = "apertium"

    @property
    def source_alpha3(self) -> str:
        return iso_639_alpha3(self.source_lang) or self.source_lang

    @property
    def target_alpha3(self) -> str:
        return iso_639_alpha3(self.target_lang) or self.target_lang

    @property
    def pair(self) -> str:
        return f"{self.source_alpha3}-{self.target_alpha3}"

    def _ensure_pair(self) -> bool:
        """Ensure the language pair is installed."""
        installed_pairs = get_installed_pairs()

        if self.pair in installed_pairs:
            return True

        # Check reverse pair (some pairs work bidirectionally)
        reverse_pair = f"{self.target_alpha3}-{self.source_alpha3}"
        if reverse_pair in installed_pairs:
            return True

        raise ProcessingException(
            f"Apertium language pair `{self.pair}` is not installed. "
            f"Available pairs: {', '.join(installed_pairs[:10])}..."
        )

    def _translate(self, text: str) -> str:
        """Translate text using Apertium."""
        try:
            with NamedTemporaryFile(mode="w+t", suffix=".txt") as temp_file:
                temp_file.write(text)
                temp_file.flush()

                result = subprocess.run(
                    ["apertium", "-u", self.pair, temp_file.name],
                    capture_output=True,
                    text=True,
                )

                if result.returncode != 0:
                    raise ProcessingException(
                        f"Apertium translation failed for pair `{self.pair}`: {result.stderr}"
                    )

                return result.stdout

        except FileNotFoundError:
            raise ApertiumNotInstalledError()


@cache
def make_translator(source_lang: str, target_lang: str) -> ApertiumTranslator:
    """Get cached translator instance."""
    return ApertiumTranslator(source_lang, target_lang)


def translate_apertium(
    text: str, source_lang: str, target_lang: str = settings.target_language
) -> str | None:
    """Factory function for Apertium translation."""
    translator = make_translator(source_lang, target_lang)

    try:
        return translator.translate(text)
    except ProcessingException as e:
        translator.log.error(str(e))
