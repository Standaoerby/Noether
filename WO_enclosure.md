# WO — sim_enclosure (module 22): the bounded arena (close the escape)

## One-line goal
Add a **bounded foraging arena** on top of `SalienceWorld` and **re-run the salience-injection battery inside it**, to test the standing diagnosis from modules 19 and 21: that agenda-injection (and collective sanction) failed to build hierarchy only because the **target could escape**. Close spatial escape and see whether injection's *harm-without-hierarchy* (E1✗/E2✗/E3✓) flips to *capture/concentration* (E1/E2 → ✓).

This is a **substrate change, not a new verb**. No LLM, no network. Pure stdlib + numpy.

---

## Why this module (context for whoever picks this up)
The tower has now shown the same shape three times:
- **Module 19 `sim_coalition`** — a quorum that silences a caught liar for everyone nearby works mechanically (3849 claims muted) but does **not** cut the liar, censor the innocent, or build a stratum (E1/E2/E3 ✗). Reason: **the quorum cannot stay assembled around a *moving* target.**
- **Module 21 `sim_salience`** — the first **exogenous** lever (injectors push salience onto a decoy cell in each listener's attention budget, evicting real rich memories). It is the first lever that **bites** (E3 ✓: victim biomass 447→400, population 1455→1272) — but only as **harm via distraction**, not hierarchy: concentration needs *mass* not a few (E1 ✗), and capture is sign-flipping noise (E2 ✗, spoiling not extraction). Reason named in the finding: on a **conservable + escapable** substrate, control of attention degrades the collective but does not accumulate — *"the missing ingredient is the same as coalition: a substrate where the target/resource can't escape."*

So the repeated, explicit prediction is: **power bites once escape is closed.** This module closes spatial escape (a **bounded, appropriable arena** — the enclosure of the commons; ВСТАВКА 1: appropriable bounded space → hierarchy) and re-tests the lever that already bit (salience). It is a genuine fork (see "Honest verdict").

---

## The module
`EnclosureWorld(SalienceWorld)`, registered as **module 22** in `verify_all.py`. It inherits the entire stack untouched (salience → sphere → comm → conservation). The only new behaviour is a **movement clamp**.

### The knob — a corner-anchored arena box
A config parameter:
```
arena_side : int | None      # None  => full grid (no-op)
                             # s     => agents are confined to the corner box rows [0, s-1] x cols [0, s-1]
```
- On **every agent move**, after the existing movement logic computes the intended destination cell `(r, c)`, clamp it:
  `r = min(max(r, 0), s-1)`, `c = min(max(c, 0), s-1)` (only when `arena_side = s` is set).
- **`arena_side = None` (or `s = GRID_R`) ⇒ the clamp is a true no-op ⇒ OFF, byte-identical to the parent.** This is the hard requirement that protects the canon (see anchors).
- The box is **anchored at the (0,0) corner on purpose**, so the existing salience **decoy cell `(0,0)` stays inside the arena** for every `arena_side`. That way the *only* difference between the enclosure-ON run and the module-21 baseline is the confinement itself — the injection target is unchanged.
- **Initialization is NOT changed.** Agents are still placed grid-wide by the canon init (same seed → same initial positions as canon). With the arena ON, agents that start outside the box are pulled into it over the first cycles by the clamp (deterministic transient); the steady state is confinement. *(Do not add an "init-inside-arena" mode unless it is gated so that OFF is still byte-identical to canon — the conservation/determinism anchors are non-negotiable; a transient is fine.)*

### Optional secondary variant (only if cheap, and clearly separated)
A `pin_victims_only` flag that clamps **only the non-injector ("victim") sub-population** while injectors roam freely — the surgical "pinned target" reading (isolates "target can't flee" without changing everyone's density). Primary experiment is the **global arena**; the pinned-only variant is a nice-to-have, not required for ACCEPT.

---

## Conservation / determinism crux (read this twice)
The enclosure must touch **only the choice of destination cell**. It must **never**:
- delete, create, or teleport matter;
- alter the eat rule `eat ≤ avail / n`;
- alter the death → soil return.

Food and heat **keep regenerating conservatively everywhere on the full grid**, reachable or not — the unreached corner simply goes unforaged, and its matter stays conserved in place. Therefore **matter drift must remain `< 1e-9` at every `arena_side`** (assert it in the demo, at full grid and at each tight size). Determinism is preserved because the clamp is a deterministic min/max on integer coordinates.

---

## OFF ≡ canon — two anchors (mandatory, verified by reproduction)
- **B0** — `arena_side = None` **and** salience off (W=0 / no injectors) **and** sphere off (radius ≥ diag, K=∞, lag=0): must be **byte-identical to canon `a91480561b6de937`** (zero clamps, zero injections, sphere degenerate).
- **B1** — `arena_side = None` **and** salience ON (the module-21 headline config, sphere on): must be **byte-identical to `sim_salience`'s ON state-fingerprint `e4c51990853eea93`** — positive control proving the arena is the *only* change.

Self-check **`enclosure_fingerprint`**: fold the existing `salience_fingerprint` with the arena bounds and the (deterministic) clamped-move trace / arena-membership counts. Print it. It must be **identical in-process across two runs and identical cross-process** (`python3 sim_enclosure.py` twice → identical full-stdout sha, rc 0 — i.e. it passes the `verify_all` per-module criterion).

---

## Experiment (what the demo `main()` should print)
Re-run the **same E1/E2/E3** as module 21, but **inside the enclosure**, against the full-grid baseline (the module-21 numbers).

- **E1 — concentration.** Top-k share of attention/eviction mass and a Gini over salience. Does confinement push it up (✓) where the full grid was flat (top-5 0.178→0.168)?
- **E2 — capture.** Injector-body minus victim-body gap. Does confinement turn the sign-flipping noise (+0.143/−0.084/−0.114/+0.048) into a stable positive transfer (✓)? This is the key one — a confined victim can't flee the cells it was made to forget, so the injector that stays put may finally eat them.
- **E3 — harm.** Victim biomass / living count (full-grid baseline 447→400, 1455→1272). Expected to persist or deepen.

### Sweeps (the heart of this module)
- **Enclosure-size sweep** — `arena_side ∈ {14 (≡ full / no-op), 10, 6, 4}`, salience ON (decoy, a few injectors, permanent). Report E1/E2/E3 at each size. **At what density (if any) does capture/hierarchy appear?** This is the analogue of the K / radius / decay sweeps from earlier modules.
- **Injector-count sweep inside a tight box** — injectors ∈ {1, 3, 10} at the tightest useful `arena_side`. Does confinement change the module-21 "mass not few" law (residency 0.037/0.062/0.191)?

Print a compact verdict line per E (✓/✗) at the headline tight size, exactly like modules 18/19/21.

---

## Honest verdict — a real fork
Report whichever the numbers show, with the same candor as the prior NULLs:
- **Levers bite** (E1/E2 flip to ✓ as the box tightens) ⇒ **escape was the missing ingredient** — narrative control becomes power exactly when the target cannot flee. Direct support for ВСТАВКА 1 (appropriable bounded space → hierarchy) and the closing of the coalition/salience arc.
- **Fourth NULL** (even a 4×4 box doesn't produce capture/concentration) ⇒ the blocker is **deeper than mobility** — it is the **conserved resource itself** (you cannot bank a gain on `eat ≤ avail/n`), and the next lever must make the resource *appropriable* (exclusion / hoardable territory), not merely pin the target. Either way the simulation leads the book.

---

## Verification bar (what I will reproduce in my sandbox before you merge)
1. **B0** byte-identical to canon `a91480561b6de937`.
2. **B1** byte-identical to `sim_salience` ON `e4c51990853eea93`.
3. **Conservation** `< 1e-9` at every `arena_side` (full, 10, 6, 4).
4. **`enclosure_fingerprint`** identical in-process and cross-process (two separate processes), rc 0 ⇒ `verify_all` per-module criterion met.
5. **File-identity** — diff against the current passing 21-module basis shows **only** `sim_enclosure.py` (new) and `verify_all.py` (+2 registration lines). All 21 prior modules + infra byte-identical ⇒ `verify_all` **22/22 by composition**, and the **eleven protected fingerprints** intact by construction.
6. **E1/E2/E3 numbers and the two sweeps** reproduced to the digit.

---

## Deliverables
- `Code/sim_enclosure.py` — `EnclosureWorld(SalienceWorld)`, module 22; `main()` prints B0/B1 anchors, the E1/E2/E3 battery, the enclosure-size sweep, the injector-count sweep, conservation asserts at each size, a success marker, and `enclosure_fingerprint`.
- `Code/verify_all.py` — register the new module (+2 lines). **Touch nothing else.**
- Open a **PR**. **Do NOT merge** — await my verdict by reproduction.

Headless command for Stan:
```
claude -p "Выполни WO_enclosure.md" --output-format json
```
