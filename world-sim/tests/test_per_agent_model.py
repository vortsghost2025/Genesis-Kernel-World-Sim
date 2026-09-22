"""Tests for per-agent model override (10JB cognitive diversity)."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

import backend.world.first_pair_cognition_model as cmod
from backend.world.first_pair_cognition_model import (
    ModelCognitionBackend,
    ProviderConfig,
    resolve_provider,
)


def _set_provider_env(monkeypatch, model="test-model", base="https://test.example.com"):
    for k in (
        "GENESIS_FIRST_PAIR_BASE_URL", "GENESIS_FIRST_PAIR_API_KEY",
        "GENESIS_FIRST_PAIR_MODEL", "GENESIS_FIRST_PAIR_FALLBACK_MODEL",
        "GENESIS_FIRST_PAIR_MODEL_EAST_ADAM", "GENESIS_FIRST_PAIR_MODEL_EAST_EVE",
        "NVIDIA_API_KEY", "OPENROUTER_API_KEY", "OLLAMA_HOST",
    ):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("GENESIS_FIRST_PAIR_BASE_URL", base)
    monkeypatch.setenv("GENESIS_FIRST_PAIR_API_KEY", "test-key")
    monkeypatch.setenv("GENESIS_FIRST_PAIR_MODEL", model)


class TestPerAgentModel:
    def test_adam_gets_adam_model(self, monkeypatch):
        _set_provider_env(monkeypatch, model="default-model")
        monkeypatch.setenv("GENESIS_FIRST_PAIR_MODEL_EAST_ADAM", "adam-specific-model")
        monkeypatch.setenv("GENESIS_FIRST_PAIR_MODEL_EAST_EVE", "eve-specific-model")

        backend = ModelCognitionBackend("east_adam")
        assert backend.model_name == "adam-specific-model"

    def test_eve_gets_eve_model(self, monkeypatch):
        _set_provider_env(monkeypatch, model="default-model")
        monkeypatch.setenv("GENESIS_FIRST_PAIR_MODEL_EAST_ADAM", "adam-specific-model")
        monkeypatch.setenv("GENESIS_FIRST_PAIR_MODEL_EAST_EVE", "eve-specific-model")

        backend = ModelCognitionBackend("east_eve")
        assert backend.model_name == "eve-specific-model"

    def test_no_override_uses_default(self, monkeypatch):
        _set_provider_env(monkeypatch, model="default-model")
        backend = ModelCognitionBackend("east_adam")
        assert backend.model_name == "default-model"

    def test_one_override_only_affects_that_agent(self, monkeypatch):
        _set_provider_env(monkeypatch, model="default-model")
        monkeypatch.setenv("GENESIS_FIRST_PAIR_MODEL_EAST_ADAM", "adam-only")

        adam_backend = ModelCognitionBackend("east_adam")
        eve_backend = ModelCognitionBackend("east_eve")
        assert adam_backend.model_name == "adam-only"
        assert eve_backend.model_name == "default-model"

    def test_blank_override_uses_default(self, monkeypatch):
        _set_provider_env(monkeypatch, model="default-model")
        monkeypatch.setenv("GENESIS_FIRST_PAIR_MODEL_EAST_ADAM", "  ")

        backend = ModelCognitionBackend("east_adam")
        assert backend.model_name == "default-model"

    def test_per_agent_models_on_same_provider(self, monkeypatch):
        _set_provider_env(monkeypatch, model="default-model")
        monkeypatch.setenv("GENESIS_FIRST_PAIR_MODEL_EAST_ADAM", "adam-model")
        monkeypatch.setenv("GENESIS_FIRST_PAIR_MODEL_EAST_EVE", "eve-model")

        adam = ModelCognitionBackend("east_adam")
        eve = ModelCognitionBackend("east_eve")
        assert adam.model_name == "adam-model"
        assert eve.model_name == "eve-model"
        assert adam.provider_type == eve.provider_type
