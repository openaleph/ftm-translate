from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    `ftm-translate` settings management using
    [pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)

    Note:
        All settings can be set via environment variables in uppercase,
        prepending `FTMTR_`
    """

    model_config = SettingsConfigDict(
        env_prefix="ftmtr_", env_file=".env", extra="ignore"
    )

    data_root: str = Field()
    """Root directory; used for temporarily writing output files"""

    whisper_executable: str = Field()
    """Path to whisper-cli"""

    whisper_model_root: str = Field()
    """Path to WhisperCpp model, usually ./models"""

    whisper_model: str = Field(default="ggml-medium-q8_0.bin")
    """Name of WhisperCpp model, inside the model_root directory"""

    whisper_timeout: int = Field(default=60 * 60)
    """Timeout for the transcription operation and the ffmpeg audio extraction"""

    whisper_language: str = Field(default="auto")
    """Two-letter language code (ISO 639-1) or auto"""
