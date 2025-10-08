# Bugfix Status - Workflow Instability Issues

**Date:** 2025-10-09
**Severity:** 🔴 CRITICAL
**Impact:** Script generation crashes, metadata loss, video generation failures

## Executive Summary

Three uncommitted local changes are causing systematic workflow failures:
1. ❌ **Script Generation:** Removed YAML recursion → `RecursionDepthExceeded` crashes
2. ❌ **Metadata Storage:** Changed Sheets range `A:Z`→`A1` → data not saved
3. ⚠️ **Video Generation:** Duplicate FFmpeg compilation → resource waste, potential bugs

## Bug Details

### 🔴 Bug #1: Script Generation Recursion Failure
**File:** `app/services/script/generator.py:249`
**Status:** 🔧 FIXING
**Logs:** `ERROR app.script_gen | maximum recursion depth exceeded`

```python
# CURRENT (BROKEN):
if isinstance(decoded, str):
    raise ValueError('YAML decoded to a string, not a mapping')

# SHOULD BE:
if isinstance(decoded, str):
    return StructuredScriptGenerator._load_yaml_mapping(decoded)
```

**Root Cause:** During JSON→YAML migration (commit `6cf55df`), recursive YAML unwrapping was removed. When LLMs return YAML wrapped in strings, parsing fails.

**Impact:** Step 2 (script_generation) crashes, killing entire workflow.

---

### 🔴 Bug #2: Google Sheets Range Error
**File:** `app/metadata_storage.py:506`
**Status:** 🔧 FIXING
**Logs:** Silent failures, data not appearing in Sheets

```python
# CURRENT (BROKEN):
range_name = f"{sheet_name}!A1"  # Single cell reference

# SHOULD BE:
range_name = f"{sheet_name}!A:Z"  # Column range for append
```

**Root Cause:** Uncommitted local change broke Google Sheets API append operations. The API requires column range notation (`A:Z`) for `.append()` calls, not single cell references (`A1`).

**Impact:**
- Line 378: `update_video_stats()` fails → no YouTube metrics saved
- Line 458: `log_execution()` fails → workflow results not recorded
- Feedback loop broken, A/B testing data lost

---

### ⚠️ Bug #3: FFmpeg Duplicate Compilation
**File:** `app/video.py:462-463`
**Status:** 🔧 FIXING
**Logs:** `ERROR app.video | ffmpeg rendering primary video stderr:`

```python
# CURRENT (INEFFICIENT):
def _run_ffmpeg(self, stream, *, description: str) -> None:
    cmd = stream.compile()  # First compile
    logger.info(f'Running ffmpeg command: {" ".join(cmd)}')
    try:
        ffmpeg.run(stream, cmd=self.ffmpeg_path or 'ffmpeg', ...)  # Second compile

# SHOULD BE:
def _run_ffmpeg(self, stream, *, description: str) -> None:
    try:
        ffmpeg.run(stream, cmd=self.ffmpeg_path or 'ffmpeg', ...)
    except ffmpeg.Error as error:
        logger.error('ffmpeg %s failed: %s', description, error)
```

**Root Cause:** Added debugging without understanding `ffmpeg.run()` also compiles internally.

**Impact:**
- Wastes CPU on duplicate compilation
- Potential state bugs if stream object mutates
- Contributing factor to video generation instability

---

## Additional Context Issues

### 📌 Historical Pattern: Removed Error Handling
**Commit:** `c4f968c` - "refactor: surface metadata storage failures"

**Change:** Removed try-catch blocks from metadata storage:
```python
# BEFORE:
try:
    self._save_to_sheets(...)
except Exception as e:
    logger.warning(f"Failed to save to Sheets: {e}")

# AFTER:
self._save_to_sheets(...)  # Now crashes workflow on Sheets errors
```

**Intent:** "Surface" failures for debugging
**Reality:** Workflow crashes instead of gracefully falling back to CSV

---

### 📌 Architecture Issue: No Graceful Degradation
**File:** `app/main.py:237-265`

```python
for index in range(run_state.start_index, len(self.steps)):
    result = await step.execute(run_state.context)
    if not getattr(result, "success", False):
        return AttemptOutcome(status=AttemptStatus.FAILURE)  # STOP EVERYTHING
```

**Problem:** One failure in 13-step pipeline = total workflow loss. No partial recovery, no fallback paths.

---

## Linting Issues (Non-Critical)

**File:** `app/services/script/generator.py`
- ❌ Unsorted imports (I001)
- ❌ Missing newline at EOF (W292)

**File:** `app/video.py`
- ❌ Unsorted imports (I001)
- ❌ Missing newline at EOF (W292)

---

## Fix Plan

### Phase 1: Critical Bugs (Immediate)
- [ ] Fix `generator.py:249` - Restore YAML recursion
- [ ] Fix `metadata_storage.py:506` - Restore `A:Z` range
- [ ] Fix `video.py:462` - Remove duplicate compile
- [ ] Fix linting issues (imports, newlines)
- [ ] Run unit tests to verify

### Phase 2: Defensive Improvements (Next)
- [ ] Add try-catch protection back to `metadata_storage.py`
- [ ] Add fallback for Sheets→CSV when Sheets unavailable
- [ ] Add retry logic for script generation
- [ ] Improve FFmpeg error logging (capture stderr properly)

### Phase 3: Architecture Hardening (Later)
- [ ] Implement circuit breakers for non-critical steps
- [ ] Add partial workflow recovery (save progress, resume from checkpoint)
- [ ] Separate critical path (news→script→video) from optional (Sheets, YouTube stats)
- [ ] Add telemetry for failure pattern analysis

---

## Test Evidence

**Unit Tests:** ✅ 31/31 passing (bugs are in integration layer)
**Integration Tests:** No tests exist (0 collected)
**Production Logs:** 4/5 recent runs failed with these exact errors

**Failure Rate:**
- `session_20251008_183809`: Script recursion crash
- `session_20251008_184744`: Video generation failure
- `session_20251008_223257`: Video generation failure
- `session_20251008_223500`: Test failure (expected)

---

## References

- **CLAUDE.md:** Documents Phase 3 FFmpeg parameter duplication fix (line 309)
- **Commit 6cf55df:** JSON→YAML migration introduced recursion bug
- **Commit c4f968c:** Removed error handling for "surfacing failures"
- **Git diff:** Shows uncommitted local changes causing bugs

---

## Status Tracking

**Started:** 2025-10-09 (current time)
**ETA:** 15 minutes for Phase 1 fixes
**Blocked:** None
**Next Steps:** Apply fixes in order, run tests, verify workflow completes
