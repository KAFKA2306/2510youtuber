# Strict Video Generation Tests

## Overview

This test suite (`test_video_generation_strict.py`) provides the **strictest possible validation** for video generation functionality. Unlike the LLM output format tests, these tests validate actual FFmpeg encoding, frame generation, and video output integrity.

## Design Philosophy

**Zero Tolerance for Failures**

- No fallback strategies - tests validate that the primary code path works correctly
- No error handling masks failures - we test the actual logic, not defensive programming
- Direct validation of FFmpeg commands, encoding progress, and output quality
- Fails immediately on any deviation from expected behavior

## Test Coverage (24 tests)

### 1. TestFFmpegCommandValidation (6 tests)
Validates FFmpeg command construction is correct **before** execution:

- **test_quality_settings_are_valid**: Quality settings must contain valid FFmpeg parameters
  - Validates `c:v`, `c:a`, `crf`, `preset`, `b:v`, `b:a` keys
  - CRF must be 0-51, preset must be valid x264 preset
  - Codec must be H.264 (libx264) for video, AAC for audio

- **test_quality_settings_no_duplicate_parameters**: No duplicate keys that would conflict

- **test_subtitle_path_normalization_handles_special_chars**: Paths normalized for FFmpeg
  - Windows: Backslashes and colons escaped
  - Linux: Paths returned unchanged

- **test_subtitle_style_string_is_valid_ass_format**: Subtitle style valid ASS format
  - Must contain: FontName, FontSize, PrimaryColour, OutlineColour, etc.
  - No newlines or carriage returns

- **test_motion_background_stream_parameters_are_valid**: Motion background stream parameters
  - Validates zoompan filter exists
  - FPS set correctly

- **test_audio_duration_extraction_is_accurate**: Duration extracted accurately
  - Tolerance: ±10ms

### 2. TestVideoInputValidation (4 tests)
Validates input files before attempting video generation:

- **test_validate_input_files_rejects_missing_audio**: Missing audio file rejected immediately
- **test_validate_input_files_rejects_missing_subtitle**: Missing subtitle file rejected immediately
- **test_validate_input_files_rejects_invalid_audio**: Invalid audio format rejected
- **test_validate_input_files_accepts_valid_files**: Valid files accepted

### 3. TestVideoOutputIntegrity (3 tests)
Validates video output files meet minimum quality standards:

- **test_video_info_extraction_validates_codec**: Codec must be H.264
- **test_video_info_extraction_validates_resolution**: Resolution must be 1920x1080
- **test_generated_video_must_have_nonzero_size**: File size ≥10KB

### 4. TestFrameEncodingProgress (4 tests)
Validates FFmpeg encodes all frames, not just the first frame:

- **test_ffmpeg_run_is_called_with_correct_parameters**: FFmpeg called with correct params
- **test_ffmpeg_error_handling_captures_stderr**: FFmpeg stderr captured when it fails
- **test_video_duration_matches_audio_duration**: Video duration = audio duration (±100ms)
- **test_video_frame_count_matches_duration_and_fps**: Frame count = duration × FPS (±2 frames)

### 5. TestFFmpegFailureScenarios (4 tests)
Test specific failure scenarios that cause FFmpeg to stop encoding:

- **test_subtitle_file_must_exist_during_encoding**: Subtitle file not deleted before FFmpeg finishes
- **test_background_image_must_be_valid_format**: Background image valid PNG/JPEG
- **test_audio_file_must_have_valid_codec**: Audio file decodable by FFmpeg
- **test_subtitle_encoding_must_be_utf8**: Subtitle file UTF-8 encoded for Japanese

### 6. TestVideoGenerationEndToEnd (3 tests)
End-to-end tests validating complete video generation pipeline:

- **test_minimal_video_generation_succeeds**: 1-second video generated successfully
- **test_video_generation_with_japanese_subtitles**: Japanese subtitles rendered correctly
- **test_video_generation_with_long_duration** (slow): 10+ second video without stopping

## Running Tests

### Quick validation (recommended for development)
```bash
# Run all tests except slow ones (should complete in ~1-2 minutes)
pytest tests/integration/test_video_generation_strict.py -v -m "not slow"
```

### Run specific test classes
```bash
# FFmpeg command validation only (fast, <1s)
pytest tests/integration/test_video_generation_strict.py::TestFFmpegCommandValidation -v

# Input validation tests (fast, <1s)
pytest tests/integration/test_video_generation_strict.py::TestVideoInputValidation -v

# Output integrity tests (medium, ~10s)
pytest tests/integration/test_video_generation_strict.py::TestVideoOutputIntegrity -v

# Frame encoding tests (slow, ~30s)
pytest tests/integration/test_video_generation_strict.py::TestFrameEncodingProgress -v

# Failure scenario tests (medium, ~10s)
pytest tests/integration/test_video_generation_strict.py::TestFFmpegFailureScenarios -v

# End-to-end tests (very slow, ~60s)
pytest tests/integration/test_video_generation_strict.py::TestVideoGenerationEndToEnd -v
```

### Run with slow tests included
```bash
# WARNING: This can take 5+ minutes
pytest tests/integration/test_video_generation_strict.py -v
```

## Known FFmpeg Issue

**Current Status**: Both primary and fallback video generation stop after encoding only 1 frame.

**Symptoms:**
```
frame=    1 fps=0.3 q=0.0 size=       0kB time=00:00:00.00 bitrate=N/A speed=   0x
[swscaler @ 0x...] Warning: data is not aligned! This can lead to a speed loss
ERROR: Video generation failed: ffmpeg error (see stderr output for detail)
```

**Analysis:**
- FFmpeg initializes correctly (libx264 loaded, subtitle filter loaded, streams mapped)
- Encoding starts but stops immediately after first frame
- Exit code 0 (no error from FFmpeg perspective)
- Duration 10:34 audio = ~15,853 frames expected @ 25fps, but only 1 frame encoded
- Warning about data alignment suggests possible memory/buffer issue

**Location**: `app/video.py` lines 464-480 (_run_ffmpeg method)

**Tests that will fail until this is fixed:**
- test_video_duration_matches_audio_duration
- test_video_frame_count_matches_duration_and_fps
- test_minimal_video_generation_succeeds
- test_video_generation_with_japanese_subtitles
- test_video_generation_with_long_duration

## Test Design Decisions

### Why no mocking?
These tests validate **actual video generation**, not mocked behavior. Mocking would hide the real FFmpeg issues.

### Why so strict?
The user explicitly requested "no fallback strategy" and "most strict tests". These tests enforce:
- Exact parameter validation
- Frame-by-frame encoding verification
- Output file integrity checks
- No tolerance for partial success

### Why separate from unit tests?
These are integration tests that:
- Execute real FFmpeg commands
- Generate actual video files
- Require FFmpeg/ffprobe installed
- Take longer to run

## Maintenance

### Adding new tests
1. Add to appropriate test class based on what you're testing
2. Mark slow tests with `@pytest.mark.slow`
3. Use `tempfile.TemporaryDirectory()` for all file operations
4. Clean up resources in `finally` blocks if not using context managers

### Updating expectations
When video generation behavior changes:
1. Run tests to see which fail
2. Update assertions to match new expected behavior
3. Document why the change was necessary
4. Re-run to confirm all tests pass

## Related Files

- `app/video.py` - VideoGenerator class (main implementation)
- `app/video.py:464-480` - _run_ffmpeg method (current failure point)
- `app/config/settings.py` - Video quality settings
- `tests/unit/adapters/test_llm_output_format.py` - LLM output tests (31 tests passing)
- `tests/integration/test_gemini_output_formats.py` - Gemini format tests (27 tests passing)

## Test Statistics

- **Total Tests:** 24 (23 excluding slow tests)
- **Current Status:** ⚠️ FFmpeg encoding issue blocks 5 tests
- **Expected Runtime:**
  - Fast tests (command validation, input validation): <5s
  - Medium tests (output integrity, failure scenarios): ~20s
  - Slow tests (end-to-end): ~60s
- **Dependencies:** FFmpeg 4.4+, ffprobe, PIL/Pillow, pydub

## Next Steps

1. **Fix FFmpeg encoding issue** - Investigate why encoding stops after 1 frame
2. **Run all tests** - Once fixed, validate all 24 tests pass
3. **Add to CI/CD** - Integrate into automated test pipeline
4. **Monitor production** - Ensure video generation works end-to-end
