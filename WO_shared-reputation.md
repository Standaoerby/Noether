# WO: shared reputation / gossip — does pooling evidence pin the brazen liar?
# (module 15, `sim_gossip.py`; deterministic, NO endpoint / NO LLM)

## Goal
Add a 15th module `Code/sim_gossip.py` that lets listeners **exchange reputation**: a listener who
has personally caught speaker S lying can tell co-located neighbours, so they distrust S without
having verified S themselves. Test whether this **pooling of evidence breaks the indiscriminate
liar** that local accountability (`sim_trust`, module 14) failed to dent — and whether it opens a
new attack surface: **meta-lying about who is trustworthy**. Plus a one-line cosmetic fix to
`sim_trust.py` (Part 0).

## Why (book framing — Теория Элит)
Module 14 found local accountability **asymmetric**: it bit the strategic liar (mock, −60%) but
barely the indiscriminate one (deceptive, ≈0). The quantified reason: trust in liars stalled
**just above the gate** (0.391/0.423 vs τ=0.35) because each listener got too few independent
verifications of one speaker to pin it. **Shared reputation is the institutional answer to local
slowness** — it pools scattered verifications so the brazen high-volume liar can finally be caught.
But it **relocates the contest to the reputation system itself**: a speaker (or a colluding bloc)
can lie about *who is honest* — smear trusted rivals, vouch for fellow liars. Hypotheses to measure:
(a) honest gossip shrinks the deceptive gap that local trust left and pushes trust in liars **below**
the gate; (b) **meta-lying restores capture even under gossip** — the demagogue who games reputation
is the new equilibrium. The arc for the book: local honesty-enforcement → institutional reputation →
**reputation capture**.

## Part 0 — cosmetic fix in `sim_trust.py` (prose only, no fingerprint impact)
The per-regime verdict loop prints the word "shrinks" unconditionally; for `deceptive` the gap grows
(`shrink = gap_off − gap_on = −0.004`), so it currently prints the contradictory "shrinks −0.004".
Replace the loop body so the verb follows the sign (see exact new code below). This changes only the
human-readable epilogue (printed AFTER the metric fingerprint + replay), so `6f31f775912f5e96`,
`4ad27743d1e0d3d5`, cross-process determinism, and conservation are all unaffected.

```python
    for r in ("deceptive", "mock-strategic"):
        d = res[r]
        shrink = d["gap_off"] - d["gap_on"]          # OFF - ON: positive = accountability shrank the gap
        pct = (shrink / d["gap_off"] * 100.0) if abs(d["gap_off"]) > 1e-9 else float("nan")
        still = "still ahead" if d["gap_on"] > 1e-3 else "neutralised"
        if shrink > 0.01:
            change = f"shrinks {shrink:.3f}, {_fmt(pct, '{:.0f}')}%"
        elif shrink < -0.01:
            change = f"grows {-shrink:.3f}, {_fmt(-pct, '{:.0f}')}%"
        else:
            change = f"\u2248 unchanged (\u0394{d['gap_on'] - d['gap_off']:+.3f})"
        print(f"{r}: capture gap {d['gap_off']:+.3f} -> {d['gap_on']:+.3f} kg "
              f"({change}); elite {still} under trust.")
```
Also lightly correct the closing sentence so it states the asymmetry rather than implying the gap
always shrinks (prose only): e.g. "accountability bites the strategic liar but barely the
indiscriminate one; being local and lagged, it does not erase capture — the asymmetry is the finding."

## Part A — behaviour-preserving seam in `sim_comm.py` (canon MUST stay byte-identical)
Add a no-op social-exchange hook called once per think-day, AFTER the `_observe` loop ("sensation
overrides hearsay") and BEFORE the cognition/migration loop. Pass it the `here` co-location dict that
the think-day already builds:

```python
def _social_exchange(self, here):
    """Co-located agents exchange information beyond foraging claims. Default: no-op
    (sim_comm has no social layer). sim_gossip overrides to pool reputation."""
    return
```
Insert the single call `self._social_exchange(here)` between the observe loop and the cognition loop.
A no-op prints nothing and changes no state → **verify `sim_comm` stdout byte-identical
`a91480561b6de937`**; `sim_comm_llm` `f353ac30db73b770`, `sim_polariz` `6c4952f66da8326e`,
`sim_trust` `6f31f775912f5e96` all unchanged.

## Part B — new module `sim_gossip.py` (module 15): `GossipCommWorld(TrustCommWorld)`
Override `_social_exchange(self, here)` to pool per-speaker reputation among co-located agents,
**trust-weighted by how much the receiver trusts the gossiper** (you believe reputation reports from
sources you trust). Auxiliary numbers only — **no matter/energy, no RNG**:

```
GOSSIP_RATE = 0.3      # definition: how far a receiver moves toward a (trusted) gossiper's opinion
```
For each cell with ≥2 agents:
- **snapshot** every present agent's trust vector at the start of the round (so the update is
  order-independent within the cell — determinism).
- for each receiver B and each other present agent A:
  - `w_src = snapshot[B][A]`  (B's trust in A as a source; default 1.0)
  - for each speaker S in `snapshot[A]`:
    - `report = self._gossip_report(A, S, snapshot[A][S])`   # honest default = the value A holds
    - `w = GOSSIP_RATE * w_src`
    - `trust[B][S] = (1 - w) * trust[B][S] + w * report`   (convex combo → stays in [0,1])

`_gossip_report(self, A, S, rep)` — **default honest**: `return rep` (A reports its true assessment).

**Meta-liar regime:** add a flag (e.g. `meta=True`) under which designated meta-liars **invert the
reputation signal** they emit — `return 1.0 - rep` (badmouth the trusted, praise the distrusted),
modelling "lying about who is honest." Make the meta-liars the lying speakers themselves (the elite
that already lies about food now also poisons reputation to shield its bloc). Keep it deterministic;
if a sharper smear/vouch (drive honest-speaker reputation →0, fellow-liar →1) is cheap, that's fine,
but the inversion is the acceptable baseline.

Lifecycle: gossip touches only `self.trust`, which `TrustCommWorld` already inherits/cleans at
birth/death — no new per-agent state required.

## Part C — the experiment (deterministic; NO endpoint, NO LLM), seed 7, same DAYS
Compare **three accountability conditions** on the lying regimes `{deceptive, mock-strategic}`:
- **OFF** — plain `CommWorld` (no trust)
- **LOCAL** — `TrustCommWorld` (module 14)
- **GOSSIP** — `GossipCommWorld`, honest reputation-sharing
Plus a fourth column for the lying regimes: **GOSSIP+META** — gossip on, lying speakers meta-lie.

Print a table with, per regime/condition:
- capture gap (elite − audience mean body, kg) and the deltas LOCAL−OFF, GOSSIP−LOCAL, META−GOSSIP
- audience belief-error (kg)
- **end-of-run mean trust held in liar speakers** — the key signal: does GOSSIP push it **below τ=0.35**
  (pinning) where LOCAL stalled at ~0.39/0.42?
End with the headline answers it computes:
1. Does shared reputation shrink the **deceptive** gap that local accountability left (LOCAL Δ≈0 →
   GOSSIP Δ<0), and does trust in liars finally drop below the gate?
2. Does **meta-lying** restore/inflate capture under gossip (META vs GOSSIP) — i.e. is gaming the
   reputation system the new extraction channel?

## Part D — gate + invariants
- `sim_gossip.py` self-verifies: `assert matter_drift < 1e-9`; **replay-FROM-LOG bit-identical**;
  stable **metric fingerprint** + self-check recompute bit-identical; cross-process byte-identical
  (`PYTHONHASHSEED` 0 vs non-0).
- Add to `verify_all.py` as **module 15**; full gate **15/15** deterministic.
- **PROTECT (byte-identical after Part A + Part 0):** `sim_comm a91480561b6de937`,
  `sim_comm_llm f353ac30db73b770`, `sim_polariz 6c4952f66da8326e`, `sim_trust 6f31f775912f5e96`.
  (Part 0 changes only `sim_trust`'s printed epilogue — its **metric** fingerprint `6f31f775912f5e96`
  is computed before the epilogue and must stay identical; confirm that explicitly.)
- Pure **stdlib + numpy**, no new deps. Diff scope: `sim_comm.py` (no-op seam), `sim_trust.py`
  (Part 0 prose), NEW `sim_gossip.py`, `verify_all.py` (+1 entry), `CHANGELOG.md`. Do **not** commit
  this WO file. Stack on **main**.

## Acceptance
1. Part-A seam proven behaviour-preserving (`sim_comm` byte-identical `a91480561b6de937`); Part-0
   confirmed to leave `sim_trust`'s metric fingerprint `6f31f775912f5e96` unchanged.
2. Gate **15/15** deterministic; all four protected fingerprints intact.
3. `sim_gossip` prints the OFF/LOCAL/GOSSIP(+META) table + the two headline answers; `matter_drift
   < 1e-9`; replay-from-log bit-identical; metric self-check bit-identical; cross-process byte-identical.
4. Open a PR with a short summary: the deceptive gap under GOSSIP vs LOCAL, whether trust in liars
   dropped below τ, and whether META restored capture. (I verify by reproduction.)
