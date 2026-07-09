# WO — sim_sphere: the observer, local materialization, attention budget, information lag

Module: **20** (`sim_sphere`) — the first vertebra of the embodied world. Registered in `verify_all` (→ 20/20).
NO living minds, NO LLM, NO network. Pure stdlib + numpy. This is the honest substrate the game will later sit on; build the nail, not the bow.
Branches off fresh `main` (`git checkout main; git pull; git checkout -b feat/sim-sphere`); PR against `main`.

## Canon this encodes (the ontology we just fixed)
Three deliberately-divergent levels:
1. **What IS** — the objective event-log (the god view). Conservation + determinism + replay live here, unbreakable.
2. **What is MATERIALIZED** — the union of agents' *presence neighbourhoods* (geometry). Matter flows and is **strictly conserved** inside the active set; outside it folds into a per-region invariant with **zero leak**. The 9M-cell whole is NEVER updated at once.
3. **What an agent KNOWS** — an **attention budget** of K observed elements, ranked by **endogenous significance**, reaching the agent with an **information lag**.

Matter exists materially whether observed or not (level 2). The budget (level 3) is a property of **belief/knowledge**, never of matter. Falling out of the budget is **forgetting**, not annihilation.

## What to build
1. **Presence geometry (materialization).** Each agent has a presence neighbourhood (a disc in continuous coordinates is fine for v1). The materialized world = union of these. Physics (the existing conserved food/heat update) runs **only on the materialized set**; dormant regions are frozen as a conserved invariant (a dormant region is by definition in flux-balance across its boundary — freezing it is physics, not a cheat). Matter accounting closes over **active set + region boundaries** to < 1e-9.
2. **Attention budget K (knowledge layer).** Each agent holds at most **K** observed elements (cells/objects/other-agents). When the count of observable-within-presence exceeds K, the **lowest-significance** items are **evicted** (→ flagged forgetting candidates). The budget governs what the agent *knows*, not what *exists*.
3. **Significance ranking — endogenous, outcome-neutral, deterministic.** Rank = a fixed function of **observable** properties only: magnitude (e.g. food quantity), proximity, novelty/change-since-last-seen, presence of another agent/threat, recency. It MUST:
   - be **endogenous** — derived from observed stimulus features, never a hand-set "this is important because the plot needs it";
   - be **outcome-neutral** — it does NOT know who lies, who is elite, or who benefits; it ranks *stimuli*, and who wins attention is a **measured result, not a baked-in premise**;
   - be **deterministic** — same scene -> same ranking, byte-for-byte.
   (Hard rule: do not let significance encode the conclusion. If a future module wants *injected* significance — Stan's "throw in a motive/object" — that is a SEPARATE module; here significance is strictly endogenous.)
4. **Information lag.** A fact entering region A's materialized state reaches agent B after `d` **logical ticks** (via region overlap or a relayed chain), `d >= 0`. Lag is a first-class, logged quantity. B's belief lawfully **trails** truth by `d` — not from deception, but from the finite speed of information. (`d=0` everywhere = the zero-lag degenerate case used by OFF.)
5. **Sleep hook (skeleton only, NO LLM).** Items evicted from the budget over a "day" are logged as **consolidation/forgetting candidates** for a future sleep module. In THIS WO: only the log hook + the eviction record. No consolidation logic, no model call.

## Hard gates (prove in the PR body before merge)
- **OFF-mode == canon, byte-identical.** With infinite budget (K=inf), full presence (radius covers the whole used extent), and zero lag (`d=0`), `sim_sphere` must reproduce `sim_comm`'s canonical stdout **`a91480561b6de937`** bit-for-bit. This is the proof that module 20 does not perturb the 1-19 tower.
- `verify_all` **20/20**: `sim_sphere` registered and self-checking (subprocess x2, rc 0 + identical sha256 stdout); the nineteen prior modules and nine locked fingerprints **untouched** (byte-identical files).
- **Conservation** `matter_drift < 1e-9` measured over the **active set + region boundaries** (not the whole grid), in BOTH a budgeted/lagged run and the OFF run. A region folding to dormant leaks zero matter.
- **Determinism**: two runs byte-identical, including the budget contents, the eviction order, and the significance ranking. Eviction ties broken deterministically (document the rule).
- Self-check prints a stable fingerprint; pure stdlib + numpy; no new pip deps; no network; importing the module is side-effect-free.
- No edits to the ten locked base files; the embodied-world hooks are additive.

## Refutable questions this opens (for the book — measured, not assumed)
- **Attention as a conserved scarce resource:** when observable-within-presence > K, what gets evicted, and does eviction concentrate (a few high-significance items crowd out everything) or stay flat? (Ties to: claim = competitively-crowded public good; smear needs **mass**; quorum can't assemble around a moving target — all of which were about *competition for a slot in someone's perception*. Budget K gives that a physical substrate.)
- **Belief-lag without lying:** how far does B's belief trail truth purely from information lag `d`, before any deception is added? (Turns "perspective != full log" from epistemic into **physical**.)
- **NULL is a finding:** if endogenous significance + lag produce no interesting attention dynamics on the bare substrate, that itself bounds where the interesting behaviour must come from (objects, injection, persons — later modules).

## Deliverable
PR with `sim_sphere.py` + the 2-line `verify_all` registration, and a short note documenting: the presence geometry, the exact significance function, the eviction tie-break rule, and the lag model. Gaika verdicts by reproduction: rebuild in sandbox, confirm OFF == `a91480561b6de937` bit-for-bit, the self-check fingerprint, conservation over the active set, byte-determinism of budget/eviction/ranking, and `verify_all` 20/20 — all offline, no network needed (this module has none).
