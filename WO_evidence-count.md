# WO — module 17: evidence-count gossip (K-witness), tuning the conviction↔slander knob

## Role
You are Claude Code working in the `Noether` repo on Stan's Windows machine. Build module 17 on top of `main`. Open a PR against `main` and **stop — do not merge**; await verdict-by-reproduction (Гайка rebuilds in a sandbox and confirms every fingerprint and table number before Stan merges).

## Why (context)
Module 16 (`sim_warn`, [[Warnings-dominate gossip]]) measured the **accountability-vs-slander fork** on one substrate: a warnings-dominate rule (trust only ever lowered, to the lowest credible warning) **pins the brazen liar** that averaging could not (deceptive trust 0.391→0.202, below gate τ=0.35), **but the same sensitivity weaponizes slander** — one fabricated warning tanks an honest rival (mock honest-trust 0.289→0.101).

The diagnosis pointed at a knob: a single credible warning (K=1) is enough to convict. Require **K independent credible warners** before a warning sticks, and K becomes a tunable dial:
- small K → catches the brazen liar (many listeners independently catch it) but lets a lone smearer through;
- larger K → suppresses lone slander, but slows pinning of a real liar and (the open question) may merely raise the bar to a coordinated smear of K colluders.

This module builds the K-witness rule and **sweeps K to find the window** where the system still pins the brazen liar while a lone smear no longer sticks.

## Build
New file `Code/sim_evidence.py`. New class `EvidenceCommWorld(TrustCommWorld)` that overrides `_social_exchange(self, here)`. **Part A is NONE** — the `_social_exchange` seam already exists in `sim_comm` since module 15. Do not add or change any seam.

### Mechanism — evidence-count, downward-only
Generalizes `sim_warn` with an evidence threshold `K_WITNESS` (int, default **2**):

For each receiver `B` and each target speaker `S`, within a gossip round over the co-located group (same neighborhood `sim_warn` uses):
1. **Snapshot** all `trust` at the start of the round (order-independence, as in `sim_gossip`/`sim_warn`). All reads below use the snapshot.
2. Gather the **distinct credible warners** about `S`: the set of source agents `A` (A≠B, A≠S) co-located with `B` such that
   - `A` is credible to `B`: `trust_snap[B][A] >= TAU_SOURCE` (reuse `TAU_SOURCE = 0.35`), **and**
   - `A`'s report about `S` is a *lowering* report: `report_A < trust_snap[B][S]` (a warning, not a vouch).
   The report value `report_A` is `A`'s own `trust_snap[A][S]` (its honest opinion), except in a smear regime (below) where designated smearers fabricate `report_A = 0.0`.
3. Let `w = number of distinct credible warners`. **If `w >= K_WITNESS`**, apply the warnings-dominate update: `trust[B][S] = min(trust_snap[B][S], min(report_A over the credible warners))`. **Else leave `trust[B][S] unchanged`** (the warning has insufficient corroboration). Gossip still only ever lowers; upward recovery remains personal re-verification only.

**Correctness anchor (free regression):** with `K_WITNESS = 1` this rule is *identical* to `sim_warn`'s WARN rule (one lowering credible report suffices, then min). Your run MUST reproduce `sim_warn`'s WARN column at K=1 — deceptive capture gap **+0.062**, trust in liars **0.202**, mock honest-trust **0.289**. Assert this equality in the self-check; it is the cheapest proof the generalization is faithful.

### Smear regimes (the slander attack, parameterized by attacker coordination)
Reuse `sim_warn`'s SMEAR idea — the lying elite fabricates a maximal warning (`report = 0.0`) about honest-policy speakers — but parameterize how many colluders fabricate:
- **`lone`**: exactly **one** designated deceptive-elite agent fabricates `report=0.0` about honest speakers (a single smearer).
- **`coord(M)`**: **M** designated deceptive-elite agents collude, each fabricating `report=0.0` about the same honest speakers.

Pick the designated smearers deterministically (e.g. lowest oids among deceptive speakers); document the choice in a comment.

## Do NOT touch (protect six fingerprints)
`sim_comm.py`, `sim_trust.py`, `sim_gossip.py`, `sim_warn.py` must remain **byte-identical**. After your change these must still hold:
- `sim_comm` canonical stdout `a91480561b6de937`
- `sim_comm_llm` replay-rerun `f353ac30db73b770`
- `sim_polariz` self-check `6c4952f66da8326e`
- `sim_trust` metric self-check `6f31f775912f5e96`
- `sim_gossip` metric self-check `0fa14c92dd4ad258`
- `sim_warn` metric self-check `419b5a4ee5adaff3`

No new dependencies (pure stdlib + numpy). Do not commit this WO file.

## Experiment (the K-sweep)
Fixed world as the trilogy: `seed 7`, `DAYS=300`, think every 6d, gate τ=0.35, `TAU_SOURCE=0.35`. Do **not** recompute OFF/LOCAL/WARN baselines — cite module 16's numbers in a header comment for reference. The evidence table sweeps **K ∈ {1, 2, 3}** over these conditions:

1. **deceptive — brazen-liar pinning** (all elite lie; no smear): trust held in liars, capture gap. *Question Q1: does pinning survive as K rises (trust in liars stays below τ)?*
2. **mock — lone smear** (`lone`; honest speakers exist): trust held in honest speakers, capture gap, audience belief-error. *Question Q2: does a lone smear stop sticking as K rises (honest trust recovers toward its no-smear level)?*
3. **mock — coordinated smear** `coord(M=K)` (M colluders equal to the current threshold), for K ∈ {2,3}: honest trust. *Question Q3: does a smear with M=K colluders get through again — i.e. is K merely a bar that coordination of size K clears?*

Keep the run lean enough that `main()` stays comfortably under ~600 s (each 300-day condition-run is ~30–40 s; the above is ≤ 8 runs). Print one compact table per regime with K across the columns, then a short Q1/Q2/Q3 readout in the same plain style as `sim_warn` (verbs from the numbers, no hand-waving). Report honestly if the window does not exist or a result refutes the hypothesis — a clean refutation is as valuable as a confirmation (as in module 15).

## Invariants / self-check (what `main()` must assert and print)
Canonical self-check configuration: **`[deceptive, K_WITNESS=2]`**, full 300 days.
- **Matter** drift `< 1e-9` kg on the canonical config (reputation moves no matter): print it.
- **Replay-from-log** of the canonical config is **bit-identical**: print `… -> BIT-IDENTICAL`.
- **Metric self-check**: recompute the metric from the log and hash; print `self-check (recompute): <hex> -> BIT-IDENTICAL`. This `<hex>` is the new protected fingerprint for module 17.
- **K=1 ≡ warn** equality assert (the correctness anchor above).
- Determinism is seeded; the whole program must be **cross-process byte-identical** (PYTHONHASHSEED-invariant).

## Gate
- `Code/verify_all.py` wires `sim_evidence` as the **17th** module and the suite is green: every module rc 0 and run1==run2 byte-identical (it is acceptable, as before, that the full monolithic run is slow and the gate is confirmed by components — modules 1–10 locked, 11–16 fingerprints intact, 17 passes matter+replay+self-check+cross-process).
- All six prior fingerprints intact; `sim_comm`/`sim_trust`/`sim_gossip`/`sim_warn` untouched.
- Pure stdlib + numpy; stacks on `main`.

## Deliverable
Diff scope exactly: new `Code/sim_evidence.py`, one line added to `Code/verify_all.py` (the 17th entry), and `CHANGELOG.md`. Open the PR against `main`, summarize the K-sweep table and the Q1/Q2/Q3 readout (with the K=1≡warn check called out), and **stop for verdict**.
