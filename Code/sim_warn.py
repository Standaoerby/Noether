"""
sim_warn.py — warnings-dominate gossip: does propagating distrust pin the liar,
and at what cost?

Module 15 (`sim_gossip`) proved naive opinion-*averaging* is anti-accountable: a
convex update can never push a receiver below the most-suspicious source, and the
credulous majority (≈1.0) floods the pool upward to ~0.9 — so the brazen liar is
never pinned. The diagnosis pointed at the *aggregation rule*, not the act of
sharing. This module changes the rule: **warnings dominate**. A receiver pulls its
trust in S DOWN toward the lowest *credible* report about S; gossip never raises
trust (only personal re-verification, in the inherited `_observe`, can).

That fixes accountability — but there is no free lunch. A reputation system sensitive
enough to catch the brazen liar is sensitive enough to be **hijacked to destroy an
honest target**: one fabricated "he lied" about an honest speaker propagates exactly
as well as a true warning. Averaging exonerates the guilty; warnings-dominate risks
convicting the innocent. This is the **accountability-vs-slander fork**, and we
measure both edges:
  (1) WARN — honest warnings: does propagating distrust finally push trust in liars
      below the gate τ and shrink the deceptive gap that local accountability left?
  (2) WARN+SMEAR — the lying elite fabricates maximal warnings about credible
      (honest-looking) rival speakers: does the same rule become a slander engine —
      tanking honest reputation and degrading the honest audience's belief?

`WarnCommWorld(TrustCommWorld)` overrides only the `_social_exchange` seam (parallel
to `GossipCommWorld`, not on top of it); it touches only `self.trust` — no matter, no
energy, no RNG. Deterministic: the downward-only min update is order-independent, so
two runs (and two processes) agree byte-for-byte. Pure stdlib + numpy.

The arc for the book: naive sharing (anti-accountable) → warnings-dominate
(accountable **but** weaponizes slander) → [next] evidence-count / K-witness cure.
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
from sim_pool import min_count_update

# heed a warning only from a source you yourself still trust at least this much — you
# believe bad reports from credible peers, ignore them from those you've caught lying.
# A definition (equals the trust gate τ by default), not a tuned knob.
TAU_SOURCE = 0.35

REGIMES = ("deceptive", "mock-strategic")
CONDITIONS = ("OFF", "LOCAL", "WARN", "SMEAR")


# --------------------------------------------------------------------------- #
#  The warning world                                                           #
# --------------------------------------------------------------------------- #
class WarnCommWorld(TrustCommWorld):
    """TrustCommWorld whose co-located agents propagate *warnings* (downward-only):
    a receiver lowers its trust in S to the lowest credible report it hears, never
    raising it. With `smear=True` the lying elite (the speakers) fabricates maximal
    warnings about credible rival speakers — slander. Only `self.trust` changes."""

    def __init__(self, log, seed=SEED, regime="deceptive", policy=None, focal=None,
                 smear=False):
        self.smear = smear
        super().__init__(log, seed=seed, regime=regime, policy=policy, focal=focal)

    def _gossip_report(self, A, S, rep):
        """What A reports about speaker S. Honest default: its true assessment `rep`.
        A smearer (a speaker, under `smear`) fabricates a maximal warning (0.0) about a
        speaker it currently rates as credible (`rep >= TAU_SOURCE`) — i.e. an
        honest-looking rival; liars already have low reputation and need no smearing,
        so the bloc is shielded implicitly. Deterministic."""
        if self.smear and A.oid in self.speaker and S in self.speaker and rep >= TAU_SOURCE:
            return 0.0
        return rep

    def _social_exchange(self, here):
        # Warnings-dominate = the K=1 case of the shared evidence-count pooling pass
        # (one credible lowering report suffices, then min). Vectorized in sim_pool;
        # behaviour is bit-identical to the prior scalar triple loop.
        for cell in sorted(here):                    # cells are independent; sorted = explicit
            min_count_update(self, here[cell], 1, TAU_SOURCE)


# --------------------------------------------------------------------------- #
#  Running a condition                                                          #
# --------------------------------------------------------------------------- #
def run_warn(regime, smear=False, days=DAYS):
    log = EventLog()
    if regime == "mock-strategic":
        w = WarnCommWorld(log, seed=SEED, regime="deceptive",
                          policy=MockStrategicPolicy(), focal=None, smear=smear)
    else:
        w = WarnCommWorld(log, seed=SEED, regime=regime, smear=smear)
    for _ in range(days):
        w.step()
    return w, log


def run_condition(regime, cond, days=DAYS):
    if cond == "OFF":
        return run_off(regime, days)
    if cond == "LOCAL":
        return run_on(regime, days)
    if cond == "WARN":
        return run_warn(regime, smear=False, days=days)
    if cond == "SMEAR":
        return run_warn(regime, smear=True, days=days)
    raise ValueError(cond)


# --------------------------------------------------------------------------- #
#  Metrics                                                                      #
# --------------------------------------------------------------------------- #
def compute_metrics(days=DAYS):
    """Per regime × condition: capture gap, audience belief-error, and end-of-run mean
    trust held in liar vs honest speakers (pinning signal and slander collateral)."""
    out = {}
    for r in REGIMES:
        out[r] = {}
        for c in CONDITIONS:
            w, log = run_condition(r, c, days)
            tl, th = (float("nan"), float("nan"))
            if c != "OFF":                           # OFF has no reputation state
                tl, th = trust_in_speaker_kinds(w, log)
            out[r][c] = {"gap": elite_gap(w), "be": float(w.belief_gap()),
                         "trust_liar": tl, "trust_honest": th}
    return out


def fingerprint(res):
    h = hashlib.sha256()
    for r in REGIMES:
        for c in CONDITIONS:
            d = res[r][c]
            h.update((f"{r}|{c}|gap{d['gap']:.6f}/be{d['be']:.6f}/"
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
    print("WARNINGS-DOMINATE GOSSIP — does propagating distrust pin the liar, at what cost?")
    print("A receiver lowers trust in S to the lowest credible warning it hears; gossip")
    print("never raises trust (only re-verification does). SMEAR = the elite fabricates")
    print("warnings about honest-looking rivals. No RNG, no LLM.")
    print(f"seed {SEED}; {DAYS}d; think every {THINK_EVERY}d; "
          f"heed-source τ={TAU_SOURCE}; gate τ={TAU_TRUST}")
    print(line)

    res = compute_metrics()

    cols = CONDITIONS
    for r in REGIMES:
        print(f"\n[{r}]")
        print(f"{'metric':<30}" + "".join(f"{c:>12}" for c in cols))
        print("-" * (30 + 12 * len(cols)))
        d = res[r]
        print(f"{'capture gap (elite−aud, kg)':<30}"
              + "".join(f"{_fmt(d[c]['gap']):>12}" for c in cols))
        print(f"{'audience belief-error (kg)':<30}"
              + "".join(f"{_fmt(d[c]['be'], '{:.2f}'):>12}" for c in cols))
        print(f"{'trust held in liars':<30}"
              + "".join(f"{_fmt(d[c]['trust_liar'], '{:.3f}'):>12}" for c in cols))
        print(f"{'trust held in honest speakers':<30}"
              + "".join(f"{_fmt(d[c]['trust_honest'], '{:.3f}'):>12}" for c in cols))
        print(f"{'  Δ WARN−LOCAL (gap)':<30}{_fmt(d['WARN']['gap'] - d['LOCAL']['gap']):>24}")
        print(f"{'  Δ SMEAR−WARN (gap)':<30}{_fmt(d['SMEAR']['gap'] - d['WARN']['gap']):>36}")

    fp = fingerprint(res)
    print(f"\nmetric fingerprint: {fp}")
    fp2 = fingerprint(compute_metrics())
    print(f"self-check (recompute): {fp2} -> "
          f"{'BIT-IDENTICAL ✓' if fp == fp2 else 'MISMATCH ✗'}")
    assert fp == fp2, "warn metrics are not reproducible across runs"

    # --- conservation: warnings are bookkeeping, they move no matter --------- #
    wW, lW = run_warn("deceptive", smear=False)
    drift = wW.matter_drift()
    print(f"\nmatter drift [deceptive, WARN] {drift:.2e} kg   (reputation moves no matter)")
    assert drift < 1e-9, "warn run leaked matter"

    # --- replay FROM LOG: the warning world is fully deterministic ------------ #
    fp_live = wW.state_fingerprint()
    wrep = WarnCommWorld(EventLog(), seed=SEED, regime="deceptive",
                         policy=ReplayPolicy(lW.events), focal=None, smear=False)
    for _ in range(DAYS):
        wrep.step()
    ok = fp_live == wrep.state_fingerprint()
    print(f"replay-FROM-LOG [deceptive, WARN]: {fp_live} vs {wrep.state_fingerprint()} -> "
          f"{'BIT-IDENTICAL ✓' if ok else 'MISMATCH ✗'}")
    assert ok, "warn run does not replay from its own claim log"

    # --- the headline answers it computes (reported, not assumed) ------------ #
    print(f"\n{line}")
    print("Q1 — does warnings-dominate gossip PIN the brazen liar (avg, mod-15, could not)?")
    for r in REGIMES:
        d = res[r]
        tl_local, tl_warn = d["LOCAL"]["trust_liar"], d["WARN"]["trust_liar"]
        dgap = d["WARN"]["gap"] - d["LOCAL"]["gap"]
        pin = "below" if tl_warn < TAU_TRUST else "stays above"
        gapverb = ("shrinks" if dgap < -0.01 else "grows" if dgap > 0.01 else "≈ flat")
        print(f"   {r:<15} trust in liars {tl_local:.3f}->{tl_warn:.3f} ({pin} τ={TAU_TRUST}); "
              f"gap vs LOCAL {gapverb} ({dgap:+.3f} kg)")
    print("Q2 — does SMEAR weaponize the same rule (tank honest reputation, restore capture)?")
    for r in REGIMES:
        d = res[r]
        th_warn, th_smear = d["WARN"]["trust_honest"], d["SMEAR"]["trust_honest"]
        dgap = d["SMEAR"]["gap"] - d["WARN"]["gap"]
        if th_warn == th_warn and th_smear == th_smear:     # both non-nan
            tank = th_warn - th_smear
            slan = (f"honest reputation {th_warn:.3f}->{th_smear:.3f} "
                    f"({'tanks' if tank > 0.01 else '≈ unchanged'} {tank:+.3f})")
        else:
            slan = "no honest speakers to smear (all-liar regime)"
        cap = ("restores" if dgap > 0.01 else "lowers" if dgap < -0.01 else "≈ no")
        print(f"   {r:<15} {slan}; capture Δ(SMEAR−WARN) {dgap:+.3f} kg ({cap} capture)")
    print("\nAccountability-vs-slander fork: warnings-dominate pins the brazen liar that")
    print("averaging could not — and the very same sensitivity lets the elite slander an")
    print(f"honest rival with one fabricated warning. deterministic from seed {SEED}  ✓")


if __name__ == "__main__":
    main()
