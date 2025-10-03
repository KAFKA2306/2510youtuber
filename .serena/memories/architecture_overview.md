# Architecture Overview

## 10-Step Core Workflow
Executed sequentially in `app/main.py`:

1. **News Collection** (`search_news.py`) - Perplexity AI → NewsAPI → fallback dummy news
2. **Script Generation** (`crew/flows.py`) - 7 CrewAI agents generate dialogue script
3. **Script Quality Check** (`japanese_quality.py`) - Validates Japanese purity 95%+
4. **Audio Synthesis** (`tts.py`) - ElevenLabs → VOICEVOX → OpenAI → gTTS → Coqui → pyttsx3
5. **STT for Alignment** (`stt.py`) - Whisper transcription of generated audio
6. **Subtitle Alignment** (`align_subtitles.py`) - Match script to actual audio timing
7. **B-roll Generation** (`services/media/`) - Stock footage matching + visual effects
8. **Video Rendering** (`video.py`) - FFmpeg compositing with subtitles
9. **Metadata Generation** (`metadata.py`) - Title, description, tags
10. **YouTube Upload** (`youtube.py`) - Automated upload with OAuth

## 7 CrewAI Agent Pipeline
Located in `app/crew/`, runs sequentially (agents 1-3 can run in parallel if `crew.parallel_analysis: true`):

1. **Deep News Analyzer** - Finds hidden insights and surprising facts
2. **Curiosity Gap Researcher** - Designs viewer engagement hooks
3. **Emotional Story Architect** - Structures narrative arc
4. **Script Writer** - Generates initial dialogue (3 speakers: 田中, 鈴木, ナレーター)
5. **Engagement Optimizer** - Maximizes retention with pattern interrupts
6. **Quality Guardian** - Validates WOW score 8.0+, metrics, pacing
7. **Japanese Purity Polisher** - Removes English artifacts, ensures 95%+ Japanese

**Critical**: All agents use `litellm` with Google AI Studio (NOT Vertex AI). `flows.py` explicitly removes Vertex AI environment variables.

## API Key Rotation System
`app/api_rotation.py` implements resilient handling:
- **Gemini**: Rotates through 5 keys on 429 errors (5-min wait per key, 10-min cooldown after all exhausted)
- **Perplexity**: Similar rotation with backoff
- **TTS**: 6-level fallback cascade

## Configuration Systems
Two systems coexist (backward compatibility):

1. **New system** (`app/config/settings.py`): Pydantic-based, reads `config.yaml`
   - Use `from app.config import cfg` for new code
2. **Legacy system** (`app/config_old.py`): Environment variables only
   - Use `.env` files in `secret/` directory

## Quality Assurance
- **Japanese Purity**: 95%+ Japanese characters (validated by `japanese_quality.py`)
- **WOW Score**: 8.0+ with metrics (surprise points, emotion peaks, curiosity gaps, etc.)
- **Retention Target**: 50%+ predicted viewer retention

## Video Generation
- Uses FFmpeg with quality presets (low/medium/high/ultra)
- Quality settings centralized in `_get_quality_settings()` methods
- **Important**: Never manually specify `crf`, `preset`, or `vcodec` alongside quality settings dict
