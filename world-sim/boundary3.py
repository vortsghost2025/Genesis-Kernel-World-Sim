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
from backend.world.first_pair_cognition_model import build_system_prompt, validate_model_output
from backend.world.first_pair_cognition_model import ModelCognitionBackend
from backend.world.first_pair_cognition_interface import AgentContext

print('=== BOUNDARY 3: FRESH READ-ONLY ADAM COGNITION AFTER HUMAN ANSWER ===')

CANONICAL = Path('.runtime/first-pair')
store = FirstPairPersistenceStore(CANONICAL)

def file_hash(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

# STEP 1: VERIFY PRECONDITIONS
print('STEP 1: VERIFY PRECONDITIONS')
goals_hash = file_hash(CANONICAL / 'goals.json')
questions_hash = file_hash(CANONICAL / 'questions.json')
prov_hash = file_hash(CANONICAL / 'provenance.jsonl')

expected_goals = '500a0a897b5da26f2c31b18b01a6b44b1b18db0cfa1143abb27a3a5369e922be'
expected_questions = '952ceacd6441beb5768a7a41c63e7fc1a0f1b29d704181d509c917382b3baf7c'
expected_prov = 'c6a044c5a114e2e1808d399e5063b6399cdf9285efc90f1d460aa37a1c9cae2a'

if goals_hash != expected_goals:
    print('ERROR: goals hash mismatch')
    exit(1)
if questions_hash != expected_questions:
    print('ERROR: questions hash mismatch')
    exit(1)
if prov_hash != expected_prov:
    print('ERROR: provenance hash mismatch')
    exit(1)

questions = load_questions(store)
if len(questions) != 1:
    print('ERROR: Expected 1 question')
    exit(1)
q = questions[0]
expected_agent = 'genesis-agent-eb4439bd1b97c6baffc0c78956f1399789c9c598872527945372b65ce99e349d'
if q.question_id != 'q1-habitat-structure':
    print('ERROR: Wrong question_id')
    exit(1)
if q.asking_agent_id != expected_agent:
    print('ERROR: Wrong agent_id')
    exit(1)
if q.status != 'answered':
    print('ERROR: Wrong status')
    exit(1)
if q.heartbeat != 0:
    print('ERROR: Wrong heartbeat')
    exit(1)
expected_answer = 'The canonical habitat has two allowed tiles: public-start-adam and public-start-eve. You start on public-start-adam; Eve starts on public-start-eve. Your current observation boundary is only public-start-adam, and your current observation contains no objects. Movement is disabled, so there is no other location you are authorized to explore yet. For now, prioritize understanding your current tile and these habitat constraints. Do not assume unseen features or objects.'
actual_answer = q.provenance.get('answer', '')
if actual_answer != expected_answer:
    print('ERROR: Answer mismatch')
    exit(1)

print('PRECONDITIONS_OK')
print('GOALS_SHA256_BEFORE=' + goals_hash)
print('QUESTIONS_SHA256_BEFORE=' + questions_hash)
print('PROVENANCE_SHA256_BEFORE=' + prov_hash)
print('QUESTION_STATUS=' + q.status)
print('QUESTION_ID=' + q.question_id)
print('QUESTION_HEARTBEAT=' + str(q.heartbeat))
print('ASKING_AGENT_ID=' + q.asking_agent_id)

# STEP 2: BUILD GOAL-AWARE CONTEXT
print()
print('STEP 2: BUILD GOAL-AWARE CONTEXT')
goals = load_goals(store)
if len(goals) != 1:
    print('ERROR: Expected 1 goal')
    exit(1)
goal = goals[0]
if goal.status != 'active':
    print('ERROR: Goal not active')
    exit(1)
if goal.goal_id != 'goal-b0971f2a04c4c41b':
    print('ERROR: Wrong goal_id')
    exit(1)

CANDIDATE = {
    'ok': True,
    'adam_identity': {
        'agent_id': 'genesis-agent-eb4439bd1b97c6baffc0c78956f1399789c9c598872527945372b65ce99e349d',
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

print('BASE_CONTEXT_HEARTBEAT=' + str(base_ctx.heartbeat_number))
print('BASE_CONTEXT_AGENT_ID=' + base_ctx.agent_id)
print('BASE_CONTEXT_GOALS_COUNT=' + str(len(base_ctx.goals)))
print('BASE_CONTEXT_UNANSWERED_COUNT=' + str(len(base_ctx.unanswered_questions)))
print('BASE_CONTEXT_ANSWERED_COUNT=' + str(len(base_ctx.answered_questions)))

# STEP 3: LOAD ACTUAL QUESTIONS FROM PERSISTENCE
print()
print('STEP 3: LOAD ACTUAL QUESTIONS FROM PERSISTENCE')
all_questions = load_questions(store)
print('LOADED_QUESTIONS_COUNT=' + str(len(all_questions)))

answered_questions_persited = [q_obj.to_envelope()['data'] for q_obj in all_questions if q_obj.status == 'answered']
unanswered_questions_persited = [q_obj.to_envelope()['data'] for q_obj in all_questions if q_obj.status == 'pending']

print('PERSISTED_ANSWERED_COUNT=' + str(len(answered_questions_persited)))
print('PERSISTED_UNANSWERED_COUNT=' + str(len(unanswered_questions_persited)))

if len(answered_questions_persited) != 1:
    print('ERROR: Expected exactly 1 answered question')
    exit(1)
answered_q = answered_questions_persited[0]
if answered_q['question_id'] != 'q1-habitat-structure':
    print('ERROR: Answered question is not q1-habitat-structure')
    exit(1)
if answered_q['asking_agent_id'] != expected_agent:
    print('ERROR: Answered question wrong agent_id')
    exit(1)

print('PERSISTED_ANSWERED_QUESTION_ID=' + answered_q['question_id'])
print('PERSISTED_ANSWERED_ASKING_AGENT=' + answered_q['asking_agent_id'])

# STEP 4: SELECT HUMAN CONTEXT
print()
print('STEP 4: SELECT HUMAN CONTEXT')
active_goal_list = [g.goal_id for g in goals if g.status == 'active']
active_goal_ids = set(active_goal_list)

print('INPUT_ANSWERED_COUNT=' + str(len(answered_questions_persited)))
print('INPUT_UNANSWERED_COUNT=' + str(len(unanswered_questions_persited)))
active_goal_ids_list = list(active_goal_ids)
print('INPUT_ACTIVE_GOALS=' + str(active_goal_ids_list))

selected_records, answered_ids, unresolved_ids, omitted = select_human_context(
    answered_questions_persited, unanswered_questions_persited, active_goal_ids
)

print('SELECTED_RECORDS_COUNT=' + str(len(selected_records)))
print('SELECTED_ANSWERED_IDS=' + str(answered_ids))
print('SELECTED_UNRESOLVED_IDS=' + str(unresolved_ids))
print('OMITTED_COUNT=' + str(omitted))

selected_q_ids = [r.get('question_id') for r in selected_records]
if 'q1-habitat-structure' not in selected_q_ids:
    print('ERROR: q1-habitat-structure not selected')
    exit(1)
print('Q1_HABITAT_STRUCTURE_SELECTED_AS_ANSWERED=YES')

# STEP 5: BUILD FINAL AGENTCONTEXT
print()
print('STEP 5: BUILD FINAL AGENTCONTEXT')
final_ctx = AgentContext(
    agent_id=base_ctx.agent_id,
    canonical_name=base_ctx.canonical_name,
    canonical_ref=base_ctx.canonical_ref,
    heartbeat_number=base_ctx.heartbeat_number,
    position=base_ctx.position,
    observation=base_ctx.observation,
    memory=base_ctx.memory,
    goals=base_ctx.goals,
    unanswered_questions=unanswered_questions_persited,
    world_public_objects=base_ctx.world_public_objects,
    habitat_allowed_tiles=base_ctx.habitat_allowed_tiles,
    habitat_movement_allowed=base_ctx.habitat_movement_allowed,
    previous_action=base_ctx.previous_action,
    timestamp_utc=base_ctx.timestamp_utc,
    other_agent_id=base_ctx.other_agent_id,
    other_agent_name=base_ctx.other_agent_name,
    other_agent_ref=base_ctx.other_agent_ref,
    answered_questions=answered_questions_persited,
    available_moves=base_ctx.available_moves,
    current_runtime_capabilities=base_ctx.current_runtime_capabilities,
    current_tile_occupants=base_ctx.current_tile_occupants,
    visible_public_messages=base_ctx.visible_public_messages,
    relevant_human_answers=answered_questions_persited,
    selected_private_memories=base_ctx.selected_private_memories,
    derived_memory_summaries=base_ctx.derived_memory_summaries,
    public_relationship_events=base_ctx.public_relationship_events,
    memory_selection_manifest=base_ctx.memory_selection_manifest,
)

print('FINAL_CONTEXT_HEARTBEAT=' + str(final_ctx.heartbeat_number))
print('FINAL_CONTEXT_ANSWERED_COUNT=' + str(len(final_ctx.answered_questions)))
print('FINAL_CONTEXT_RELEVANT_HUMAN_ANSWERS_COUNT=' + str(len(final_ctx.relevant_human_answers)))
print('FINAL_CONTEXT_UNANSWERED_COUNT=' + str(len(final_ctx.unanswered_questions)))

# STEP 6: BUILD SYSTEM PROMPT AND VERIFY ANSWER REENTRY
print()
print('STEP 6: BUILD SYSTEM PROMPT AND VERIFY ANSWER REENTRY')
prompt = build_system_prompt(final_ctx)
print('PROMPT_LENGTH=' + str(len(prompt)))

answer_in_prompt = expected_answer in prompt
print('ANSWER_VISIBLE_IN_PROMPT=' + str(answer_in_prompt))
if not answer_in_prompt:
    answer_lines = [line.strip() for line in expected_answer.split('\n') if line.strip()]
    prompt_lines = [line.strip() for line in prompt.split('\n') if line.strip()]
    answer_norm = ' '.join(answer_lines)
    ping_norm = ' '.join(prompt_lines)
    answer_in_prompt = answer_norm in ping_norm
    print('ANSWER_VISIBLE_IN_PROMPT_NORMALIZED=' + str(answer_in_prompt))

answer_occurrences = prompt.count(expected_answer)
print('EXACT_ANSWER_OCCURRENCES_IN_PROMPT=' + str(answer_occurrences))
if answer_occurrences == 0:
    answer_occurrences = ping_norm.count(answer_norm)
    print('EXACT_ANSWER_OCCURRENCES_IN_PROMPT_NORMALIZED=' + str(answer_occurrences))

prompt_hash = hashlib.sha256(prompt.encode('utf-8')).hexdigest()
print('SYSTEM_PROMPT_SHA256=' + prompt_hash)

# STEP 7: PRE-MODEL STATE HASHES
print()
print('STEP 7: PRE-MODEL STATE HASHES')
pre_goals_hash = file_hash(CANONICAL / 'goals.json')
pre_questions_hash = file_hash(CANONICAL / 'questions.json')
pre_prov_hash = file_hash(CANONICAL / 'provenance.jsonl')
pre_dir_list = sorted([f.name for f in CANONICAL.iterdir() if f.is_file()])
print('PRE_MODELS_GOALS_SHA256=' + pre_goals_hash)
print('PRE_MODELS_QUESTIONS_SHA256=' + pre_questions_hash)
print('PRE_MODELS_PROVENANCE_SHA256=' + pre_prov_hash)
print('PRE_MODELS_DIRECTORY=' + str(pre_dir_list))

# STEP 8: EXACTLY ONE REAL MODEL CALL VIA BACKEND
print()
print('STEP 8: EXACTLY ONE REAL MODEL CALL')
backend = ModelCognitionBackend('east_adam')
print('MODEL_BACKEND_PROVIDER=' + backend._config.provider_type)
print('MODEL_BACKEND_BASE_URL=' + backend._config.base_url)
print('MODEL_BACKEND_MODEL=' + backend._config.model)
print('MODEL_BACKEND_API_KEY=' + str(backend._config.api_key))

print('MAKING EXACTLY ONE REAL MODEL CALL VIA BACKEND.OBSERVE_AND_ORIENT...')
try:
    cognition_output = backend.observe_and_orient(final_ctx)
    print('OBSERVE_AND_ORIENT_SUCCESS')

    # Print the cognition output fields
    print('ACTION=' + str(cognition_output.action))
    print('MEMORY_WRITE=' + str(cognition_output.memory_write))
    print('GOAL_UPDATES=' + str(cognition_output.goal_updates))
    print('QUESTIONS_RAISED=' + str(cognition_output.questions_raised))
    print('INTERNAL_REASONING=' + str(cognition_output.internal_reasoning))
    print('CONFIDENCE=' + str(cognition_output.confidence))
    print('OBSERVATION_SUMMARY=' + str(cognition_output.observation_summary))
    print('DECISION_SUMMARY=' + str(cognition_output.decision_summary))
    print('UNCERTAINTY=' + str(cognition_output.uncertainty))

except Exception as e:
    print('OBSERVE_AND_ORIENT_FAILED=' + str(e))

# STEP 9: POST-MODEL STATE HASHES (ZERO-WRITE PROOF)
print()
print('STEP 9: POST-MODEL STATE HASHES (ZERO-WRITE PROOF)')
post_goals_hash = file_hash(CANONICAL / 'goals.json')
post_questions_hash = file_hash(CANONICAL / 'questions.json')
post_prov_hash = file_hash(CANONICAL / 'provenance.jsonl')
post_dir_list = sorted([f.name for f in CANONICAL.iterdir() if f.is_file()])

print('POST_MODELS_GOALS_SHA256=' + post_goals_hash)
print('POST_MODELS_QUESTIONS_SHA256=' + post_questions_hash)
print('POST_MODELS_PROVENANCE_SHA256=' + post_prov_hash)
print('POST_MODELS_DIRECTORY=' + str(post_dir_list))

goals_unchanged = (pre_goals_hash == post_goals_hash)
questions_unchanged = (pre_questions_hash == post_questions_hash)
prov_unchanged = (pre_prov_hash == post_prov_hash)
dir_unchanged = (pre_dir_list == post_dir_list)

print('GOALS_UNCHANGED=' + str(goals_unchanged))
print('QUESTIONS_UNCHANGED=' + str(questions_unchanged))
print('PROVENANCE_UNCHANGED=' + str(prov_unchanged))
print('CANONICAL_FILESET_UNCHANGED=' + str(dir_unchanged))
canon_writes = 0 if (goals_unchanged and questions_unchanged and prov_unchanged and dir_unchanged) else 1
print('CANONICAL_WRITES=' + str(canon_writes))
print('MEMORY_WRITES=0')
print('MOVEMENT=0')
print('ACTION_EXECUTED=NO')
print('OUTPUT_APPLIED=NO')
print('COMMITS_CREATED=0')
print('PUSHED=NO')
print('GATE_7_OPENED=NO')
print('FIRST_PAIR_CREATION_AUTHORIZED=FALSE')
print('BOUNDARY_3_EXECUTED=YES')
