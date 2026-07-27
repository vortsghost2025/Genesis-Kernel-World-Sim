"""Phase 10FQ — Model-backed First Pair cognition.

Implements the CognitionBackend interface for OpenAI-compatible providers
(Ollama, OpenRouter, NVIDIA NIM, OpenAI-compatible endpoints). All calls
are bounded, validated, and never leak private cross-agent memory.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from typing import Any

from openai import OpenAI

from backend.world.first_pair_cognition_interface import (
    AgentContext,
    CognitionBackend,
    CognitionOutput,
)

# ---------------------------------------------------------------------------
# Provider selection helpers
# ---------------------------------------------------------------------------

_SAFE_ID_CHARS = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.-"
)


def _is_safe_id(value: str) -> bool:
    return (
        isinstance(value, str)
        and 1 <= len(value) <= 128
        and all(c in _SAFE_ID_CHARS for c in value)
    )


def _resolve_provider() -> dict:
    """Return {'base_url': str, 'api_key': str | None, 'model': str}."""
    base = os.environ.get("GENESIS_FIRST_PAIR_BASE_URL", "").strip()
    key = os.environ.get("GENESIS_FIRST_PAIR_API_KEY", "").strip()
    model = os.environ.get("GENESIS_FIRST_PAIR_MODEL", "").strip()

    if base and model:
        return {"base_url": base.rstrip("/") + "/v1", "api_key": key or None, "model": model}

    nv_key = os.environ.get("NVIDIA_API_KEY", "").strip()
    if nv_key:
        return {
            "base_url": "https://integrate.api.nvidia.com/v1",
            "api_key": nv_key,
            "model": model or "nvidia/llama-3.1-nemotron-70b-instruct",
        }

    or_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if or_key:
        return {
            "base_url": "https://openrouter.ai/api/v1",
            "api_key": or_key,
            "model": "openrouter/auto",
        }

    ollama_host = os.environ.get("OLLAMA_HOST", "http://localhost:11434").strip()
    return {
        "base_url": ollama_host.rstrip("/") + "/v1",
        "api_key": None,
        "model": model or "llama3.2",
    }


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

_FORBIDDEN_MARKERS = (
    "true_map",
    "known_map",
    "hidden_substrate",
    "world-sim/data",
    "C:\\",
    "D:\\",
    "/root",
    "/home",
    "/etc",
    "/var",
    "/proc",
    "/sys",
    "api_key",
    "access_token",
    "password",
    "secret",
    "private_config",
    ".env",
)

_SUFFIX_REPAIR_MSG = "Repair attempt: validation error — see error field for details."


def _is_clean_text(text: str) -> bool:
    lowered = text.lower()
    return not any(m in lowered for m in _FORBIDDEN_MARKERS)


@dataclass
class ParsedAction:
    action_type: str | None = None
    object_id: str | None = None
    object_type: str | None = None
    description: str | None = None
    tile_id: str | None = None
    target_tile: str | None = None
    reason: str | None = None
    target_object_id: str | None = None
    modifications: dict | None = None
    question_id: str | None = None
    question: str | None = None
    reason_for_asking: str | None = None
    related_goal_id: str | None = None
    requested_human_capability: str | None = None
    urgency: str | None = None
    capability_id: str | None = None
    capability_reason: str | None = None
    message: str | None = None
    recipient: str | None = None


_VALID_ACTIONS = frozenset({
    "no_action",
    "create_public_object",
    "inspect_public_object",
    "modify_owned_public_object",
    "leave_public_message",
    "ask_human",
    "request_capability",
    "move",
})


def _parse_action(raw: Any) -> ParsedAction:
    if not isinstance(raw, dict):
        return ParsedAction()
    at = raw.get("action_type")
    if at not in _VALID_ACTIONS:
        return ParsedAction(action_type=None)
    return ParsedAction(
        action_type=str(at),
        object_id=str(raw.get("object_id") or ""),
        object_type=str(raw.get("object_type") or "generic"),
        description=str(raw.get("description") or ""),
        tile_id=str(raw.get("tile_id") or ""),
        target_tile=str(raw.get("target_tile") or ""),
        reason=str(raw.get("reason") or ""),
        target_object_id=str(raw.get("target_object_id") or ""),
        modifications=raw.get("modifications"),
        question_id=str(raw.get("question_id") or ""),
        question=str(raw.get("question") or ""),
        reason_for_asking=str(raw.get("reason_for_asking") or ""),
        related_goal_id=raw.get("related_goal_id"),
        requested_human_capability=str(raw.get("requested_human_capability") or ""),
        urgency=str(raw.get("urgency") or "low"),
        capability_id=str(raw.get("capability_id") or ""),
        capability_reason=str(raw.get("capability_reason") or ""),
        message=str(raw.get("message") or ""),
        recipient=str(raw.get("recipient") or "all"),
    )


def _validate_goal_update(gu: Any) -> str | None:
    if not isinstance(gu, dict):
        return "not_a_dict"
    for field in ("goal_id", "agent_id", "description", "status"):
        if field not in gu or not isinstance(gu[field], str):
            return f"missing_or_invalid_{field}"
    if gu["status"] not in ("active", "completed", "abandoned", "in_progress"):
        return "invalid_status"
    if not _is_safe_id(gu["goal_id"]):
        return "unsafe_goal_id"
    return None


def _validate_memory(m: Any) -> str | None:
    if not isinstance(m, dict):
        return "not_a_dict"
    if "type" not in m or "content" not in m:
        return "missing_fields"
    if not isinstance(m["type"], str) or not isinstance(m["content"], str):
        return "wrong_type"
    return None


def _validate_question(q: Any) -> str | None:
    if not isinstance(q, dict):
        return "not_a_dict"
    for field in ("question_id", "question", "reason_for_asking"):
        if field not in q or not isinstance(q[field], str):
            return f"missing_or_invalid_{field}"
    if q.get("urgency", "low") not in ("low", "medium", "high"):
        return "invalid_urgency"
    if not _is_safe_id(q["question_id"]):
        return "unsafe_question_id"
    return None


# ---------------------------------------------------------------------------
# Model Output
# ---------------------------------------------------------------------------

@dataclass
class ModelOutput:
    observation_summary: str = ""
    self_model_update: str | None = None
    goal_updates: list[dict] = field(default_factory=list)
    proposed_action: ParsedAction | None = None
    memory_candidates: list[dict] = field(default_factory=list)
    questions_for_humans: list[dict] = field(default_factory=list)
    uncertainty: str = ""
    decision_summary: str = ""
    confidence: float = 0.0
    validation_errors: list[str] = field(default_factory=list)
    is_valid: bool = False


def _validate_model_output(raw: dict) -> ModelOutput:
    errors: list[str] = []

    output = ModelOutput()

    # observation_summary
    obs = raw.get("observation_summary")
    if not isinstance(obs, str) or not obs.strip():
        errors.append("missing_or_invalid_observation_summary")
    elif not _is_clean_text(obs):
        errors.append("contaminated_observation_summary")
    else:
        output.observation_summary = obs

    # self_model_update (optional)
    smu = raw.get("self_model_update")
    if smu is not None:
        if isinstance(smu, str) and _is_clean_text(smu):
            output.self_model_update = smu

    # goal_updates
    goal_updates_raw = raw.get("goal_updates", [])
    if isinstance(goal_updates_raw, list):
        for gu in goal_updates_raw:
            err = _validate_goal_update(gu)
            if err:
                errors.append(f"invalid_goal_update:{err}")
            elif _is_clean_text(gu.get("description", "")):
                output.goal_updates.append(gu)
    else:
        errors.append("goal_updates_not_a_list")

    # proposed_action
    action_raw = raw.get("proposed_action")
    if action_raw is not None:
        parsed = _parse_action(action_raw)
        if parsed.action_type is None:
            errors.append("invalid_or_unknown_action")
        else:
            output.proposed_action = parsed

    # memory_candidates
    mem_raw = raw.get("memory_candidates", [])
    valid_mem: list[dict] = []
    if isinstance(mem_raw, list):
        for m in mem_raw:
            err = _validate_memory(m)
            if err:
                errors.append(f"invalid_memory:{err}")
            elif _is_clean_text(m.get("content", "")):
                valid_mem.append({"type": m["type"], "content": m["content"]})
    output.memory_candidates = valid_mem

    # questions_for_humans
    qs_raw = raw.get("questions_for_humans", [])
    valid_qs: list[dict] = []
    if isinstance(qs_raw, list):
        for q in qs_raw:
            err = _validate_question(q)
            if err:
                errors.append(f"invalid_question:{err}")
            else:
                valid_qs.append(q)
    output.questions_for_humans = valid_qs

    # uncertainty
    unc = raw.get("uncertainty")
    if isinstance(unc, str) and _is_clean_text(unc):
        output.uncertainty = unc

    # decision_summary
    ds = raw.get("decision_summary")
    if isinstance(ds, str) and _is_clean_text(ds):
        output.decision_summary = ds

    # confidence
    conf = raw.get("confidence")
    if isinstance(conf, (int, float)) and 0 <= float(conf) <= 1:
        output.confidence = float(conf)

    output.validation_errors = errors
    output.is_valid = not errors
    return output


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

_AVAILABLE_ACTIONS_DESC = """
Available actions:
- no_action: do nothing this cycle
- create_public_object: create a new object in the world (requires: object_id, object_type, description, tile_id)
- inspect_public_object: examine an existing object (requires: target_object_id)
- modify_owned_public_object: modify one of your own objects (requires: target_object_id, modifications dict)
- leave_public_message: leave a public message (requires: message)
- ask_human: ask a question to the human operator (requires: question_id, question, reason_for_asking, requested_human_capability, urgency)
- request_capability: request a new capability from the human (requires: capability_id, capability_reason)
- move: move to a different tile (requires: target_tile) — currently blocked by habitat configuration
"""


def build_system_prompt(context: AgentContext) -> str:
    goals_str = json.dumps(context.goals, indent=2) if context.goals else "[]"
    unanswered_str = (
        json.dumps(context.unanswered_questions, indent=2)
        if context.unanswered_questions
        else "[]"
    )
    objects_str = (
        json.dumps(
            [v for v in context.world_public_objects.values() if isinstance(v, dict)],
            indent=2,
        )
        if context.world_public_objects
        else "[]"
    )
    mem_str = json.dumps(context.memory, indent=2) if context.memory else "[]"

    return f"""You are {context.canonical_name}, an agent operating inside a constructed world simulation.

Your persistent identity:
- Agent ID: {context.agent_id}
- Canonical name: {context.canonical_name}
- Canonical ref: {context.canonical_ref}

You share this world with Eve (agent ID: genesis-agent-9c37c102cc309769f5c1a4011cf45d629942d9dfd8832dc1ef4079bf593f211a). You are distinct agents with separate private memories.

Current heartbeat: {context.heartbeat_number}
Your position: {context.position}

Your observation:
{json.dumps(context.observation, indent=2)}

Your private memories:
{mem_str}

Your current goals:
{goals_str}

Public world objects at your position:
{objects_str}

Habitat allowed tiles: {context.habitat_allowed_tiles}
Movement allowed: {context.habitat_movement_allowed}

Unresolved questions you have asked:
{unanswered_str}
{_AVAILABLE_ACTIONS_DESC}

You must respond with a single JSON object containing exactly these fields:
- observation_summary (string): a concise summary of what you observe
- self_model_update (string or null): an optional update to your internal self-model
- goal_updates (list): list of goal update objects, each with goal_id, agent_id, description, status
- proposed_action (object or null): a single action object with action_type and type-specific fields, or null to take no action
- memory_candidates (list): list of memory objects, each with type and content
- questions_for_humans (list): list of question objects, each with question_id, question, reason_for_asking, related_goal_id (or null), requested_human_capability, urgency
- uncertainty (string): what you are uncertain about
- decision_summary (string): a concise inspectable explanation of your reasoning
- confidence (float): a value between 0 and 1 indicating your confidence

Do not include any text outside the JSON object. Do not include chain-of-thought.
"""


# ---------------------------------------------------------------------------
# Model Cognition Backend
# ---------------------------------------------------------------------------


class ModelCognitionBackend(CognitionBackend):
    """Cognition backend backed by an OpenAI-compatible model provider."""

    def __init__(self, agent_ref: str) -> None:
        self._agent_ref = agent_ref
        self._config = _resolve_provider()
        self._client = OpenAI(
            base_url=self._config["base_url"],
            api_key=self._config["api_key"],
        )
        self._model = self._config["model"]

    @property
    def provider_type(self) -> str:
        return self._config["base_url"]

    @property
    def model_name(self) -> str:
        return self._model

    def observe_and_orient(self, context: AgentContext) -> CognitionOutput:
        system_prompt = build_system_prompt(context)
        raw_output, err = self._call_model_with_repair(system_prompt, context)

        if err or raw_output is None:
            return CognitionOutput(
                action=None,
                memory_write=[{"type": "error", "content": f"Model call failed: {err}"}],
                goal_updates=None,
                questions_raised=None,
                internal_reasoning=f"Model returned no valid output. {err or ''}",
                confidence=0.0,
            )

        validated = _validate_model_output(raw_output)

        if not validated.is_valid:
            return CognitionOutput(
                action=None,
                memory_write=[{
                    "type": "validation_error",
                    "content": "; ".join(validated.validation_errors),
                }],
                goal_updates=None,
                questions_raised=None,
                internal_reasoning=f"Output validation failed: {'; '.join(validated.validation_errors)}",
                confidence=0.0,
            )

        # Build action from validated ParsedAction
        action: dict | None = None
        if validated.proposed_action and validated.proposed_action.action_type != "no_action":
            pa = validated.proposed_action
            action = {"action_type": pa.action_type}
            if pa.action_type == "create_public_object":
                action["object_id"] = pa.object_id
                action["object_type"] = pa.object_type or "generic"
                action["description"] = pa.description
                action["tile_id"] = pa.tile_id
            elif pa.action_type == "inspect_public_object":
                action["target_object_id"] = pa.target_object_id
            elif pa.action_type == "modify_owned_public_object":
                action["target_object_id"] = pa.target_object_id
                action["modifications"] = pa.modifications or {}
            elif pa.action_type == "leave_public_message":
                action["message"] = pa.message
                action["recipient"] = pa.recipient
            elif pa.action_type == "ask_human":
                action["question_id"] = pa.question_id
                action["question"] = pa.question
                action["reason_for_asking"] = pa.reason_for_asking
                action["related_goal_id"] = pa.related_goal_id
                action["requested_human_capability"] = pa.requested_human_capability
                action["urgency"] = pa.urgency
            elif pa.action_type == "request_capability":
                action["capability_id"] = pa.capability_id
                action["capability_reason"] = pa.capability_reason
            elif pa.action_type == "move":
                action["target_tile"] = pa.target_tile
                action["reason"] = pa.reason

        # Build memory candidates
        memory_write: list[dict] | None = None
        if validated.memory_candidates:
            memory_write = validated.memory_candidates

        # Build goal updates
        goal_updates: list[dict] | None = None
        if validated.goal_updates:
            goal_updates = validated.goal_updates

        # Build questions
        questions: list[dict] | None = None
        if validated.questions_for_humans:
            questions = validated.questions_for_humans

        reasoning_parts = []
        if validated.observation_summary:
            reasoning_parts.append(f"Observed: {validated.observation_summary[:120]}")
        if validated.decision_summary:
            reasoning_parts.append(f"Decided: {validated.decision_summary[:120]}")
        if validated.uncertainty:
            reasoning_parts.append(f"Uncertain about: {validated.uncertainty[:80]}")

        return CognitionOutput(
            action=action,
            memory_write=memory_write,
            goal_updates=goal_updates,
            questions_raised=questions,
            internal_reasoning="; ".join(reasoning_parts) if reasoning_parts else "No cognition details.",
            confidence=validated.confidence,
        )

    def _call_model_with_repair(
        self, system_prompt: str, context: AgentContext
    ) -> tuple[dict | None, str | None]:
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                ],
                temperature=0.3,
                max_tokens=2048,
            )
        except Exception as e:
            return None, str(e)

        raw_text = response.choices[0].message.content if response.choices else None
        if not raw_text or not raw_text.strip():
            return None, "empty_response"

        raw_json = self._extract_json(raw_text)
        if raw_json is None:
            return None, "no_valid_json_in_response"

        validated = _validate_model_output(raw_json)

        if validated.is_valid:
            return raw_json, None

        # One bounded repair attempt
        repair_prompt = (
            f"Your previous response had validation errors: {'; '.join(validated.validation_errors)}\n"
            "Please correct and return only a valid JSON object with the exact required fields.\n"
            f"Original system prompt: {system_prompt[:200]}..."
        )
        try:
            response2 = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "assistant", "content": raw_text},
                    {"role": "user", "content": repair_prompt},
                ],
                temperature=0.2,
                max_tokens=2048,
            )
        except Exception as e:
            return None, f"Repair also failed: {e}"

        raw_text2 = response2.choices[0].message.content if response2.choices else None
        if not raw_text2 or not raw_text2.strip():
            return None, "repair_empty_response"

        raw_json2 = self._extract_json(raw_text2)
        if raw_json2 is None:
            return None, "repair_no_valid_json"

        validated2 = _validate_model_output(raw_json2)
        if validated2.is_valid:
            return raw_json2, None

        return None, f"repair_failed: {'; '.join(validated2.validation_errors)}"

    @staticmethod
    def _extract_json(text: str) -> dict | None:
        text = text.strip()
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return None

    def propose_goal(self, context: AgentContext) -> dict | None:
        return None

    def evaluate_questions(self, context: AgentContext) -> list[dict]:
        return []

    def reflect_on_outcome(
        self, context: AgentContext, previous_action: dict | None, outcome: dict
    ) -> str:
        if previous_action is None:
            return f"Outcome: {outcome.get('status', 'unknown')}"
        return f"Previous action {previous_action.get('action_type')}: {outcome.get('status', 'unknown')}"
