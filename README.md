# Dental Voice Agent — Pipecat + Telnyx (real-time streaming)

Spanish-speaking dental-clinic virtual receptionist. Real-time streaming voice over
Telnyx media streaming, Deepgram Nova-3 STT + Aura-2 (Spanish) TTS — one Deepgram key for both — and a LangGraph
tool-calling agent over the existing Supabase RPCs. No DTMF menus, no TeXML Gather loops,
no webhook ping-pong, no magic tokens — proper tools (`transfer_call`, `hangup_call`) and
in-process `MemorySaver` memory (no Redis).

## Architecture

```
Inbound call → Telnyx app → Pipecat runner (POST /) returns a minimal <Stream> XML
   → Telnyx opens a bidirectional media WebSocket to the runner's /ws (8 kHz PCMU)
   → bot() builds the transport + pipeline:
       transport.input() → Deepgram STT (nova-3, es) → LangGraphProcessor → Deepgram Aura-2 TTS (es) → transport.output()
```

The runner hosts the server; we never write a FastAPI app. We *do* build the transport
from the parsed call (to read `call_control_id` + caller phone), per the official
Telnyx guide.

## Setup

```bash
cd ~/dental-voice-pipecat
uv sync --extra dev          # install deps
cp .env.example .env         # then fill in the keys
```

Fill `.env`: Anthropic (default LLM; or OpenAI / Kimi-via-Telnyx), **Deepgram** (one key — STT *and* Aura-2 Spanish TTS), Telnyx
API key, Supabase URL + service key, and `HUMAN_TRANSFER_NUMBER`.

## Telnyx configuration

1. Create / use a Telnyx app whose **Voice webhook URL** points at the runner's public
   URL (`https://<PUBLIC_HOST>/`). The runner answers with the `<Stream>` bridge; there is
   **no conversational TeXML** (no menus/Gather/Say).
2. **Re-point your numbers** (`+17622138423`, `+34951840694`) from their current TeXML
   apps to this app. A number serves one app at a time.
3. The media WebSocket needs a **public `wss://`** host — use ngrok/Cloudflare in dev
   (the `-x` value below).

## Run

```bash
uv run bot.py -t telnyx -x <your-ngrok-host>
# the runner serves the webhook at POST / and media WS at /ws
```

Then call your number.

## Tests

```bash
uv run pytest                # phone normalization, supabase service, tools, graph routing
```

Tests mock HTTP (respx) and the LLM (scripted) — deterministic, no live keys needed.

## Known caveats / things to verify on a live call

- **Caller phone source.** `bot.py` reads the caller number from the parsed media-WS
  call data (`from`). If your Telnyx stream doesn't surface `from`, pass it as a custom
  stream parameter or fetch it via the Call Control API by `call_control_id`. Patient
  identification depends on this.
- **`transfer_call` on a `<Stream>`-bridged call.** Verify Telnyx accepts the Call
  Control `transfer` by `call_control_id`. If not, switch call bring-up to a custom
  webhook + `streaming_start` so the call is natively Call Control.
- **`langgraph_processor.py` is version-sensitive.** Frame names / streaming-token
  extraction follow current Pipecat + LangChain; confirm against the versions `uv` pins.
- **Deepgram language is `es`** (not `es-ES`) — Nova-3 Spanish streaming.

## Layout

```
bot.py                 runner entry (bot() + main())
src/config/settings.py env config (pydantic-settings)
src/services/          supabase_client, telnyx_client, phone
src/prompts/           system_prompt builder
src/tools/             9 tools + registry (binds phone + call_control_id per call)
src/graph/             LangGraph agent (state, nodes, agent + MemorySaver)
src/transport/         pipeline, langgraph_processor, tts_factory
src/models/schemas.py  tool envelope + arg schemas
src/tests/             pytest suite
```
