# WO_institution.md — Module 24: `sim_institution` (the protector institution)

## Goal

Build module 24, `sim_institution`, adding the **institution that defends property** — the verb ВСТАВКА 13–14 names after appropriation (coalition → institution → police-state). It sits on top of module 23 (`sim_appropriation`): owners are taxed to fund a **guard caste** that **quashes challenges** to ownership, freezing the stratum. This tests whether enforced property *sharpens* the owner stratum (higher concentration, lower turnover, suppressed challenge) beyond bare appropriation — or whether the institution merely parasitizes (NULL) or the guards eat the owners (capture-of-guards).

`InstitutionWorld(AppropriationWorld)` — inherits the entire tower. Pure stdlib + numpy. **No base edits.** One off-switchable seam, exactly in the spirit of module 23's `_appropriate()`.

## Non-negotiable invariants (this is graded on these)

1. **OFF ≡ parent, byte-for-byte.** Master switch `sigma=0` → the seam returns immediately, touching no bodies and no ledger → `InstitutionWorld` is byte-identical to `AppropriationWorld` at the same config.
   - **B0** (`sigma=0`, all-off, both policies) ≡ canon `a91480561b6de937`.
   - **B1** (`sigma=0` at the appropriation headline config: `rho=0.5`, `box6`, `founders`, salience-on) ≡ appropriation self-check `931680477b4e012b` — byte-for-byte. This proves no base drift.
2. **Conservation < 1e-9 at EVERY config.** The ONLY mass-moving operation is the wealth levy, and it is **body→body** with an exact float remainder (same trick as module 23's tribute). Challenges and defense are **ledger-only** (no mass). `matter_drift` must be `< 1e-9` on every cell of the battery and every sweep point. **This is the #1 check** — a leak here would make any "sharpening" an artifact.
3. **Determinism**, in-process (recompute identical) and **cross-process** (two separate `python3 sim_institution.py` → identical full-stdout sha256).
4. **File identity**: the only changes vs the current module-23 basis are `Code/sim_institution.py` (new) and `Code/verify_all.py` (+2 lines: the module's list entry + its registration tuple). All 23 prior modules + infra stay byte-identical → `verify_all` **24/24** by composition; thirteen+ protected fingerprints intact by construction.
5. `main()` must finish well under the `verify_all` per-module timeout (600s). Prune sweep resolution before exceeding it; never raise the timeout.
6. **Open the PR, do NOT merge.** Await verdict-by-reproduction.

## The seam (no base edits)

Override `step()`. Master off-switch is `self.sigma` (the levy rate = institution strength); the within-on A/B knob is `self.enforce`.

```python
def step(self):
    super().step()                      # base + appropriation run UNCHANGED
    if self.sigma <= 0.0:               # INSTITUTION OFF -> byte-identical AppropriationWorld
        return                          # (enforce flag is irrelevant when sigma==0)
    self._collect_levy()                # body->body, exact remainder
    self._do_challenges()               # ledger only; defense applied inside per self.enforce
```

### `_collect_levy()` — financing (body→body, exact conservation)

- **Owners** (the taxed) = the agents who currently own property under the active `owner_policy`:
  - `founders`: the `M` lowest-oid founder-speakers (own everywhere) — `M` agents.
  - `claim`: every agent currently owning ≥1 cell.
- **Enforcers** = a **fixed identity caste**, disjoint from owners: `sorted(speaker_ids)[M : M + M_e]` (the next-lowest oids after the founder block), for **both** policies. Under `claim`, enforcers neither claim nor challenge (caste stays disjoint).
- Levy is a pure **wealth tax on the body**, one levy per owning agent (NOT per cell): each alive owner pays `t = sigma * body` (`sigma ≤ 1` keeps body ≥ 0). Wealth = body, not cell-count.
- Pool `T = Σ t` over alive owners. Distribute equally among alive enforcers: `share = T / n_e` to each, **last enforcer takes the float remainder** `T - (n_e-1)*share`. Bodies live in `self.pop` → matter moves only between live bodies, exact.
- Edge cases (must conserve trivially): no alive enforcers → collect nothing (`T=0`, skip). No alive owners → `T=0`. An owner that is also (somehow) the last enforcer cannot occur (castes disjoint by construction).

### `_do_challenges()` — challenge + local defense (ledger only, no mass)

Operates on the **per-cell ownership ledger that exists under `claim`**. Under `founders` (own-everywhere, no per-cell ledger) this is a **no-op on ownership** — the levy layer still runs, so `founders + institution` = "second extracting caste, no turnover mechanism" (turnover is trivially zero; founders is already maximally ossified).

Under `claim`, deterministically:
```
for cell in sorted(owned cells that have >=1 co-located NON-owner, NON-enforcer agent):
    challenger = lowest-oid co-located non-owner, non-enforcer agent on that cell
    if self.enforce and (any alive enforcer is co-located on that cell):
        quashed += 1                      # DEFENSE: ownership unchanged
    else:
        _cell_owner[cell] = challenger.oid # challenge SUCCEEDS: ownership flips
        succeeded += 1                     # E3 counter
```
Iterate cells in sorted order, challenger = min oid → fully deterministic. Defense is **spatial**: an enforcer must physically be on the contested cell to quash (enforcers forage toward the oasis like everyone, so presence on rich/owned cells is emergent — E3 measures whether local presence is *sufficient*; partial failure is an allowed, honest result).

## Defaults (veto now if any is wrong)

- `sigma = 0.5` headline; sweep `{0.0, 0.25, 0.5, 0.75, 1.0}`.
- `M = 3` owners (founders; fair biomass share = 0.025 as in module 23). `M_e = 3` enforcers (disjoint caste). Enforcer-corps sweep `M_e ∈ {1, 3, 6}` at headline.
- `rho = 0.5` stays **ON** under the institution (tribute is active — otherwise there is nothing to defend; the institution sits atop live appropriation).
- `owner_policy`: run **both** `founders` and `claim`. The rich arm is `claim` (challenges/turnover live there).
- `enforce ∈ {off, on}` is the within-on A/B at `sigma>0`.
- **No salience axis** in the battery (salience is perceptual, does not touch body mass — including it would be 2× wasted cells). Salience is ON only inside the B1 anchor run (to reproduce module-23 headline exactly).
- `DAYS=300`, `SEED=7`, grid/oasis/etc. inherited unchanged.

## Battery (cover more under one seam)

- **OFF cell**: `sigma=0` → must reproduce `AppropriationWorld` (anchors B0, B1).
- **Cross-product** at `sigma=0.5`: `{enforce off, on} × {open, box6} × {founders, claim}` (8 cells). Report E1 + conservation for each.
- **sigma sweep** `{0,0.25,0.5,0.75,1.0}` at `(enforce=on, claim)` for both `open` and `box6` — E1/E2/E3 vs strength.
- **enforcer-corps sweep** `M_e ∈ {1,3,6}` at headline (`sigma=0.5, enforce=on, box6, claim`).

## Experiments + pre-registered hypotheses

- **E1 — sharper concentration.** Biomass share of `owners ∪ enforcers` vs the module-23 owner-only baseline (0.045 open / 0.102 box / 0.216 at rho=1.0 box). Also report owner-share and enforcer-share **separately**. *Hypothesis*: the institution lifts total concentration and adds a second extracting layer.
- **E2 — ossification (NEW; module 23 did not measure this).** Owner-class turnover over time (claim arm): record top-5 owners by owned-cell-count at mid-run (day 150) and measure the fraction still in top-5 at end (day 300). *Hypothesis*: `enforce=on` **freezes** the same owners (high retention / low turnover) vs churn at `enforce=off`. This is the "institution makes the elite hereditary in fact" signature. (Under `founders`, turnover is trivially 0 — report as such.)
- **E3 — challenge suppression.** Count successful ownership flips per run, `enforce=off` vs `on` at matched config. *Hypothesis*: `enforce=on` drives successful challenges toward 0 (bounded by enforcer presence).

## Honest forks (pre-register all three; report whichever the data shows)

1. **Sharpening confirmed** — higher concentration **and** lower turnover **and** suppressed challenge ⇒ ВСТАВКА 13–14 lands; "institution sharpens the stratum / police-state" reads cleanly.
2. **NULL / over-extraction** — institution taxes but does NOT freeze (turnover unchanged), or a greedy `sigma` starves everyone like the hungry box (module 22) ⇒ institution is parasitic, not stratifying. Publishable.
3. **Capture-of-guards** — enforcers out-eat owners and become the elite themselves (the separate enforcer-share-vs-owner-share metric catches this). "Who guards the guards" — a book thread in its own right.

State which fork the run supports, with the numbers, and flag any non-monotonicity honestly (as in module 23's open-grid wobble).

## Self-check / fingerprints (print in `main()`)

- Re-print the **B0** and **B1** anchors and assert they equal `a91480561b6de937` and `931680477b4e012b` respectively (proves OFF ≡ parent, no base drift).
- Print `INSTITUTION_FINGERPRINT` = sha256 of a canonical state digest at a fixed headline config — use `claim, sigma=0.5, enforce=on, box6, rho=0.5, salience OFF` (the arm that exercises levy + challenge + defense). Recompute in-process to confirm identical; the cross-process check covers determinism.
- Assert `matter_drift < 1e-9` at every battery/sweep config; print the max drift seen.

## Guardrails (repeat)

- Touch only `Code/sim_institution.py` (new) and `Code/verify_all.py` (+2 lines). Nothing else.
- `sigma=0` ≡ parent byte-for-byte (single clean off-switch; `enforce` is a sub-knob only at `sigma>0`).
- Conservation `< 1e-9` at every config — the levy is body→body with exact remainder; challenge/defense are ledger-only.
- Determinism in-process and cross-process.
- `main()` under the 600s verify_all timeout (prune sweeps if needed; never raise the timeout).
- **Open the PR; do NOT merge.** Await verdict-by-reproduction.

## Deliverables / acceptance

- `Code/sim_institution.py` with `InstitutionWorld(AppropriationWorld)`, the `step()` seam, `_collect_levy()`, `_do_challenges()`, and a `main()` that runs the battery + sweeps, prints E1/E2/E3, the anchors, `INSTITUTION_FINGERPRINT`, and max `matter_drift`.
- `Code/verify_all.py` +2 lines registering `sim_institution`; `verify_all` green **24/24** (rc 0 twice + byte-identical stdout across the two runs).
- A short PR description with: the chosen fork + headline numbers, B0/B1 anchors, `INSTITUTION_FINGERPRINT`, max drift, and the founders-vs-claim contrast. Do **not** merge.
