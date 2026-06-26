"""TTS provider factory — swap providers by changing TTS_PROVIDER only.

Default is Deepgram Aura-2 (Spanish) — it reuses DEEPGRAM_API_KEY (same provider
as STT, one key, one bill) and is cheaper than Cartesia. ElevenLabs / Azure remain
selectable. All providers output a stream Pipecat resamples to 8 kHz for Telnyx.
"""
from __future__ import annotations

from ..config.settings import Settings


def create_tts(settings: Settings):
    provider = settings.tts_provider

    if provider == "deepgram":
        from pipecat.services.deepgram.tts import DeepgramTTSService

        # Aura-2's voice id IS the Deepgram model id (e.g. aura-2-<voice>-es); set both.
        voice = settings.deepgram_tts_voice
        return DeepgramTTSService(
            api_key=settings.deepgram_api_key,
            settings=DeepgramTTSService.Settings(model=voice, voice=voice),
        )

    if provider == "elevenlabs":
        from pipecat.services.elevenlabs.tts import ElevenLabsTTSService

        return ElevenLabsTTSService(
            api_key=settings.elevenlabs_api_key,
            voice_id=settings.elevenlabs_voice_id,
            params=ElevenLabsTTSService.InputParams(language="es"),
        )

    if provider == "azure":
        from pipecat.services.azure.tts import AzureTTSService

        return AzureTTSService(
            api_key=settings.azure_speech_api_key,
            region=settings.azure_speech_region,
            voice=settings.azure_voice_id,
        )

    raise ValueError(f"Unknown TTS_PROVIDER: {provider!r}")
