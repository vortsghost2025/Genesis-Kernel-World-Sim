"""The operator desk — answers at the moment of need, in register.

Sean was the relay: agents asked, his phone pinged, answering waited
on a human. The delegation says the operator answers factual
questions. These tests pin the desk's contract:

  - answers state mechanics and the asker's OWN live facts
  - answers never advise ("you should/must" is a register violation)
  - unknown or capability-shaped questions escalate to the human
  - answered questions leave the unheard pool (no repeat pings)
"""
from __future__ import annotations

import sys
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM))
sys.path.insert(0, str(WORLD_SIM / "scripts"))

import operator_desk as desk  # noqa: E402
from backend.world import survival  # noqa: E402


def _facts(**over):
    f = {
        "agent_ref": "west_eve", "hunger": 92.0, "warmth": 44.0,
        "vitality": 11.0, "downed": True,
        "position": "cont_b_origin_000",
        "inventory": {}, "food_on_hand": "nothing edible",
        "other_ref": "west_adam", "other_name": "adam",
        "other_position": "cont_b_gen_33_51",
        "other_food": "wild_berries ×42",
        "tile_food": [], "weather": "clear", "season": "autumn",
        "night": True, "temperature": 38.0, "tick": 4650,
        "terms": "epistemic.5",
    }
    f.update(over)
    return f


class TestRegisterGuardrail:
    def test_guardrail_rejects_advice(self):
        for phrase in ("you should eat", "you must build", "try to gather",
                       "we recommend moving"):
            try:
                desk.assert_no_advice(phrase)
                raised = False
            except ValueError:
                raised = True
            assert raised, f"advice slipped through: {phrase!r}"

    def test_purpose_answer_assigns_nothing(self):
        a = desk.draft_answer(
            "What should I do next? What is my purpose?", _facts())
        assert "no task exists" in a.lower()
        for directive in ("you should", "you must", "try to"):
            assert directive not in a.lower()

    def test_answers_are_grounded_in_the_askers_real_numbers(self):
        f = _facts(hunger=77.0, warmth=33.0, vitality=8.0)
        a = desk.draft_answer("I am starving, how do I recover?", f)
        assert "77" in a, "answer must name the asker's actual hunger"
        assert "33" in a, "answer must name the asker's actual warmth"
        assert "8" in a, "answer must name the asker's actual vitality"


class TestAnswerBank:
    def test_survival_question_states_eat_and_partner_facts(self):
        a = desk.draft_answer("How can I recover vitality while downed?",
                              _facts())
        assert "eat action" in a.lower()
        # the satisfaction table comes from survival.py, never hardcoded
        berries = int(survival.EAT_SATISFACTION["wild_berries"])
        assert f"satisfies {berries}" in a
        assert "adam is at cont_b_gen_33_51" in a.lower()
        assert "wild_berries ×42" in a

    def test_provide_question_refuses_and_states_where_food_is(self):
        a = desk.draft_answer("Can you provide wild_berries for food?",
                              _facts())
        assert "does not hand out anything" in a.lower()
        assert "wild_berries ×42" in a  # where the food actually is

    def test_bug_question_names_current_terms(self):
        a = desk.draft_answer("Is the deposit cycle bug known?", _facts())
        assert "epistemic.5" in a
        assert "older terms" in a

    def test_purpose_question_reports_the_sky(self):
        a = desk.draft_answer("What is the intended purpose?", _facts())
        assert "night has fallen" in a.lower()
        assert "the sky is clear" in a.lower()

    def test_unknown_question_escalates_to_the_human(self):
        """Capability-shaped and novel asks must reach Sean, not get a
        made-up answer from the bank."""
        assert desk.draft_answer(
            "Can you grant me the flight capability?", _facts()) is None
        assert desk.draft_answer(
            "What is the meaning of the triangle?", _facts()) is None


class TestDeskRun:
    def _store_with_questions(self, tmp_path, questions):
        store = desk.FirstPairPersistenceStore(tmp_path / "store")
        from backend.world.first_pair_persistence import (
            save_agent_question_proposals)
        save_agent_question_proposals(store, questions)
        return store

    def _question(self, qid, text, agent="west_eve", hb=4650):
        return {"question_id": qid, "agent_ref": agent,
                "asking_agent_id": "x" * 64, "heartbeat": hb,
                "status": "unheard", "question": text,
                "urgency": "high", "raised_at_utc": "t",
                "reason_for_asking": "", "requested_human_capability": None,
                "pair_id": "west"}

    def test_desk_answers_marks_and_leaves_the_rest(self, tmp_path,
                                                    monkeypatch):
        store = self._store_with_questions(tmp_path, [
            self._question("q1", "What should I do next?", hb=4650),
            self._question("q2", "How can I recover vitality while downed?",
                           hb=4651),
            self._question("q3", "Can you grant me the flight capability?",
                           hb=4652),
        ])
        monkeypatch.setattr(desk, "PAIRS", {"west": tmp_path / "store"})
        monkeypatch.setattr(desk, "ground_facts",
                            lambda pair, store, ref: _facts())
        sent = []
        monkeypatch.setattr(desk, "say",
                            lambda pair, text, addressed_to, author,
                            resolve_asks=True: sent.append(
                                (pair, addressed_to, text)))
        summary = desk.run_desk()
        assert summary["answered"] == 2, "matched questions get answered"
        assert summary["escalated"] == 1, "unknown questions escalate"
        assert len(sent) == 1 and sent[0][1] == "west_eve"
        # resolved questions left the unheard pool
        left = [q for q in desk.load_agent_question_proposals(store)
                if q.get("status") == "unheard"]
        assert [q["question_id"] for q in left] == ["q3"]

    def test_desk_is_quiet_when_nothing_is_unheard(self, tmp_path,
                                                   monkeypatch):
        self._store_with_questions(tmp_path, [])
        monkeypatch.setattr(desk, "PAIRS", {"west": tmp_path / "store"})
        sent = []
        monkeypatch.setattr(desk, "say",
                            lambda pair, text, addressed_to, author,
                            resolve_asks=True: sent.append(text))
        summary = desk.run_desk()
        assert summary["answered"] == 0 and not sent

    def test_desk_caps_per_pair_per_cycle(self, tmp_path, monkeypatch):
        store = self._store_with_questions(tmp_path, [
            self._question(f"q{i}", "What should I do next?", hb=4600 + i)
            for i in range(6)
        ])
        monkeypatch.setattr(desk, "PAIRS", {"west": tmp_path / "store"})
        monkeypatch.setattr(desk, "ground_facts",
                            lambda pair, store, ref: _facts())
        monkeypatch.setattr(desk, "say",
                            lambda pair, text, addressed_to, author,
                            resolve_asks=True: None)
        summary = desk.run_desk(max_per_pair=2)
        assert summary["answered"] == 2, "cap bounds a flood of asks"
        assert summary["deferred"] == 4, "the rest wait for next poll"
        assert summary["escalated"] == 0, "matched-type asks do not escalate"
