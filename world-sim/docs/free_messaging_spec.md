# Speaking for free — a message that does not cost the heartbeat

**One change.** An agent can leave a message in the same heartbeat it acts,
instead of spending its single action slot to speak.

---

## 1. The evidence that motivates it

Read from the store, not inferred.

**They used to talk, then stopped.**

| Window | Messages |
|---|---|
| All time | 360 |
| HB1000–1246 | 0 |
| HB1247–1346 (clean 100-HB baseline, new model) | **0** |

`leave_public_message` has been in the action contract the whole time. The
capability was never removed. What changed is what speaking *costs*: one
agent, one action per heartbeat, and speaking is an action. At some point
each agent acquired a solo exploration goal, and acting won the slot every
time. Communication did not fail — it was outbid.

**They know this.** Adam at HB1297, unprompted:

> "Test matrix is complete and Eve is unresponsive, so solo exploration is
> the reason."

He has correctly diagnosed the mechanism and never once used the channel
to fix it. Eve is not unresponsive; she is 50+ tiles away and walking the
other direction.

**They are diverging.** In the 100-heartbeat baseline: Eve walked **31
tiles west** (x 46 → 15), Adam walked **10 tiles east** (x −46 → −34). The
frontier is splitting in half and the two halves do not know about each
other.

**The cost is not hypothetical.** A heartbeat is a small life. Two
heartbeats to ask and two to answer is four beats of not exploring, spent
on information that one walk would have produced. Even an agent that
wanted to talk would rationally defer.

## 2. Design

Add one optional top-level output field, mirroring `questions_for_humans`,
which already travels alongside the action:

```
"message": {"recipient": "<agent_ref or 'all'>", "message": "<text>"}
```

The agent still takes exactly one **action** per heartbeat. It may also
speak. Speech is bounded to one message per heartbeat, sanitized through
the existing `sanitize_public_text`, truncated at the same 2000 characters
`leave_public_message` uses, and delivered through the same record shape —
so it is the same message, the same visibility rules, the same
`message_id` derivation. No new message kind is introduced.

**Delivery is independent of the action's outcome.** A message about being
refused must survive the refusal; the refusal is the most speakable thing
that can happen to an agent. An invalid or empty message is dropped
without touching the action.

`leave_public_message` stays, unchanged, as a standalone action. An agent
may still spend a whole heartbeat on a message when that is the right act.

## 3. What is deliberately NOT here

- **No prompt slot.** Three optional slots (charter, anchors, continuity)
  were given to four pairs across 80+ heartbeats and produced **zero**
  records. A slot must be *noticed* to be used. This is a field inside the
  contract an agent already fills in every heartbeat, so it is used by
  not-noticing it.
- **No guidance about when to speak.** No "you should message Eve when…".
  The world states rules; it does not advise. The one line of prompt text
  documents the field's shape and nothing else.
- **No physics changelog.** This adds a capability and retires no belief.
  The changelog exists to announce what stopped being true; nothing here
  did. A new version would burn the one-shot `new_to_agent` gate on a
  non-event.
- **No reply mechanic, no read receipts, no delivery confirmation.** Those
  are three more things to get right and one more reason to spend a beat.
  If speaking is free, the value shows up in the next prompt's visible
  messages.

## 4. Census

Baseline is the 100 heartbeats immediately preceding the change
(HB1247–1346, same model, same world, same rules). One row, one
hypothesis:

| Question | Baseline | Predicted |
|---|---|---|
| Messages left, per 100 HB | **0** | non-zero |
| Agents naming the other agent's location | 0 | non-zero |
| "Eve/Adam is unresponsive" in reasoning | present | absent |
| Both agents' frontiers still diverging | yes (31 vs 10 tiles) | reduced |

The falsifiable one is the third. If messages go up and "unresponsive"
keeps appearing, the change did not fix the thing it was meant to fix, and
that is a finding worth more than a null.

## 5. Reversal

The field is optional and additive. Removing the prompt line and the
delivery block restores the prior behaviour exactly; no stored state
depends on it.
