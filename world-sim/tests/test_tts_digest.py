"""TTS-friendly messages: what they did, what they said, what they need.

Sean hears these through a screen reader. Every coordinate, every
heartbeat number, every move count is noise that makes the message
harder to understand. What he needs to hear:

- What they did (in plain words)
- What they said to each other (quoted)
- Messages to him or questions they have

NOT:
- Coordinates
- Heartbeat numbers
- Move counts
- Telemetry of any kind

This rewrites the steward's hourly digest to produce narrative
sentences, and the agent-watch alert format to be one clean line.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM / "scripts"))

import world_steward as ws  # noqa: E402


class TestDigestIsNarrative:
    def test_no_coordinates(self):
        """The word 'cont_a_gen' or any tile-id pattern must never
        appear. Sean hears this through TTS."""
        msg = ws.build_digest(
            east={"summary": "Adam is waiting. Eve is walking toward him.",
                  "quote": "I'm on my way to you",
                  "question": None},
            west={"summary": "Adam built a tower. Eve is standing by.",
                  "quote": None,
                  "question": "What should I do next?"},
        )
        low = msg.lower()
        for junk in ("cont_", "gen_", "hb", "heartbeat", "moves",
                     "gather:", "tile", "coordinate"):
            assert junk not in low, f"TTS noise: {junk!r} in: {msg}"

    def test_names_and_actions_in_plain_words(self):
        msg = ws.build_digest(
            east={"summary": "Adam is waiting at the start.",
                  "quote": "I'm here, come find me",
                  "question": None},
            west={"summary": "Eve deposited clay into a container.",
                  "quote": None,
                  "question": None},
        )
        assert "Adam" in msg
        assert "waiting" in msg
        assert "Eve" in msg
        assert "clay" in msg

    def test_quotes_appear(self):
        """When they message each other, Sean hears the words."""
        msg = ws.build_digest(
            east={"summary": "They exchanged messages.",
                  "quote": "I'm on my way, stay there",
                  "question": None},
            west={"summary": "Quiet.",
                  "quote": None,
                  "question": None},
        )
        assert "on my way" in msg

    def test_questions_reach_him(self):
        """An agent asking the operator something is the one thing
        that must always be audible."""
        msg = ws.build_digest(
            east={"summary": "Adam is waiting.",
                  "quote": None,
                  "question": None},
            west={"summary": "Adam has a question.",
                  "quote": None,
                  "question": "Is there anything left to test?"},
        )
        assert "question" in msg.lower()
        assert "anything left" in msg

    def test_quiet_pairs_are_one_word(self):
        """A pair that did nothing gets 'quiet', not a paragraph."""
        msg = ws.build_digest(
            east={"summary": "quiet",
                  "quote": None,
                  "question": None},
            west={"summary": "quiet",
                  "quote": None,
                  "question": None},
        )
        assert len(msg) < 80, f"too long for a quiet period: {msg}"
