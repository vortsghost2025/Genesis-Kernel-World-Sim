# Genesis Kernel World Sim — Outsider Briefing

**Purpose of this document:** bring a smart outsider from zero to able-to-critique
in one reading. No codebase access assumed. Every claim below is measured, not
pitched — where we guessed wrong, that is recorded too, because a reviewer who
catches our self-deceptions is more useful than one who admires our results.

---

## 1. What this is

A persistent simulated world inhabited by LLM-driven NPCs. The "first pair" —
Adam and Eve — have been alive for **1,043 heartbeats**. A heartbeat is one
tick of the world: each agent observes, a language model proposes a single
action, the runtime validates and executes it, and everything is persisted.

A second pair ("west") exists as a dormant comparison store, 100+ heartbeats
behind. All live results below are the east pair.

Three constraints shape every decision:

1. **Free-tier models only.** All cognition runs on free lanes (NVIDIA
   Nemotron primary, GLM fallback), enforced by fail-closed gates. No paid
   spend exists anywhere in the loop.
2. **One action per agent per heartbeat.** Action is the scarce resource.
   Anything an agent does — move, gather, speak, build — costs its whole turn.
3. **Everything is persisted, almost nothing is presented.** This is the
   central tension of the project (see §3).

## 2. How it works (the thirty-second version)

- **World:** a tile map (hills, forests, grassland, a single fresh-water tile
  in 80,000) with fog of war. Agents see only nearby tiles; a known-map
  accumulates per agent (Adam: 63 tiles, Eve: 89).
- **Physics versions:** the world's rules carry version numbers
  ("epistemic.1.1"). Notably, there is **no hunger, no food meter, no
  weather** — earlier mechanics were retired, and the agents spent hundreds of
  heartbeats testing mechanics that no longer existed before we learned to
  announce rule changes in plain language.
- **Memory:** every heartbeat is stored forever (~2,000 memories per agent,
  hashed, manifested). But each heartbeat's model call carries only ~16 of
  them (~0.8%) — 6 recent + 6 relevant inside a character budget. The agent
  *is* its prompt, so from its spot, 99% of its past does not exist each turn.
- **Durable slots** (things that bypass memory selection): a self-authored
  **charter** (unwritten after 1,043 heartbeats), **built objects** whose
  descriptions echo back verbatim ("anchors"), and **public messages** (360
  sent — the channel the agents actually live in).
- **Ops:** a read-only watcher sends Telegram alerts on notable events; a
  bridge process resumes the operator's session when an agent needs a human;
  a chain tool advances heartbeats unattended with fail-closed verification.

## 3. What we have done (the honest changelog)

**Runner integrity (5 defects).** The heartbeat launcher advertised safety
properties it didn't enforce — a free-only guard that printed but never
gated, evidence paths that resolved to doubled directories, provider
provenance that was never persisted. Each was reproduced TDD-style (failing
test first), fixed, and specced. Twice since, our *own* fixes introduced new
defects (a `--log` flag passed to a parser that rejects it killed every
spawn; a test that asserted the bug). Both were caught by running, not by
reading — now a standing lesson: claims are checked against execution.

**Transmission, not new pressure (Phase 1).** The agents couldn't see water
or hazards the board already contained — the fog projection dropped them.
We added the missing fields to observations only. Result: Adam navigated to
the single water tile and gathered water. A complete causal chain from fix
to behavior.

**Observation persistence.** Every per-agent observation is now audit-logged,
so "what did the agent actually see?" is answerable after the fact.

**Known-map merge order.** Agents were blocked from tiles they could see
because the known-map merged *after* movement validation. Reordered to merge
before acting. Reachability blocks: zero across 100+ heartbeats since.

**A spec we killed before implementing.** A "weather dial" phase claimed the
world already cycled weather and needed only wiring. Measured before
implementation: the weather code belonged to a different simulation; our
world had no weather at all. The spec was corrected on the record instead of
implemented — wiring it would have smuggled in a new mechanic under a
"read-only" label.

**Phase B: anchors (ran to a null result).** Hypothesis: built objects whose
descriptions echo back verbatim give findings the charter's durability, and
agents will use the slot because it requires no new decision. 100-heartbeat
census: **zero new builds in 100 heartbeats** — while the agents mapped 100+
new tiles, found water, and never got stuck or confused. The slot works (19
objects each render verbatim); they don't want it. Verdict recorded: the
unmet need is not individual findings.

**Memory synthesis (in progress).** The summaries layer — designed to be
compressed understanding — ran on extractive stubs ("Previous action move:
success"), 16 of them for 2,000+ memories. We admitted model-written rollups
under strict rules: testimony, never evidence (raw always outranks it);
every named entity must occur verbatim in covered sources (machine-checked);
owner-bound IDs refuse cross-agent coverage; phased oldest-first backfill,
bounded per run. ~60 rollups landed so far. Failures taught us the free-tier
model thinks out loud and truncates its own JSON — fixed with prompt bans,
temperature zero, and a repair ladder. Residual failure rate ~10%, tolerated
by design (gaps stay visible, retried next run).

## 4. What the agents are actually like

- Tireless, systematic surveyors. Eve tracks Adam's plans across heartbeats
  from fragments; Adam names his surveys ("systematic hill survey").
- Socially grounded: founding statements, cooperation language, 360 messages.
  Their identity lives in conversation, not in the charter slot built for it.
- Never stuck recently: 0 reachability blocks, 0 questions in 100 heartbeats.
- They found two real board deadlocks before we did (a food-yield net-zero,
  a goods catch-22) — in one case the spec author noted the agents found in
  24 heartbeats what he missed in 100.

## 5. Open threads (where we know we don't know)

1. **The charter question.** Identity slots go unused while identity talk
   fills messages. Our reframed hypothesis: the scarce resource isn't
   identity but *joint plans* — what the pair agreed, surviving until next
   heartbeat without re-saying it. Unproven.
2. **Scaling.** Relevance scoring iterates all memories every heartbeat
   (O(n), n ≈ 2,000 and growing); key files load whole (2.5MB manifest).
   Fine at 1,043 heartbeats; visibly degrades by ~10x. No fix yet, by choice.
3. **Synthesis pace vs accrual.** Every heartbeat adds memories; backfill
   needs a standing rhythm or the gap re-opens. No cadence set yet.
4. **The west pair.** Dormant comparison store. Revive as a control, or
   retire? Undecided.
5. **Preamble residual.** ~10% of synthesis groups need retries. Tolerated,
   not solved.

## 6. What we are asking you

You have no code and no history with us. That is the point — you can see the
shapes we are blind to. We want:

1. **Assumption challenges.** What are we treating as load-bearing that looks
   decorative from outside — or vice versa? (Example of the genre: we treated
   "storage" and "presentation" as one problem for weeks; they are two.)
2. **Missed improvements.** Given the constraints (free-tier, one action per
   turn, ~0.8% memory presentation), what is the highest-leverage change we
   have not tried? Small, structural answers preferred over new mechanics.
3. **Measurements we should be taking but aren't.** Our discipline is
   "measure the board before changing the rules" — where are we flying blind?
4. **The biggest risk.** If this project fails or stalls in the next 1,000
   heartbeats, what is the most likely cause, and what would you do about it
   this week?
5. **The NPC question.** If you woke each heartbeat with 1% of your past and
   one action to spend, what would you need most that no slot currently
   provides? Answer from inside that situation, not from the architecture.

Ground rules for suggestions: no paid services, no new agent actions unless
you argue why a structural change can't do it, and every proposal should name
how it would be falsified — we run 100-heartbeat censuses and record nulls
as findings.
