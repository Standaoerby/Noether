# WO_appropriation.md — sim_appropriation (module 23): the appropriable resource

## Why this module
Four NULLs in a row on **capture** have named one suspect. The accountability vertical (14–19), the prompt-stake (ВСТАВКА-27), the flat sphere eviction (20), the spoiling-not-extraction of salience (21), and the geometry-not-lever enclosure (22) all said the same thing: levers bite, but **none builds a stable hierarchy on a conserved + escapable + non-appropriable substrate**. Module 22 ruled out *mobility* as the blocker (closing escape concentrated attention geometrically and starved everyone, but capture stayed NULL, gap +0.048→−0.101). The simulation then named its own next verb: the remaining untried primitive is the **appropriability of the resource itself** — `eat ≤ avail/n` lets no one *bank, exclude, or transfer* a surplus, so advantages are always competed/regrown away.

This module builds the first **extractive** verb: an **owner** present at a cell **appropriates** a share of co-located non-owners' bodies (rent / tribute / protection racket). Unlike salience (negative-sum **spoiling**), this is a genuine **transfer to the owner** — the first mechanism that can *accumulate* an advantage. It is the last unbuilt link of ВСТАВКА 1 (страх → **собственность** → иерархия), and module 22's verdict says it is the load-bearing one.

## Concept
A **substrate change, not a new physics**: `AppropriationWorld(EnclosureWorld)` inherits the whole tower untouched (enclosure → salience → sphere → comm → conservation) and adds **one** seam — a conservative, deterministic body→body transfer applied *after* the base foraging step. Because it inherits enclosure and salience, the battery can run appropriation **alone**, **× the closed-escape arena**, and **× the salience lever** — i.e. the decisive "property + no exit" experiment, in one task.

## The seam (NO base edits — this is critical)
Do **not** touch base apportionment or any locked/prior module. The appropriation transfer is an override of `step()`:

```
def step(self):
    super().step()                 # base physics apportion eat<=avail/n EQUALLY, unchanged
    if self.appropriation <= 0.0:  # rho==0 -> no transfer -> byte-identical to parent
        return
    self._appropriate()            # conservative body->body transfer at shared cells
```

`_appropriate()` semantics (recommended form; finalize but keep all constraints):
- For each cell, gather co-located **owners** `O` and **non-owners** `N` (present this tick).
- If `O` and `N` both non-empty: each non-owner pays tribute `t = rho * body_nonowner`, **capped** so its body stays ≥ 0 (and ≥ any subsistence floor the base uses, if applicable); the collected tribute is split **evenly** among the owners at that cell.
- **Conservation cap on the receiving side:** if the base imposes any per-agent body maximum, an owner absorbs only up to that max and the **un-absorbable remainder stays with the paying non-owner** — never destroyed. (If there is no body cap, owners simply grow.)
- Body travels with the agent (it is in `self.pop`, never in grid pools) → matter is **exactly conserved**: the transfer only moves mass between two living bodies. Drift must stay < 1e-9.
- Fully deterministic: iterate cells and agents in a **sorted (by oid)** order; no iteration over unordered sets/dicts in a way that affects the result.

`rho == 0.0` (`appropriation=0.0`) ⇒ `_appropriate` never runs ⇒ `step()` ≡ `super().step()` ⇒ **OFF byte-identical to parent**, for any `owner_policy`.

### Owner identity — `owner_policy` (the cheap "more": assigned vs emergent property)
- `"founders"` (**assigned property / exclusion**): the `M` founder-identity agents — the *same identities* the salience `injectors` argument selects — are owners **everywhere**, regardless of whether injection is on. Property as a conferred class right. (Lets us ask: does giving the agenda-setters a property right finally build the hierarchy that agenda-setting alone could not?)
- `"claim"` (**emergent property / territory**): an agent that owns no cell **claims** the (unowned) cell it currently occupies — a persistent ownership tag — and thereafter owns it and appropriates from non-owners there. First **bankable stock** in the whole tower (owned-cell count). Deterministic claim tie-break (lowest oid claims an unowned contested cell). Ownership persists; on the owner's death the cell reverts to unowned.

Both policies ride the **same** transfer seam and the **same** off-switch (`rho=0`).

## Conservation crux (spell it out — this is the #1 risk of an extraction verb)
The base step apportions `eat ≤ avail/n` exactly as before (we never touch it → base fingerprints unchanged). The only new effect is a **mass-preserving transfer between two bodies in `self.pop`**: tribute leaves a non-owner and arrives at owners, capped on **both** ends (payer body ≥ 0; receiver ≤ any cap, remainder retained by payer). No food is created, none destroyed, the pool/regrowth is untouched. Therefore matter drift is ~0 by construction. **Assert `matter_drift() < 1e-9` at EVERY config in the battery** — this is the backstop and the thing I will reproduce hardest.

## OFF ≡ parent anchors (must hold byte-for-byte)
- **B0** (`rho=0` + arena off + salience off + sphere off) ≡ canon `a91480561b6de937`, **zero transfers** asserted.
- **B1** (`rho=0` + arena=6 + salience ON) ≡ a **live** `EnclosureWorld` run at the identical config (since `rho=0` ≡ parent) — byte-identical; appropriation is the only change. (No frozen hex needed; compare to a live parent run, the way module 22's B1b compared to a live SalienceWorld.)
- Assert both for `owner_policy` ∈ {"founders","claim"} (OFF is policy-independent).

## Self-check fingerprint
`appropriation_fingerprint(w)` = sha256 of `enclosure_fingerprint(w)` folded with `|rho|owner_policy|total_appropriated_kg|n_owners|n_owned_cells|`. Print it; recompute in-process (assert identical); and confirm **cross-process** (two separate `python3 sim_appropriation.py` give identical full stdout, rc 0 — the verify_all per-module criterion).

## The battery (the real "more" — one task = the full appropriation arc + interactions)
Headline config: `rho` ≈ 0.5, `owner_policy="founders"`, `M` founders = the salience `FEW`. Reuse the existing `e1_concentration / e2_capture / e3_harm` metrics; **add** the ownership metrics below.

1. **Cross-product** E1/E2/E3 over **{appropriation OFF, ON} × {open grid, box 6} × {salience inject OFF, ON}** (8 cells). This is the decisive grid:
   - appropriation-only (open): does a transfer **alone** build a *stable* elite, or get competed/fled away (as every prior transient advantage did)?
   - **appropriation × enclosure (box 6): the predicted sufficient combo — property + no escape.**
   - appropriation × salience: do agenda-setters-as-owners compound?
   - the triple.
2. **rho sweep** {0, 0.25, 0.5, 0.75, 1.0} on the open grid **and** in box 6: at what extraction rate (if any) does E2 gap go **positive and persistent** AND E1 Gini **rise** — and does enclosure shift that threshold left? (The key question is not whether a transfer momentarily helps owners — by construction it must — but whether it **compounds into a stable stratum** on a conserved substrate, and whether immobility is required.)
3. **owner_policy comparison** at headline: `"founders"` (assigned) vs `"claim"` (emergent territory). Does property need to be **assigned**, or can a landed class **self-organize**? For `"claim"`, also report territory concentration (owned-cell Gini) and whether ownership self-concentrates.
4. **New ownership metrics** (fold into the E-suite, printed in the table): owner share-of-biomass; owner−nonowner body gap (E2 already gives this); **ownership/territory Gini**; total appropriated (kg); n owners / n owned cells; owner survival vs non-owner survival.

Keep the printed verdict honest and explicit about which arm (if any) crosses into hierarchy.

## Honest fork (either outcome is a clean book result)
- **Hierarchy at last:** E1 Gini ↑, E2 gap ↑ **and persistent**, owners a stable stratum (especially × enclosure) → **appropriability WAS the missing ingredient**; ВСТАВКА 1 confirmed — property is the load-bearing link the prior five mechanisms lacked.
- **Fifth NULL / conjunction-only:** a transfer happens but does **not** compound on the open grid (owners' advantage competed away, or targets flee), and only bites **with** enclosure → property needs **enforcement/immobility** too; the minimal sufficient set is **property + closed escape** (maps onto ВСТАВКА 13–14: coalition → institution → police-state).
- Report which it is, by reproduction.

## Guardrails (hold these or the verdict can't be clean)
- Touch **ONLY** `Code/sim_appropriation.py` (new) + `Code/verify_all.py` (+2 registration lines). **No edits to any base or prior module.** If you think you need a base hook for "intake this tick", you don't — read bodies after `super().step()` and transfer a fraction of **body** (the recommended form), which needs no base change.
- `rho=0` **must** be byte-identical to the parent (assert B0 ≡ canon, B1 ≡ live enclosure, both owner policies).
- **Conservation:** assert `matter_drift() < 1e-9` at **every** config in the battery (cross-product, both sweeps, both policies). This is the main risk of an extraction mechanism.
- **Determinism:** `appropriation_fingerprint` identical in-process and cross-process; deterministic owner/claim tie-breaks (sort by oid; no result-affecting iteration over unordered containers).
- **Runtime:** the cross-product (8) + rho sweeps (2×5) + policy compare ≈ 25–30 full runs. DAYS stays canon (300). Ensure a single `python3 sim_appropriation.py` finishes **well under the 600 s verify_all per-module timeout** (each verify_all run executes main() once, twice total). If tight, trim sweep points rather than DAYS.
- Pure stdlib + numpy. No network. Import side-effect free.
- Run `verify_all.py` (expect **23/23**), open a PR, and **do NOT merge** — await the verdict by reproduction.

## Deliverables
- `Code/sim_appropriation.py` — `AppropriationWorld(EnclosureWorld)`, `_appropriate()` seam, `run_appropriation(...)`, `appropriation_fingerprint(...)`, ownership metrics, and a `main()` that prints: B0/B1 anchors, the 8-cell cross-product table, both rho sweeps, the owner_policy comparison, the new ownership metrics, the self-check, and an explicit honest verdict.
- `Code/verify_all.py` — +2 lines registering module 23.
- A PR (not merged) with `verify_all` green at 23/23.
