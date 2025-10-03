# Project Overview

## Purpose
Automated YouTube video generation system that creates high-engagement financial news videos using AI agents. The system:
- Uses CrewAI with 7 specialized agents to generate scripts optimized for 50%+ viewer retention
- Synthesizes multi-speaker Japanese audio (3 speakers: 田中, 鈴木, ナレーター)
- Generates videos with B-roll footage from stock video services
- Automatically uploads to YouTube with metadata

## Tech Stack
- **Language**: Python 3.10+
- **Package Manager**: `uv` (recommended) or pip
- **AI Frameworks**:
  - CrewAI (agent orchestration)
  - LiteLLM with Google AI Studio (Gemini models)
  - Perplexity AI (news collection)
- **LLM Models**: Gemini 2.5 Flash (all 7 agents)
- **TTS Services**: ElevenLabs → VOICEVOX → OpenAI → gTTS → Coqui → pyttsx3 (fallback cascade)
- **Speech Recognition**: OpenAI Whisper
- **Video Processing**: FFmpeg, ffmpeg-python, Pillow
- **Data Handling**: Pydantic v2, pandas
- **APIs**: Google YouTube API, Pixabay, Pexels
- **Testing**: pytest with markers (unit/integration/e2e)
- **Linting/Formatting**: Ruff

## Key Dependencies
- anthropic, google-generativeai, elevenlabs, openai
- google-api-python-client, google-auth, gspread
- pydub, ffmpeg-python, Pillow
- SpeechRecognition, openai-whisper, gtts, coqui-tts, pyttsx3
- python-dotenv, pytest, ruff

## System Requirements
- Platform: Linux (WSL2 tested)
- FFmpeg 4.4+ (for subtitle rendering)
- Disk space for temp files and video output
