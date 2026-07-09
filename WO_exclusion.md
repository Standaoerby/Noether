# WO_exclusion.md — Module 26: `sim_exclusion` (denial of access → stratify without a parasitic caste?)

## Goal

Build module 26, `sim_exclusion`: the owner **denies non-owners access to its cell** — a second extractive verb beside tribute (23), the levy-funded guard (24) and inheritance (25). The institution (24) taught the key lesson: on a conserved substrate, a verb that **parks foraging mass in a non-productive caste** (the guards) collapses carrying capacity (population 91→2 / 575→53) — "the elite rules a graveyard." Exclusion is the natural counter-test: the excluded agent is **not** taxed into a parasitic pool — it simply **forages elsewhere**, so mass stays productive. **Does denial-of-access stratify the population WITHOUT the capacity collapse the levy caused?** This is the direct, clean parallel to the institution: same property baseline, add one verb, watch whether it kills the population.

`ExclusionWorld(InheritanceWorld)` — keeps the tower chain cumulative (World26(World25)); upper layers inert by default (heritable=off, sigma=0). Pure stdlib + numpy. One off-switchable seam, **no base edits**.

## Buildability (verified against the substrate — this shaped the mechanism)

Three findings from reading the code, each constraining the design:
1. **Grazing is inline in `sim_comm.step()`** (the `avail/n` per-cell split, lines ~273–284) with **no separate method**, and `sim_comm`'s canonical fingerprint `a91480561b6de937` is frozen — so a grazing-level seam would require either reimplementing `step()` (fragile) or editing the base (breaks the canon anchor). **Forbidden.** The denial therefore moves to the **movement** layer.
2. **Movement goes through an `ActionAdapter`** (`apply(self, world, a, dec, legal)`; mutates `a.i,a.j`; an illegal/again-self move is a no-logging "stay"). Module 22's `ClampingAdapter(ActionAdapter)` already swaps a custom adapter in via `self.adapter`, delegating **verbatim** to the parent when its feature is off (byte-identical). **Exclusion reuses exactly this hook** — `ExcludingAdapter(ClampingAdapter)` — composing with the clamp.
3. **Claim ownership (`_do_claims` populating `_cell_owner`) is gated on `rho>0`** (`if self.appropriation <= 0: return`). At `rho=0` no territory forms → exclusion would be inert. So the battery runs at **`rho=0.5`** (the appropriation headline): ownership exists, and exclusion is tested as a verb **added on top of the property/tribute baseline** — the exact analogue of how the institution was tested. (This means `exclusion=off, rho=0.5` reproduces module 23 — and is the B1 anchor.)

→ Clean seam, no base edits, no `step()` reimplementation, conservation trivial (movement relocates bodies; a blocked move is a "stay" — no matter moves either way).

## Non-negotiable invariants (graded on these)

1. **OFF ≡ parent, byte-for-byte.** `exclusion=False` → `ExcludingAdapter.apply` delegates straight to `super()` (ClampingAdapter, which at `arena_side=None` delegates to the base `ActionAdapter`) and the world touches nothing else → byte-identical to `InheritanceWorld` at the same config.
   - **B0** (`exclusion=off`, `rho=0`, `sigma=0`, `heritable=off`, arena off, both `owner_policy`) ≡ canon `a91480561b6de937`.
   - **B1** (`exclusion=off`, `rho=0.5`, `box6`, `claim`, salience-on, the appropriation headline) ≡ appropriation self-check `931680477b4e012b` — byte-for-byte (we add nothing when off). Proves no base/parent drift.
2. **Conservation < 1e-9 at EVERY config.** Exclusion only redirects **movement** (a denied move becomes a "stay"); movement relocates a body between cells and moves no matter into/out of any pool. The body→body tribute (`rho`) is the parent's, unchanged. `matter_drift < 1e-9` on every battery cell (assert; print the max).
3. **Determinism**, in-process and **cross-process** (two separate `python3 sim_exclusion.py` → identical full-stdout sha256). The exclusion check and the per-tick occupancy snapshot (occupied mode) must be fully deterministic.
4. **File identity**: only `Code/sim_exclusion.py` (new) and `Code/verify_all.py` (+2 lines). All 25 prior modules + infra byte-identical → `verify_all` **26/26** by composition; sixteen protected fingerprints intact by construction.
5. `main()` well under the 600s verify_all timeout.
6. **Open the PR, do NOT merge.** Await verdict-by-reproduction.

## The seam (no base edits)

`ExcludingAdapter(ClampingAdapter)`, installed as `self.adapter` in `ExclusionWorld.__init__` (replacing the clamp; it subclasses it, so the arena still works):

```python
class ExcludingAdapter(ClampingAdapter):
    def apply(self, world, a, dec, legal):
        if not world.exclusion:
            return super().apply(world, a, dec, legal)        # OFF -> byte-identical (clamp/canon)
        # 1. resolve the intended destination exactly as the clamp would (respect arena box)
        # 2. if dest == current cell -> normal (no exclusion needed)
        # 3. owner = world._cell_owner.get(dest)   # claim policy
        #    blocked if owner is not None and owner != a.oid and:
        #       absentee : always (cell owned by another -> barred, owner present or not)
        #       occupied : owner is currently on dest  (per world._occ_snapshot[dest], see below)
        #    -> on block: do NOT move (stay), increment world._excluded_moves, emit nothing
        #    -> else: perform the (clamped) move exactly as super() would
```

- **Owner identity / "same owner" check**: claim policy → `world._cell_owner.get(dest)`. A mover is barred only if the destination is owned by a **different** agent (`owner is not None and owner != a.oid`). (Owners may always enter their own cells; unowned cells are free.)
- **`occupied` mode needs an occupancy snapshot.** The adapter caches, per tick, `world._occ_snapshot = {cell: set(oids currently there)}`, rebuilt lazily on the **first** `apply` call of a new `world.t` (detect via a cached `_t_seen`). At first-apply, no moves have happened this tick (move phase runs after graze/death/repro in `step()`), so the snapshot reflects positions at move-phase start → deterministic, order-independent. `owner_present(dest) = world._cell_owner.get(dest) in world._occ_snapshot.get(dest, ())`. `absentee` mode does **not** use the snapshot (pure `_cell_owner`).
- Conservation: a block = "stay" (no `a.i,a.j` change, no move event) — identical matter footprint to a legal stay. Nothing leaks.

`ExclusionWorld` adds only: `self.exclusion`, `self.exclude_mode`, `self._excluded_moves=0`, the snapshot cache, and installs the adapter. **No `step()` override** (the adapter is called from the base move phase). When `exclusion=False`, none of this changes behavior.

## Switches & defaults (veto now if any is wrong)

- `exclusion ∈ {False, True}` — master. `False` ≡ parent.
- `exclude_mode ∈ {"absentee", "occupied"}` — the escape/capture analog, within ON. **Run BOTH** (per Stan's "оба"). `occupied` ≈ capture (owner monopolizes the cell when present → eats more); `absentee` ≈ escape (cell barred even when owner away → resource regrows unused, non-owner merely displaced).
- Inherited defaults for the battery: `rho=0.5` (property/tribute baseline = module 23, so ownership exists and exclusion is an *added* verb), `owner_policy="claim"` (territorial; under `founders` owners own everywhere → exclusion would bar non-owners from the whole grid = degenerate total lockout — note it, optionally one corner cell, don't headline it), `sigma=0`, `heritable=off`, salience off in the battery (B1 keeps it on to reproduce mod-23).
- `DAYS=300`, `SEED=7`, grid/oasis inherited.

## Battery

- **OFF cell**: `exclusion=off`, both policies → reproduce parent (anchors B0 at rho=0, B1 at rho=0.5/box).
- **Main cross-product** (`claim`, `rho=0.5`): `{exclusion off} ∪ ({absentee, occupied} × {open, box6})`. Report E1/E2 + the capture/escape diagnostics + conservation for each.
- (Optional, if it fits <600s) a `founders` degenerate corner for one arena to show total-lockout behavior.

## Experiments + pre-registered hypotheses

- **E2 — stratification WITHOUT collapse (THE test; the institution's lesson).** Compare **alive count** exclusion off vs on, and the owner−non-owner **body gap**. *Hypothesis*: exclusion raises the body gap (owners hold exclusive forage) **while population stays healthy** — sharp contrast to the institution's levy (91→2 / 575→53), because no foraging mass is parked in a parasitic caste; the excluded simply eat elsewhere. If true: a verb *can* stratify without killing capacity.
- **E1 — concentration.** Owner biomass share, owner body gap, territory-Gini, exclusion on vs off (and vs the tribute-only mod-23 baseline). Does territorial denial concentrate *beyond* what tribute alone did?
- **capture vs escape (occupied vs absentee).** *occupied*: owner body gap **up**, owned cells **grazed down** (owner eats the freed share). *absentee*: owned cells **under-grazed** (mean plant on owned cells **higher** — locked & unused), owner gap **smaller**, non-owners **crowd** the remaining unowned cells. Measure: owner body gap; mean `plant` on owned vs unowned cells (utilization); non-owner crowding; total biomass.
- **Efficiency / waste.** Total biomass and total foraged, on vs off. *Hypothesis*: `absentee` **wastes** capacity (dog-in-the-manger: resource locked unused → lower total biomass) even though it parks no parasitic caste; `occupied` redistributes with little waste.

## Honest forks (pre-register all; report whichever the data shows)

1. **Stratifies without collapse** — exclusion (esp. `occupied`) raises the owner gap while population holds → the clean contrast to the institution: a verb that doesn't park mass in a parasitic caste *can* concentrate without killing the base. (Maps ВСТАВКА 13–14: exclusion sharpens the stratum cheaply.)
2. **Absentee wastes capacity** — locked-unused resource lowers total biomass / dips population, "dog in the manger" — territoriality is inefficient even without a guard caste (a *different* failure mode than the levy's).
3. **NULL on the open grid** — non-owners just forage the ample unowned cells; owners don't accumulate; exclusion is toothless where escape is easy (echo of the early escape-NULLs, 20–22).
4. **Box6 amplifies** — the cramped arena leaves nowhere to flee → exclusion bites (gap up, maybe crowding/starvation), while open is toothless: exclusion's power is contingent on enclosure.

Flag any non-monotonicity honestly. Single seed (SEED=7) — report it as one draw; a multi-seed check can follow if the result is positive.

## Self-check / fingerprints (print in `main()`)

- Re-print **B0** and **B1**; assert they equal `a91480561b6de937` and `931680477b4e012b` (OFF ≡ parent, no drift).
- Print `EXCLUSION_FINGERPRINT` = sha256 of a canonical state digest at a fixed headline config: `exclusion=on, exclude_mode="absentee", box6, rho=0.5, claim, salience off`. Recompute in-process (assert identical); cross-process check covers determinism. Fold `_excluded_moves` into the digest.
- Assert `matter_drift < 1e-9` at every config; print the max.

## Guardrails (repeat)

- Touch only `Code/sim_exclusion.py` (new) and `Code/verify_all.py` (+2 lines).
- `exclusion=False` ≡ parent byte-for-byte (adapter delegates to `super()`, world adds nothing; no `step()` override).
- Conservation `< 1e-9` at every config — exclusion only redirects movement (block = stay), zero mass ops.
- Determinism in-process and cross-process; deterministic occupancy snapshot.
- `main()` under the 600s verify_all timeout.
- **Open the PR; do NOT merge.** Await verdict-by-reproduction.

## Deliverables / acceptance

- `Code/sim_exclusion.py` with `ExcludingAdapter(ClampingAdapter)` + `ExclusionWorld(InheritanceWorld)` (installs the adapter; adds the two switches, the `_excluded_moves` counter, the per-tick occupancy snapshot for `occupied`), and a `main()` running the battery, printing E1/E2, the capture/escape diagnostics (owner gap; owned-vs-unowned plant utilization; crowding; total biomass), the anchors, `EXCLUSION_FINGERPRINT`, and max `matter_drift`.
- `Code/verify_all.py` +2 lines registering `sim_exclusion`; `verify_all` green **26/26** (rc 0 twice + byte-identical stdout across the two runs).
- A short PR description: the chosen fork + headline numbers (does it stratify without collapse?), B0/B1 anchors, `EXCLUSION_FINGERPRINT`, max drift, the **absentee-vs-occupied** contrast, and the **open-vs-box6** contrast. Do **not** merge.
