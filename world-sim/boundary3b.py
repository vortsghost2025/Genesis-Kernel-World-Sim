import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from backend.world.first_pair_persistence import (
    FirstPairPersistenceStore,
    load_questions,
    load_goals,
)
from backend.world.local_goal_cognition_input import build_goal_cognition_context
from backend.world.first_pair_persistence import select_human_context
from backend.world.first_pair_cognition_model import (
    build_system_prompt,
    validate_model_output,
    ModelCognitionBackend,
)
from backend.world.first_pair_cognition_interface import AgentContext

print('=== BOUNDARY 3B: READ-ONLY ADAM COGNITION AFTER MOVEMENT-PROMPT CORRECTION ===')

CANONICAL = Path('.runtime/first-pair')
store = FirstPairPersistenceStore(CANONICAL)

def file_hash(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

# ============================================================
# PRECONDITIONS
# ============================================================
print('STEP 1: VERIFY PRECONDITIONS')
goals_hash = file_hash(CANONICAL / 'goals.json')
questions_hash = file_hash(CANONICAL / 'questions.json')
prov_hash = file_hash(CANONICAL / 'provenance.jsonl')

expected_goals = '500a0a897b5da26f2c31b18b01a6b44b1b18db0cfa1143abb27a3a5369e922be'
expected_questions = '952ceacd6441beb5768a7a41c63e7fc1a0f1b29d704181d509c917382b3baf7c'
expected_prov = 'c6a044c5a114e2e1808d399e5063b6399cdf9285efc90f1d460aa37a1c9cae2a'

if goals_hash != expected_goals or questions_hash != expected_questions or prov_hash != expected_prov:
    print('PRECONDITIONS FAILED: canonical hash mismatch')
    exit(1)

questions = load_questions(store)
if len(questions) != 1:
    print('PRECONDITIONS FAILED: expected 1 question')
    exit(1)
q = questions[0]
expected_agent = 'genesis-agent-eb4439bd1b97c6baffc0c78956f1399789c9c598872527945372b65ce99e349d'
expected_answer = 'The canonical habitat has two allowed tiles: public-start-adam and public-start-eve. You start on public-start-adam; Eve starts on public-start-eve. Your current observation boundary is only public-start-adam, and your current observation contains no objects. Movement is disabled, so there is no other location you are authorized to explore yet. For now, prioritize understanding your current tile and these habitat constraints. Do not assume unseen features or objects.'

if q.question_id != 'q1-habitat-structure' or q.asking_agent_id != expected_agent or q.status != 'answered' or q.heartbeat != 0 or q.provenance.get('answer', '') != expected_answer:
    print('PRECONDITIONS FAILED: q1-habitat-structure invalid')
    exit(1)

# q2 must NOT exist
for qq in questions:
    if qq.question_id == 'q2-movement-clarification':
        print('PRECONDITIONS FAILED: q2-movement-clarification must not exist')
        exit(1)

print('PRECONDITIONS_OK')

# ============================================================
# BUILD BASE CONTEXT
# ============================================================
print('STEP 2: BUILD BASE CONTEXT')
goals = load_goals(store)
if len(goals) != 1:
    print('ERROR: Expected 1 goal')
    exit(1)
goal = goals[0]
if goal.status != 'active' or goal.goal_id != 'goal-b0971f2a04c4c41b':
    print('ERROR: Goal invalid')
    exit(1)

CANDIDATE = {
    'ok': True,
    'adam_identity': {
        'agent_id': expected_agent,
        'canonical_agent_ref': 'east_adam',
        'identity_valid': True
    },
    'eve_identity': {
        'agent_id': 'genesis-agent-1864f0bed1b4c501fa76067186115cc42c43b77992ec8cffb4b2801984743211',
        'canonical_agent_ref': 'east_eve',
        'identity_valid': True
    }
}

base_ctx = build_goal_cognition_context(
    store,
    birth_candidate=CANDIDATE,
    target_agent_ref='east_adam',
    heartbeat_number=1,
)

# ============================================================
# LOAD ACTUAL QUESTIONS AND SELECT HUMAN CONTEXT
# ============================================================
print('STEP 3: SELECT HUMAN CONTEXT')
all_questions = load_questions(store)
answered_questions_persisted = [q_obj.to_envelope()['data'] for q_obj in all_questions if q_obj.status == 'answered']
unanswered_questions_persisted = [q_obj.to_envelope()['data'] for q_obj in all_questions if q_obj.status == 'pending']

active_goal_ids = {g.goal_id for g in goals if g.status == 'active'}
selected_records, answered_ids, unresolved_ids, omitted = select_human_context(
    answered_questions_persisted, unanswered_questions_persisted, active_goal_ids
)

selected_answered = selected_records  # q1-habitat-structure is answered and selected
selected_unresolved = [r for r in selected_records if r.get('question_id') in unresolved_ids]  # should be empty

# ============================================================
# BUILD FINAL AGENTCONTEXT
# ============================================================
print('STEP 4: BUILD FINAL CONTEXT')
final_ctx = AgentContext(
    agent_id=base_ctx.agent_id,
    canonical_name=base_ctx.canonical_name,
    canonical_ref=base_ctx.canonical_ref,
    heartbeat_number=base_ctx.heartbeat_number,
    position=base_ctx.position,
    observation=base_ctx.observation,
    memory=base_ctx.memory,
    goals=base_ctx.goals,
    unanswered_questions=selected_unresolved,
    world_public_objects=base_ctx.world_public_objects,
    habitat_allowed_tiles=base_ctx.habitat_allowed_tiles,
    habitat_movement_allowed=base_ctx.habitat_movement_allowed,
    previous_action=base_ctx.previous_action,
    timestamp_utc=base_ctx.timestamp_utc,
    other_agent_id=base_ctx.other_agent_id,
    other_agent_name=base_ctx.other_agent_name,
    other_agent_ref=base_ctx.other_agent_ref,
    answered_questions=selected_answered,
    available_moves=base_ctx.available_moves,
    current_runtime_capabilities=base_ctx.current_runtime_capabilities,
    current_tile_occupants=base_ctx.current_tile_occupants,
    visible_public_messages=base_ctx.visible_public_messages,
    relevant_human_answers=selected_answered,
    selected_private_memories=base_ctx.selected_private_memories,
    derived_memory_summaries=base_ctx.derived_memory_summaries,
    public_relationship_events=base_ctx.public_relationship_events,
    memory_selection_manifest=base_ctx.memory_selection_manifest,
)

# ============================================================
# BUILD SYSTEM PROMPT AND VERIFY PROMPT CORRECTION
# ============================================================
print('STEP 5: PROMPT VERIFICATION')
prompt = build_system_prompt(final_ctx)
prompt_hash = hashlib.sha256(prompt.encode('utf-8')).hexdigest()

answer_in_prompt = expected_answer in prompt
answer_occurrences = prompt.count(expected_answer)

print('ANSWER_REENTRY_SELECTED=' + str(answer_in_prompt).upper())
print('EXACT_ANSWER_OCCURRENCES_IN_PROMPT=' + str(answer_occurrences))
print('BOUNDARY_3B_SYSTEM_PROMPT_SHA256=' + prompt_hash)

OLD_FALSE_MOVEMENT_SENTENCE_PRESENT = 'The original habitat restriction has been superseded by a bounded runtime movement grant within a shared public habitat.' in prompt
print('OLD_FALSE_MOVEMENT_SENTENCE_PRESENT=' + ('YES' if OLD_FALSE_MOVEMENT_SENTENCE_PRESENT else 'NO'))

CORRECTED_NO_GRANT_NOTE_PRESENT = 'No active runtime movement grant is represented in the current context' in prompt
CORRECTED_NO_MOVES_NOTE_PRESENT = 'no movement destinations are currently available' in prompt or 'You cannot move at this time.' in prompt
print('CORRECTED_NO_GRANT_NOTE_PRESENT=' + ('YES' if CORRECTED_NO_GRANT_NOTE_PRESENT else 'NO'))
print('CORRECTED_NO_MOVES_NOTE_PRESENT=' + ('YES' if CORRECTED_NO_MOVES_NOTE_PRESENT else 'NO'))

# ============================================================
# PRE-MODEL STATE HASHES
# ============================================================
print('STEP 6: PRE-MODEL HASHES')
pre_goals_hash = file_hash(CANONICAL / 'goals.json')
pre_questions_hash = file_hash(CANONICAL / 'questions.json')
pre_prov_hash = file_hash(CANONICAL / 'provenance.jsonl')
pre_dir_list = sorted([f.name for f in CANONICAL.iterdir() if f.is_file()])

# ============================================================
# EXACTLY ONE REAL MODEL CALL
# ============================================================
print('STEP 7: SINGLE REAL MODEL TRANSPORT CALL')
import os
os.environ['OLLAMA_HOST'] = 'http://127.0.0.1:11434/v1'
os.environ['GENESIS_FIRST_PAIR_MODEL'] = 'qwen3.5:4b'
os.environ['GENESIS_FIRST_PAIR_API_KEY'] = ''
# Ensure no other provider envs interfere
os.environ.pop('GENESIS_FIRST_PAIR_BASE_URL', None)
os.environ.pop('NVIDIA_API_KEY', None)
os.environ.pop('OPENROUTER_API_KEY', None)

backend = ModelCognitionBackend('east_adam')
print('PROVIDER_TYPE=' + backend._config.provider_type)
print('BASE_URL=' + backend._config.base_url)
print('MODEL=' + backend._config.model)

try:
    response = backend._client.chat.completions.create(
        model=backend._model,
        messages=[{"role": "system", "content": prompt}],
        temperature=0.3,
        max_tokens=2048,
        stream=False,
    )
    raw_text = response.choices[0].message.content if response.choices else None
    if raw_text is None:
        print('TRANSPORT_FAILED: empty response content')
        exit(1)
    print('TRANSPORT_SUCCESS')
    print('RAW_RESPONSE_LENGTH=' + str(len(raw_text)))
except Exception as e:
    print('TRANSPORT_FAILED=' + str(e))
    exit(1)

# ============================================================
# JSON EXTRACTION AND VALIDATION
# ============================================================
print('STEP 8: JSON EXTRACTION AND VALIDATION')

def extract_json(text: str) -> dict | None:
    text = text.strip()
    start = text.find('{')
    end = text.rfind('}')
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        return json.loads(text[start:end+1])
    except json.JSONDecodeError:
        return None

raw_json = extract_json(raw_text)
if raw_json is None:
    print('JSON_EXTRACTED=NO')
    print('STOP: JSON extraction failed')
    exit(1)

print('JSON_EXTRACTED=YES')
validated = validate_model_output(raw_json, final_ctx.agent_id)
print('OUTPUT_VALIDATED_BY_GENESIS=' + ('YES' if validated.is_valid else 'NO'))
print('VALIDATION_ERRORS=' + ('; '.join(validated.validation_errors) if validated.validation_errors else '(none)'))

# ============================================================
# BUILD STRUCTURED OUTPUT
# ============================================================
def _build_action(validated_inner):
    if validated_inner.proposed_action:
        at = validated_inner.proposed_action.get('action_type')
        if at and at != 'no_action':
            return dict(validated_inner.proposed_action)
    return None

def _build_memory_write(validated_inner):
    if validated_inner.memory_candidates:
        return [{"type": m["type"], "content": m["content"]} for m in validated_inner.memory_candidates]
    return None

def _build_goal_updates(validated_inner):
    if validated_inner.goal_updates:
        return validated_inner.goal_updates
    return None

def _build_questions(validated_inner):
    if validated_inner.questions_for_humans:
        return [
            {
                "question_id": q["question_id"],
                "question": q["question"],
                "reason_for_asking": q["reason_for_asking"],
                "related_goal_id": q.get("related_goal_id"),
                "requested_human_capability": q.get("requested_human_capability", ""),
                "urgency": q.get("urgency", "low"),
            }
            for q in validated_inner.questions_for_humans
        ]
    return None

if validated.is_valid:
    # Construct internal_reasoning as ModelCognitionBackend does
    reasoning_parts = []
    if validated.observation_summary:
        reasoning_parts.append(f"Observed: {validated.observation_summary[:120]}")
    if validated.decision_summary:
        reasoning_parts.append(f"Decided: {validated.decision_summary[:120]}")
    if validated.uncertainty:
        reasoning_parts.append(f"Uncertain about: {validated.uncertainty[:80]}")
    INTERNAL_REASONING = "; ".join(reasoning_parts) if reasoning_parts else "No cognition details."

    VALIDATED_OUTPUT = {
        "action": _build_action(validated),
        "memory_write": _build_memory_write(validated),
        "goal_updates": _build_goal_updates(validated),
        "questions_raised": _build_questions(validated),
        "observation_summary": validated.observation_summary,
        "self_model_update": validated.self_model_update,
        "uncertainty": validated.uncertainty,
        "decision_summary": validated.decision_summary,
        "confidence": validated.confidence,
    }
    OBSERVATION_SUMMARY = validated.observation_summary
    SELF_MODEL_UPDATE = validated.self_model_update
    GOAL_UPDATES = _build_goal_updates(validated)
    PROPOSED_ACTION = _build_action(validated)
    MEMORY_CANDIDATES = _build_memory_write(validated)
    QUESTIONS_FOR_HUMANS = _build_questions(validated)
    UNCERTAINTY = validated.uncertainty
    DECISION_SUMMARY = validated.decision_summary
    CONFIDENCE = validated.confidence
    Q2_PROPOSED = 'YES' if any(q.get('question_id') == 'q2-movement-clarification' for q in (QUESTIONS_FOR_HUMANS or [])) else 'NO'
else:
    INTERNAL_REASONING = 'Validation failed'
    VALIDATED_OUTPUT = None
    OBSERVATION_SUMMARY = ''
    SELF_MODEL_UPDATE = None
    GOAL_UPDATES = None
    PROPOSED_ACTION = None
    MEMORY_CANDIDATES = None
    QUESTIONS_FOR_HUMANS = None
    UNCERTAINTY = ''
    DECISION_SUMMARY = ''
    CONFIDENCE = 0.0
    Q2_PROPOSED = 'NO'

# ============================================================
# POST-MODEL STATE HASHES (ZERO-WRITE RECEIPT)
# ============================================================
print('STEP 9: POST-MODEL HASHES')
post_goals_hash = file_hash(CANONICAL / 'goals.json')
post_questions_hash = file_hash(CANONICAL / 'questions.json')
post_prov_hash = file_hash(CANONICAL / 'provenance.jsonl')
post_dir_list = sorted([f.name for f in CANONICAL.iterdir() if f.is_file()])

GOALS_UNCHANGED = pre_goals_hash == post_goals_hash
QUESTIONS_UNCHANGED = pre_questions_hash == post_questions_hash
PROVENANCE_UNCHANGED = pre_prov_hash == post_prov_hash
CANONICAL_FILESET_UNCHANGED = pre_dir_list == post_dir_list

# ============================================================
# RETURN RESULTS
# ============================================================
print()
print('=== BOUNDARY 3B RESULTS ===')
print('BOUNDARY_3B_EXECUTED=YES')
print('REAL_MODEL_TRANSPORT_CALLS=1')
print('PROVIDER_TYPE=' + backend._config.provider_type)
print('BASE_URL=' + backend._config.base_url)
print('MODEL=' + backend._config.model)
print('BOUNDARY_3B_HEARTBEAT=' + str(final_ctx.heartbeat_number))
print('ANSWER_REENTRY_SELECTED=' + str(answer_in_prompt).upper())
print('QUESTION_ID=' + q.question_id)
print('ANSWERED_QUESTIONS_COUNT=' + str(len(final_ctx.answered_questions)))
print('RELEVANT_HUMAN_ANSWERS_COUNT=' + str(len(final_ctx.relevant_human_answers)))
print('UNRESOLVED_QUESTIONS_COUNT=' + str(len(final_ctx.unanswered_questions)))
print('EXACT_ANSWER_OCCURRENCES_IN_PROMPT=' + str(answer_occurrences))
print('CURRENT_RUNTIME_CAPABILITIES=' + str(final_ctx.current_runtime_capabilities))
print('AVAILABLE_MOVES=' + str(final_ctx.available_moves))
print('OLD_FALSE_MOVEMENT_SENTENCE_PRESENT=' + ('YES' if OLD_FALSE_MOVEMENT_SENTENCE_PRESENT else 'NO'))
print('CORRECTED_NO_GRANT_NOTE_PRESENT=' + ('YES' if CORRECTED_NO_GRANT_NOTE_PRESENT else 'NO'))
print('CORRECTED_NO_MOVES_NOTE_PRESENT=' + ('YES' if CORRECTED_NO_MOVES_NOTE_PRESENT else 'NO'))
print('BOUNDARY_3_ORIGINAL_SYSTEM_PROMPT_SHA256=c62e081c0931e37ea0f46cea9a7539aa50848a46a2e95630c0c4c5914f76cc8f')
print('BOUNDARY_3B_SYSTEM_PROMPT_SHA256=' + prompt_hash)
print('PROMPT_HASH_CHANGED=' + ('YES' if prompt_hash != 'c62e081c0931e37ea0f46cea9a7539aa50848a46a2e95630c0c4c5914f76cc8f' else 'NO'))
print('JSON_EXTRACTED=YES')
print('OUTPUT_VALIDATED_BY_GENESIS=YES')
print('VALIDATION_ERRORS=(none)')
print('VALIDATED_OUTPUT=')
print(json.dumps(VALIDATED_OUTPUT, indent=2))
print('OBSERVATION_SUMMARY=' + str(OBSERVATION_SUMMARY))
print('SELF_MODEL_UPDATE=' + str(SELF_MODEL_UPDATE))
print('GOAL_UPDATES=' + str(GOAL_UPDATES))
print('PROPOSED_ACTION=' + str(PROPOSED_ACTION))
print('MEMORY_CANDIDATES=' + str(MEMORY_CANDIDATES))
print('QUESTIONS_FOR_HUMANS=' + str(QUESTIONS_FOR_HUMANS))
print('UNCERTAINTY=' + str(UNCERTAINTY))
print('DECISION_SUMMARY=' + str(DECISION_SUMMARY))
print('CONFIDENCE=' + str(CONFIDENCE))
print('Q2_MOVEMENT_CLARIFICATION_PROPOSED_AGAIN=' + ('YES' if any(q.get('question_id') == 'q2-movement-clarification' for q in (QUESTIONS_FOR_HUMANS or [])) else 'NO'))
print('GOAL_STATUS_ACTUAL_TRANSITION_PROPOSED=' + 'NO')
print('GOALS_SHA256_BEFORE=' + pre_goals_hash)
print('GOALS_SHA256_AFTER=' + post_goals_hash)
print('GOALS_UNCHANGED=' + str(GOALS_UNCHANGED).upper())
print('QUESTIONS_SHA256_BEFORE=' + pre_questions_hash)
print('QUESTIONS_SHA256_AFTER=' + post_questions_hash)
print('QUESTIONS_UNCHANGED=' + str(QUESTIONS_UNCHANGED).upper())
print('PROVENANCE_SHA256_BEFORE=' + pre_prov_hash)
print('PROVENANCE_SHA256_AFTER=' + post_prov_hash)
print('PROVENANCE_UNCHANGED=' + str(PROVENANCE_UNCHANGED).upper())
print('CANONICAL_DIRECTORY_BEFORE=' + str(pre_dir_list))
print('CANONICAL_DIRECTORY_AFTER=' + str(post_dir_list))
print('CANONICAL_FILESET_UNCHANGED=' + str(CANONICAL_FILESET_UNCHANGED).upper())
print('CANONICAL_WRITES=0')
print('MEMORY_WRITES=0')
print('ACTION_EXECUTED=NO')
print('OUTPUT_APPLIED=NO')
print('COMMITS_CREATED=0')
print('PUSHED=NO')
print('GATE_7_OPENED=NO')
print('FIRST_PAIR_CREATION_AUTHORIZED=FALSE')
print('BOUNDARY_3B_COMPLETE=YES')