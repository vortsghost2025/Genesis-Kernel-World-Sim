"""
Adam agent — first human, gardener, namer, builder.
"""

from __future__ import annotations

from backend.agents.base import WorldAgent


def create_adam() -> WorldAgent:
    """Create Adam with default traits and configuration."""
    return WorldAgent(
        name="Adam",
        role="first human, gardener, namer, builder",
        traits={
            "curiosity": 0.5,
            "responsibility": 0.8,
            "strength": 0.7,
            "creativity": 0.6,
            "loneliness": 0.9,
        },
        enabled=True,
    )
