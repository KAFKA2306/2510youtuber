"""Utilities for managing configured speakers and their aliases."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Dict, Iterable, List, Optional

from app.config.settings import SpeakerConfig, settings


LEGACY_SPEAKER_ALIASES: Dict[str, str] = {"田中": "武宏", "鈴木": "つむぎ", "司会": "ナレーター"}


@dataclass(frozen=True)
class SpeakerRegistry:
    """Access helper around configured TTS speaker definitions."""

    voice_configs: Dict[str, SpeakerConfig]

    @property
    def canonical_names(self) -> List[str]:
        return list(self.voice_configs.keys())

    @property
    def alias_map(self) -> Dict[str, str]:
        mapping: Dict[str, str] = {}
        for name in self.canonical_names:
            stripped = name.strip()
            if stripped:
                mapping[stripped] = stripped

        for legacy_name, canonical in LEGACY_SPEAKER_ALIASES.items():
            if canonical in mapping:
                mapping.setdefault(legacy_name, canonical)
            else:
                # keep legacy alias pointing to itself when canonical missing
                mapping.setdefault(legacy_name, legacy_name)

        return mapping

    def canonicalize(self, label: Optional[str]) -> Optional[str]:
        if not label:
            return None
        return self.alias_map.get(label.strip(), label.strip())

    def aliases_regex_pattern(self, additional_aliases: Iterable[str] = ()) -> str:
        aliases = set(self.alias_map.keys()) | {alias for alias in additional_aliases if alias}
        ordered = sorted(aliases, key=len, reverse=True)
        if not ordered:
            return ""
        import re

        return "|".join(re.escape(alias) for alias in ordered)

    def get_voice_config(self, speaker: str) -> Optional[SpeakerConfig]:
        canonical = self.canonicalize(speaker)
        if canonical and canonical in self.voice_configs:
            return self.voice_configs[canonical]
        return None


@lru_cache(maxsize=1)
def get_speaker_registry() -> SpeakerRegistry:
    """Return a cached registry built from the current application settings."""

    return SpeakerRegistry(voice_configs=settings.tts_voice_configs)

