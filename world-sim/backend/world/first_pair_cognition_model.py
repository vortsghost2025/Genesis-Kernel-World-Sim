"""Phase 10FQ — Model-backed First Pair cognition.

Implements the CognitionBackend interface for OpenAI-compatible providers.
All calls are bounded, validated, and never leak private cross-agent memory.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from typing import Any

from openai import OpenAI

from backend.world.first_pair_cognition_interface import (
    AgentContext,
    CognitionBackend,
    CognitionOutput,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MAX_OBSERVATION_CHARS = 2000
_MAX_MEMORY_CHARS = 2000
_MAX_QUESTION_CHARS = 1000
_MAX_REASON_CHARS = 1000
_MAX_DECISION_CHARS = 500
_MAX_IDENTIFIER_CHARS = 128
_MAX_GOAL_UPDATES = 16
_MAX_MEMORY_CANDIDATES = 16
_MAX_HUMAN_QUESTIONS = 8
_MAX_MESSAGE_CHARS = 2000
_MAX_TARGET_CHARS = 128

_SAFE_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_.-]{1,128}$")

# Contamination markers — casefolded for case-insensitive matching
_FORBIDDEN_MARKERS = (
    "true_map",
    "known_map",
    "hidden_substrate",
    "world-sim/data",
    "world_sim/data",
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

# Windows drive-letter patterns (case-insensitive)
_WINDOWS_DRIVE_RE = re.compile(r"^[a-z]:\\", re.IGNORECASE)

# Required top-level fields for model output
_REQUIRED_TOP_FIELDS = frozenset({
    "observation_summary",
    "self_model_update",
    "goal_updates",
    "proposed_action",
    "memory_candidates",
    "questions_for_humans",
    "uncertainty",
    "decision_summary",
    "confidence",
})

_VALID_STATUSES = frozenset({"active", "completed", "abandoned", "in_progress"})
_VALID_URGENCY = frozenset({"low", "medium", "high"})
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


# ---------------------------------------------------------------------------
# Provider configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ProviderConfig:
    provider_type: str
    base_url: str
    model: str
    api_key: str | None = None


class ProviderError(Exception):
    pass


def _check_url(url: str) -> str:
    url = url.strip()
    if not (url.startswith("http://") or url.startswith("https://")):
        raise ProviderError(f"URL must start with http:// or https://: {url[:40]}")
    # Strip /v1 or /v1/ to avoid doubling
    url = re.sub(r"/v1/?$", "", url)
    return url + "/v1"


def resolve_provider() -> ProviderConfig:
    """Resolve model provider from environment. Never silently selects Ollama."""
    base = os.environ.get("GENESIS_FIRST_PAIR_BASE_URL", "").strip()
    key = os.environ.get("GENESIS_FIRST_PAIR_API_KEY", "").strip()
    model = os.environ.get("GENESIS_FIRST_PAIR_MODEL", "").strip()
    nv_key = os.environ.get("NVIDIA_API_KEY", "").strip()
    or_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    ollama_host = os.environ.get("OLLAMA_HOST", "").strip()

    # --- Explicit base URL ---
    if base:
        if not model:
            raise ProviderError(
                "GENESIS_FIRST_PAIR_BASE_URL is set but GENESIS_FIRST_PAIR_MODEL is not set"
            )
        # localhost / 127.0.0.1 / [::1] may omit the API key
        url_lower = base.lower()
        is_local = any(h in url_lower for h in ("localhost", "127.0.0.1", "[::1]", "::1"))
        if not is_local and not key:
            raise ProviderError(
                "Remote GENESIS_FIRST_PAIR_BASE_URL requires GENESIS_FIRST_PAIR_API_KEY"
            )
        url = _check_url(base)
        return ProviderConfig("explicit_url", url, model, key or None)

    # --- NVIDIA ---
    if nv_key:
        if not model:
            raise ProviderError(
                "NVIDIA_API_KEY is set but GENESIS_FIRST_PAIR_MODEL is not set"
            )
        url = "https://integrate.api.nvidia.com/v1"
        return ProviderConfig("nvidia", url, model, nv_key)

    # --- OpenRouter ---
    if or_key:
        if not model:
            raise ProviderError(
                "OPENROUTER_API_KEY is set but GENESIS_FIRST_PAIR_MODEL is not set"
            )
        url = "https://openrouter.ai/api/v1"
        return ProviderConfig("openrouter", url, model, or_key)

    # --- Ollama ---
    if ollama_host:
        if not model:
            raise ProviderError(
                "OLLAMA_HOST is set but GENESIS_FIRST_PAIR_MODEL is not set"
            )
        url = _check_url(ollama_host)
        return ProviderConfig("ollama", url, model, None)

    # --- No provider ---
    raise ProviderError(
        "No usable provider configuration. Set one of: "
        "GENESIS_FIRST_PAIR_BASE_URL (+ GENESIS_FIRST_PAIR_MODEL, "
        "+ GENESIS_FIRST_PAIR_API_KEY for remote), "
        "NVIDIA_API_KEY (+ GENESIS_FIRST_PAIR_MODEL), "
        "OPENROUTER_API_KEY (+ GENESIS_FIRST_PAIR_MODEL), "
        "OLLAMA_HOST (+ GENESIS_FIRST_PAIR_MODEL)"
    )


# ---------------------------------------------------------------------------
# Sanitise provider exceptions
# ---------------------------------------------------------------------------

_PROVIDER_SAFE_MESSAGE_RE = re.compile(r"[^\x20-\x7e]")


def sanitize_provider_error(exc: Exception) -> str:
    msg = str(exc)
    # Strip any non-printable characters
    msg = _PROVIDER_SAFE_MESSAGE_RE.sub("?", msg)
    # Truncate to a safe length
    if len(msg) > 500:
        msg = msg[:500] + "..."
    # Strip anything that looks like a key/token
    msg = re.sub(r"(?i)(sk-[a-z0-9-]{10,})[a-z0-9-]+", r"\1***", msg)
    msg = re.sub(r"(?i)(nvapi-)[a-z0-9-]+", r"\1***", msg)
    msg = re.sub(r"(?i)(key|token|password|secret)=[^\s&]+", r"\1=***", msg)
    return msg


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _is_safe_id(value: str) -> bool:
    return bool(isinstance(value, str) and _SAFE_ID_PATTERN.match(value))


def _casefolded_contaminated(text: str) -> bool:
    lowered = text.casefold()
    for marker in _FORBIDDEN_MARKERS:
        if marker in lowered:
            return True
    if _WINDOWS_DRIVE_RE.match(text.strip()):
        return True
    return False


def _check_length(value: str, max_chars: int, field_name: str) -> str | None:
    if not isinstance(value, str):
        return f"{field_name}:not_a_string"
    if len(value) > max_chars:
        return f"{field_name}:exceeds_{max_chars}_chars"
    return None


def _reject_unknown_fields(
    raw: dict, allowed: frozenset[str], prefix: str = ""
) -> list[str]:
    errors: list[str] = []
    for key in raw:
        if key not in allowed:
            errors.append(f"{prefix}unknown_field:{key}" if prefix else f"unknown_field:{key}")
    return errors


# ---------------------------------------------------------------------------
# Action-specific exact schemas
# ---------------------------------------------------------------------------

_ACTION_SCHEMAS: dict[str, frozenset[str]] = {
    "no_action": frozenset({"action_type"}),
    "create_public_object": frozenset({
        "action_type", "object_id", "object_type", "description", "tile_id",
    }),
    "inspect_public_object": frozenset({"action_type", "target_object_id"}),
    "modify_owned_public_object": frozenset({
        "action_type", "target_object_id", "modifications",
    }),
    "leave_public_message": frozenset({"action_type", "message", "recipient"}),
    "ask_human": frozenset({
        "action_type", "question_id", "question", "reason_for_asking",
        "related_goal_id", "requested_human_capability", "urgency",
    }),
    "request_capability": frozenset({"action_type", "capability_id", "capability_reason"}),
    "move": frozenset({"action_type", "target_tile", "reason"}),
}


def validate_action_exact(raw: dict, context_agent_id: str) -> list[str]:
    errors: list[str] = []
    at = raw.get("action_type")
    if at not in _VALID_ACTIONS:
        return ["invalid_action_type"]

    allowed = _ACTION_SCHEMAS[at]
    errors.extend(_reject_unknown_fields(raw, allowed, "action"))

    if at == "no_action":
        return errors

    if at == "create_public_object":
        for f in ("object_id", "object_type", "description", "tile_id"):
            val = raw.get(f, "")
            if not isinstance(val, str) or not val.strip():
                errors.append(f"action:empty_{f}")
        oid = raw.get("object_id", "")
        if oid and not _is_safe_id(oid):
            errors.append("action:unsafe_object_id")
        desc = raw.get("description", "")
        if isinstance(desc, str):
            err = _check_length(desc, _MAX_OBSERVATION_CHARS, "action:description")
            if err:
                errors.append(err)
            elif _casefolded_contaminated(desc):
                errors.append("action:contaminated_description")

    elif at == "inspect_public_object":
        tid = raw.get("target_object_id", "")
        if not isinstance(tid, str) or not tid.strip():
            errors.append("action:empty_target_object_id")

    elif at == "modify_owned_public_object":
        tid = raw.get("target_object_id", "")
        if not isinstance(tid, str) or not tid.strip():
            errors.append("action:empty_target_object_id")
        mods = raw.get("modifications")
        if not isinstance(mods, dict):
            errors.append("action:modifications_not_a_dict")
        else:
            for key in mods:
                if key in ("object_id", "creator_agent_id", "created_heartbeat"):
                    errors.append(f"action:cannot_modify_{key}")

    elif at == "leave_public_message":
        msg = raw.get("message", "")
        if not isinstance(msg, str) or not msg.strip():
            errors.append("action:empty_message")
        if isinstance(msg, str):
            err = _check_length(msg, _MAX_MESSAGE_CHARS, "action:message")
            if err:
                errors.append(err)
            elif _casefolded_contaminated(msg):
                errors.append("action:contaminated_message")
        rec = raw.get("recipient", "")
        if not isinstance(rec, str) or not rec.strip():
            errors.append("action:empty_recipient")

    elif at == "ask_human":
        for f in ("question_id", "question", "reason_for_asking"):
            val = raw.get(f, "")
            if not isinstance(val, str) or not val.strip():
                errors.append(f"action:empty_{f}")
        qid = raw.get("question_id", "")
        if qid and not _is_safe_id(qid):
            errors.append("action:unsafe_question_id")
        q = raw.get("question", "")
        if isinstance(q, str):
            err = _check_length(q, _MAX_QUESTION_CHARS, "action:question")
            if err:
                errors.append(err)
        rfa = raw.get("reason_for_asking", "")
        if isinstance(rfa, str):
            err = _check_length(rfa, _MAX_REASON_CHARS, "action:reason_for_asking")
            if err:
                errors.append(err)
        urg = raw.get("urgency", "low")
        if urg not in _VALID_URGENCY:
            errors.append("action:invalid_urgency")
        related = raw.get("related_goal_id")
        if related is not None and (not isinstance(related, str) or not _is_safe_id(related)):
            errors.append("action:invalid_related_goal_id")

    elif at == "request_capability":
        cap_id = raw.get("capability_id", "")
        if not isinstance(cap_id, str) or not cap_id.strip():
            errors.append("action:empty_capability_id")
        cap_reason = raw.get("capability_reason", "")
        if not isinstance(cap_reason, str) or not cap_reason.strip():
            errors.append("action:empty_capability_reason")

    elif at == "move":
        tt = raw.get("target_tile", "")
        if not isinstance(tt, str) or not tt.strip():
            errors.append("action:empty_target_tile")
        err = _check_length(tt, _MAX_TARGET_CHARS, "action:target_tile")
        if err:
            errors.append(err)

    return errors


# ---------------------------------------------------------------------------
# Model Output validation
# ---------------------------------------------------------------------------


@dataclass
class ModelOutput:
    observation_summary: str = ""
    self_model_update: str | None = None
    goal_updates: list[dict] = field(default_factory=list)
    proposed_action: dict | None = None
    memory_candidates: list[dict] = field(default_factory=list)
    questions_for_humans: list[dict] = field(default_factory=list)
    uncertainty: str = ""
    decision_summary: str = ""
    confidence: float = 0.0
    validation_errors: list[str] = field(default_factory=list)
    is_valid: bool = False


def validate_model_output(raw: dict, context_agent_id: str) -> ModelOutput:
    errors: list[str] = []
    output = ModelOutput()

    # --- Reject unknown top-level fields ---
    errors.extend(_reject_unknown_fields(raw, _REQUIRED_TOP_FIELDS))

    # --- Reject missing fields ---
    for field in _REQUIRED_TOP_FIELDS:
        if field not in raw:
            errors.append(f"missing_field:{field}")

    # --- observation_summary ---
    obs = raw.get("observation_summary")
    if isinstance(obs, str):
        err = _check_length(obs, _MAX_OBSERVATION_CHARS, "observation_summary")
        if err:
            errors.append(err)
        elif not obs.strip():
            errors.append("observation_summary:empty")
        elif _casefolded_contaminated(obs):
            errors.append("observation_summary:contaminated")
        else:
            output.observation_summary = obs
    elif "observation_summary" in raw:
        errors.append("observation_summary:wrong_type")

    # --- self_model_update (optional string or null) ---
    smu = raw.get("self_model_update")
    if smu is not None and smu != "":
        if isinstance(smu, str):
            if _casefolded_contaminated(smu):
                errors.append("self_model_update:contaminated")
            elif len(smu) > _MAX_OBSERVATION_CHARS:
                errors.append(f"self_model_update:exceeds_{_MAX_OBSERVATION_CHARS}_chars")
            else:
                output.self_model_update = smu
        else:
            errors.append("self_model_update:wrong_type")

    # --- goal_updates ---
    gu_list = raw.get("goal_updates")
    if isinstance(gu_list, list):
        if len(gu_list) > _MAX_GOAL_UPDATES:
            errors.append(f"goal_updates:exceeds_{_MAX_GOAL_UPDATES}")
        else:
            for i, gu in enumerate(gu_list):
                if not isinstance(gu, dict):
                    errors.append(f"goal_updates[{i}]:not_a_dict")
                    continue
                # Reject unknown fields in goal update
                errors.extend(_reject_unknown_fields(
                    gu, frozenset({"goal_id", "agent_id", "description", "status", "created_heartbeat"}),
                    f"goal_updates[{i}]",
                ))
                for f in ("goal_id", "agent_id", "description", "status"):
                    if f not in gu or not isinstance(gu[f], str) or not gu[f].strip():
                        errors.append(f"goal_updates[{i}]:missing_or_empty_{f}")
                    elif f == "goal_id" and not _is_safe_id(gu.get("goal_id", "")):
                        errors.append(f"goal_updates[{i}]:unsafe_goal_id")
                status_val = gu.get("status", "")
                if status_val not in _VALID_STATUSES:
                    errors.append(f"goal_updates[{i}]:invalid_status:{status_val}")
                # Enforce context agent_id
                gid = gu.get("agent_id", "")
                if gid and gid != context_agent_id:
                    errors.append(f"goal_updates[{i}]:agent_id_mismatch:{gid}")
                desc = gu.get("description", "")
                if isinstance(desc, str):
                    err = _check_length(desc, _MAX_OBSERVATION_CHARS, f"goal_updates[{i}]:description")
                    if err:
                        errors.append(err)
                    elif _casefolded_contaminated(desc):
                        errors.append(f"goal_updates[{i}]:contaminated")
                if not errors or all("goal_updates" not in e for e in errors[-10:]):
                    output.goal_updates.append(gu)
    elif "goal_updates" in raw:
        errors.append("goal_updates:wrong_type")

    # --- proposed_action ---
    act_raw = raw.get("proposed_action")
    # None / absent means no action — this is valid
    if act_raw is not None:
        if isinstance(act_raw, dict):
            action_errors = validate_action_exact(act_raw, context_agent_id)
            if action_errors:
                errors.extend(action_errors)
            else:
                at = act_raw.get("action_type")
                if at != "no_action":
                    output.proposed_action = dict(act_raw)
        else:
            errors.append("proposed_action:wrong_type")

    # --- memory_candidates ---
    mem_raw = raw.get("memory_candidates")
    if isinstance(mem_raw, list):
        if len(mem_raw) > _MAX_MEMORY_CANDIDATES:
            errors.append(f"memory_candidates:exceeds_{_MAX_MEMORY_CANDIDATES}")
        else:
            for i, m in enumerate(mem_raw):
                if not isinstance(m, dict):
                    errors.append(f"memory_candidates[{i}]:not_a_dict")
                    continue
                errors.extend(_reject_unknown_fields(
                    m, frozenset({"type", "content"}), f"memory_candidates[{i}]",
                ))
                for f in ("type", "content"):
                    if f not in m or not isinstance(m[f], str):
                        errors.append(f"memory_candidates[{i}]:missing_or_invalid_{f}")
                content = m.get("content", "")
                if isinstance(content, str):
                    err = _check_length(content, _MAX_MEMORY_CHARS, f"memory_candidates[{i}]:content")
                    if err:
                        errors.append(err)
                    elif _casefolded_contaminated(content):
                        errors.append(f"memory_candidates[{i}]:contaminated")
                if not errors or all("memory_candidates" not in e for e in errors[-10:]):
                    output.memory_candidates.append(m)
    elif "memory_candidates" in raw:
        errors.append("memory_candidates:wrong_type")

    # --- questions_for_humans ---
    qs_raw = raw.get("questions_for_humans")
    if isinstance(qs_raw, list):
        if len(qs_raw) > _MAX_HUMAN_QUESTIONS:
            errors.append(f"questions_for_humans:exceeds_{_MAX_HUMAN_QUESTIONS}")
        else:
            for i, q in enumerate(qs_raw):
                if not isinstance(q, dict):
                    errors.append(f"questions_for_humans[{i}]:not_a_dict")
                    continue
                allowed_q = frozenset({
                    "question_id", "question", "reason_for_asking",
                    "related_goal_id", "requested_human_capability", "urgency",
                })
                errors.extend(_reject_unknown_fields(q, allowed_q, f"questions_for_humans[{i}]"))
                for f in ("question_id", "question", "reason_for_asking"):
                    if f not in q or not isinstance(q[f], str) or not q[f].strip():
                        errors.append(f"questions_for_humans[{i}]:missing_or_empty_{f}")
                qid = q.get("question_id", "")
                if qid and not _is_safe_id(qid):
                    errors.append(f"questions_for_humans[{i}]:unsafe_question_id")
                q_text = q.get("question", "")
                if isinstance(q_text, str):
                    err = _check_length(q_text, _MAX_QUESTION_CHARS, f"questions_for_humans[{i}]:question")
                    if err:
                        errors.append(err)
                rfa = q.get("reason_for_asking", "")
                if isinstance(rfa, str):
                    err = _check_length(rfa, _MAX_REASON_CHARS, f"questions_for_humans[{i}]:reason_for_asking")
                    if err:
                        errors.append(err)
                urg = q.get("urgency", "low")
                if urg not in _VALID_URGENCY:
                    errors.append(f"questions_for_humans[{i}]:invalid_urgency")
                related = q.get("related_goal_id")
                if related is not None and (not isinstance(related, str) or not _is_safe_id(related)):
                    errors.append(f"questions_for_humans[{i}]:invalid_related_goal_id")
                if not errors or all("questions_for_humans" not in e for e in errors[-10:]):
                    output.questions_for_humans.append(q)
    elif "questions_for_humans" in raw:
        errors.append("questions_for_humans:wrong_type")

    # --- uncertainty ---
    unc = raw.get("uncertainty")
    if isinstance(unc, str):
        err = _check_length(unc, _MAX_OBSERVATION_CHARS, "uncertainty")
        if err:
            errors.append(err)
        elif _casefolded_contaminated(unc):
            errors.append("uncertainty:contaminated")
        else:
            output.uncertainty = unc
    elif "uncertainty" in raw:
        errors.append("uncertainty:wrong_type")

    # --- decision_summary ---
    ds = raw.get("decision_summary")
    if isinstance(ds, str):
        err = _check_length(ds, _MAX_DECISION_CHARS, "decision_summary")
        if err:
            errors.append(err)
        elif _casefolded_contaminated(ds):
            errors.append("decision_summary:contaminated")
        else:
            output.decision_summary = ds
    elif "decision_summary" in raw:
        errors.append("decision_summary:wrong_type")

    # --- confidence ---
    conf = raw.get("confidence")
    if isinstance(conf, bool):
        errors.append("confidence:boolean_not_allowed")
    elif isinstance(conf, (int, float)):
        if 0 <= float(conf) <= 1:
            output.confidence = float(conf)
        else:
            errors.append("confidence:out_of_range")
    elif "confidence" in raw:
        errors.append("confidence:wrong_type")

    output.validation_errors = errors
    output.is_valid = not errors
    return output


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

_AVAILABLE_ACTIONS_DESC = """
Available actions:
- no_action: do nothing this cycle
- create_public_object: create a new object in the world (requires: object_id, object_type, description, tile_id; object must be placed on your current tile)
- inspect_public_object: examine an existing object (requires: target_object_id)
- modify_owned_public_object: modify one of your own objects (requires: target_object_id, modifications dict)
- leave_public_message: leave a public message (requires: message, recipient)
- ask_human: ask a question to the human operator (requires: question_id, question, reason_for_asking, requested_human_capability, urgency)
- request_capability: request a new capability from the human (requires: capability_id, capability_reason)
- move: move to an adjacent tile (requires: target_tile, reason) — you may move only one edge per heartbeat; only to tiles listed in available_moves
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
    answered_str = (
        json.dumps(context.answered_questions, indent=2)
        if context.answered_questions
        else "[]"
    )
    moves_str = (
        json.dumps(context.available_moves, indent=2)
        if context.available_moves
        else "[]"
    )
    caps_str = (
        json.dumps(context.current_runtime_capabilities, indent=2)
        if context.current_runtime_capabilities
        else "[]"
    )
    occupants_str = (
        json.dumps(context.current_tile_occupants, indent=2)
        if context.current_tile_occupants
        else "[]"
    )
    vis_msgs_str = (
        json.dumps(context.visible_public_messages, indent=2)
        if context.visible_public_messages
        else "[]"
    )
    ans_questions_str = (
        json.dumps(context.relevant_human_answers, indent=2)
        if context.relevant_human_answers
        else "[]"
    )

    # Bounded memory fields
    selected_mem_str = (
        json.dumps(context.selected_private_memories, indent=2)
        if context.selected_private_memories
        else "[]"
    )
    summaries_str = (
        json.dumps(context.derived_memory_summaries, indent=2)
        if context.derived_memory_summaries
        else "[]"
    )
    rel_events_str = (
        json.dumps(context.public_relationship_events, indent=2)
        if context.public_relationship_events
        else "[]"
    )

    # Movement grant note (truthful to context)
    if context.current_runtime_capabilities:
        if context.available_moves:
            movement_note = (
                "Note: A bounded runtime movement grant is active. "
                "You may move only to tiles listed in available_moves."
            )
        else:
            movement_note = (
                "Note: A bounded runtime movement grant is active, "
                "but no movement destination is currently available. "
                "Do not attempt to move unless a destination appears in available_moves."
            )
    else:
        if context.available_moves:
            movement_note = (
                "Note: No active runtime movement grant is represented in the current context. "
                "Movement availability is determined solely by available_moves."
            )
        else:
            movement_note = (
                "Note: No active runtime movement grant is represented in the current context, "
                "and no movement destinations are currently available. "
                "You cannot move at this time."
            )

    return f"""You are {context.canonical_name}, an agent operating inside a constructed world simulation.

Your persistent identity:
- Agent ID: {context.agent_id}
- Canonical name: {context.canonical_name}
- Canonical ref: {context.canonical_ref}

You share this world with {context.other_agent_name} (agent ID: {context.other_agent_id}, ref: {context.other_agent_ref}). You are distinct agents with separate private memories.

Current heartbeat: {context.heartbeat_number}
Your position: {context.position}

Your observation:
{json.dumps(context.observation, indent=2)}

--- PRIVATE MEMORIES (SELECTED SUBSET) ---
{selected_mem_str}

IMPORTANT: The memories shown above are a selected subset of your full private memory. You have {context.memory_selection_manifest.get('raw_private_memory_count', 0)} total private memories in your persistent store; only {context.memory_selection_manifest.get('selected_private_memory_count', 0)} are included in this request. Older or lower-relevance memories may be compressed into derived summaries below. Lack of a memory in this prompt does NOT prove the event never occurred. The other agent's private memories are never available to you.

--- DERIVED MEMORY SUMMARIES ---
{summaries_str}

Note: These summaries are derived interpretations linked to raw evidence. They may compress older experiences. Each summary references specific raw memory IDs.

--- PUBLIC RELATIONSHIP EVENTS ---
{rel_events_str}

Note: These are observable public interaction events recorded from validated world outcomes. No emotional scores, trust ratings, or social attachment values are assigned.

Your current goals:
{goals_str}

Public world objects at your position:
{objects_str}

Habitat allowed tiles: {context.habitat_allowed_tiles}
Movement allowed (original habitat): {context.habitat_movement_allowed}

--- RUNTIME CONTEXT ---
Tiles you can move to (one edge per heartbeat): {moves_str}
Your active capabilities: {caps_str}
Other agents at your current tile: {occupants_str}
Visible public messages: {vis_msgs_str}
Human answers you have received: {ans_questions_str}

{movement_note}

Unresolved questions you have asked:
{unanswered_str}

Answers you have received:
{answered_str}
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


_OLLAMA_LOCAL_API_KEY_PLACEHOLDER = "ollama"


def _client_api_key(config: ProviderConfig) -> str | None:
    """Return the api_key to hand the OpenAI SDK for a real client.

    Local Ollama (``provider_type == "ollama"``) genuinely requires no
    credential, so ``ProviderConfig.api_key`` remains ``None``. However the
    OpenAI SDK 2.24 constructor requires a non-empty api_key string, even
    though the local OpenAI-compatible endpoint ignores authentication.
    Supply a fixed, non-secret local placeholder only at this SDK construction
    boundary for Ollama; every other provider passes its supplied api_key
    through unchanged (``resolve_provider`` already guarantees non-empty for
    remote providers). The placeholder is not a credential and must never be
    logged or persisted as one.
    """
    if config.provider_type == "ollama" and not config.api_key:
        return _OLLAMA_LOCAL_API_KEY_PLACEHOLDER
    return config.api_key


class ModelCognitionBackend(CognitionBackend):
    """Cognition backend backed by an OpenAI-compatible model provider.

    Performs bounded, operator-configured provider transport to obtain
    cognition output.  Context is read-only; outputs are proposals that
    pass through runtime validation.  Accepts an optional injected client
    (fake transport) for testing—no real provider transport is attempted
    when a client is injected.
    """

    def __init__(
        self,
        agent_ref: str,
        client: Any = None,
    ) -> None:
        self._agent_ref = agent_ref
        self._config = resolve_provider()
        self._client = client or OpenAI(
            base_url=self._config.base_url,
            api_key=_client_api_key(self._config),
            timeout=300.0,
        )
        self._model = self._config.model

    @classmethod
    def from_provider_config(
        cls,
        agent_ref: str,
        config: ProviderConfig,
    ) -> ModelCognitionBackend:
        self = cls.__new__(cls)
        self._agent_ref = agent_ref
        self._config = config
        self._client = OpenAI(
            base_url=config.base_url,
            api_key=_client_api_key(config),
            timeout=300.0,
        )
        self._model = config.model
        return self

    @classmethod
    def with_client(cls, agent_ref: str, client: Any, config: ProviderConfig) -> ModelCognitionBackend:
        self = cls.__new__(cls)
        self._agent_ref = agent_ref
        self._config = config
        self._client = client
        self._model = config.model
        return self

    @property
    def provider_type(self) -> str:
        return self._config.provider_type

    @property
    def model_name(self) -> str:
        return self._model

    def observe_and_orient(self, context: AgentContext) -> CognitionOutput:
        system_prompt = build_system_prompt(context)
        raw_output, err = self._call_model_with_repair(system_prompt, context)

        if err or raw_output is None:
            safe_err = sanitize_provider_error(Exception(err)) if err else "unknown_error"
            return CognitionOutput(
                action=None,
                memory_write=[{"type": "error", "content": safe_err}],
                goal_updates=None,
                questions_raised=None,
                internal_reasoning=f"Model call failed. {safe_err}",
                confidence=0.0,
                uncertainty=f"Provider timeout or error: {safe_err}",
            )

        validated = validate_model_output(raw_output, context.agent_id)

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
                uncertainty=f"Output validation failed: {'; '.join(validated.validation_errors)}",
            )

        # Build action dict from validated proposal
        action: dict | None = None
        if validated.proposed_action:
            at = validated.proposed_action.get("action_type")
            if at and at != "no_action":
                action = dict(validated.proposed_action)

        # Memory candidates
        memory_write: list[dict] | None = None
        if validated.memory_candidates:
            memory_write = [
                {"type": m["type"], "content": m["content"]}
                for m in validated.memory_candidates
            ]

        # Goal updates
        goal_updates: list[dict] | None = None
        if validated.goal_updates:
            goal_updates = validated.goal_updates

        # Questions
        questions: list[dict] | None = None
        if validated.questions_for_humans:
            questions = [
                {
                    "question_id": q["question_id"],
                    "question": q["question"],
                    "reason_for_asking": q["reason_for_asking"],
                    "related_goal_id": q.get("related_goal_id"),
                    "requested_human_capability": q.get("requested_human_capability", ""),
                    "urgency": q.get("urgency", "low"),
                }
                for q in validated.questions_for_humans
            ]

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
            observation_summary=validated.observation_summary,
            decision_summary=validated.decision_summary,
            uncertainty=validated.uncertainty,
        )

    def _call_model_with_repair(
        self, system_prompt: str, context: AgentContext
    ) -> tuple[dict | None, str | None]:
        # --- Original call ---
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
            return None, sanitize_provider_error(e)

        raw_text = response.choices[0].message.content if response.choices else None
        if not raw_text or not raw_text.strip():
            return None, "empty_response"

        raw_json = _extract_json(raw_text)
        if raw_json is None:
            return None, "no_valid_json_in_response"

        validated = validate_model_output(raw_json, context.agent_id)
        if validated.is_valid:
            return raw_json, None

        # --- One bounded repair attempt ---
        repair_prompt = (
            f"Your previous response had validation errors: {'; '.join(validated.validation_errors)}\n"
            "Please correct and return only a valid JSON object with the exact required fields."
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
            return None, sanitize_provider_error(e)

        raw_text2 = response2.choices[0].message.content if response2.choices else None
        if not raw_text2 or not raw_text2.strip():
            return None, "repair_empty_response"

        raw_json2 = _extract_json(raw_text2)
        if raw_json2 is None:
            return None, "repair_no_valid_json"

        validated2 = validate_model_output(raw_json2, context.agent_id)
        if validated2.is_valid:
            return raw_json2, None

        return None, f"repair_failed: {'; '.join(validated2.validation_errors)}"

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
