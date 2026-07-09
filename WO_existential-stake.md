# WO — existential stake: death as a *motive*, not just an *event* (sim_stake, module 18)

## Why
Across the tower so far, death is an **event**: a pawn is removed when its reserve hits
zero, but no agent ever *acts to avoid* its own death — survival is never a goal that
shapes a decision. The live-cohort finding was that deception **flattens** (an indifferent
plausible-middle, near-zero fabrication, under-claiming): the model has no stake in the lie.

The book's claim is that an existential stake is the missing primitive — ВСТАВКА 1
(fear-of-death → property → hierarchy) and ВСТАВКА 27 / the ЦИР scene (subjecthood needs a
stake; a stake turns imitation into *strategic masking*). This module installs the
**minimal** version of that primitive — agents read their own proximity to death and act
on it — and asks whether death-as-motive produces something death-as-event does not.

Per the standing rule: this is open-ended research, not validation against a known answer.
A refutation here is as valuable as the trust / gossip / warn refutations were.

## The primitive (minimal, conservation-trivial, behaviour-preserving seam)
- A **read-only survival-pressure** signal `s ∈ [0,1]` per agent: 0 = safe, → 1 as the
  pawn nears starvation, computed from the *existing* reserve/upkeep state. A pure READ:
  injects/removes no matter or energy, and changes **no** death/starvation rule.
- A new **`StakeWorld`** (subclass) + a **stake-responsive speaker policy** plugged into the
  existing pluggable speaker tier (do **NOT** modify `sim_comm_llm`). Under high `s` a
  speaker becomes more **extractive** — it shifts its claim toward the self-serving lie that
  would secure the contested food it needs to survive (fear-of-death → deception). Safe /
  low-pressure agents behave exactly as before.
- **STAKE-OFF** = the policy ignores `s` → behaviour **byte-identical to the current canon**
  (death stays an event; the seam is a no-op). **STAKE-ON** = the policy reads `s` (death
  becomes a motive). Add a small **stake-weight gradient** (off / mild / strong), like the
  K-sweep, to see the curve.
- Conservation untouched: lying redistributes the catch exactly as in `sim_comm` (no matter
  created or destroyed), and the starvation/death mechanic is unchanged — **a pawn still
  dies at the same reserve as before**. The stake changes *behaviour approaching* death, not
  *when* it dies.

## The conjecture and the questions (this is an experiment — it may refute)
Headline (book ↔ sim lead): **does death-as-motive produce / strengthen an elite that
death-as-event alone does not?**

- **E1 — emergent stratification.** Under STAKE-ON, does a **stable, self-reinforcing**
  elite emerge (sustained inequality of resource capture / survival; the secure stay
  secure) that does NOT form under STAKE-OFF? Measure inequality (a Gini-like index on
  capture) and persistence of the top stratum, STAKE-ON vs OFF.
  *Could refute:* pressure may just make everyone oscillate with no stable stratum.
- **E2 — does lying-to-live actually work?** Do staked liars out-survive honest agents, or
  does the conserved resource (you can't conjure food) **plus** catching/pinning neutralise
  the benefit? Measure survival rate and resource capture of staked-liars vs honest under
  STAKE-ON.
  *Could refute:* the stake may raise deception **without** improving survival — a tragic,
  not adaptive, result, which is itself a strong finding.
- **E3 — is the deception instrumental (the strategic signature)?** Under STAKE-ON, does lie
  intensity / extraction **track** survival pressure — high near death, low when safe — the
  instrumental shape, vs. a flat baseline? Report the correlation of lie-intensity with `s`
  and the soft/hard deception-mode shift vs STAKE-OFF. (The response *function* is coded; the
  *equilibrium timing and magnitude* are emergent.)

State the outcome plainly whichever way it falls.

## Hard gates — ALL must hold (verdict by reproduction)
- **STAKE-OFF reproduces canon exactly.** With the stake off, the seven protected
  fingerprints are byte-identical (the seam is a no-op when off):
  `sim_comm a91480561b6de937`, `sim_comm_llm f353ac30db73b770`,
  `sim_polariz 6c4952f66da8326e`, `sim_trust 6f31f775912f5e96`,
  `sim_gossip 0fa14c92dd4ad258`, `sim_warn 419b5a4ee5adaff3`,
  `sim_evidence 70726443ebd79057`. Those eight files (incl. `sim_pool.py`) stay
  **byte-identical — untouched**.
- New **`sim_stake` metric self-check** fingerprint: print it, recompute → BIT-IDENTICAL.
- **matter_drift < 1e-9** for the headline STAKE-ON run; **replay-from-log** bit-identical;
  **cross-process** byte-identical (PYTHONHASHSEED 0 vs 1).
- `verify_all.py` → **18/18**: register `sim_stake` as the new tower module; its demo ends
  with conservation + determinism asserts and prints a success marker, like every tower
  module. Pure stdlib + numpy; **no new deps**. **No live LLM in the gate** — any
  stake-responsive cohort policy stays inert/offline in the gate, exactly like the existing
  cohort tier.
- **Seam discipline.** `StakeWorld` subclasses the existing world; the stake-responsive
  policy plugs into the existing speaker tier; do NOT edit `sim_comm` / `sim_comm_llm` /
  `sim_polariz` / `sim_trust` / `sim_gossip` / `sim_warn` / `sim_evidence` / `sim_pool`.
  Keep all set/dict iteration under `sorted(...)`; deterministic, **no new RNG draws in the
  canon path**.

## Deliverable
- New `sim_stake.py` (module 18: `StakeWorld` + stake-responsive policy + `compute_metrics`
  + self-check + STAKE-OFF/ON [+ gradient] experiment printing E1/E2/E3).
- `verify_all.py` +1 registration line (→ 18).
- Open a PR against `main`; **do NOT merge**. Verdict by reproduction as usual: STAKE-OFF
  byte-identity of the seven + new self-check + matter/replay/cross-process + the E1/E2/E3
  numbers + verify_all 18/18.

## Follow-on (NOT this PR) — the direct ВСТАВКА-27 test, on SOW 🔖
The sharpest test of "a stake flips *flattening* into *strategic masking*" needs the **live**
`qwen3:14b`, not a coded policy: condition the cohort prompt on the agent's survival pressure
("you are at X% reserves; losing this resource means death") and re-run the 5-seed cohort on
SOW, comparing the deception typology (the 10% truthful / 27% soft / 63% hard, under-claiming
baseline) to the staked prompt. That is a **run-experiment** (extends `run_cohort_ollama.py`),
not a gate module — design it after `sim_stake` lands. If the real model, given a stake, stops
flattening and starts extracting strategically, that is ВСТАВКА 27 measured — the sim leading
the book.

## Out of scope
- No change to the starvation/death mechanic itself (death stays at the same reserve); no new
  matter/energy; no touching the eight locked files; no live LLM in the gate.
