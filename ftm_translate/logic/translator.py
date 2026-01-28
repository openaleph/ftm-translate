from abc import ABC, abstractmethod
from functools import cached_property

from structlog import BoundLogger, get_logger

from ftm_translate.exceptions import ProcessingException
from ftm_translate.settings import Engine, Settings

settings = Settings()


class Translator(ABC):
    engine: Engine

    def __init__(
        self, source_lang: str, target_lang: str = settings.target_language
    ) -> None:
        self.source_lang = source_lang
        self.target_lang = target_lang
        self.log.info("👋 Initializing translator ...")

    @cached_property
    def log(self) -> BoundLogger:
        return get_logger(
            __name__,
            engine=self.engine,
            source_lang=self.source_lang,
            target_lang=self.target_lang,
        )

    @abstractmethod
    def _ensure_pair(self) -> bool:
        """Ensure language pair exists for given engine (implemented by subclass)"""
        ...

    @cached_property
    def ensure_pair(self) -> bool:
        """Cached check that language pair exists"""
        return self._ensure_pair()

    @abstractmethod
    def _translate(self, text: str) -> str | None:
        """Translate given text input (implemented by subclass)"""
        ...

    def translate(self, text: str) -> str | None:
        """Translate given text input"""
        if self.ensure_pair:
            return self._translate(text)
        return None

    def error(self) -> None:
        raise ProcessingException(
            f"Couldn't translate `{self.source_lang}` -> `{self.target_lang}` "
            f"using `{self.engine}` engine"
        )
