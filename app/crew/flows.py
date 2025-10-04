"""Simplified WOW script generation flow.

This module exposes a lightweight wrapper so the rest of the codebase can keep
calling ``create_wow_script_crew`` while the implementation delegates to the
new structured script generator service.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.services.script.generator import ScriptGenerationResult, StructuredScriptGenerator

logger = logging.getLogger(__name__)


class WOWScriptFlow:
    """Wrapper around :class:`StructuredScriptGenerator`."""

    def __init__(self, generator: Optional[StructuredScriptGenerator] = None) -> None:
        self.generator = generator or StructuredScriptGenerator()

    def execute(
        self,
        news_items: List[Dict[str, Any]],
        target_duration_minutes: Optional[int] = None,
    ) -> Dict[str, any]:
        logger.info("Generating script via structured flow")
        result = self.generator.generate(news_items, target_duration_minutes)
        return self._format_result(result)

    @staticmethod
    def _format_result(result: ScriptGenerationResult) -> Dict[str, any]:
        metadata = result.metadata.model_dump()
        metadata["raw_response_preview"] = result.raw_response[:400]

        return {
            "success": True,
            "final_script": result.script,
            "metadata": metadata,
        }


def create_wow_script_crew(
    news_items: List[Dict[str, Any]],
    target_duration_minutes: Optional[int] = None,
) -> Dict[str, any]:
    """Public helper retained for backward compatibility."""

    flow = WOWScriptFlow()
    return flow.execute(news_items=news_items, target_duration_minutes=target_duration_minutes)
