# WO — sim_salience (module 21): exogenous significance injection

## Goal
Add the first **exogenous salience-injection** verb to the embodied substrate: an agent can push significance into *other* agents' attention budgets, independent of a cell's intrinsic features. This is the lever the three prior NULLs (accountability vertical 14–19, prompt-stake ВСТАВКА-27, flat eviction in `sim_sphere`) said power needs. Build it cleanly, then let the E1/E2/E3 battery decide whether active salience-pushing produces concentration / capture / harm — or NULLs a fourth time on the conservable + escapable substrate.

Module name: `sim_salience`. Class: `SalienceWorld(SphereWorld)`. No LLM, no network — pure stdlib + numpy.

## Where this sits
`sim_sphere` (module 20) gave each agent an **attention budget** of ≤K cells ranked by an **endogenous, source-neutral** significance
`sig(cell) = 1.0·food + 5.0·prox + 2.0·recency + 3.0·co_occupants` (reads the agent's *belief* `mem[c]`, not truth),
and evicts the lowest-significance cell when the budget overflows. Finding: eviction does **not** concentrate (top-5 hold 6–10%). Bare geometry yields no power.

`sim_salience` adds the **exogenous** term: designated **injectors** can add a salience bonus to a *target cell* in a *listener's* ranking, carried over the existing communication seam. Everything else (materialization, lag, the matter step) is inherited unchanged.

## The mechanic (precise)
Augment the significance function with an injected term:

```
sig_listener(cell) = base_sphere_sig(cell) + W * injected[listener][cell]
```

- `injected[listener]` is a per-listener dict `cell -> accumulated salience bonus`. It is **belief/attention bookkeeping only** — it never enters `mem[c].food` and never touches the matter/heat grid.
- `W = injection_strength` (float ≥ 0). **W = 0 ⇒ injected term contributes nothing ⇒ OFF.**
- **Injection event:** when an injector communicates to a listener (reuse the existing comm/`_social_exchange`/`_absorb_claim` seam — the same tick a claim is delivered), it also adds `inject_amount` to `injected[listener][target_cell]`. The injector is **immune to its own injection** (it does not inject into itself).
- **Decay:** once per think-cycle, every listener's `injected[listener][cell] *= decay` (0 ≤ decay ≤ 1), and entries that fall below an epsilon are dropped. `decay = 0` ⇒ one-shot (gone next cycle); `decay = 1` ⇒ permanent (must be reachable for the sweep). Decay is deterministic.
- **Crowding-out is the causal path.** A high `injected` value forces the target cell to hold a budget slot; with finite K the **lowest-significance other cell is evicted** — possibly a real high-food cell. The agent then forages on the best-*believed*-food cell **among the cells still in its budget**. So injection harms by **making victims forget good cells**, not by falsifying values. This keeps the lever orthogonal to the deception layers (11–19).

### Target policy
`target_policy ∈ {"decoy", "self"}`:
- `"decoy"` (**primary**, the agenda-setting / diversion analogue): the injector promotes a fixed designated **low-food** cell `T_decoy` in listeners' budgets — pure slot-consumption to evict their good-cell memories. The injector itself ignores `T_decoy` and forages the real cells.
- `"self"` (secondary, cheap to include): the injector promotes its **own current cell**.

## Conservation / determinism crux (do not violate)
1. **Matter-neutral.** `sim_salience` must touch **only** the significance ranking and the `injected` ledger. Do **not** modify the food/heat arrays, `eat`, or any matter flow. Matter drift must stay identical to `sim_sphere` (0.00e+00 at OFF and sphere-radius-0; < 1e-9 elsewhere). If a conservation assert moves off `sim_sphere`'s numbers, the seam is leaking — stop and fix.
2. **Significance ≠ belief ≠ matter.** Three separate quantities. Injection writes only to significance (via `injected`). Belief (`mem[c].food`) and the matter grid are untouched by injection.
3. **OFF ≡ canon, byte-for-byte.** With `injection_strength = 0` (or an empty injector set) **and** the sphere layer at its no-op config (radius ≥ diagonal, K = ∞, lag = 0), the run must reproduce canon `a91480561b6de937` exactly. Second anchor: `injection_strength = 0` with the sphere layer **ON** (finite K) must reproduce the `sim_sphere` ON-behavior exactly (positive control — injection is the only change). When no injector ever fires, **no injection events may be logged** (so the OFF stdout is identical to the baseline).
4. **Determinism.** Injector set, targets, amounts, decay, and tie-breaks all derive from deterministic state. Eviction tie-break stays `(sig, cell)` ascending (smaller `(row, col)` evicted first) — now with the injected term folded into `sig`. Two runs must be byte-identical.

## Self-check fingerprint
Extend `sim_sphere`'s self-check to also fold in: per-listener `injected` ledger contents (sorted), the ordered list of injection events (tick, injector, listener, target, amount), and the resulting eviction order under injection. Emit a `salience_fingerprint`. It must be identical in-process across the two demo runs **and** across two separate `python3 sim_salience.py` processes (this is the criterion `verify_all.py` will check).

## Experiment (print these, OFF vs ON, to the digit)
Standard substrate (grid 14×14, OASIS_CAP 150, N0 120, SEED 7, DAYS 300, THINK_EVERY 6, TAU_TRUST 0.35). Reuse the deceptive/mock speaker setup from the comm layers so there are rivals worth diverting.

**Baselines**
- B0: INJECT-OFF + sphere-OFF ≡ canon `a91480561b6de937` (byte check).
- B1: INJECT-OFF + sphere-ON (radius 0, K = 8, lag 1) ≡ `sim_sphere` ON-behavior (positive control).

**E1 — concentration / hierarchy.** With injectors ON, does attention concentrate?
- top-5 share of total significance-mass across all agents' budgets, ON vs OFF;
- injected-cell **residency**: fraction of agent-budget-slots occupied by injected target cells;
- a **significance-Gini** across cells (does a small set of cells dominate everyone's attention?).

**E2 — capture.** Does steering rivals' attention pay? Injector vs victim **body / intake gap**, ON vs OFF (target_policy = decoy). Compare against the deception-channel capture gaps from earlier modules — is the attention channel an *additional* extraction route?

**E3 — foraging harm.** Even if no stable elite forms: victims' **belief error** and **biomass**, ON vs OFF. Does crowding-out good-cell memories make victims forage worse regardless of injector profit?

**Sweeps**
- **decay ∈ {0.0, 0.6, 0.95, 1.0}** — does *permanent* injection concentrate where decaying injection does not? (the "must keep paying" knob.)
- **injector fraction ∈ {1 agent, few, many}** — does concentration need *few* injectors (salience monopoly) or *many* (mass)? (mirrors the gossip mass-vs-threshold finding.)

State the verdict honestly per E1/E2/E3 (✓ / ✗), same format as `sim_stake` / `sim_coalition`. A fourth NULL is a real result — if injection on a mobile target / conservable resource still fails to concentrate, that sharpens the thesis toward the pinned/bounded-target module. Do not tune to make it bite or to make it NULL.

## Verification bar (I will reproduce before merge)
I pull `sim_salience.py` + the `verify_all.py` diff into my sandbox and rebuild on the canonical basis, then confirm to the digit:
- B0 OFF byte-identical to `a91480561b6de937`; B1 identical to `sim_sphere` ON-behavior.
- Conservation: drift 0.00e+00 at OFF/sphere-radius-0, < 1e-9 elsewhere — matching `sim_sphere`.
- `salience_fingerprint` identical in-process and cross-process (`python3 sim_salience.py` ×2).
- File-identity: all 20 prior modules + infra byte-identical to the passing basis; diff is exactly `sim_salience.py` (new) + `verify_all.py` (registration). ⇒ ten protected fingerprints intact, `verify_all` 21/21 by composition.
- The E1/E2/E3 numbers reproduce.

## Deliverables
- `Code/sim_salience.py` — module 21, `SalienceWorld(SphereWorld)`, demo `main()` that runs the baselines + E1/E2/E3 + both sweeps, ends with conservation `assert`s and prints the success marker + `salience_fingerprint`.
- `Code/verify_all.py` — register `sim_salience` (one MODULES entry + one docstring line). **Touch nothing else.**
- Do **not** modify any other module. Do **not** merge — open a PR on a feature branch and await my verdict-by-reproduction.
