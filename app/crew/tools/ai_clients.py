"""Compatibility shim redirecting to the adapter layer."""

from app.adapters.llm import (
    AIClient,
    AIClientFactory,
    CrewAIGeminiLLM,
    GeminiClient,
    LLMClient,
    get_crewai_gemini_llm,
)
from app.adapters.search import PerplexityClient

__all__ = [
    "AIClient",
    "AIClientFactory",
    "CrewAIGeminiLLM",
    "GeminiClient",
    "LLMClient",
    "PerplexityClient",
    "get_crewai_gemini_llm",
]
