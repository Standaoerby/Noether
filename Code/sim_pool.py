"""
sim_pool.py — shared, numpy-vectorized per-cell pooling for the warnings-family modules.

`sim_warn` (K=1) and `sim_evidence` (K-witness) override `_social_exchange` with the
same O(co-located² × candidates) scaffolding and the same downward-only min/count rule;
they differ only in the witness threshold K. This module factors the common gathering
into one vectorized pass and the shared reduction, so each module is a one-line call.
**Pure speed — behaviour bit-identical.**

(`sim_gossip`'s rule — a trust-weighted convex *average* — is a sequential, order-
dependent SUM; vectorizing it over receivers reproduces the exact bits but is *slower*
than its scalar loop, because each source needs its own numpy step rather than one
reduction. Per the WO it keeps its scalar fold and does not use this module.)

This is NOT a tower module: it has no invariants of its own and is not registered in
`verify_all.py`; its correctness is exactly the two modules' fingerprints (and the
K=1 ≡ sim_warn anchor) holding bit-for-bit after the refactor.

Determinism contract (preserved here):
  * reads a SNAPSHOT of `world.trust` taken at the start of the cell; writes live trust;
    never reads partially-updated trust within a cell.
  * candidate set = union of speakers any present source rates; cells independent.
  * `min` / distinct-count are associative/commutative → vectorized freely, exact.
  * all set/dict iteration is under explicit `sorted(...)` (hash-independence).
"""

from __future__ import annotations

import numpy as np


def _gather(world, members):
    """One snapshot + matrix build, shared by both rules. Reads a snapshot of
    `world.trust`; mutates nothing. Returns:
      oids  : member oids in `members` order
      C     : candidate speaker oids (sorted) any present source rates
      n, m  : len(members), len(C)
      Tas   : [b,a] member b's snapshot trust in member a (default 1.0)
      Cur   : [b,c] member b's snapshot trust in candidate C[c] (default 1.0)
      Has   : [a,c] member a holds an opinion on candidate C[c]
      Rep   : [a,c] member a's reported opinion of C[c] via world._gossip_report
              (so the smear/meta hook still applies); valid where Has."""
    oids = [a.oid for a in members]
    n = len(members)
    snap = {oid: dict(world.trust[oid]) for oid in oids}
    midx = {oid: i for i, oid in enumerate(oids)}

    cset = set()
    for oid in oids:
        cset.update(snap[oid].keys())
    C = sorted(cset)
    cidx = {s: j for j, s in enumerate(C)}
    m = len(C)

    Tas = np.ones((n, n))
    Cur = np.ones((n, m))
    Has = np.zeros((n, m), dtype=bool)
    Rep = np.empty((n, m))
    # fill only existing entries (sparse) -> O(total entries), not O(n^2 + n*m)
    for b in range(n):
        for s, val in snap[oids[b]].items():
            a = midx.get(s)
            if a is not None:
                Tas[b, a] = val
            c = cidx.get(s)        # candidates always present, but guard anyway
            if c is not None:
                Cur[b, c] = val
    for a in range(n):
        ma = members[a]
        for s, val in snap[oids[a]].items():
            c = cidx.get(s)
            if c is not None:
                Has[a, c] = True
                Rep[a, c] = world._gossip_report(ma, s, val)
    return oids, C, n, m, Tas, Cur, Has, Rep


def min_count_update(world, members, k_witness, tau_source):
    """Warnings-dominate with a K-witness threshold (sim_warn = K=1, sim_evidence = K).

    For each receiver B and candidate speaker S: count the distinct credible sources A
    (A != B, B's snapshot trust in A >= tau_source) whose report LOWERS B's snapshot
    trust in S; if at least `k_witness` of them, drop B's trust in S to the worst of
    them. Downward-only; A == S is allowed (matches sim_warn's neighbourhood semantics,
    on which the K=1 ≡ warn anchor depends). `min`/count are order-independent → exact."""
    if len(members) < 2:
        return
    oids, C, n, m, Tas, Cur, Has, Rep = _gather(world, members)
    if m == 0:
        return
    aneqb = ~np.eye(n, dtype=bool)                 # [b,a] a != b
    cred_ba = (Tas >= tau_source) & aneqb          # [b,a] b finds a credible (and a!=b)
    for c in range(m):
        cur_c = Cur[:, c]                          # [b]
        rep_c = Rep[:, c]                          # [a] (valid where Has[:,c])
        has_c = Has[:, c]                          # [a]
        # a is a *credible warner* for b iff: credible, holds an opinion, and lowers cur
        mask = cred_ba & has_c[None, :] & (rep_c[None, :] < cur_c[:, None])   # [b,a]
        cnt = mask.sum(axis=1)                      # [b]
        worst = np.where(mask, rep_c[None, :], np.inf).min(axis=1)            # [b]
        s_oid = C[c]
        for b in np.nonzero(cnt >= k_witness)[0]:
            world.trust[oids[b]][s_oid] = float(min(cur_c[b], worst[b]))
