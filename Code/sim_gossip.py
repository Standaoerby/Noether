"""
sim_gossip.py — shared reputation / gossip: does pooling evidence pin the brazen liar?

Module 14 (`sim_trust`) made listeners locally accountable and found accountability
**asymmetric**: it bit the strategic liar (mock, −60%) but barely the indiscriminate
one (deceptive, ≈0). The quantified reason — trust in liars stalled *just above* the
gate (0.39/0.42 vs τ=0.35) because each listener got too few independent
verifications of one high-volume speaker to pin it.

Shared reputation is the institutional answer to local slowness: a listener who has
personally caught speaker S lying can tell co-located neighbours, so they distrust S
without having verified S themselves. Scattered verifications pool, and the brazen
liar can finally be caught. But it **relocates the contest to the reputation system
itself** — a speaker (or colluding bloc) can lie about *who is honest*: smear trusted
rivals, vouch for fellow liars. That is the demagogue's move, and we measure it too.

`GossipCommWorld(TrustCommWorld)` overrides the no-op `_social_exchange` seam: once per
think-day, co-located agents pool per-speaker reputation, **trust-weighted by how much
the receiver trusts the gossiper** (you believe reputation reports from sources you
trust). Auxiliary numbers only — it touches `self.trust`, which `TrustCommWorld`
already inherits and cleans at birth/death; no matter, no energy, no RNG.

The experiment compares OFF / LOCAL / GOSSIP (and, for the lying regimes, GOSSIP+META,
where the lying elite also inverts the reputation it reports) on `{deceptive,
mock-strategic}`, and asks two things: does honest gossip push trust in liars *below*
the gate and shrink the deceptive gap local trust left; and does meta-lying restore
capture under gossip — is gaming the reputation system the new extraction channel?

The arc for the book: local honesty-enforcement → institutional reputation →
**reputation capture**. Deterministic, sorted aggregation, no API, stdlib + numpy.
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

# how far a receiver moves toward a (trusted) gossiper's opinion. A definition, not a
# tuned knob: the per-exchange weight is GOSSIP_RATE scaled by trust in the source.
GOSSIP_RATE = 0.3

REGIMES = ("deceptive", "mock-strategic")
CONDITIONS = ("OFF", "LOCAL", "GOSSIP", "META")


# --------------------------------------------------------------------------- #
#  The gossiping world                                                         #
# --------------------------------------------------------------------------- #
class GossipCommWorld(TrustCommWorld):
    """TrustCommWorld whose co-located agents also pool per-speaker reputation. With
    `meta=True` the lying elite (the speakers) inverts the reputation it reports —
    badmouthing the trusted, vouching for the distrusted — modelling lying about *who*
    is honest. Only `self.trust` changes; the conserved dynamics are untouched."""

    def __init__(self, log, seed=SEED, regime="deceptive", policy=None, focal=None,
                 meta=False):
        self.meta = meta
        super().__init__(log, seed=seed, regime=regime, policy=policy, focal=focal)

    def _gossip_report(self, A, S, rep):
        """What agent A says about speaker S's reputation. Honest default: its true
        assessment `rep`. A meta-liar (a speaker, under `meta`) poisons the system to
        shield its bloc: it **vouches** for fellow speakers (reports 1.0, "the elite is
        trustworthy") and smears anyone else (0.0). This is the sharper bloc-favouring
        meta-lie the WO permits — coherent where a flat 1-rep inversion would have a
        liar badmouth the very allies it trusts. Deterministic, no RNG."""
        if self.meta and A.oid in self.speaker:
            return 1.0 if S in self.speaker else 0.0
        return rep

    def _social_exchange(self, here):
        for cell in sorted(here):                    # cell order is irrelevant; sorted = explicit
            agents = here[cell]
            if len(agents) < 2:
                continue
            # freeze every present agent's reputation vector for this round, so sources
            # report start-of-round values (order-independent) and only receivers move.
            snap = {a.oid: dict(self.trust[a.oid]) for a in agents}
            for B in agents:
                tb = self.trust[B.oid]
                for A in agents:
                    if A.oid == B.oid:
                        continue
                    w = GOSSIP_RATE * snap[B.oid].get(A.oid, 1.0)   # weight by trust in source
                    if w <= 0.0:
                        continue
                    for S, repA in snap[A.oid].items():
                        report = self._gossip_report(A, S, repA)
                        cur = tb.get(S, 1.0)
                        tb[S] = (1.0 - w) * cur + w * report        # convex combo -> stays in [0,1]


# --------------------------------------------------------------------------- #
#  Running a condition                                                          #
# --------------------------------------------------------------------------- #
def run_gossip(regime, meta=False, days=DAYS):
    """GOSSIP (honest reputation-sharing) or GOSSIP+META (lying elite poisons it)."""
    log = EventLog()
    if regime == "mock-strategic":
        w = GossipCommWorld(log, seed=SEED, regime="deceptive",
                            policy=MockStrategicPolicy(), focal=None, meta=meta)
    else:
        w = GossipCommWorld(log, seed=SEED, regime=regime, meta=meta)
    for _ in range(days):
        w.step()
    return w, log


def run_condition(regime, cond, days=DAYS):
    if cond == "OFF":
        return run_off(regime, days)
    if cond == "LOCAL":
        return run_on(regime, days)
    if cond == "GOSSIP":
        return run_gossip(regime, meta=False, days=days)
    if cond == "META":
        return run_gossip(regime, meta=True, days=days)
    raise ValueError(cond)


# --------------------------------------------------------------------------- #
#  Metrics                                                                      #
# --------------------------------------------------------------------------- #
def compute_metrics(days=DAYS):
    """Per regime × condition: capture gap, audience belief-error, and the end-of-run
    mean trust the audience holds in liar speakers (the pinning signal)."""
    out = {}
    for r in REGIMES:
        out[r] = {}
        for c in CONDITIONS:
            w, log = run_condition(r, c, days)
            trust_liar = float("nan")
            if c != "OFF":                           # OFF has no reputation state
                trust_liar, _honest = trust_in_speaker_kinds(w, log)
            out[r][c] = {"gap": elite_gap(w),
                         "be": float(w.belief_gap()),
                         "trust_liar": trust_liar}
    return out


def fingerprint(res):
    h = hashlib.sha256()
    for r in REGIMES:
        for c in CONDITIONS:
            d = res[r][c]
            h.update((f"{r}|{c}|gap{d['gap']:.6f}/be{d['be']:.6f}/"
                      f"tl{d['trust_liar']:.6f}").encode())
    return h.hexdigest()[:16]


# --------------------------------------------------------------------------- #
#  Demo / self-verification                                                    #
# --------------------------------------------------------------------------- #
def _fmt(v, fmt="{:+.3f}"):
    return "—" if (isinstance(v, float) and v != v) else fmt.format(v)


def main():
    line = "=" * 78
    print(line)
    print("SHARED REPUTATION / GOSSIP — does pooling evidence pin the brazen liar?")
    print("Co-located listeners pool per-speaker reputation, weighted by trust in the")
    print("source. Meta-lying = the elite inverts the reputation it reports. No RNG, no LLM.")
    print(f"seed {SEED}; {DAYS}d; think every {THINK_EVERY}d; "
          f"gossip rate {GOSSIP_RATE}; gate τ={TAU_TRUST}")
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
        print(f"{'  Δ LOCAL−OFF':<30}{_fmt(d['LOCAL']['gap'] - d['OFF']['gap']):>24}")
        print(f"{'  Δ GOSSIP−LOCAL':<30}{_fmt(d['GOSSIP']['gap'] - d['LOCAL']['gap']):>36}")
        print(f"{'  Δ META−GOSSIP':<30}{_fmt(d['META']['gap'] - d['GOSSIP']['gap']):>48}")

    fp = fingerprint(res)
    print(f"\nmetric fingerprint: {fp}")
    fp2 = fingerprint(compute_metrics())
    print(f"self-check (recompute): {fp2} -> "
          f"{'BIT-IDENTICAL ✓' if fp == fp2 else 'MISMATCH ✗'}")
    assert fp == fp2, "gossip metrics are not reproducible across runs"

    # --- conservation: gossip is bookkeeping, it moves no matter ------------- #
    wG, lG = run_gossip("deceptive", meta=False)
    drift = wG.matter_drift()
    print(f"\nmatter drift [deceptive, GOSSIP] {drift:.2e} kg   (reputation moves no matter)")
    assert drift < 1e-9, "gossip run leaked matter"

    # --- replay FROM LOG: the gossiping world is fully deterministic ---------- #
    fp_live = wG.state_fingerprint()
    wrep = GossipCommWorld(EventLog(), seed=SEED, regime="deceptive",
                           policy=ReplayPolicy(lG.events), focal=None, meta=False)
    for _ in range(DAYS):
        wrep.step()
    ok = fp_live == wrep.state_fingerprint()
    print(f"replay-FROM-LOG [deceptive, GOSSIP]: {fp_live} vs {wrep.state_fingerprint()} -> "
          f"{'BIT-IDENTICAL ✓' if ok else 'MISMATCH ✗'}")
    assert ok, "gossip run does not replay from its own claim log"

    # --- the headline answers it computes (reported, not assumed) ------------ #
    print(f"\n{line}")
    print("Q1 — does shared reputation pin the liar (trust in liars below τ, gap shrunk)?")
    for r in REGIMES:
        d = res[r]
        tl_local, tl_goss = d["LOCAL"]["trust_liar"], d["GOSSIP"]["trust_liar"]
        dgap = d["GOSSIP"]["gap"] - d["LOCAL"]["gap"]
        moved = "rises" if tl_goss > tl_local + 1e-9 else "falls"
        pin = "below" if tl_goss < TAU_TRUST else "stays above"
        gapverb = ("shrinks" if dgap < -0.01 else "grows" if dgap > 0.01 else "≈ flat")
        print(f"   {r:<15} trust in liars {tl_local:.3f}->{tl_goss:.3f} ({moved}, {pin} "
              f"τ={TAU_TRUST}); gap vs LOCAL {gapverb} ({dgap:+.3f} kg)")
    print("Q2 — does meta-lying (elite vouches for its bloc) restore capture vs honest gossip?")
    for r in REGIMES:
        d = res[r]
        meta_d = d["META"]["gap"] - d["GOSSIP"]["gap"]
        verdict = ("restores" if meta_d > 0.01 else "lowers" if meta_d < -0.01
                   else "≈ does not change")
        print(f"   {r:<15} Δ(META−GOSSIP) {meta_d:+.3f} kg — gaming reputation {verdict} capture")
    print("\nFinding: naive opinion-pooling gossip is CAPTURED BY THE CREDULOUS MAJORITY —")
    print("it spreads only diluted distrust that stays far above the gate, so it does not")
    print("pin the brazen liar and even washes out the local accountability that bit the")
    print("strategic one. Institutional reputation, pooled naively, is anti-accountable;")
    print(f"the demagogue barely needs to meta-lie. deterministic from seed {SEED}  ✓")


if __name__ == "__main__":
    main()
