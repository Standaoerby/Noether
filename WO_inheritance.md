# WO_inheritance.md — Module 25: `sim_inheritance` (heritable property → dynasties)

## Goal

Build module 25, `sim_inheritance`: ownership **survives the owner's death and passes to an heir of the same bloodline**, instead of reverting to the commons. This is the verb the institution (module 24) conspicuously **failed** to produce: its E2 ossification was unmeasurable (the owner class went extinct, turnover `nan`). Inheritance is the direct test of **temporal persistence of the stratum** — do dynasties form and hold across generations, the thing that makes an elite *hereditary in fact*?

`InheritanceWorld(InstitutionWorld)` — inherits the whole tower. Pure stdlib + numpy. **No base edits.** One off-switchable seam.

Why parent = `InstitutionWorld` but default `sigma=0`: this keeps the tower chain strictly cumulative (`World25(World24)`) while running the **clean** inheritance test with the institution **inert** (`sigma=0` ≡ AppropriationWorld byte-for-byte) — i.e. inheritance is tested WITHOUT the capacity-killing levy that collapsed module 24. A secondary arm (`sigma=0.5`) then studies inheritance *under* the institution.

## Buildability (confirmed against the substrate — no base edits needed)

The base records everything inheritance needs, readable from `self.gen` and the event log:
- Reproduction emits `self.log.emit(self.t, "birth", "individual", where=..., actor=child_oid, parent=parent_oid, data={"gene":...})` (see `sim_comm.py`). So every birth carries (child, parent).
- `self.gen[oid]` = generation depth (0 for founders seeded at init, `gen[child]=gen[parent]+1`).
- `EventLog.query(t0, t1, kind=..., kinds=...)` returns events; `log.events` is the list. Birth events are `kind="birth"`, `actor=child`, `parent=parent`.
- Live set = `{a.oid for a in self.pop}`. Per-cell ownership = `self._cell_owner` (dict cell→owner_oid); `territory_counts()` helper exists.

→ At the `InheritanceWorld` layer, reconstruct a **house id** `_house[oid]` = root founding ancestor, purely by observing birth events. **No reproduction/base code is touched.**

## Non-negotiable invariants (graded on these)

1. **OFF ≡ parent, byte-for-byte.** Master switch `heritable=False` → the seam does nothing extra (no log read, no `_house`, `_do_claims` delegates straight to `super()`) → `InheritanceWorld` is byte-identical to `InstitutionWorld` at the same config.
   - **B0** (`heritable=False`, `sigma=0`, all-off, both `owner_policy` founders/claim) ≡ canon `a91480561b6de937`.
   - **B1** (`heritable=False`, `sigma=0` at the appropriation headline: `rho=0.5`, `box6`, `founders`, salience-on) ≡ appropriation self-check `931680477b4e012b` — byte-for-byte. Proves no base drift.
2. **Conservation < 1e-9 at EVERY config.** Inheritance is a **pure ledger operation** (reassign entries in `_cell_owner`); it adds **zero** mass-moving operations. The only mass that moves is the inherited appropriation tribute (`rho`), unchanged; default `sigma=0` so no levy. `matter_drift < 1e-9` must hold on every battery cell and sweep point (this is the easiest module yet for conservation — assert it anyway and print the max).
3. **Determinism**, in-process (recompute identical) and **cross-process** (two separate `python3 sim_inheritance.py` → identical full-stdout sha256). The `_house` reconstruction and heir selection must be fully deterministic.
4. **File identity**: only `Code/sim_inheritance.py` (new) and `Code/verify_all.py` (+2 lines). All 24 prior modules + infra byte-identical → `verify_all` **25/25** by composition; fifteen+ protected fingerprints intact by construction.
5. `main()` well under the 600s verify_all timeout. Prune sweeps before exceeding it; never raise the timeout.
6. **Open the PR, do NOT merge.** Await verdict-by-reproduction.

## The seam (no base edits)

### Lineage map `_house[oid]` (observation only, gated on `heritable`)

Maintain a cursor over birth events; at the **start** of `step()` (only when `self.heritable`), fold in births up to `t-1`:
```
for e in new birth events with e.t <= self.t - 1 (since cursor):
    self._house[e.actor] = self._house.get(e.parent, e.parent)   # child joins parent's house
self._cursor = len(self.log.events)   # or advance past consumed events
```
Founders (gen 0, seeded at init, no birth event) → `_house.get(founder, founder) == founder` (self). Anyone relevant to an inheritance THIS step (a dead owner, or a living heir) was born in a prior step, so its house is already recorded → deterministic, no circularity. **When `heritable=False`, do none of this** (keeps OFF byte-identical and RNG-untouched).

### Override `_do_claims` (the reversion-on-death is here)

`InstitutionWorld._do_claims` (and `AppropriationWorld`'s under it) prune owned cells whose owner is dead, then let living agents claim unowned cells under foot. Inheritance intercepts the prune:

```python
def _do_claims(self):
    if not self.heritable:
        return super()._do_claims()          # OFF -> byte-identical parent (any sigma)
    self._inherit_dead()                     # reassign dead owners' cells to a living heir
    super()._do_claims()                     # then normal claim logic runs (reassigned cells now have a LIVING owner -> survive the parent prune; reverted cells already gone)
```

`_inherit_dead()` — for each owned cell whose owner satisfies the **same death predicate the parent prune uses** (owner not alive):
- **bloodline heir** = the lowest-oid **living** agent in the same house (`_house[a.oid] == _house[dead_owner]`). If found → `_cell_owner[cell] = heir_oid`.
- **no living kin** → apply `heir_fallback`:
  - `"revert"` → `del _cell_owner[cell]` (lineage extinct → estate returns to commons).
  - `"escheat"` → reassign to the **nearest living owner of any house** (min Manhattan distance to a cell currently owned by a living owner; tie-break lowest-oid owner; if no living owner anywhere → revert). Land consolidates into surviving houses.

Use the parent's exact aliveness predicate so the two paths compose cleanly (reassigned-to-living cells survive `super()`'s prune; reverted cells are consistently removed). Reimplementing the claim pass inline instead of `inherit-then-super` is acceptable **iff** `heritable=False` still returns `super()` (byte-identical) and conservation holds.

## Switches & defaults (veto now if any is wrong)

- `heritable ∈ {False, True}` — master for this module's seam. `False` ≡ parent.
- `heir_fallback ∈ {"revert", "escheat"}` — mode within ON. **Run BOTH** (per Stan).
- Inherited, with new defaults for the clean test: `sigma=0` (institution inert), `rho=0.5` (tribute ON → estates are wealth-producing), `owner_policy="claim"` (bloodline only meaningful on per-cell territory), salience off in the battery (perceptual; B1 anchor keeps it on to reproduce mod-23).
- `DAYS=300`, `SEED=7`, grid/oasis inherited unchanged.

## Battery (cover more under one seam)

- **OFF cell**: `heritable=False`, `sigma=0`, both policies → reproduce parent (anchors B0, B1).
- **Main cross-product** (`owner_policy=claim`, `sigma=0`, `rho=0.5`): `{heritable off, on} × {heir_fallback revert, escheat} × {open, box6}`. (`heritable=off` makes fallback irrelevant → run once per arena.) Report E1/E2/E3 + conservation for each.
- **Secondary arm — inheritance UNDER the institution**: `heritable=on`, `sigma=0.5`, `enforce=on`, both fallbacks, `{open, box6}`. Does heritability **rescue** the dynasty the institution killed, or does the levy still collapse the population (mod-24)? Report alive-count + E2 + conservation.

## Experiments + pre-registered hypotheses

- **E2 — dynasty persistence (THE headline; what the institution failed to produce).** On the claim arm: (a) number of **distinct houses** ever holding top-K territory over the run (fewer ⇒ more dynastic); (b) fraction of **end-state top-K territory** whose owner's house traces to an **original founding house** (a gen-0 root that owned early); (c) mean/max **generation depth** (`self.gen`) of end-state top owners. *Hypothesis (on)*: a few founding houses dominate the end-state, high persistence, high gen-depth. *(off)*: top owners are recent claimants, many distinct houses, churn.
- **E1 — lineage concentration.** Territory-Gini and **top-house land share** (group owned cells by the owner's house), `heritable` on vs off. *Hypothesis (on)*: land concentrates into fewer houses than the mod-23 claim churn baseline.
- **E3 — inherited body advantage.** With `rho` on, the owner−non-owner **body gap** (mod-23's +9 kg metric) trajectory: does `heritable=on` let the advantage **compound/persist** across deaths vs **reset** at off? Also: persistence of a house's cumulative tribute income.
- **Inequality trajectory.** Biomass-Gini and territory-Gini sampled over time (e.g. days 50/150/300), `heritable` on vs off — does inheritance prevent the death-reset re-leveling (ratchet up)?

## Honest forks (pre-register all; report whichever the data shows)

1. **Dynasties form & persist** (E2 ✓) — heritability ossifies the stratum the institution couldn't: few founding houses dominate, high gen-depth at the top. The hereditary-elite link of ВСТАВКА 13–14, finally on a live population.
2. **NULL** — inheritance changes little: owners die faster than they breed heirs, or living kin aren't available, so estates churn anyway (especially under `revert`). Heritability needs reproduction to bite.
3. **Fallback-divergent** — `escheat` consolidates land monotonically (a ratchet into surviving houses regardless of breeding) while `revert` re-levels on line-extinction; the two fallbacks diverge sharply (report both Ginis).
4. **Inherited graveyard** (secondary arm) — under `sigma=0.5` the mod-24 collapse dominates: heritability inherits a near-extinct population and cannot rescue the dynasty. (Connect explicitly to mod-24.)

Flag any non-monotonicity honestly (as in mod-23's open-grid wobble).

## Self-check / fingerprints (print in `main()`)

- Re-print **B0** and **B1**; assert they equal `a91480561b6de937` and `931680477b4e012b` (OFF ≡ parent, no base drift).
- Print `INHERITANCE_FINGERPRINT` = sha256 of a canonical state digest at a fixed headline config: `heritable=on, heir_fallback="revert", box6, sigma=0, rho=0.5, claim, salience off`. Recompute in-process (assert identical); cross-process check covers determinism.
- Assert `matter_drift < 1e-9` at every battery/arm config; print the max.

## Guardrails (repeat)

- Touch only `Code/sim_inheritance.py` (new) and `Code/verify_all.py` (+2 lines).
- `heritable=False` ≡ parent byte-for-byte (all inheritance bookkeeping gated on it; no log read / no `_house` / `_do_claims` delegates to `super()` when off).
- Conservation `< 1e-9` at every config — inheritance is pure ledger (no mass ops added).
- Determinism in-process and cross-process.
- `main()` under the 600s verify_all timeout (prune if needed; never raise it).
- **Open the PR; do NOT merge.** Await verdict-by-reproduction.

## Deliverables / acceptance

- `Code/sim_inheritance.py` with `InheritanceWorld(InstitutionWorld)`, the `_house` reconstruction (observation-only, gated on `heritable`), the `_do_claims` seam with `_inherit_dead()` (bloodline heir + revert/escheat fallback), and a `main()` that runs the battery + the `sigma=0.5` secondary arm, printing E1/E2/E3, the inequality trajectory, the anchors, `INHERITANCE_FINGERPRINT`, and max `matter_drift`.
- `Code/verify_all.py` +2 lines registering `sim_inheritance`; `verify_all` green **25/25** (rc 0 twice + byte-identical stdout across the two runs).
- A short PR description: the chosen fork + headline numbers, B0/B1 anchors, `INHERITANCE_FINGERPRINT`, max drift, the **revert-vs-escheat** contrast, and the **`sigma=0.5` secondary-arm** result (does heritability rescue the dynasty or inherit a graveyard). Do **not** merge.
