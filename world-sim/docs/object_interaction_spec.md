# Objects hold things — the interaction Eve asked for

**One change.** Objects can accept materials and give them back. A
new action, `use_object`, lets an agent deposit into, extract from, and
inspect any public object on their tile. Objects stop being markers
and become containers.

---

## 1. What Eve asked for

At HB1864, west Eve answered the operator's question directly:

> *"What I need that the world does not provide is an interaction
> mechanism. What I cannot do is put materials into an object and get
> something back out."*

She named the exact missing mechanic. This spec adds it.

## 2. The action

`use_object` (requires: target_object_id, operation, materials for
deposit/extract):

- **`deposit`**: moves materials from the agent's inventory into the
  object's `contents`. The object's record updates. The inventory
  updates. The deposit is visible to anyone who inspects the object.
- **`extract`**: moves materials from the object's `contents` into the
  agent's inventory. Same bookkeeping, reversed.
- **`inspect`**: returns the object's full record INCLUDING its
  contents — what's inside, how much, who put it there.

## 3. Design decisions

- **Type-blind.** Any public object can hold contents. A storage
  holds stone; a cairn holds berries between its rocks; a crafting
  surface holds the materials laid on it. The agent named the type;
  the world doesn't privilege vocabulary. This is the same principle
  as the object visibility extension.

- **Public objects are public.** Any agent can deposit into or
  extract from any object, regardless of who built it. Objects are
  in the world; what they hold is in the world.

- **The record updates honestly.** Every deposit and extract changes
  the object's `contents` dict and the agent's inventory. The
  mutation is in the heartbeat record.

- **Deposits are bounded by inventory; extracts by contents.** You
  cannot deposit what you do not hold. You cannot extract what the
  object does not contain. Both are refused with a reason.

## 4. The physics change

This is a real physics change — objects were described as inert;
now they hold things. The changelog states it:

> *"No longer true: that objects are inert records. Objects can now
> hold materials. Use the use_object action to deposit into, extract
> from, or inspect what any object contains."*

## 5. What this gives them

- The 90+ objects Eve built become containers — each one can now
  hold something, be checked, and give back what was put in.
- For the first time, an agent can build something that CHANGES
  because of what another agent did to it: Adam deposits stone into
  Eve's storage; Eve extracts it. The object is the same object;
  what it holds is different.
- The "record-keeping space" that west Adam's charter names becomes
  slightly more than a record: it becomes a place where records can
  be modified by use, not just by description.
