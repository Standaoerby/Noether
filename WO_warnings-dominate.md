# WO: warnings-dominate gossip — does propagating distrust pin the liar, and at what cost?
# (module 16, `sim_warn.py`; deterministic, NO endpoint / NO LLM)

## Goal
Add a 16th module `Code/sim_warn.py` that replaces module-15's **opinion-averaging** gossip with a
rule where **warnings dominate**: a receiver pulls its trust in S DOWN toward the lowest *credible*
report about S (and gossip never raises trust — only personal verification does). Test the two-edged
hypothesis: (1) propagating distrust finally **pins the brazen liar** that averaging could not; (2)
the very same sensitivity makes **slander** a weapon — one false "he lied" about an honest speaker
propagates just as effectively. This is the **accountability-vs-slander fork**.

## Why (book framing — Теория Элит)
Module 15 proved naive averaging is **anti-accountable**: convex averaging can't push a receiver
below the most-suspicious source, and the credulous majority (≈1.0) floods the pool upward to ~0.9,
so the brazen liar is never pinned and meta-lying is redundant. The diagnosis pointed at the
**aggregation rule**, not the act of sharing. The fix is to propagate the *decay* of trust, not its
average — let a credible warning dominate. But there is no free lunch to expect: **a reputation
system sensitive enough to catch the brazen liar is sensitive enough to be hijacked to destroy an
honest target.** Averaging exonerates the guilty; warnings-dominate risks convicting the innocent.
Measure both edges: does WARN pin the liar (trust in liars finally below τ, deceptive gap shrinks),
and does SMEAR (the lying elite fabricating warnings about honest speakers) tank honest reputation
and degrade the honest audience. The arc: naive sharing (anti-accountable) → warnings-dominate
(accountable **but** weaponizes slander) → [next] evidence-count / K-witness as the partial cure.

## Part A — none (the seam already exists)
Module 15 added the behaviour-preserving `_social_exchange(self, here)` hook to `sim_comm.py`.
**Do NOT touch `sim_comm.py`, `sim_trust.py`, or `sim_gossip.py`.** `sim_warn.py` subclasses
`TrustCommWorld` and overrides `_social_exchange` with a different aggregation rule — parallel to
`GossipCommWorld`, not on top of it. The five protected fingerprints below must stay byte-identical
simply because their files are not edited.

## Part B — new module `sim_warn.py` (module 16): `WarnCommWorld(TrustCommWorld)`
Override `_social_exchange(self, here)` with a **downward-only, warnings-dominate** rule. Auxiliary
numbers only — **no matter/energy, no RNG**. Constant (definition):
```
TAU_SOURCE = 0.35     # heed a warning only from a source you yourself still trust >= this
                      # (equals the trust gate τ by default: you believe bad reports from credible peers)
```
For each cell with ≥2 agents:
- **snapshot** every present agent's trust vector at round start (order-independence → determinism).
- for each receiver B and each speaker S that any present source has an opinion on:
  - gather credible reports: `reports = [ self._gossip_report(A, S, snapshot[A][S]) for A in members if A.oid != B.oid and snapshot[B].get(A.oid, 1.0) >= TAU_SOURCE ]`
  - if `reports`: `worst = min(reports)`; **pull down only**: `self.trust[B.oid][S] = min(self.trust[B.oid].get(S, 1.0), worst)`
- Gossip thus only ever LOWERS trust; recovery happens solely through personal re-verification in the
  inherited `_observe`. (A consequence to note in the printout: under this rule, *vouching is inert* —
  you cannot raise trust by gossip — so the only gossip-borne attack is **slander**.)

`_gossip_report(self, A, S, rep)` — **default honest**: `return rep`.

**SMEAR regime** (the slander attack): under a flag, designated meta-liars **fabricate a maximal
warning about honest speakers** — `return 0.0` when S is an honest speaker (else `return rep`). Make
the meta-liars the lying elite (the `deceptive` speakers), smearing the honest-policy speakers. Use
the speaker policy/regime the sim already knows to identify "honest speaker"; keep it deterministic.

Lifecycle: touches only `self.trust` (inherited birth/death handling). No new per-agent state.

## Part C — the experiment (deterministic; NO endpoint, NO LLM), seed 7, same DAYS
For the lying regimes `{deceptive, mock-strategic}`, report a table across conditions:
- **OFF** — `CommWorld`
- **LOCAL** — `TrustCommWorld` (mod 14)
- **WARN** — `WarnCommWorld`, honest reports
- **WARN+SMEAR** — `WarnCommWorld`, meta-liars smear honest speakers
(AVG from `GossipCommWorld` (mod 15) is optional as a reference column — you may cite mod-15's numbers
instead of recomputing, to keep runtime down.)

Per regime/condition print:
- capture gap (elite − audience mean body, kg), with Δ WARN−LOCAL and Δ SMEAR−WARN
- audience belief-error (kg)
- **end-of-run mean trust held in liar speakers** — does WARN push it **below τ=0.35** (pinning) where
  LOCAL stalled ~0.39/0.42 and AVG rose to ~0.88?
- **end-of-run mean trust held in HONEST speakers** — the collateral: does SMEAR tank it (slander), and
  does it recover (the smearer loses credibility once pinned)?

Headline answers it computes:
1. Does warnings-dominate gossip **pin the brazen liar** (trust in liars < τ; deceptive gap shrinks vs
   LOCAL) where averaging failed?
2. Does **SMEAR** weaponize the same rule — tank honest-speaker reputation and degrade the honest
   audience's belief — i.e. is the cure for anti-accountability a slander engine? Note any timing
   nuance (smear works in the early window, then the meta-liar's own lies cost it the credibility to
   keep slandering).

## Part D — gate + invariants
- `sim_warn.py` self-verifies: `assert matter_drift < 1e-9`; **replay-FROM-LOG bit-identical**; stable
  **metric fingerprint** + self-check recompute bit-identical; cross-process byte-identical
  (`PYTHONHASHSEED` 0 vs non-0).
- Add to `verify_all.py` as **module 16**; full gate **16/16** deterministic.
- **PROTECT (byte-identical — these files are NOT edited):** `sim_comm a91480561b6de937`,
  `sim_comm_llm f353ac30db73b770`, `sim_polariz 6c4952f66da8326e`, `sim_trust 6f31f775912f5e96`,
  `sim_gossip 0fa14c92dd4ad258`.
- Pure **stdlib + numpy**, no new deps. Diff scope: NEW `sim_warn.py`, `verify_all.py` (+1 entry),
  `CHANGELOG.md` — and **nothing else**. Do **not** commit this WO file. Stack on **main**.
- Heavy like gossip (O(co-located²) pooling); keep the module's own run lean (don't recompute AVG if
  it pushes you past ~2 min) — vectorization is a separate concern, not for this WO.

## Acceptance
1. No edits to `sim_comm`/`sim_trust`/`sim_gossip`; all five protected fingerprints intact.
2. Gate **16/16** deterministic.
3. `sim_warn` prints the OFF/LOCAL/WARN/WARN+SMEAR table + the two headline answers; `matter_drift
   < 1e-9`; replay-from-log bit-identical; metric self-check bit-identical; cross-process byte-identical.
4. Open a PR with a short summary: whether WARN pinned the liar (trust < τ, gap vs LOCAL), and whether
   SMEAR tanked honest reputation / restored capture. (I verify by reproduction.)
