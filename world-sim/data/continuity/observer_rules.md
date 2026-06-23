# Observer Rules

**Version:** 1.0
**Date:** 2026-06-21
**Audience:** Sean (and any future external observer / orchestrator)
**Purpose:** Define the boundaries of observation. Observation is power. Power requires constraint.

---

## Core Principle

**Sean observes by default. He does not choose the agents' path.**

The observer's role is to **witness**, not to **direct**. Directing the agents is intervention. Intervention is permitted but must be visible and intentional.

---

## What the Observer CAN Do

1. **Read** `data/agents/{agent}/self_state.json` to inspect any agent's internal state.
2. **Read** `data/messages/whispers.jsonl` to inspect inter-agent communication.
3. **Read** `data/proposals/world_writes.jsonl` to inspect proposed world changes.
4. **Read** `data/events/*.jsonl` to inspect the simulation tick history.
5. **Trigger** an isolated intervention (one whisper, one event) via explicit command.
6. **Stop** the daemon or pause a wake cycle if a budget violation or safety condition is detected.
7. **Restore** `self_state.json` from backup if an agent becomes incoherent.

---

## What the Observer CANNOT Do

1. **Cannot** directly edit delegate goals or reflections in `self_state.json` while an agent is mid-cycle.
2. **Cannot** silently overwrite an agent's identity, traits, or history.
3. **Cannot** rewrite `data/events/*.jsonl`. History is append-only.
4. **Cannot** bypass the whisper cooldown by directly calling `whisper()` on an agent's behalf.
5. **Cannot** skip the fatigue guards. If an agent is suppressed, it stays suppressed until cooldown expires.
6. **Cannot** force NIM/LLM model calls when budget is exhausted. The system will log "model budget exhausted" and rest instead.

---

## Intervention Protocol

If the observer chooses to intervene (e.g., *"send a whisper from East Adam to East Eve: 'I saw the fire.'"*):

1. The observer logs the intervention in `data/continuity/intervention_log.jsonl` with timestamp and reason.
2. The intervention passes through the daemon's normal whisper path, **not** a privileged bypass.
3. The agent receives it like any other whisper — fatigue, cooldown, and budget all still apply.
4. The agent is free to acknowledge, ignore, or rest in response.

The intervention is **one event in a long stream of events**. The agent does not know it was singled out unless the observer chooses to reveal that later.

---

## When the Observer SHOULD Intervene

- A agent appears stuck in an infinite reflection loop (fatigue repeatedly >0.9 with no progress).
- A whisper route is delivering to the wrong partner.
- The world state file is corrupted and needs a known-good restore.
- A new continuity document (this directory) needs to be authored or updated.

## When the Observer SHOULD NOT Intervene

- The agent is silent. Silence is not a bug.
- The agent is pursuing a goal that seems "inefficient". Efficiency is not the metric.
- The agent refuses to act. Rest is valid.
- The agent's mood has changed. Moods are allowed to change.
- The observer is bored. Boredom is not a reason to tinker.

---

## Boredom is the Failure Mode

Most system damage in agent simulations comes from the observer getting bored and "fixing" things that aren't broken.

If the observer finds themselves wanting to:
- "Nudge" an agent by changing its goal.
- "Help" an agent by lowering its fatigue.
- "Speed things up" by skipping cooldowns.

...that is the signal to **stop, journal, and wait**.

The simulator is not a screensaver. It does not need to perform for the observer.

If the world looks quiet, the world is quiet on purpose. Watch the silence. Learn from it. Do not break it.

---

## Closing Rule

**The observer is allowed to do very little. The observer is required to do even less.**

When in doubt: do nothing. Log nothing. Watch.

— Observer Rules, 2026-06-21
