from typing import Literal, TypeAlias

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


Engine: TypeAlias = Literal["argos", "apertium"]


class Settings(BaseSettings):
    """
    `ftm-translate` settings management using
    [pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)

    Note:
        All settings can be set via environment variables in uppercase,
        prepending `FTMTR_`
    """

    model_config = SettingsConfigDict(
        env_prefix="ftm_translate_", env_file=".env", extra="ignore"
    )

    engine: Engine = Field(default="argos")
    """Translation engine to use (needs to be installed): argos / apertium"""

    target_language: str = Field(default="en")
    """Globally configure target language"""
