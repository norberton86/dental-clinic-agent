"""Centralised configuration loaded from environment variables."""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # LLM
    llm_provider: Literal["anthropic", "openai", "telnyx", "gemini"] = "anthropic"
    telnyx_inference_model: str = "moonshotai/Kimi-K2.6"  # used when llm_provider=telnyx
    openai_api_key: str | None = None
    openai_model: str = "gpt-4.1"
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-4-6"
    # Gemini (Google AI Studio, OpenAI-compatible endpoint). Free-tier keys get
    # intermittent 503s → max_retries handles it; use a billed key for production.
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.5-flash-lite"
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai/"

    # STT
    deepgram_api_key: str = ""
    deepgram_model: str = "nova-3"
    deepgram_language: str = "es"
    # Silence (ms) Deepgram waits before finalizing a transcript. Higher = it waits
    # through natural mid-sentence pauses instead of cutting the caller off; lower =
    # snappier but risks splitting one sentence into multiple turns. ~400 is balanced.
    deepgram_endpointing_ms: int = 400
    # Optional: emit an UtteranceEnd after this gap (ms, must be >=1000). None = off.
    deepgram_utterance_end_ms: int | None = None

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

    # Email (SMTP) — optional appointment confirmation/reminder emails.
    # Works with any SMTP provider (Gmail app password, Resend, SendGrid, SES…).
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    email_from: str | None = None
    email_from_name: str = "Clínica Dental Smile"
    smtp_use_tls: bool = True

    # Calendar — "Add to calendar" links in confirmation emails (booking/reschedule).
    clinic_name: str = "Clínica Dental Smile"
    calendar_timezone: str = "Europe/Madrid"  # the CLINIC's timezone (where the appointment is)

    # Logging
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
