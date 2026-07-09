# WO — collective sanction (`sim_coalition`, module 19): the first *joint* political verb

## One line
Install the minimal **collective-enforcement** primitive: a *quorum* of co-located agents who have each independently caught a target lying can **suppress that target's voice for everyone nearby — including listeners who still trust it**. No single agent can do this; a coalition can. SANCTION-OFF must be byte-identical canon.

## Why this module (the gap)
Every layer so far acts **alone**. Communication (11), polarization (13), and the whole accountability vertical (14–17) all change **the receiver's own belief**: gossip averages others' reports into *my* trust (15), warn takes the min (16), evidence waits for *K* credible reports (17) — then *I* act on *my* updated trust. The target's reach drops only **indirectly**, because more receivers privately distrust it. No agent has ever taken a **joint action that changes the world for a non-consenting third party**.

That third-party, threshold-gated action is the political verb the book points at in ВСТАВКА 13–14 (alpha/coalition → institutionalization → police-state). This module installs its **minimal** form and asks what coordination produces that individual accountability (14–17) and individual motive (18) could not.

This is open-ended exploratory research — there is no ground truth. A refutation here is as valuable as a confirmation (it would join trust/gossip/warn/stake). Report what the numbers actually say.

## The new verb: enforcement, not updating
- **14–17 (persuasion/updating):** others' reports move *my* trust; I then act on *my* belief. A credulous agent keeps believing the liar and keeps getting redirected.
- **19 (enforcement/imposition):** when a **quorum** of co-located agents have each gated target `T` (trust `< τ`), `T`'s claims are **blocked from entering any nearby listener's perspective** this tick — *even a listener who personally still trusts `T`*. The collective overrides the individual. That is the institutional move: the group's verdict becomes binding on a non-member.

Why this has teeth in *this* substrate: power here flows through **narrative** (a lie redirects the audience's foraging → the liar/elite extracts). So silencing the liar's voice is not symbolic — it cuts the actual extraction channel. The collective sanction that matters in a narrative-driven world is **control of who gets heard**.

## What to build
New module **`sim_coalition.py` (module 19)**. Register it in `verify_all.py` (→ 19 entries; `sim_pool` still not registered). Do **not** modify any locked module.

- **`CoalitionWorld`** subclasses the trust layer (`TrustCommWorld`, module 14) so coalitions form from *already-caught* liars (read existing per-listener `trust[A][T]`). Reuse the per-cell pooling in **`sim_pool`** (module 16/17 infrastructure) to count, deterministically and order-independently, the co-located gated agents.
- **Sanction seam** = override of the claim-absorption hook (`_absorb_claim`, the same behavior-preserving seam module 14 already uses). Before a listener `B` ingests speaker `T`'s claim:
  - compute `w = #{ distinct agents A co-located with B (or with T at claim locale — pick one and document it) such that trust[A][T] < τ_sanction }` via `sim_pool`;
  - if `w ≥ Q_QUORUM` → **`T` is sanctioned at this locale this tick**: `B` does **not** ingest `T`'s claim (suppressed), regardless of `trust[B][T]`;
  - else → `B` ingests exactly as in the module-14 trust path (unchanged).
  - `A == T` allowed/excluded — pick the choice that keeps the OFF no-op exact and **document the deviation in code** (as evidence did with `A==S`).
- **SANCTION-OFF** = flag off / `Q_QUORUM = ∞`: the seam is a **pure no-op**; the world reduces to the underlying behavior exactly.
- **Gradient**: SANCTION-OFF, then ON at a small sweep of quorum values (e.g. `Q ∈ {2, 3, majority-of-present}`). Coalition forms from honestly-caught liars (no new signal invented).
- **SMEAR harness** (reuse the module 16/17 smear scaffold): a lying elite fabricates maximal distrust of an **honest** competitor to manufacture a **false quorum** against it. Modes `lone` (one smearer) and `coord` (`M = Q` smearers), so E2 can test whether the quorum protects the innocent.

Conservation is trivial here (claims carry no matter; foraging redistribution is the existing conserved `eat ≤ avail/n` split — uneaten food regrows per the locked ecology rule). Assert it anyway. Death rule untouched. No new RNG; deterministic quorum counting (set-count + threshold are order-independent).

## Refutable experiments (seed 7, 300 days, gradient OFF/ON×Q)
- **E1 — does collective sanction cut the brazen liar where individual accountability could not?** Module 14 found a *volume* liar (indiscriminate `deceptive`) barely dented by private trust gating (capture ≈ 0 change), and shared reputation either whitewashed it (15) or pinned only via mass at the cost of slander (16/17). Hypothesis: a quorum that has each caught `T` can actually **cut `T`'s capture** (elite−audience body gap, and `T`'s "heard fraction"), because suppression hits the extraction channel directly. **Refutable:** the liar may simply forage/speak where no quorum exists (spatial escape), or the quorum may never form because catching is too sparse — leaving capture untouched (toothless on a mobile target). That refutation would rhyme with module 14 ("not enough independent catches to pin") and module 18 ("form ≠ power on a conserved, escapable substrate").
- **E2 — does the sanction misfire and silence the innocent (censorship)?** Module 16 showed warnings-dominate convicts the innocent via slander; module 17 showed slander needs **mass**, not threshold-crossing, and self-limits. Hypothesis under SMEAR: a lying elite reaches a false quorum and **de-platforms an honest competitor** — the honest agent's *true* claims are suppressed, the audience loses good information, the elite extracts. **Refutable both ways:** the quorum requirement (mass) may protect the honest agent (smearers are few, lose credit once their own food-lies are caught → no quorum), **or** a coordinated elite (`M = Q`) may reach quorum and starve the truth-teller. This is the collective verb's pathology — the analogue of warn's slander, now as *censorship*.
- **E3 — does coordination manufacture a persistent hierarchy?** The payoff. Module 18 showed *individual* death-stake does **not** produce an elite on a conserved + catchable resource (Gini flat 0.365→0.363). Does *collective enforcement* produce the stratum that individual motive could not — a stable speaking in-group vs a silenced out-group? Measure Gini and persistence of **both** "heard" status and body mass, OFF vs ON. **If E3 ✓ while module-18 E1 ✗**, the book thesis sharpens: **hierarchy comes from coordinated enforcement, not from individual fear/stake** — ВСТАВКА 13–14 (coalition → institution) out-generates ВСТАВКА 1 (fear → property) in this substrate. **Refutable:** exclusion may just kill the target and dissolve (transient, no structure), leaving no persistent in/out split.

## Hard gates (must all pass before PR is reviewable)
1. **OFF = canon, proven a no-op on two configurations:**
   - all lower seams off → base comm canon `a91480561b6de937` **byte-identical**;
   - trust ON / sanction OFF → trust self-check `6f31f775912f5e96` **byte-identical**.
   (The sanction seam must perturb nothing when disabled.)
2. **New self-check fingerprint** for `sim_coalition` (stable, printed).
3. **Conservation:** matter drift `< 1e-9` on a SANCTION-ON strong run (assert).
4. **Replay** byte-identical (replay-from-log reproduces the run) and **cross-process** identical (PYTHONHASHSEED 0 vs 1).
5. **`verify_all` 19/19** (rc 0 + run1 == run2 for every module).
6. **Locked modules untouched:** the eight protected files (`sim_comm`, `sim_comm_llm`, `sim_polariz`, `sim_trust`, `sim_gossip`, `sim_warn`, `sim_evidence`, `sim_pool`) and `sim_stake` byte-identical (`cmp`); the **eight protected fingerprints** + `sim_stake`'s `c9f80743fc27cbc8` intact. The diff is exactly `sim_coalition.py` (new) + `verify_all.py` (+1 registration line).
7. **Pure stdlib + numpy.** No live LLM, no network, no endpoint in the gate.

Open the PR on a branch; do **not** merge. I give the verdict by reproduction (pull the branch files, rebuild in sandbox, confirm fingerprints + every number to the digit) before Stan merges.

## Follow-on (NOT this PR)
- 🔖 A **material-exclusion** variant (a quorum denies `T` its share of a contested cell's `avail`, redistributing to non-excluded present agents — conservation-neutral) is the natural sibling verb, but it needs an *overridable foraging/eating seam*. If no such seam exists in the locked base, **do not add one by editing locked code** — leave it for a future WO. This PR does the **voice-level** verb, which lives on the known `_absorb_claim` seam.
- After this module merges and is synced, the next step is the **live ВСТАВКА-27 test on `qwen3:14b`** (survival-conditioned cohort prompt, 5 seeds on SOW) — a run-experiment, not a gate module.
