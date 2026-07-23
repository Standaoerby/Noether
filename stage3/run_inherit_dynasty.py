"""run_inherit_dynasty.py — mod-K Ф2/Ф3: does inheritance under mortality lock the caste, or
does finding #5's dilution survive? Three arms (WO §3) at the science config rho=0.1 claim,
arena=None, T=3000 (finding #5's horizon), seeds 7/8/9:

  1. base            inherit=off, frailty=off   — Polis-base ≡ canon (churn = starvation,
                                                   revert to commons). The #5-analog baseline.
  2. inherit/nodeath inherit=on,  frailty=off   — inheritance, but owners ~immortal (die only
                                                   of starvation) => it fires RARELY.
  3. inherit/mortal  inherit=on,  frailty=gompertz — owners die their own death => inheritance
                                                   fires MASSIVELY. Here #5 holds or inverts.

Ф2 (this report): characterise arm 1 — does it reproduce #5's dilution qualitatively
(owner_share low, rising toward T as the population explosion dilutes the caste)? And
MK-INHERIT-FIRES: does arm 3 actually fire (w._inherit_events > 0) at full T=3000 — founders
without descendants do not inherit, the effect accrues with generations (WO §2 refinement B),
so it is measured at T=3000, NOT early snapshots. NO K1/K2 verdicts in Ф2.

Metrics are the canon-25 _snapshot formulas ported to Polis (owner_share added). e2_dynasty
hardcodes t=300 as "end"; here we compute END metrics at t=3000 ourselves.

Run:  py stage3/run_inherit_dynasty.py --arms base --seeds 7,8,9          # Ф2 base
      py stage3/run_inherit_dynasty.py --arms mortal --seeds 7 --fires    # MK-INHERIT-FIRES
      py stage3/run_inherit_dynasty.py                                    # full matrix (Ф3)
"""
from __future__ import annotations

import argparse
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "Code"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sim_eventlog import EventLog                          # noqa: E402
from sim_salience import gini                              # noqa: E402  (same gini canon-25 uses)
from stage3.polis import Polis                             # noqa: E402
from stage3.run_artifact_f import _cfg                     # noqa: E402

HDR = "=" * 78
T = 3000
SNAPS = (50, 150, 300, 500, 1000, 2000, 3000)
ARMS = {
    "base":    dict(inherit_on=False, frailty="off"),
    "nodeath": dict(inherit_on=True,  frailty="off"),
    "mortal":  dict(inherit_on=True,  frailty="gompertz"),
    "escheat": dict(inherit_on=True,  frailty="gompertz", heir_fallback="escheat"),  # K3
}


def _snapshot(w):
    """Canon-25 _snapshot ported to Polis, plus owner_share. Pure read."""
    counts = w.territory_counts()
    ranked = [oid for oid, _ in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))]
    top5 = ranked[:5]
    per_house = defaultdict(int)
    for _c, oid in w._cell_owner.items():
        per_house[w.house(oid)] += 1
    owners_alive = w.owner_ids()
    tot_body = sum(a.body for a in w.pop)
    owner_body = sum(a.body for a in w.pop if a.oid in owners_alive)
    return {
        "t": w.t, "alive": len(w.pop), "n_owners": len(owners_alive),
        "owning_houses": frozenset(per_house),
        "top5_houses": frozenset(w.house(o) for o in top5),
        "n_owned_cells": len(w._cell_owner),
        "owner_share": (owner_body / tot_body) if tot_body > 0 else float("nan"),
        "house_gini": gini(list(per_house.values())) if per_house else float("nan"),
        "top_house_share": (max(per_house.values()) / sum(per_house.values()))
                           if per_house else float("nan"),
        "distinct_owner_houses": len(per_house),
        "max_gen": max((w.gen.get(o, 0) for o in top5), default=0),
        "inherit_events": int(getattr(w, "_inherit_events", 0)),
    }


def _run(arm, seed, rho=0.1):
    cfg = _cfg(days=0, seed=seed, rho=rho, owner="claim", arena=None, **ARMS[arm])
    w = Polis(EventLog(), cfg)
    snaps = {}
    for _ in range(T):
        w.step()
        if len(w.pop) == 0:
            break
        if w.t in SNAPS:
            snaps[w.t] = _snapshot(w)
    return snaps, int(getattr(w, "_inherit_events", 0))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", default="base,nodeath,mortal")
    ap.add_argument("--seeds", default="7,8,9")
    ap.add_argument("--fires", action="store_true", help="print the MK-INHERIT-FIRES line")
    ap.add_argument("--rho", type=float, default=0.1, help="appropriation (0.1 science / 0.5 control)")
    args = ap.parse_args()
    arms = args.arms.split(",")
    seeds = [int(s) for s in args.seeds.split(",")]

    print(HDR)
    print(f"mod-K dynasty — rho={args.rho} claim, arena=none, T={T}. Metrics: canon-25 _snapshot@Polis.")
    print(HDR)
    for arm in arms:
        print(f"ARM {arm} ({ARMS[arm]}):")
        print(f"  {'seed':>4}{'t':>6}{'pop':>7}{'owner_share':>12}{'own_cells':>10}"
              f"{'own_houses':>11}{'house_gini':>11}{'top_h_share':>12}{'maxGen':>7}{'inh_ev':>8}")
        for seed in seeds:
            snaps, fires = _run(arm, seed, rho=args.rho)
            for t in SNAPS:
                if t in snaps:
                    s = snaps[t]
                    print(f"  {seed:>4}{t:>6}{s['alive']:>7}{s['owner_share']:>12.4f}"
                          f"{s['n_owned_cells']:>10}{s['distinct_owner_houses']:>11}"
                          f"{s['house_gini']:>11.3f}{s['top_house_share']:>12.3f}"
                          f"{s['max_gen']:>7}{s['inherit_events']:>8}")
            if args.fires:
                fired = fires > 0
                print(f"  -> seed {seed} MK-INHERIT-FIRES: {fires} successions "
                      f"{'✓ fires' if fired else '✗ DID NOT FIRE (seam dead)'}")
            print()
    print(HDR)


if __name__ == "__main__":
    main()
