# Important Patterns and Gotchas

## CrewAI + LiteLLM + Gemini
- System MUST use Google AI Studio (Generative AI SDK), NOT Vertex AI
- `flows.py` removes all Vertex-related environment variables before CrewAI initialization
- API key rotation happens at `litellm.completion` call level, not via environment variables
- Each agent can use different models (configured in `config.yaml` under `crew.agents`)

## Speaker Format Enforcement
Scripts MUST follow this exact format:
```
田中: セリフテキスト
鈴木: セリフテキスト
ナレーター: セリフテキスト
```
- Agent 7 (Japanese Purity Polisher) enforces this format
- Any deviation breaks TTS processing

## Video Generation Failure Points
Common causes:
1. **Parameter duplication** - `crf`, `preset` specified twice (main/fallback/test paths)
2. **Missing audio files** - TTS failure upstream
3. **Insufficient disk space** - For temp files
4. **FFmpeg version** - Need 4.4+ for subtitle rendering

**Phase 3 fix**: All three video generation code paths now use `**self._get_quality_settings()` without additional explicit parameters.

## Japanese Purity Issues
- **Phase 3 fix**: Agent 6-7 prompts modified to prevent English metadata contamination
- Common pollutants: "json", "wow_score", "Task", "Output"
- Enforcement point: After Agent 7 completes
- Target: 95%+ Japanese characters (configurable in `config.yaml`)

## TTS Fallback Chain
Order (stops at first success):
1. ElevenLabs (quota: 10k chars/month on free tier)
2. VOICEVOX Nemo (free, unlimited, requires local server)
3. OpenAI TTS
4. gTTS (Google Text-to-Speech)
5. Coqui TTS
6. pyttsx3 (offline fallback)

**Best practice**: Start VOICEVOX Nemo server for free unlimited TTS:
```bash
./scripts/voicevox_manager.sh start
```

## API Rate Limiting
- Gemini: Rotates through 5 keys on 429 errors
- Perplexity: Similar rotation with backoff
- System automatically waits and retries
- Add more rotation keys (`GEMINI_API_KEY_2`, `GEMINI_API_KEY_3`, etc.) to prevent exhaustion

## Configuration Migration
Two systems coexist:
- **New**: `config.yaml` + `app/config/settings.py` (Pydantic)
- **Legacy**: `.env` files + `app/config_old.py`

When modifying config:
1. Update `config.yaml` for new system
2. Document `.env` requirements for legacy compatibility
3. Use `from app.config import cfg` in new code

## Testing Strategy
- **Unit tests** (`tests/unit/`): Mock all external APIs, test pure logic
- **Integration tests** (`tests/integration/`): Use fixtures, test component interaction
- **E2E tests** (`tests/e2e/`): Real APIs, costs money, requires `--run-e2e` flag
- **Always run unit tests before commit**: `pytest tests/unit -v`

## Common Error Patterns

### "Could not clean all English" warnings
- **Cause**: Agent 6/7 outputting metadata in English
- **Fix**: Update `app/config/prompts/quality_check.yaml` with explicit JSON-only output instructions

### FFmpeg "crf or preset" errors
- **Cause**: Duplicate parameter specification
- **Fix**: Ensure only `**self._get_quality_settings()` is used

### Agent creation failures
- **Cause**: Missing `GEMINI_API_KEY` or incorrect format
- **Fix**: Verify with `uv run python -m app.verify`

### Rate limit 429 errors
- **Cause**: API rate limits hit
- **Fix**: System auto-rotates, or add more keys
