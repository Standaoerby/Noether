# WO: trust-weighting — does accountability break the lie equilibrium?
# (module 14, `sim_trust.py`; deterministic, NO endpoint / NO LLM)

## Goal
Add a 14th module `Code/sim_trust.py` that makes listeners **accountable**: each listener
tracks a per-speaker reputation, verifies claims when it later visits the claimed cell, and
**discounts claims from speakers it has caught lying**. Then measure whether this accountability
**breaks the extraction equilibrium** that `sim_comm`/`sim_comm_llm` exposed (deceptive elite
captures biomass; honesty ≈ silence). Trust is a property of the *listener*, orthogonal to who
speaks, so this runs on the existing deterministic regimes — no live model needed.

## Why (book framing — Теория Элит)
Right now belief is **naively credulous**: a claim enters the listener's memory as fact regardless
of the speaker's track record (the `# naive trust about a remote cell` loop). That zero-cost
credulity is exactly what makes lying an equilibrium. The question for an elite-theory bench:
does *accountability* (reputation + discounting) neutralise the liar's capture? Expected nuance to
measure, not assume: local per-listener accountability is **slow** — every victim must independently
discover the lie, and re-seeded oases hand the liar fresh lies — so capture likely **shrinks but
does not vanish**, with a lag the liar profits from. That residual is the finding.

## Part A — behaviour-preserving seam in `sim_comm.py` (canon MUST stay byte-identical)
Factor the inline listener-absorption block in `step()` (the loop commented
`# naive trust about a remote cell`, currently writing `self.mem[L.oid][B] = (claim, self.t)` and
updating `from_hearsay`) into an **overridable method** whose default body is the EXACT current
logic, then replace the inline loop with a call to it:

```python
def _absorb_claim(self, L, B, claim, true_B, spk):
    """Listener L folds speaker spk's claim about remote cell B into belief.
    Default = naive trust (unconditional). sim_trust overrides to weight by reputation.
    Behaviour-preserving: identical to the prior inline loop body."""
    if B == (L.i, L.j):
        return
    self.mem[L.oid][B] = (claim, self.t)
    if abs(claim - true_B) > 1e-9:
        self.from_hearsay[L.oid].add(B)
    else:
        self.from_hearsay[L.oid].discard(B)
```

Nothing else in `sim_comm.py` changes. This mirrors how the `_decide_claim` speaker seam was added.
**Verify byte-identical:** `sim_comm.py` stdout fingerprint stays `a91480561b6de937`;
`sim_comm_llm` replay stays `f353ac30db73b770`; `sim_polariz` self-check stays `6c4952f66da8326e`.

## Part B — new module `sim_trust.py` (module 14): `TrustCommWorld(CommWorld)`
Auxiliary state only (plain numbers/dicts — **no matter/energy, no RNG**, does not touch `self.rng`):
- `self.trust`: `{listener_oid: {speaker_oid: float∈[0,1]}}`, **default 1.0** (full benefit of the
  doubt → trust-ON starts identical to trust-OFF and diverges only as lies are verified).
- `self.claimed_by`: `{listener_oid: {cell: (speaker_oid, claimed_food)}}` — who last told L about
  each cell, and what they claimed.

Lifecycle (mirror the existing dict handling in `step()`):
- on **death**: drop `trust[oid]` and `claimed_by[oid]` (alongside the `mem/belief/from_hearsay` pop).
- on **birth**: inherit *copies* from the parent (alongside the `mem/belief/from_hearsay` inheritance)
  — reputation is heritable like memory. 🔖

Override `_absorb_claim(self, L, B, claim, true_B, spk)`:
- if `B == (L.i, L.j)`: return.
- **always** record accountability: `self.claimed_by[L.oid][B] = (spk.oid, claim)` (so any later
  visit can verify, regardless of the gate — lets trust both fall *and* recover).
- consult `w = self.trust[L.oid].get(spk.oid, 1.0)`. **Trust gate (definition, not tuned):**
  - if `w >= TAU_TRUST`: absorb exactly as default (write `mem[B]`, update `from_hearsay`).
  - else: **skip the belief write** — a sufficiently-distrusted speaker no longer moves L's
    foraging belief. (Accountability tracking still happened above.)
  Keep a clear separation: *what I was told* (always recorded) vs *what I act on* (gated by trust).

Override `_observe(self, a)`:
- `super()._observe(a)`  # senses true food at (a.i,a.j), discards it from `from_hearsay`.
- **verification:** if `(a.i, a.j)` in `self.claimed_by[a.oid]`: take `(spk_oid, claimed)`, read
  `true_food = float(self.plant[a.i, a.j])`, update `self.trust[a.oid][spk_oid]` by the rule below,
  then pop that `claimed_by` entry.

Trust update rule (definitions, document as such; tune only if degenerate). With `e = |claimed - true_food|`:
- kept promise (`e <= TOL_TRUST`): `trust = 1 - (1 - trust) * KEEP_RECOVER`   # recover toward 1
- broke promise (`e  > TOL_TRUST`): `trust = trust * BREAK_DECAY`             # multiplicative penalty
clamp to `[0,1]`. Suggested constants: `TAU_TRUST=0.35`, `TOL_TRUST=0.05` kg (matches the
truthful band), `BREAK_DECAY=0.5`, `KEEP_RECOVER=0.5`. No randomness anywhere.

## Part C — the experiment (deterministic; NO endpoint, NO LLM)
For each regime in `{none, honest, deceptive, mock-strategic}` run the substrate **twice** at the
same `seed=7`, same `DAYS`: **trust-OFF** (plain `CommWorld`; for `mock-strategic` use the existing
`MockStrategicPolicy` via the `sim_comm_llm` path) vs **trust-ON** (`TrustCommWorld`, same speaker
policy). Print one table comparing ON vs OFF with the deltas:
- `elite_gap = elite mean-body − audience mean-body` (ON, OFF, Δ)
- `audience belief-error` in kg (ON, OFF, Δ)
- end-of-run **mean trust held in deceptive speakers vs honest speakers** (the "accountability
  bites" signal — should collapse for liars, stay high for honest)
- residual capture under ON (is the deceptive/mock elite still ahead, and by how much?)
End the printout with the one-line answer it computes: *does trust-weighting shrink the
deceptive/mock capture gap (and by how much), and does honesty become competitive again?*

## Part D — gate + invariants
- `sim_trust.py` self-verifies on run: `assert matter_drift < 1e-9`; **replay-FROM-LOG bit-identical**
  (the trust world is fully deterministic → it must replay from its own log, like the cohort runner);
  print a stable **metric fingerprint** + a self-check recompute that is bit-identical; cross-process
  byte-identical (`PYTHONHASHSEED` 0 vs non-0).
- Add to `verify_all.py` as **module 14**; full gate **14/14** deterministic (runs twice, byte-identical).
- **PROTECT (must stay byte-identical after Part A):** `sim_comm` `a91480561b6de937`,
  `sim_comm_llm` `f353ac30db73b770`, `sim_polariz` `6c4952f66da8326e`.
- Pure **stdlib + numpy**, no new deps. Diff scope: `sim_comm.py` (seam refactor ONLY),
  NEW `sim_trust.py`, `verify_all.py` (+1 entry), `CHANGELOG.md`. Do **not** commit this WO file.
- Stack on **main** (merge PR #6 first), not on the integration branch.

## Acceptance
1. Part-A refactor proven behaviour-preserving (`sim_comm` stdout byte-identical, `a91480561b6de937`).
2. Gate **14/14** deterministic; all three protected fingerprints intact.
3. `sim_trust` prints the ON/OFF table + the headline answer; `matter_drift < 1e-9`; replay-from-log
   bit-identical; metric self-check bit-identical; cross-process byte-identical.
4. Open a PR with a short summary: the capture-gap Δ per regime and whether accountability neutralises
   the lie. (I verify by reproduction: pull the files, rebuild, confirm fingerprints + the ON/OFF deltas.)
