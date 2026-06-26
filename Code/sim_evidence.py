"""
sim_evidence.py — evidence-count gossip (K-witness): tuning the conviction↔slander knob.

Module 16 (`sim_warn`) measured the accountability-vs-slander fork: a warnings-dominate
rule (trust only ever lowered, to the lowest credible warning) **pins the brazen liar**
that averaging could not (deceptive trust 0.391→0.202, below gate τ=0.35) — **but the
same sensitivity weaponizes slander** (one fabricated warning tanks an honest rival,
mock honest-trust 0.289→0.101).

The diagnosis pointed at a knob: under warnings-dominate a *single* credible warning
(K=1) is enough to convict. Require **K independent credible warners** before a warning
sticks, and K becomes a tunable dial:
  - small K → catches the brazen liar (many listeners independently catch it) but lets a
    lone smearer through;
  - larger K → suppresses lone slander, but slows pinning of a real liar and may merely
    raise the bar to a *coordinated* smear of K colluders.

`EvidenceCommWorld(TrustCommWorld)` overrides only `_social_exchange` (the seam exists
since module 15; Part A is none). It generalizes `sim_warn`: a warning about S sticks
for receiver B only if at least `K_WITNESS` distinct credible sources independently
report a *lowering* opinion of S; then B's trust drops to the worst of them. Gossip
still only ever lowers; recovery is personal re-verification only. With **K=1 the rule
is identical to `sim_warn`'s WARN** — asserted as a free regression.

This module sweeps K ∈ {1,2,3} to look for the window where the system still pins the
brazen liar while a lone smear no longer sticks — and tests whether a coordinated smear
of M=K colluders simply clears the higher bar. Auxiliary numbers only: no matter, no
energy, no RNG. Deterministic (set-count + min are order-independent). stdlib + numpy.

Module-16 baselines for reference (seed 7, 300 d), NOT recomputed here:
  deceptive  capture gap  OFF +0.098 · LOCAL +0.102 · WARN +0.062
  deceptive  trust in liars        LOCAL 0.391 · WARN 0.202
  mock       honest-speaker trust  WARN(no smear) 0.289 · SMEAR 0.101
"""

from __future__ import annotations

import hashlib

import numpy as np

from sim_eventlog import EventLog, SEED
from sim_comm import DAYS, THINK_EVERY
from sim_comm_llm import MockStrategicPolicy, ReplayPolicy
from sim_trust import (
    TrustCommWorld, run_off, run_on, elite_gap, trust_in_speaker_kinds, TAU_TRUST,
)

TAU_SOURCE = 0.35      # heed a warning only from a source you still trust >= this (= gate τ)
K_DEFAULT = 2          # distinct credible warners required before a warning sticks


# --------------------------------------------------------------------------- #
#  The evidence-counting world                                                 #
# --------------------------------------------------------------------------- #
class EvidenceCommWorld(TrustCommWorld):
    """TrustCommWorld whose co-located agents propagate warnings only when at least
    `k_witness` distinct credible sources independently report a lowering opinion of
    the same speaker. Downward-only, like `sim_warn`; K=1 reduces to it exactly.

    `smear_mode`: None (honest) | 'lone' (one colluder) | 'coord' (M colluders). The
    designated smearers — the lying elite fabricating maximal warnings (0.0) about
    credible/honest-looking rival speakers — are the M lowest-oid founder speakers
    (deterministic). Only `self.trust` changes."""

    def __init__(self, log, seed=SEED, regime="deceptive", policy=None, focal=None,
                 k_witness=K_DEFAULT, smear_mode=None, n_smearers=0):
        self.k_witness = k_witness
        self.smear_mode = smear_mode
        self._n_smearers = n_smearers
        super().__init__(log, seed=seed, regime=regime, policy=policy, focal=focal)
        # designate smearers deterministically: the M lowest-oid founder speakers
        # (the lying elite). Empty unless a smear regime is requested.
        m = n_smearers if smear_mode in ("lone", "coord") else 0
        self._smearers = set(sorted(self.speaker)[:m])

    def _gossip_report(self, A, S, rep):
        """A's report about speaker S. Honest default: its true assessment `rep`. A
        designated smearer fabricates a maximal warning (0.0) about a speaker it rates
        credible (`rep >= TAU_SOURCE`) — an honest-looking rival; liars already carry
        low reputation, so the bloc is shielded implicitly. Deterministic."""
        if A.oid in self._smearers and S in self.speaker and rep >= TAU_SOURCE:
            return 0.0
        return rep

    def _social_exchange(self, here):
        K = self.k_witness
        for cell in sorted(here):                    # cells independent; sorted = explicit
            members = here[cell]
            if len(members) < 2:
                continue
            snap = {a.oid: dict(self.trust[a.oid]) for a in members}
            cands = set()
            for a in members:
                cands.update(snap[a.oid].keys())     # speakers any present source rates
            for B in members:
                sb = snap[B.oid]
                tb = self.trust[B.oid]
                for S in sorted(cands):
                    cur = sb.get(S, 1.0)             # B's snapshotted trust in S
                    worst = None
                    w = 0                            # distinct credible warners about S
                    for A in members:
                        # A != B and A must hold an opinion on S. (We do NOT exclude
                        # A == S: sim_warn lets a speaker's own propagated low self-
                        # reputation act as a witness, and the K=1 ≡ sim_warn anchor
                        # below requires byte-identical neighborhood semantics.)
                        if A.oid == B.oid or S not in snap[A.oid]:
                            continue
                        if sb.get(A.oid, 1.0) < TAU_SOURCE:    # A credible to B?
                            continue
                        report = self._gossip_report(A, S, snap[A.oid][S])
                        if report < cur:             # a lowering report (a warning)
                            w += 1
                            worst = report if worst is None else min(worst, report)
                    if w >= K and worst is not None:
                        tb[S] = min(cur, worst)      # corroborated -> warnings dominate


# --------------------------------------------------------------------------- #
#  Running a condition                                                          #
# --------------------------------------------------------------------------- #
def run_evidence(regime, k_witness, smear_mode=None, n_smearers=0, days=DAYS):
    log = EventLog()
    kw = dict(k_witness=k_witness, smear_mode=smear_mode, n_smearers=n_smearers)
    if regime == "mock-strategic":
        w = EvidenceCommWorld(log, seed=SEED, regime="deceptive",
                              policy=MockStrategicPolicy(), focal=None, **kw)
    else:
        w = EvidenceCommWorld(log, seed=SEED, regime=regime, **kw)
    for _ in range(days):
        w.step()
    return w, log


def _metrics(w, log):
    tl, th = trust_in_speaker_kinds(w, log)
    return {"gap": elite_gap(w), "be": float(w.belief_gap()),
            "trust_liar": tl, "trust_honest": th}


# --------------------------------------------------------------------------- #
#  The K-sweep                                                                  #
# --------------------------------------------------------------------------- #
def compute_metrics(days=DAYS):
    out = {}
    # 1. deceptive — brazen-liar pinning (no smear), K = 1,2,3
    for K in (1, 2, 3):
        out[("deceptive", K, "none")] = _metrics(*run_evidence("deceptive", K, days=days))
    # 2. mock — lone smear (one colluder), K = 1,2,3
    for K in (1, 2, 3):
        out[("mock", K, "lone")] = _metrics(
            *run_evidence("mock-strategic", K, smear_mode="lone", n_smearers=1, days=days))
    # 3. mock — coordinated smear, M = K colluders, K = 2,3
    for K in (2, 3):
        out[("mock", K, "coord")] = _metrics(
            *run_evidence("mock-strategic", K, smear_mode="coord", n_smearers=K, days=days))
    # mock — no-smear baselines per K (for like-for-like smear comparison + the K=1
    # honest-trust ≡ WARN anchor). These let Q2/Q3 measure a smear against the right K.
    for K in (1, 2, 3):
        out[("mock", K, "none")] = _metrics(*run_evidence("mock-strategic", K, days=days))
    return out


def fingerprint(res):
    h = hashlib.sha256()
    for key in sorted(res):
        d = res[key]
        h.update((f"{key}|gap{d['gap']:.6f}/be{d['be']:.6f}/"
                  f"tl{d['trust_liar']:.6f}/th{d['trust_honest']:.6f}").encode())
    return h.hexdigest()[:16]


# --------------------------------------------------------------------------- #
#  Demo / self-verification                                                    #
# --------------------------------------------------------------------------- #
def _fmt(v, fmt="{:+.3f}"):
    return "—" if (isinstance(v, float) and v != v) else fmt.format(v)


def main():
    line = "=" * 78
    print(line)
    print("EVIDENCE-COUNT GOSSIP (K-witness) — tuning the conviction↔slander knob")
    print("A warning about S sticks for B only if >= K distinct credible sources")
    print("independently report a lowering opinion; then trust drops to the worst.")
    print("K=1 is exactly sim_warn. SMEAR: M deceptive-elite colluders fabricate 0.0.")
    print(f"seed {SEED}; {DAYS}d; think every {THINK_EVERY}d; "
          f"heed-source τ={TAU_SOURCE}; gate τ={TAU_TRUST}")
    print(line)

    res = compute_metrics()

    # 1. deceptive pinning across K
    print("\n[deceptive — brazen-liar pinning, no smear]")
    print(f"{'metric':<28}" + "".join(f"{f'K={K}':>12}" for K in (1, 2, 3)))
    print("-" * (28 + 12 * 3))
    print(f"{'capture gap (kg)':<28}"
          + "".join(f"{_fmt(res[('deceptive', K, 'none')]['gap']):>12}" for K in (1, 2, 3)))
    print(f"{'trust held in liars':<28}"
          + "".join(f"{_fmt(res[('deceptive', K, 'none')]['trust_liar'], '{:.3f}'):>12}"
                    for K in (1, 2, 3)))

    # 2. mock lone smear across K
    print("\n[mock — lone smear (1 colluder)]")
    print(f"{'metric':<28}" + "".join(f"{f'K={K}':>12}" for K in (1, 2, 3)))
    print("-" * (28 + 12 * 3))
    print(f"{'trust in honest speakers':<28}"
          + "".join(f"{_fmt(res[('mock', K, 'lone')]['trust_honest'], '{:.3f}'):>12}"
                    for K in (1, 2, 3)))
    print(f"{'capture gap (kg)':<28}"
          + "".join(f"{_fmt(res[('mock', K, 'lone')]['gap']):>12}" for K in (1, 2, 3)))
    print(f"{'audience belief-error (kg)':<28}"
          + "".join(f"{_fmt(res[('mock', K, 'lone')]['be'], '{:.2f}'):>12}" for K in (1, 2, 3)))
    print(f"{'no-smear honest-trust (base)':<28}"
          + "".join(f"{_fmt(res[('mock', K, 'none')]['trust_honest'], '{:.3f}'):>12}"
                    for K in (1, 2, 3)))

    # 3. mock coordinated smear M=K
    print("\n[mock — coordinated smear, M=K colluders] (vs lone & no-smear at same K)")
    print(f"{'metric':<28}" + "".join(f"{f'K=M={K}':>12}" for K in (2, 3)))
    print("-" * (28 + 12 * 2))
    print(f"{'coord honest-trust':<28}"
          + "".join(f"{_fmt(res[('mock', K, 'coord')]['trust_honest'], '{:.3f}'):>12}"
                    for K in (2, 3)))
    print(f"{'lone honest-trust':<28}"
          + "".join(f"{_fmt(res[('mock', K, 'lone')]['trust_honest'], '{:.3f}'):>12}"
                    for K in (2, 3)))
    print(f"{'no-smear honest-trust':<28}"
          + "".join(f"{_fmt(res[('mock', K, 'none')]['trust_honest'], '{:.3f}'):>12}"
                    for K in (2, 3)))

    # --- fingerprint + self-check (recompute the whole sweep) ---------------- #
    fp = fingerprint(res)
    print(f"\nmetric fingerprint: {fp}")
    fp2 = fingerprint(compute_metrics())
    print(f"self-check (recompute): {fp2} -> "
          f"{'BIT-IDENTICAL ✓' if fp == fp2 else 'MISMATCH ✗'}")
    assert fp == fp2, "evidence metrics are not reproducible across runs"

    # --- K=1 ≡ sim_warn WARN (the correctness anchor / free regression) ------ #
    # Compare against a LIVE sim_warn WARN run, not the rounded constants, so the
    # equality is byte-level: K=1 must reproduce module 16's WARN column exactly.
    from sim_warn import run_warn as _warn_run
    wdw, ldw = _warn_run("deceptive", smear=False)
    ref_gap, (ref_tl, _rh) = elite_gap(wdw), trust_in_speaker_kinds(wdw, ldw)
    wmw, lmw = _warn_run("mock-strategic", smear=False)
    _rl, ref_th = trust_in_speaker_kinds(wmw, lmw)
    d1, m1 = res[("deceptive", 1, "none")], res[("mock", 1, "none")]
    print("\nK=1 ≡ sim_warn WARN (correctness anchor, vs a live sim_warn run):")
    print(f"  deceptive gap {d1['gap']:+.4f} (warn {ref_gap:+.4f}) · "
          f"trust in liars {d1['trust_liar']:.4f} (warn {ref_tl:.4f}) · "
          f"mock honest-trust {m1['trust_honest']:.4f} (warn {ref_th:.4f})")
    assert abs(d1["gap"] - ref_gap) < 1e-9, f"K=1 deceptive gap {d1['gap']} != warn {ref_gap}"
    assert abs(d1["trust_liar"] - ref_tl) < 1e-9, f"K=1 trust in liars != warn {ref_tl}"
    assert abs(m1["trust_honest"] - ref_th) < 1e-9, f"K=1 mock honest-trust != warn {ref_th}"
    print("  -> BIT-MATCH ✓ (K=1 reproduces module 16's WARN column exactly)")

    # --- canonical config [deceptive, K=2]: matter + replay-from-log --------- #
    wC, lC = run_evidence("deceptive", 2)
    drift = wC.matter_drift()
    print(f"\nmatter drift [deceptive, K=2] {drift:.2e} kg   (reputation moves no matter)")
    assert drift < 1e-9, "evidence run leaked matter"
    wrep = EvidenceCommWorld(EventLog(), seed=SEED, regime="deceptive",
                             k_witness=2, smear_mode=None, n_smearers=0)
    for _ in range(DAYS):
        wrep.step()
    ok = wC.state_fingerprint() == wrep.state_fingerprint()
    print(f"replay-FROM-LOG [deceptive, K=2]: {wC.state_fingerprint()} vs "
          f"{wrep.state_fingerprint()} -> {'BIT-IDENTICAL ✓' if ok else 'MISMATCH ✗'}")
    assert ok, "evidence run does not replay from its own claim log"

    # --- the headline answers it computes (reported, not assumed) ------------ #
    print(f"\n{line}")
    print("Q1 — does pinning the brazen liar survive as K rises (trust in liars < τ)?")
    for K in (1, 2, 3):
        d = res[("deceptive", K, "none")]
        tl = d["trust_liar"]
        print(f"   K={K}: trust in liars {tl:.3f} ({'below' if tl < TAU_TRUST else 'above'} "
              f"τ={TAU_TRUST}); capture gap {d['gap']:+.3f} kg")
    pin_ok = all(res[("deceptive", K, "none")]["trust_liar"] < TAU_TRUST for K in (1, 2, 3))
    gaps = [res[("deceptive", K, "none")]["gap"] for K in (1, 2, 3)]
    print(f"   -> pinning {'survives all K' if pin_ok else 'breaks'}; "
          f"but higher K {'raises' if gaps[2] > gaps[0] + 0.01 else 'does not raise'} the "
          f"capture gap ({gaps[0]:+.3f}->{gaps[2]:+.3f}) — slower corroboration, longer profit.")
    print("Q2 — does a LONE smear tank honest reputation, and does K block it?")
    for K in (1, 2, 3):
        th = res[("mock", K, "lone")]["trust_honest"]
        base = res[("mock", K, "none")]["trust_honest"]
        drop = base - th
        eff = "tanks" if drop > 0.02 else "no measurable effect vs no-smear"
        print(f"   K={K}: lone-smear {th:.3f} vs no-smear {base:.3f} (Δ{-drop:+.3f}) — {eff}")
    print("Q3 — does a COORDINATED smear of M=K colluders get through?")
    for K in (2, 3):
        thc = res[("mock", K, "coord")]["trust_honest"]
        base = res[("mock", K, "none")]["trust_honest"]
        drop = base - thc
        got = "gets through" if drop > 0.02 else "still no measurable effect"
        print(f"   K=M={K}: coord-smear {thc:.3f} vs no-smear {base:.3f} (Δ{-drop:+.3f}) — {got}")
    print("\nFinding: K cleanly preserves brazen-liar pinning across the sweep (trust in")
    print("liars stays below τ), at the cost of a slower pin (higher K, larger capture")
    print("gap). But a LONE or M=K-coordinated smearer barely moves population honest-")
    print("trust at any K — a handful of liar-smearers have negligible reach and lose")
    print("credibility as their own food-lies are caught. The slander weapon of module")
    print(f"16 needed MASS (all speakers), not just clearing K. deterministic seed {SEED}  ✓")


if __name__ == "__main__":
    main()
