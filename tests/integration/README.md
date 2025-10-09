# Integration Tests for Gemini LLM Output Formats

## Overview

This test suite provides comprehensive validation of LLM output format handling with Gemini API.

**Test Coverage:**
- ✅ **27 Unit Tests** - Mock-based tests for YAML parsing logic (no API calls)
- ✅ **5 Integration Tests** - Real Gemini API calls to validate output formats

## Test Categories

### 1. TestExtractStructuredYAML (8 tests)
Tests the `extract_structured_yaml()` function with various edge cases:
- Markdown code fences (```yaml, ```yml)
- Japanese content preservation
- Nested structures
- Double-wrapped YAML strings
- Invalid/empty inputs
- List structures

### 2. TestParseYAMLFromGemini (6 tests)
Tests agent-specific YAML parsing logic:
- RAW output agents (`script_writer`, `japanese_purity_polisher`)
- Structured output agents (requires valid YAML)
- Markdown wrapper handling
- Preface text ignoring

### 3. TestMalformedOutputHandling (8 tests)
Tests robustness against malformed outputs:
- JSON vs YAML formats
- Mixed syntax
- Incomplete markdown fences
- Special characters (emojis, quotes)
- Multiline strings
- Error cases (scalars, lists vs dicts)

### 4. TestPerformanceAndEdgeCases (5 tests)
Tests performance and unusual inputs:
- Large YAML outputs (100+ items)
- Unicode escape sequences
- YAML comments
- Empty mappings
- Key order preservation

### 5. TestGeminiRealAPIOutputFormats (5 tests - Integration)
Tests with real Gemini API calls:
- Valid YAML generation from structured prompts
- Japanese YAML generation
- Schema-based structured output
- Complex nested structures
- Round-trip parsing

## Running Tests

### Unit Tests Only (Fast, No API Calls)

```bash
# Run all non-integration tests (recommended for CI/development)
pytest tests/integration/test_gemini_output_formats.py -v -m "not integration"

# Should see: 27 passed, 5 deselected
```

### Integration Tests (Real API Calls, Requires API Key)

**⚠️ Warning:** Integration tests make real API calls to Gemini and will consume quota.

```bash
# Set API key
export GEMINI_API_KEY="your-actual-gemini-api-key"

# Run integration tests only
pytest tests/integration/test_gemini_output_formats.py -v -m integration

# Run all tests (unit + integration)
pytest tests/integration/test_gemini_output_formats.py -v
```

### Running Specific Test Classes

```bash
# Run only extraction tests
pytest tests/integration/test_gemini_output_formats.py::TestExtractStructuredYAML -v

# Run only parser tests
pytest tests/integration/test_gemini_output_formats.py::TestParseYAMLFromGemini -v

# Run only malformed handling tests
pytest tests/integration/test_gemini_output_formats.py::TestMalformedOutputHandling -v

# Run only real API tests (requires API key)
pytest tests/integration/test_gemini_output_formats.py::TestGeminiRealAPIOutputFormats -v
```

## Test Results

### Current Status

✅ **Unit Tests: 27/27 passing** (0.3s runtime)
- All YAML extraction edge cases validated
- Agent-specific parsing logic verified
- Malformed output handling robust
- Performance tests passing

⚠️ **Integration Tests: Requires manual run with API key**
- Blocked by test safety mechanism (litellm stub in conftest.py)
- To run: Ensure `GEMINI_API_KEY` is set and litellm is properly imported
- Expected runtime: ~30-60 seconds (5 API calls)

## Test Design Principles

### 1. No Fallbacks - Direct Fixes Only
These tests validate that the actual parsing logic works correctly, not that error handling masks failures.

### 2. Real-World Edge Cases
Test cases based on actual Gemini response patterns observed in production:
- YAML wrapped in markdown fences
- Preface text before structured output
- Japanese content mixed with YAML
- Double-wrapped YAML strings (recursive parsing)

### 3. Comprehensive Coverage
- Positive cases: Valid YAML in various formats
- Negative cases: Malformed/invalid inputs
- Edge cases: Empty, large, special characters
- Integration: Real API behavior validation

## Common Issues & Solutions

### Issue: "litellm is not installed; stub completion invoked"
**Cause:** Test safety mechanism prevents accidental API calls
**Solution:** Integration tests require explicit setup. litellm must be importable before conftest.py loads.

### Issue: YAML parsing returns None
**Cause:** Pattern doesn't match expected format
**Fix:** Check if using correct markdown fence (```yaml or ```yml), not ```json

### Issue: RAW agent returns dict instead of string
**Cause:** Input accidentally contains valid YAML (e.g., `key: value`)
**Fix:** Use plain sentences without colons for RAW output tests

## Maintenance

### Adding New Tests

1. **Unit Tests** - Add to appropriate test class, no `@pytest.mark.integration` needed
2. **Integration Tests** - Add to `TestGeminiRealAPIOutputFormats`, mark with `@pytest.mark.integration`

### Updating Expectations

When Gemini output format changes:
1. Run unit tests first to isolate parsing logic issues
2. Check integration tests to see real API behavior
3. Update extraction logic in `app/adapters/llm.py:extract_structured_yaml()`
4. Update test expectations to match new behavior

## Related Files

- `app/adapters/llm.py` - LLM client and YAML extraction logic
- `app/crew/agent_review.py` - Agent-specific YAML parsing
- `tests/unit/adapters/test_llm_output_format.py` - Original unit tests (3 tests)
- `tests/conftest.py` - Shared test fixtures and configuration

## Test Statistics

- **Total Tests:** 32 (27 unit + 5 integration)
- **Coverage:** YAML extraction, agent parsing, error handling, real API validation
- **Runtime:** <1s (unit only), ~30-60s (with integration)
- **API Calls:** 0 (unit only), 5 (with integration)
- **Dependencies:** pytest, pyyaml, app modules (litellm for integration)
