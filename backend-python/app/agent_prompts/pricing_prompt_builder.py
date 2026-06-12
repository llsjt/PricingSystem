"""Compatibility entry point for pricing prompt construction.

The concrete CrewAI task prompts still live in ``app.crew.crew_factory`` while
M4 extraction proceeds. Keeping this module gives prompt-versioned callers a
stable import path without changing runtime prompt text.
"""

from app.crew.crew_factory import build_pricing_crew

__all__ = ["build_pricing_crew"]

