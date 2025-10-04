# VOICEVOX Nemo Quick Guide

VOICEVOX Nemo provides a free Japanese TTS fallback when ElevenLabs is rate limited or
unavailable. Keep Docker running and let the manager script handle lifecycle and health
checks.

## Prerequisites
- Docker Engine available without `sudo`
- Local port `50121` free (override with `VOICEVOX_PORT`)

## Start, Stop, Inspect
```bash
./scripts/voicevox_manager.sh start
./scripts/voicevox_manager.sh status
./scripts/voicevox_manager.sh stop
```
The script pulls `voicevox/voicevox_engine:cpu-ubuntu20.04-0.24.1` by default, exposes port
`50021` to the chosen host port, and enables Docker restart policy `unless-stopped`.

### Useful operations
```bash
./scripts/voicevox_manager.sh restart    # Relaunch container
./scripts/voicevox_manager.sh logs       # Tail manager + container logs
./scripts/voicevox_manager.sh test       # Generate /logs/voicevox_test.wav
```
Logs are stored in `logs/voicevox_nemo.log`. Health checks hit `http://localhost:PORT/health`.

## Configuration
Set defaults in `config.yaml` and override with environment variables when needed.
```yaml
tts:
  voicevox:
    enabled: true
    port: 50121
    speaker: 1  # 四国めたん (female)
```
Environment overrides: `VOICEVOX_IMAGE`, `VOICEVOX_CONTAINER_NAME`, `VOICEVOX_PORT`,
`VOICEVOX_SPEAKER`, `VOICEVOX_CPU_LIMIT`, `VOICEVOX_MEMORY_LIMIT`, `VOICEVOX_START_TIMEOUT`.

## Verification
Run the configuration validator before long runs; it will auto-start VOICEVOX if required and
perform a synthesis smoke test when the server is up.
```bash
uv run python -m app.verify
```
During workflows VOICEVOX sits behind the TTS fallback chain
(ElevenLabs → VOICEVOX → OpenAI TTS → gTTS → Coqui → pyttsx3).
