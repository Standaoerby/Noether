# WO — vectorize the shared per-cell pooling pass (sim_gossip / sim_warn / sim_evidence)

## Why
Modules 15–17 (`sim_gossip`, `sim_warn`, `sim_evidence`) each override `_social_exchange`
with an O(co-located² × candidates) triple loop (per cell: for each receiver B, for each
candidate speaker S, scan every co-located source A). This dominates `verify_all.py`, now
~20 min. The three loops share almost all scaffolding and differ only in the aggregation
rule. Factor the common scaffolding into one shared, numpy-vectorized pass; let each module
plug its rule. **Pure speed; behavior must not change.**

## Special status of this WO — read first
This is an **authorized, behavior-preserving refactor of previously-locked modules**
`sim_gossip` and `sim_warn`. It is the *one* allowed reason to touch them: a
fingerprint-preserving optimization. Consequently:
- The verdict is by **output-fingerprint reproduction, NOT file byte-identity** for
  `sim_gossip` / `sim_warn` / `sim_evidence` — their file bytes WILL change. That is expected.
- `sim_comm`, `sim_comm_llm`, `sim_polariz`, `sim_trust` stay **byte-identical files** — do
  not touch them.
- Put the shared helper in a **new module `sim_pool.py`**. Do NOT add it to `sim_comm`: the
  cleanest guarantee that `a91480561b6de937` stays byte-identical is not editing that file.

## The refactor
1. **New `sim_pool.py`** — one helper that, for a single cell, gathers (vectorized with
   numpy) for every receiver B and candidate speaker S: the credible sources A (A≠B, B's
   *snapshot* trust in A ≥ `TAU_SOURCE`), each A's report about S via `_gossip_report(A,S,rep)`
   (so the smear hook still applies), and B's snapshot trust in S. The helper must NOT bake
   in any one module's aggregation — it returns the gathered evidence (or invokes a small
   per-module callback) so each module applies its own rule on top.
2. **Each module keeps its rule**, now expressed on the gathered evidence:
   - `sim_gossip`: trust-weighted **average** (current semantics).
   - `sim_warn`: downward-only **min** over credible lowering reports (≡ evidence K=1).
   - `sim_evidence`: downward-only min, but only if **≥ K** distinct credible lowering
     reports (K-witness); keep the `A==S`-allowed semantics (the K=1≡warn anchor depends on it).
3. **Preserve the seam contract**: `_social_exchange(self, here)` signature unchanged; cells
   independent and processed in `sorted(here)` order; candidate set = union of speakers any
   present source rates; receiver loop over `members`; only `self.trust` mutated; downward-only;
   recovery still personal re-verification only.

## Determinism — the trap to avoid
- `min` and distinct-count are associative/commutative → safe to vectorize freely.
- **`sim_gossip`'s average is a SUM** → float addition is NOT associative. Reproduce the
  EXACT accumulation order, weighting, and division the current code uses, or
  `0fa14c92dd4ad258` will drift. If in doubt, keep gossip's reduction in its current scalar
  order and vectorize only the *gathering*; do not reorder the sum.
- Keep all set/dict iteration under explicit `sorted(...)` exactly as today (hash-independence).
- Snapshot semantics (read from a per-cell snapshot of trust, write to live trust) must be
  preserved — vectorization must NOT read partially-updated trust within a cell.

## Hard gates — ALL must hold (verdict by reproduction)
Fingerprints, bit-exact:
- `sim_gossip` self-check `0fa14c92dd4ad258`
- `sim_warn` self-check `419b5a4ee5adaff3` AND replay-from-log `0769725190f10057`
- `sim_evidence` metric fingerprint `70726443ebd79057` AND replay-from-log `50dae1e8052c2682`
- `sim_evidence` K=1 ≡ live `sim_warn` WARN anchor: |Δ| = 0 on gap / trust-in-liars /
  mock-honest (gap +0.062453, trust-in-liars 0.201595, mock-honest 0.288835)

Byte-identical files (do not touch): `sim_comm` `a91480561b6de937`,
`sim_comm_llm` `f353ac30db73b770`, `sim_polariz` `6c4952f66da8326e`,
`sim_trust` `6f31f775912f5e96`.

Invariants for gossip/warn/evidence: `matter_drift` < 1e-9; replay-from-log bit-identical;
cross-process byte-identical (PYTHONHASHSEED 0 vs 1).

Suite: `verify_all.py` stays **17/17** — do NOT register `sim_pool` as a tower module; it is
infrastructure with no invariants of its own (its correctness is proven by the three
fingerprints holding). Pure stdlib + numpy; **no new deps**.

## Deliverable
- New `sim_pool.py`; edited `sim_gossip.py` / `sim_warn.py` / `sim_evidence.py`.
- Report **gate wall-time before vs after** — the headline of this WO. Time `verify_all.py`
  (or at least the sum of the three heavy modules' self-runs) before and after, and quote both.
- Open a PR against `main`; **do NOT merge**. Wait for verdict-by-reproduction. Expect me to
  pull `sim_pool.py` + the three changed modules, rebuild, and confirm every fingerprint is
  bit-identical and the anchor is still exactly 0 — file bytes changing is expected; outputs
  must not move by a single ULP.

## Out of scope
- No semantic change to any rule; no new metrics; no touching the four byte-locked modules;
  no change to `verify_all`'s module set.
