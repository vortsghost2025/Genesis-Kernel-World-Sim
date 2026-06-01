"""
World Sim Configuration

Per-agent NIM key management, world settings, simulation controls, and video config.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

PROVIDER_MODES = ("mock", "nim-dry-run", "nim-live")


@dataclass
class AgentConfig:
    """Configuration for a single agent."""
    name: str
    role: str = ""
    provider: str = "mock"
    model: str = "meta/llama-3.1-8b-instruct"
    key_env: str = ""
    traits: dict[str, float] = field(default_factory=dict)
    enabled: bool = True


@dataclass
class VideoConfig:
    """Video generation and HLS streaming configuration."""
    enabled: bool = False
    segment_duration_s: int = 18
    regen_interval_ticks: int = 5
    image_provider: str = "mock"  # "mock", "nim-live", "nim-dry-run"
    image_model: str = "qwen/qwen-image-2512"
    tts_provider: str = "mock"  # "mock", "riva"
    output_dir: str = "data/stream"
    fps: int = 24

    @classmethod
    def from_env(cls) -> "VideoConfig":
        """Load Video configuration from environment variables."""
        return cls(
            enabled=os.environ.get("VIDEO_ENABLED", "false").lower() == "true",
            segment_duration_s=int(os.environ.get("VIDEO_SEGMENT_DURATION", "18")),
            regen_interval_ticks=int(os.environ.get("VIDEO_REGEN_INTERVAL", "5")),
            image_provider=os.environ.get("VIDEO_IMAGE_PROVIDER", "mock"),
            image_model=os.environ.get("VIDEO_IMAGE_MODEL", "qwen/qwen-image-2512"),
            tts_provider=os.environ.get("VIDEO_TTS_PROVIDER", "mock"),
            output_dir=os.environ.get("VIDEO_OUTPUT_DIR", "data/stream"),
            fps=int(os.environ.get("VIDEO_FPS", "24")),
        )


@dataclass
class WorldSimConfig:
    """Global simulation configuration."""
    provider_mode: str = "mock"
    tick_interval_ms: int = 5000
    max_ticks: int = 0  # 0 = unlimited
    save_interval: int = 10
    agents: dict[str, AgentConfig] = field(default_factory=dict)
    video_config: VideoConfig = field(default_factory=lambda: VideoConfig.from_env())

    @classmethod
    def from_env(cls) -> "WorldSimConfig":
        """Load configuration from environment variables."""
        config = cls(
            provider_mode=os.environ.get("WORLD_PROVIDER_MODE", "mock"),
            tick_interval_ms=int(os.environ.get("WORLD_TICK_INTERVAL", "5000")),
            max_ticks=int(os.environ.get("WORLD_MAX_TICKS", "0")),
            save_interval=int(os.environ.get("WORLD_SAVE_INTERVAL", "10")),
        )

        # Load agent configs from environment
        # Format: AGENT_<NAME>_PROVIDER, AGENT_<NAME>_MODEL, AGENT_<NAME>_KEY_ENV
        agent_names = os.environ.get("WORLD_AGENTS", "Adam,Eve").split(",")
        for name in agent_names:
            name = name.strip()
            if not name:
                continue
            prefix = f"AGENT_{name.upper()}"
            agent = AgentConfig(
                name=name,
                role=os.environ.get(f"{prefix}_ROLE", ""),
                provider=os.environ.get(f"{prefix}_PROVIDER", "mock"),
                model=os.environ.get(f"{prefix}_MODEL", "meta/llama-3.1-8b-instruct"),
                key_env=os.environ.get(f"{prefix}_KEY_ENV", f"{prefix}_NIM_KEY"),
                enabled=os.environ.get(f"{prefix}_ENABLED", "true").lower() == "true",
            )
            config.agents[name] = agent

        return config

    def get_agent_key(self, agent_name: str) -> str:
        """Get API key for an agent from environment."""
        agent = self.agents.get(agent_name)
        if not agent or not agent.key_env:
            return ""
        return os.environ.get(agent.key_env, "")

    def add_agent(self, name: str, role: str = "", model: str = "", key_env: str = "") -> None:
        """Add a new agent to the simulation."""
        if name not in self.agents:
            self.agents[name] = AgentConfig(
                name=name,
                role=role,
                model=model or "meta/llama-3.1-8b-instruct",
                key_env=key_env or f"AGENT_{name.upper()}_NIM_KEY",
            )

    def remove_agent(self, name: str) -> None:
        """Remove an agent from the simulation."""
        if name in self.agents:
            del self.agents[name]

    def validate(self) -> list[str]:
        """Validate configuration. Returns list of warnings."""
        warnings: list[str] = []
        if self.provider_mode not in PROVIDER_MODES:
            warnings.append(f"Unknown provider_mode: {self.provider_mode!r}")
        for name, agent in self.agents.items():
            if agent.provider not in PROVIDER_MODES:
                warnings.append(f"Agent {name}: unknown provider {agent.provider!r}")
            if agent.provider == "nim-live" and not self.get_agent_key(name):
                warnings.append(f"Agent {name}: nim-live mode but no key configured")
        return warnings


# Global config instance
config = WorldSimConfig.from_env()
