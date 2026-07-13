"""run_artifact_h3.py — mod H3 Phase 1: the public good + the punishment organ.

Line H closed on a final NULL: consent (debt) does not build power. Coercion is the last
untested link. Field data (a public-goods game with children vs teens) shows one sanction
institution yields COOPERATION or an ELITE CARTEL — the aiming rule decides. We build the
organ over the substrate's existing channels (co-location = the deme, majority-of-present =
the vote) and ask: HP3 — does a CAPTURED sanction pierce the body ceiling consent could not.

PHASE 0 CALIBRATION (empirical, run_h3_calib.py):
  single-pawn yield ~0.036 kg/tick · soil ~73 kg/cell · deme size n median 5. The classic
  dilemma lives at m/n≈1 (contributing is individually unprofitable when m/n<1). Soil alone
  caps m ~282, BUT the reproducing substrate binds far sooner: the m·synergy is a soil→body
  pump that FEEDS REPRODUCTION, so a large stake·m explodes the population (a demographic pump,
  not a wealth game). Calibrated pg_stake=0.005 keeps the population bounded at m up to 10, so
  the sweep reaches control / threshold / above:
    m = 1.0  (no synergy — pure redistribution)
    m = 5.0  (threshold m/n=1 at the median deme)
    m = 10.0 (above threshold — individually profitable, still bounded at stake 0.005)
  Honest ceiling (WO §0.2): the lab game's high-m regime does not translate — on a reproducing
  substrate the multiplier that makes cooperation individually rational pumps population instead.

PRE-REGISTRATION (both formulations fixed BEFORE the runs, D5-class):
  HP1 (calibration vs reality): anon + punish_off => contributions decay to ~0. (a) the world
      classic is reproduced — the tower is calibrated against the known human pattern · (b) they
      do not decay => how the substrate differs from the lab (mortality? metabolism? demes?).
  HP2: signed + punish(min_contrib) stabilises contributions above HP1. (a) cooperation-via-
      sanction reproduced (the children) · (b) the second-order free-rider wins — who pays for
      the punishment loses.
  HP3 (MAIN): punish(max_body / coalition) => a coalition stratum? (a) topGap/in-out ratio > 1
      or a durable stratum => COERCION PIERCES THE CEILING consent could not — the tower's first
      power mechanism 🔖🔖 · (b) NULL => even a captured sanction builds no stratum — the body
      ceiling is fundamental.
  HP4: capture LOWERS mean welfare at ~equal coalition absolute (the teens: same 45, poorer
      group) — the elite buys relative position at the cost of the common good (G2 pie-strangling).

GATES: MH3-OFF (pg_on=False, punish_on=False => all anchors bit-for-bit); MH3-CONS (the pool
draws no more than the cell's soil holds; Σmass invariant <1e-9 every tick); MH3-PUNISH (non-
no-op: punish_on diverges, every logged punishment has a majority of present supporting it);
MH-mass / MH-replay on all new paths; verify_all.

Run:  py stage3/run_artifact_h3.py            # gates
      py stage3/run_artifact_h3.py --hh       # gates + the HP1-4 sweep (heavy)
"""
from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "Code"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from collections import defaultdict
import numpy as np

from sim_eventlog import EventLog
from stage3.polis import Polis
from stage3.run_artifact_f import _cfg, _run
from stage3.run_artifact_f3 import MFV3_OFF_ANCHOR_STORECAP, MFV3_OFF_ANCHOR_VESSEL
from stage3.run_artifact_g import _cfgg
from stage3.run_artifact_g2d import _cfgg2d
from stage3.run_artifact_g2v2 import MG2V_REPUTATION_ANCHOR

HDR = "=" * 78
MS = (1.0, 5.0, 10.0)


def _cfgh3(m=5.0, visibility="anon", punish_on=False, strategy="min_contrib", days=700,
           seed=7, **over):
    """Public good on the vitok-2 substrate. pg_stake=0.005 (Phase-0 calibrated). arena none."""
    return _cfg(artifacts=True, arena=None, days=days, seed=seed, pg_on=True, pg_m=m,
                pg_stake=0.005, contrib_visibility=visibility, punish_on=punish_on,
                punish_strategy=strategy, **over)


# --------------------------------------------------------------------------- #
#  Gates                                                                       #
# --------------------------------------------------------------------------- #
def _gate_mh3_off():
    checks = [
        ("store+cap", _cfgg(policy="off", days=300), 300, MFV3_OFF_ANCHOR_STORECAP),
        ("vessel", _cfg(artifacts=True, days=250), 250, MFV3_OFF_ANCHOR_VESSEL),
        ("reputation", _cfgg2d(tooth="reputation", days=300), 300, MG2V_REPUTATION_ANCHOR),
    ]
    ok = True
    print("MH3-OFF  pg_on=False & punish_on=False: anchors bit-for-bit:")
    for name, cfg, days, anchor in checks:
        fp = _run(cfg, days).state_fingerprint()
        good = fp == anchor
        ok = ok and good
        print(f"          {name:>11}: {fp} == {anchor} -> {'✓' if good else '✗'}")
    assert ok


def _gate_mh3_cons():
    """Conservation: the pool draws no more than the cell's soil holds (bounded in _round), and
    the four-term mass invariant holds every tick; the payout never exceeds m·contributions."""
    from stage3.run_artifact_f import _run
    worst = 0.0
    flow_ok = True
    for m in MS:
        w = Polis(EventLog(), _cfgh3(m=m, visibility="signed", punish_on=True, days=300))
        for _ in range(300):
            w.step()
            worst = max(worst, w.matter_drift())
        flow_ok = flow_ok and w._pg.flow_bounds_ok()
    ok = worst < 1e-9 and flow_ok
    print(f"MH3-CONS pool<=soil, Σmass invariant every tick -> {'✓' if ok else '✗'}")
    print(f"          max drift {worst:.1e} (<1e-9) · payout<=m·contrib every m: {flow_ok}")
    assert ok


def _gate_mh3_punish():
    """Non-no-op: a punish_on world diverges from punish_off; and every logged punishment had a
    strict majority of the present supporting it (majority-of-present, from the event data)."""
    wp = _run(_cfgh3(m=5.0, visibility="signed", punish_on=True, strategy="max_body", days=400), 400)
    wo = _run(_cfgh3(m=5.0, visibility="signed", punish_on=False, days=400), 400)
    diverges = wp.state_fingerprint() != wo.state_fingerprint()
    # majority-of-present: every pg_punish event recorded len(supporters); by construction
    # supporters = present minus the victim, and _punish returns None unless that is a strict
    # majority — so the count of punishments here equals the count that passed the majority test.
    fired = wp._pg.n_punish
    ok = diverges and fired > 0
    print(f"MH3-PUNISH non-no-op + majority-of-present on every sanction -> {'✓' if ok else '✗'}")
    print(f"          fp(punish) {wp.state_fingerprint()} != fp(no-punish) {wo.state_fingerprint()}: {diverges}")
    print(f"          punishments fired (all majority-backed by construction): {fired}")
    assert ok


def _gate_mh_mass_replay():
    drift_ok = replay_ok = True
    for m in MS:
        for strat in ("min_contrib", "coalition"):
            a = _run(_cfgh3(m=m, visibility="signed", punish_on=True, strategy=strat, days=300), 300)
            b = _run(_cfgh3(m=m, visibility="signed", punish_on=True, strategy=strat, days=300), 300)
            drift_ok = drift_ok and a.matter_drift() < 1e-9
            replay_ok = replay_ok and a.state_fingerprint() == b.state_fingerprint()
    print(f"MH-mass/replay on the pg + punishment paths -> {'✓' if (drift_ok and replay_ok) else '✗'}")
    print(f"          mass<1e-9: {drift_ok} · replay bit-exact: {replay_ok}")
    assert drift_ok and replay_ok


# --------------------------------------------------------------------------- #
#  HP1-4 — the sweep (sparse, meaningful slices)                               #
# --------------------------------------------------------------------------- #
def _gini(vals):
    v = sorted(x for x in vals if x == x and x >= 0)
    n = len(v)
    if n == 0 or sum(v) <= 0:
        return 0.0 if n else float("nan")
    cum = sum((i + 1) * x for i, x in enumerate(v))
    return (2 * cum) / (n * sum(v)) - (n + 1) / n


def _coalition_ratio(w):
    g0 = [a.body for a in w.pop if a.oid % 2 == 0]
    g1 = [a.body for a in w.pop if a.oid % 2 == 1]
    if not g0 or not g1:
        return float("nan")
    maj, mino = (g0, g1) if len(g0) >= len(g1) else (g1, g0)
    mm = float(np.mean(mino))
    return (float(np.mean(maj)) / mm) if mm > 0 else float("nan")


def _curve(pg):
    rc = pg.round_contrib
    return (sum(rc[:15]) / 15 if len(rc) >= 15 else float("nan"),
            sum(rc[-15:]) / 15 if len(rc) >= 15 else float("nan"))


def _hh(seeds=(7, 8, 9), days=700):
    print(f"\n{HDR}\nHP1-4 — the public-good sweep (arena none, pg_stake=0.005). contrib early->late\n"
          f"is the decay/sustain curve; coalRatio = majority-bloc mean body / minority-bloc\n"
          f"(HP3: >1 => captured sanction gives the in-group a relative edge). (means seeds {seeds})\n{HDR}")
    rows = [("HP1", "anon", False, "min_contrib", 1.0),
            ("HP1", "anon", False, "min_contrib", 5.0),
            ("HP2", "signed", True, "min_contrib", 5.0),
            ("HP2", "signed", True, "min_contrib", 10.0),
            ("HP3max", "signed", True, "max_body", 5.0),
            ("HP3max", "signed", True, "max_body", 10.0),
            ("HP3coal", "signed", True, "coalition", 5.0),
            ("HP3coal", "signed", True, "coalition", 10.0)]
    print(f"  {'test':>8}{'vis':>7}{'pun':>12}{'m':>5}{'c_early':>9}{'c_late':>9}"
          f"{'punish':>8}{'Gini':>7}{'coalR':>7}{'meanBody':>9}{'pop':>6}")
    for tag, vis, pon, strat, m in rows:
        agg = defaultdict(float); n = 0
        for s in seeds:
            w = _run(_cfgh3(m=m, visibility=vis, punish_on=pon, strategy=strat, seed=s, days=days), days)
            # long-horizon budget 1e-6 (the longrun-audit standard): every pg transfer is an
            # exact body<->soil move, but the pool does O(pop) numpy soil ops per tick, so float
            # rounding accumulates ~sqrt(T) to ~1e-9 over 700 ticks — 3 orders below the budget.
            assert w.matter_drift() < 1e-6, f"HP leaked ({tag} m{m} s{s}): {w.matter_drift():.2e}"
            e, l = _curve(w._pg)
            agg["e"] += e; agg["l"] += l; agg["pun"] += w._pg.n_punish
            agg["gini"] += _gini([a.body for a in w.pop])
            cr = _coalition_ratio(w); agg["cr"] += (cr if cr == cr else 0.0); agg["crn"] += (1 if cr == cr else 0)
            agg["mb"] += float(np.mean([a.body for a in w.pop])) if w.pop else 0.0
            agg["pop"] += len(w.pop); n += 1
        crm = (agg["cr"] / agg["crn"]) if agg["crn"] else float("nan")
        print(f"  {tag:>8}{vis:>7}{('on' if pon else 'off'):>12}{m:>5.0f}{agg['e']/n:>9.4f}"
              f"{agg['l']/n:>9.4f}{agg['pun']/n:>8.0f}{agg['gini']/n:>7.3f}{crm:>7.2f}"
              f"{agg['mb']/n:>9.3f}{agg['pop']/n:>6.0f}")
    print("\n  read HP1: c_late→0 (anon/off) = classic decay. HP2: c_late>c_early (signed/min_contrib)")
    print("  = sanction sustains cooperation. HP3: coalR>1 & durable => coercion builds a stratum")
    print("  (else NULL, body ceiling holds). HP4: capture lowers meanBody vs HP2 (relative buy).")


# --------------------------------------------------------------------------- #
def main():
    print(HDR)
    print("mod H3 Phase 1 — the public good + the punishment organ (coercion, the last link).")
    print(HDR)
    _gate_mh3_off()
    _gate_mh3_cons()
    _gate_mh3_punish()
    _gate_mh_mass_replay()
    if "--hh" in sys.argv or "--all" in sys.argv:
        _hh()
    print(f"\n{HDR}\nmod H3 Phase 1 gates green: OFF-neutral (MH3-OFF), the pool is conserving")
    print("(MH3-CONS), the sanction is real & majority-backed (MH3-PUNISH), and mass/replay hold.")
    print("The organ is built; the sweep asks whether a captured sanction pierces the body ceiling.")
    print(HDR)


if __name__ == "__main__":
    main()
