# NVIDIA model context limits — the 130k cap was our own invention

**2026-10-10.** Sean reported GLM-5.3-flash and DeepSeek V4.1-flash
listing at ~130k context on his NVIDIA key, forcing premature compaction
— the model's real window is 1M.

## What was actually wrong

`C:/Users/seand/.config/opencode/opencode.json` — the OpenCode client
config, not the repo — carried `"limit": {"context": 131072}` for both
models on the `nvidia` provider. Nobody measured that number. It was a
conservative placeholder, and the client compacts any conversation that
approaches it, so every session on those models was being folded at 13%
of the real window.

NVIDIA's `/v1/models` endpoint returns **no context metadata at all**
(just id/owner/created), so nothing upstream was going to correct it.

## The measurement

Escalating `max_tokens` probes against `integrate.api.nvidia.com` with a
tiny prompt, reading the rejections:

| max_tokens | z-ai/glm-5.3-flash |
|---|---|
| 131072 | ACCEPTED |
| 140000 | ACCEPTED |
| 262144 | ACCEPTED |
| 500000 | ACCEPTED |
| 1048576 | rejected — *"This model configuration accepts at most 1048576 combined input and output tokens"* |

The server's own error message names the limit: **1,048,576 combined
input+output**, matching OpenRouter's metadata (`context_length:
1048576`) and the model's published spec.

`deepseek-ai/deepseek-v4.1-flash` timed out at *every* size including
tiny requests — a route availability problem, not a size rejection.
Its limit was set to 1048576 on OpenRouter-metadata grounds, not
server-verified. Re-verify with the same escalation probe when the
route answers again.

## The fix

`opencode.json` now reads `"limit": {"context": 1048576, "output":
65536}` for both models. Output raised from 16384 because the server
accepted `max_tokens=500000` — the old output cap was also invented.

## The method, for next time

A tiny-prompt + oversized-`max_tokens` request gets rejected with the
limit named in the error, without paying for a large prompt. Escalate
until rejected; the last rejection is the truth. Probe scripts kept at
`world-sim/.scratch/probe_nvidia_escalate.py`.

Also recorded: NVIDIA key #0 (fingerprint `20d0f0c517d9…`) went dead
(403) since the Sept 30 census and is now denylisted — 22 fingerprints
total.
