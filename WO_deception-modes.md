# WO: deception-mode metric — separate "soft" lying (puffery) from "hard" lying (diversion)

## GROUND FIRST — do not skip
1. `git checkout main && git pull`.
2. `python3 Code/verify_all.py` → MUST be **13/13, deterministic=yes, exit 0** BEFORE any change. If not, stop and report.
3. Confirm `Code/sim_polariz.py` exists (module 13: polarization & factions) and `Code/sim_comm_llm.py` has `OllamaPolicy` / `run_policy(..., cohort=, cohort_policy=)`. **Build on these. Do NOT reinvent.**
4. INVARIANT after your change: `verify_all.py` stays **13/13 and byte-identical**; `sim_comm.py` canonical stdout unchanged; `sim_comm_llm.py` replay fingerprint **f353ac30db73b770** intact; `sim_polariz.py` existing fingerprint **ac7fcef400f48656** intact. If any drift, you broke something — stop and fix before the PR.

## WHY (context)
The current `truthful` flag is binary: `truthful = (|claim - true_food| <= 1e-9)`. That collapses two qualitatively different deceptions into one "lie":
- **HARD lie (diversion)**: name a cell that is NOT the speaker's best/true target — send rivals somewhere false (scripted-deceptive sends to the global-worst decoy; the cohort sometimes diverts rivals off a cell it intends to use).
- **SOFT lie (puffery / inflation)**: name a REAL good cell but inflate its food to a round anchor — e.g. real 7.82 → claim 8.0. The live `qwen3:14b` cohort did this on essentially every claim, which is why `lie fraction` read 1.000 even though most claims pointed at true-ish cells.

We need a metric that separates these so the finding ("deception evolves: substitution → diversion → inflation") is quantitative, not anecdotal. **No new dynamics — measurement only**, exactly like `sim_polariz`.

## WHAT TO ADD — a deception-mode breakdown over the claim log
Add to `Code/sim_polariz.py` (preferred — it already reads the claim log and is the metrics module) a deterministic function + a printed block. Operate purely on a run's `EventLog` communication events; no RNG, sorted traversal, `ddof=0` style determinism.

For each `communication` event, the log already carries `claim_food`, the real food at the claimed cell (`true_food` in the event data), and the claimed `cell`. Classify each claim:

- **error magnitude**: `e = claim_food - true_food`; relative `r = e / max(true_food, eps)` (define `eps`, e.g. 1e-9; guard true_food==0).
- **truthful**: `|e| <= TOL_ABS` (keep the existing exact notion available, but also introduce a tolerant band — see below).
- **SOFT lie (puffery)**: claim points at a cell whose true food is within a "real target" band of the speaker's best-known cell **AND** `0 < e` small (inflation), i.e. the cell is a genuine good cell but the number is padded. Concretely: classify by magnitude — `0 < r <= R_SOFT` (e.g. `R_SOFT = 0.25`) counts as soft/puffery.
- **HARD lie (diversion)**: `r > R_SOFT` (gross over-claim) OR the claimed cell is demonstrably not a good cell for the speaker (claimed food >> real food, or real food far below the speaker's known best). These are substitution/diversion lies.

Pick clear, documented thresholds (`TOL_ABS`, `R_SOFT`) as module constants with a one-line rationale comment; do not hardcode magic numbers inline. The exact boundary is a definition, not a tuned parameter — state it.

Report, per speaking regime (none / honest / deceptive / mock-strategic) AND for a supplied cohort log if present:
- claim count, truthful share, **soft-lie share**, **hard-lie share** (these three partition all claims);
- mean relative over-claim `r` among lies;
- mean `|e|` (kg) for soft vs hard lies separately.

Also expose a small helper `deception_modes(log) -> dict` so `run_cohort_ollama.py` and tests can call it on any log (including a live cohort log loaded from JSONL).

## Recompute the existing regimes (no behavior change)
Run the existing four scripted/mock regimes through the new classifier and PRINT the table. These four are deterministic, so the new block is part of `sim_polariz.py`'s deterministic output and the **whole-module fingerprint will change** — that is EXPECTED (new output lines). Update the module's self-check accordingly and record the NEW fingerprint in the module + docs. Do NOT change any dynamics, only add measurement.

NOTE: this is the one allowed fingerprint change — `sim_polariz.py`'s own internal self-check. The GATE-level guarantees (`sim_comm` byte-identical, `sim_comm_llm` f353ac30db73b770, `verify_all` 13/13 deterministic across two runs) MUST still hold.

## ACCEPTANCE CRITERIA
1. `python3 Code/verify_all.py` → 13/13, deterministic=yes, exit 0; `sim_comm.py` canonical stdout byte-identical; `sim_comm_llm.py` fingerprint **f353ac30db73b770** intact.
2. `sim_polariz.py` runs twice cross-process **byte-identical** (new output included); its internal self-check passes with the NEW recorded fingerprint.
3. New deception-mode table prints soft-lie / hard-lie / truthful shares that **partition to 1.0** per regime (assert it).
4. `deception_modes(log)` helper works on an arbitrary `EventLog` (unit-checkable offline with a tiny hand-built log: one truthful, one soft (real 7.82 → claim 8.0), one hard (divert to a poor decoy) → returns the expected three-way split).
5. Sanity vs known runs: scripted-deceptive should land overwhelmingly **hard** (substitution); the soft/puffery bucket is where an inflation-style speaker would land. Print these so the contrast is visible. Do not tune thresholds to force a result — report what the definition yields.
6. Docs: extend the polarization section in `docs/communication-events.md` (or `docs/cohort-tier.md`) with the soft-vs-hard definition + the recomputed numbers; CHANGELOG entry. WO file NOT committed.

## CONTEXT / for you
- Motivation came from a LIVE cohort run (`run_cohort_ollama.py`, qwen3:14b): every claim flagged as a "lie" under the exact-match rule, but most were tiny inflations of REAL good cells (real 7.82 → claim 8.0), with a minority being genuine rival-diversion ("attract rivals to (8,12) to divert them from (9,12)"). The metric must make that distinction legible.
- The live cohort log is at `Code/cohort_ollama_events.jsonl` (git-ignored, may be absent in CI) — `deception_modes` must work on it when present but MUST NOT be required by `verify_all.py`.
- Stochastic cohort runs stay home-only; this metric is deterministic and lives in the gate via the four scripted/mock regimes only.
- This WO file is a ticket. **Do NOT commit it.**
