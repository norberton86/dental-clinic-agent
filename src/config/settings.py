"""Centralised configuration loaded from environment variables."""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # LLM
    llm_provider: Literal["anthropic", "openai", "telnyx"] = "anthropic"
    telnyx_inference_model: str = "moonshotai/Kimi-K2.6"  # used when llm_provider=telnyx
    openai_api_key: str | None = None
    openai_model: str = "gpt-4.1"
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-4-6"

    # STT
    deepgram_api_key: str = ""
    deepgram_model: str = "nova-3"
    deepgram_language: str = "es"

    # TTS  (Deepgram Aura-2 reuses DEEPGRAM_API_KEY — no separate TTS key/bill)
    tts_provider: Literal["deepgram", "elevenlabs", "azure"] = "deepgram"
    deepgram_tts_voice: str = "aura-2-carina-es"  # Spanish Aura-2 (carina); voices at developers.deepgram.com/docs/tts-models
    elevenlabs_api_key: str | None = None
    elevenlabs_voice_id: str | None = None
    azure_speech_api_key: str | None = None
    azure_speech_region: str | None = None
    azure_voice_id: str = "es-ES-ElviraNeural"

    # Telnyx
    telnyx_api_key: str = ""
    telnyx_public_key: str | None = None
    public_host: str | None = None
    port: int = 8080

    # Supabase
    supabase_url: str = ""
    supabase_service_key: str = ""

    # Call routing
    human_transfer_number: str = ""
    default_country_code: str = "+34"

    # Logging
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
