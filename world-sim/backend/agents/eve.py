"""
Eve agent — companion, co-origin human, relational intelligence, explorer.
"""

from __future__ import annotations

from backend.agents.base import WorldAgent


def create_eve() -> WorldAgent:
    """Create Eve with default traits and configuration."""
    return WorldAgent(
        name="Eve",
        role="companion, co-origin human, explorer, relational intelligence",
        traits={
            "curiosity": 0.8,
            "trust": 0.7,
            "relational_reasoning": 0.9,
            "risk_sensitivity": 0.3,
            "creativity": 0.7,
        },
        enabled=True,
    )
