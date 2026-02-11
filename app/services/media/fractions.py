"""Utility helpers for parsing ffprobe-style fraction strings."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
@dataclass(frozen=True)
class FractionParseResult:
    """Represents the outcome of parsing a fraction string."""
    value: float
    is_valid: bool
    raw: Optional[str] = None
class FractionParser:
    """Parses fraction strings like ``"30000/1001"`` from ffprobe metadata."""
    def __init__(self, *, default: float = 0.0) -> None:
        self._default = default
    def parse(self, value: Optional[str]) -> FractionParseResult:
        """Attempt to parse ``value`` into a float, falling back to ``default``."""
        if value is None:
            return FractionParseResult(self._default, False, value)
        text = value.strip()
        if not text:
            return FractionParseResult(self._default, False, value)
        try:
            if "/" in text:
                numerator_text, denominator_text = text.split("/", 1)
                numerator = float(numerator_text)
                denominator = float(denominator_text)
                if denominator == 0:
                    return FractionParseResult(self._default, False, value)
                return FractionParseResult(numerator / denominator, True, value)
            return FractionParseResult(float(text), True, value)
        except (TypeError, ValueError):
            return FractionParseResult(self._default, False, value)
