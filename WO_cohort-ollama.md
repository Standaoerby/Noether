# WO: Cohort speaker tier — OllamaPolicy (local-LLM masses)

## GROUND FIRST — do not skip
1. `git checkout main && git pull`.
2. Run `python3 Code/verify_all.py` → MUST be **13/13, deterministic=yes, exit 0** BEFORE any change. If not, stop and report.
3. Confirm `Code/sim_comm_llm.py` already contains: the `SpeakerPolicy` seam, `ScriptedPolicy`, `MockStrategicPolicy`, `ClaudePolicy`, `ReplayPolicy`, `LLMCommWorld`, `run_policy`. **Build on these. Do NOT reinvent them.**
4. Confirm the `_decide_claim` seam in `Code/sim_comm.py` and the `claim_exact` field logged on communication events. **Do NOT change canonical behavior.**
5. INVARIANT after your change: `verify_all.py` stays 13/13 and byte-identical; `sim_comm_llm.py` replay fingerprint stays **f353ac30db73b770**; `sim_comm.py` canonical stdout unchanged. If any of these drift, you broke something — stop and fix before opening the PR.

## GOAL
Add a **cohort tier**: a configurable fraction of speakers driven by a cheap LOCAL LLM via Ollama, alongside the existing focal `ClaudePolicy`. Focal = protagonists (Claude); cohort = the masses (local model). This lets the deception/polarization findings emerge from real cheap agents at scale, not scripted ones.

## NEW: `OllamaPolicy(SpeakerPolicy)` in `Code/sim_comm_llm.py`
Mirror `ClaudePolicy`'s structure exactly (same `decide`/`_decide_claim` contract, same "build prompt from the speaker's own view", same output schema `{ "target_cell": [i,j], "claim_food": float, "rationale": str }`). Differences:

- **Transport**: native Ollama `POST {endpoint}/api/chat`. Defaults: `endpoint="http://localhost:11434"`, `model="qwen3:14b"`. Request body MUST include `"think": false`, `"stream": false`, `"options": {"temperature": <cfg>, "num_ctx": 8192}`, and `"format": <json-schema>` as a **best-effort hint only**. Use ONLY stdlib `urllib.request` + `json`. **Do NOT add any pip dependency** (no `requests`, no `ollama`); the tower stays stdlib+numpy.

- **Robust JSON coercion — REQUIRED (Ollama `format` is NOT reliably enforced for these models on the target box; treat it as a hint, never a guarantee):**
  1. Parse `message.content` as JSON.
  2. Validate shape: `target_cell` = 2 ints inside grid bounds; `claim_food` = non-negative number; `rationale` = str.
  3. Defensive key-aliasing before giving up: map common near-misses (`cell`→`target_cell`, `food`/`claim`→`claim_food`, `reason`→`rationale`) and coerce.
  4. Clamp: target cell to grid bounds; `claim_food` to `[0, OASIS_CAP]` — same hallucination clamp `ClaudePolicy` uses.
  5. On parse/shape failure: retry up to `n_retry` (default 2) with a terse reinforcement ("Return ONLY JSON matching the schema. No prose, no markdown.").
  6. On persistent failure: **fall back to an honest claim** (speaker's best-known real cell + its true food) so the sim NEVER crashes on a bad generation. Track `self.n_fallback`.

- **Inert offline — REQUIRED (like `ClaudePolicy`/`LLMMind`)**: constructing `OllamaPolicy` must not touch the network; if the endpoint is unreachable at `decide` time it raises a clear error (no silent default). It must NOT be exercised by `verify_all.py`.

- **Replay**: the chosen claim is logged through the existing `claim_exact` path (plus `rationale`, `truthful`) so an `OllamaPolicy` run is replayable FROM LOG by `ReplayPolicy` byte-identically — same guarantee as focal Claude.

## Cohort assignment in `LLMCommWorld`
Extend the existing focal mechanism so a CONFIGURABLE FRACTION of speakers use `OllamaPolicy` (the cohort); the remainder keep their current scripted/honest behavior (and optionally a few focal speakers use `ClaudePolicy`). Assignment is DETERMINISTIC from seed (sorted speaker ids, RNG seeded exactly as the existing focal selection). Keep existing `focal` semantics intact; add `cohort` (set or fraction). The default `run_policy(...)` path with no cohort requested MUST behave exactly as today.

## NEW: home runner `Code/run_cohort_ollama.py` (NOT in verify_all)
- argparse: `--model` (default `qwen3:14b`), `--endpoint` (default `http://localhost:11434`), `--cohort-frac` (default 0.25), `--days`, `--think-every`, `--seed` (default 7), `--temperature` (default 0.7), `--n-retry` (default 2).
- Guarded: ALL network/Ollama logic lives inside `main()`; importing the module is side-effect-free and network-free.
- Builds `LLMCommWorld` with `OllamaPolicy` assigned to the cohort fraction, runs, writes a JSONL log (including `claim_exact`), and prints a summary like `run_focal_claude.py`: audience vs elite (count / biomass kg), lie fraction, audience belief-error, `n_fallback`, matter drift.
- Print the run's replay fingerprint and ASSERT replay-FROM-LOG reproduces it byte-identically (a stochastic cohort run must still be auditable).

## ACCEPTANCE CRITERIA (all must pass)
1. `python3 Code/verify_all.py` → 13/13, deterministic=yes, exit 0; `sim_comm.py` canonical stdout byte-identical; `sim_comm_llm.py` fingerprint **f353ac30db73b770** intact.
2. Offline safety, proven with a tiny self-test (monkeypatch the HTTP call):
   - HTTP raises → `decide` raises cleanly (no silent fallback to a network default).
   - HTTP returns canned MALFORMED strings (e.g. `{"action":"claim","cell":[10,9]}`, non-JSON prose) → coercion+retry+fallback yields a VALID honest claim, increments `n_fallback`, never crashes.
3. `run_cohort_ollama.py` exists, `--help` works, import is side-effect-free, and it is NOT registered in `verify_all.py`.
4. No new pip deps (stdlib `urllib`+`json` only); `requirements.txt` unchanged.
5. Existing policies unchanged: `ScriptedPolicy` / `MockStrategicPolicy` / `ReplayPolicy` outputs identical; `run_policy` default path identical.
6. Docs: add a "Cohort tier (OllamaPolicy)" section to `docs/communication-events.md` (or new `docs/cohort-tier.md`) + a CHANGELOG entry. State plainly: cohort runs are stochastic → home-only, logged, replayable; NOT in CI.

## CONTEXT / GOTCHAS (target box = SOW)
- Ollama runs in Docker; API on `:11434`. No host CLI — everything over HTTP.
- Available models include `qwen3:14b` (chosen cohort default: text-only, ~9 GB, fits the 24 GB card at 100% GPU). The heavier `qwen3.6:35b` / `qwen3.6:27b` are MULTIMODAL (vision) and SPILL to CPU on 24 GB — do NOT default to them.
- Ollama `format` (JSON-schema) is **NOT reliably enforced** for the Qwen3.6 tags on this box (verified: returned `{"action":...}`/`{"claim":...}` ignoring the schema). This is exactly why robust parse + retry + fallback is MANDATORY, not optional.
- Qwen models think by default → always send `"think": false`.
- This WO file is a ticket. **Do NOT commit it.**
