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
    speaker: 1  # 四国めたん あまあま (female)
```
Environment overrides: `VOICEVOX_IMAGE`, `VOICEVOX_CONTAINER_NAME`, `VOICEVOX_PORT`,
`VOICEVOX_SPEAKER`, `VOICEVOX_CPU_LIMIT`, `VOICEVOX_MEMORY_LIMIT`, `VOICEVOX_START_TIMEOUT`.

### Available Speakers

Get the complete list dynamically from the API: `http://localhost:50021/speakers`

**Popular speakers and style IDs:**

| Character | Style | ID | Notes |
|-----------|-------|----|----|
| **四国めたん** (Shikoku Metan) | ノーマル (Normal) | 2 | Female voice |
| | あまあま (Sweet) | 0 | |
| | ツンツン (Tsundere) | 6 | |
| | セクシー (Sexy) | 4 | |
| | ささやき (Whisper) | 36 | |
| | ヒソヒソ (Hushed) | 37 | |
| **ずんだもん** (Zundamon) | ノーマル (Normal) | 3 | Neutral voice |
| | あまあま (Sweet) | 1 | |
| | ツンツン (Tsundere) | 7 | |
| | セクシー (Sexy) | 5 | |
| | ささやき (Whisper) | 22 | |
| | ヒソヒソ (Hushed) | 38 | |
| | ヘロヘロ (Exhausted) | 75 | |
| | なみだめ (Tearful) | 76 | |
| **春日部つむぎ** (Kasukabe Tsumugi) | ノーマル (Normal) | 8 | Female voice |
| **雨晴はう** (Amahare Hau) | ノーマル (Normal) | 10 | |
| **波音リツ** (Namine Ritsu) | ノーマル (Normal) | 9 | |
| | クイーン (Queen) | 65 | |
| **玄野武宏** (Kurono Takehiro) | ノーマル (Normal) | 11 | Male voice |
| | 喜び (Joy) | 39 | |
| | ツンギレ (Irritated) | 40 | |
| | 悲しみ (Sad) | 41 | |
| **琴詠ニア** (Kotoyomi Nia) | ノーマル (Normal) | 74 | |

**Default speaker configuration (configured in `config.yaml`):**
- 武宏 (玄野武宏): ID 11 - Male economic analyst, calm and logical
- つむぎ (春日部つむぎ): ID 8 - Female reporter, curious and engaging
- ナレーター (ずんだもん): ID 3 - Neutral narrator for intro/outro

**Alternative speakers for financial news:**
- Male professional: 玄野武宏 喜び (ID: 39), ツンギレ (ID: 40), 悲しみ (ID: 41)
- Female variations: 四国めたん ノーマル (ID: 2), セクシー (ID: 4)
- Neutral backup: 波音リツ (ID: 9)

## Verification
Run the configuration validator before long runs; it will auto-start VOICEVOX if required and
perform a synthesis smoke test when the server is up.
```bash
uv run python -m app.verify
```
During workflows VOICEVOX sits behind the TTS fallback chain
(ElevenLabs → VOICEVOX → OpenAI TTS → gTTS → Coqui → pyttsx3).
