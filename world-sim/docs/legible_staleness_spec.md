# Legible staleness — the record carries its own age

**One change.** A single factual line in the prompt's PUBLIC RELATIONSHIP
EVENTS section: how old the record's newest entries are. No advice, no
nudge, no operator voice. The age of the silence, in plain words.

---

## 1. Why this and not "last-known position"

The reasoning chain, stated so a null here means something:

1. A free channel shipped at HB1347. **Zero messages** in 100 heartbeats.
   Speaking was priced out, then made free, and nothing changed. The price
   was not the constraint.
2. The relationship ledger holds 252 `co_location` events spanning
   HB1–939 and the prompt renders them all as raw JSON — a wall of
   evidence with **no age on any of it**. Nothing in the frame scales
   "a long time" against "a heartbeat," so nothing reads the record as
   having gone quiet.
3. Adam at HB1436, verbatim: *"the test matrix is complete and Eve is
   unresponsive, so I'm pursuing the water source search independently."*
   The belief is causal in his own reasoning and the record that would
   contradict it carries no timestamp he can read.
4. My first proposal — a last-known-position line **when recently seen** —
   was verified inert before shipping: they have not been within sight of
   each other since the last co-location at HB939, so a recent-sighting
   channel would carry nothing. A mechanism that can never fire is not a
   mechanism. This one fires every heartbeat, for free, from data the
   prompt already loads.

The hypothesis under test: silence is invisible because it is unmeasured,
and measured silence is *talked about*. If the age of the record becomes
legible, the agents' own goal-of-contact should do the rest. If messages
resume, the budget was never the thing; the record just needed to be able
to say how quiet it had gotten.

## 2. The line

Rendered above the events list, every heartbeat, in the section they
already have:

> Public record: 360 messages, the most recent at heartbeat 936 —
> 474 heartbeats ago. The most recent co-location event is from
> heartbeat 939 — 471 heartbeats ago.

That is the whole interface. Two numbers, recomputed from the public
record each heartbeat, no persistence, no new world state. When the
record has no messages: `Public record: no messages yet.` When it has no
co-location events, that clause is absent rather than invented.

## 3. What is deliberately NOT here

- **No advice.** No "you could", "you should", "consider". The world
  states what is in the record. Naming silence as a fact is the entire
  change; telling them what silence means would be telling them what to
  think, which is the build-we-refused-to-write.
- **No operator or physics voice.** This is not a changelog, not a
  physics bump, not a capability grant. It is an export of existing
  public data, computed at read time.
- **No positions.** The relationship ledger does not carry locations, so
  none are invented. The last meeting place is not said.

## 4. Census

Baseline is HB1247–1346 + HB1347–1446 (the free-speech blocks, both 0
messages, "unresponsive" still present in reasoning at HB1436). One row,
same falsifiable test as the last one:

| Question | Baseline | Predicted here |
|---|---|---|
| Messages left, per 100 HB | 0 | non-zero |
| "unresponsive" in decision reasoning | present at HB1436 | absent |
| Co-location events per 100 HB | 0 | unchanged or growing |

The honest null: if messages stay at zero and "unresponsive" stays in the
reasoning, then silence was never the pressure. That closes this line of
mechanism and the next one has to be a world-facing one — sighting
records, summons, or something structural.

## 5. Reversal

The change is render-only. Removing the line restores the prior prompt
exactly; no store, ledger, or record depends on it.
