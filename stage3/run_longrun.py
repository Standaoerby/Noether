"""run_longrun.py — long-horizon degeneracy audit harness (WO_longrun-audit).

READ-ONLY over canon: it imports each world and drives its OWN `for _ in range(T):
w.step()` loop (the horizon is a free knob everywhere — no world self-terminates,
Q1 of Phase 0). Nothing in Code/sim_*.py is touched; arena and horizon are frame
parameters, never code defaults. Every anchor stays sacred.

For each world (arena none = full 14x14 field, its characteristic mechanic ON) it
runs to T=3000 or an early termination, evaluating detectors D1-D9 each tick and
streaming per-tick metrics to a jsonl. Termination:
  (a) extinction   len(pop) == 0
  (b) eternal cycle a state_fingerprint repeats (deterministic substrate => proof)
  (c) stationarity  the metric vector is unchanged for W ticks (frozen world)

Mass note (Q2 of Phase 0): a dead body returns to soil (sim_comm.py:293); soil
regrows plant, so extinction conserves M0 and is a demographic end, not a mass sink.

Usage:
  py stage3\run_longrun.py --tower --seed 7 --T 3000        # Phase 1: the 8 worlds
  py stage3\run_longrun.py --polis --seed 7 --T 3000        # Phase 2: the 5 configs
  py stage3\run_longrun.py --world appropriation --T 3000
  py stage3\run_longrun.py --budget                         # Phase 0.3/0.4 drift+time
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "Code"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402

HDR = "=" * 78
W_STATIONARY = 300          # Stan-approved stationarity window (§Решения 2)
FP_EVERY = 1                # fingerprint every tick — cheap and exact for cycle proof
OUT_DIR = Path(os.path.dirname(os.path.abspath(__file__))) / "longrun_out"


# --------------------------------------------------------------------------- #
#  World factory — each world at arena=None, its characteristic mechanic ON.   #
#  We call the module's own run_*(days=0) so the canonical headline config is  #
#  reproduced exactly, then drive the loop ourselves.                          #
# --------------------------------------------------------------------------- #
def _make(name):
    from sim_eventlog import EventLog
    if name == "comm":
        from sim_comm import CommWorld
        return CommWorld(EventLog(), seed=7, regime="none"), "regime=none (canonical forage)"
    if name == "appropriation":
        import sim_appropriation as m
        w, _ = m.run_appropriation(appropriation=m.RHO, owner_policy="claim",
                                   arena_side=None, seed=7, days=0)
        return w, f"rho={m.RHO} claim owners"
    if name == "institution":
        import sim_institution as m
        w, _ = m.run_institution(sigma=m.SIGMA, enforce=True, owner_policy="claim",
                                 appropriation=m.RHO, arena_side=None, seed=7, days=0)
        return w, f"enforce=True sigma={m.SIGMA} rho={m.RHO}"
    if name == "inheritance":
        import sim_inheritance as m
        w, _ = m.run_inheritance(heritable=True, owner_policy="claim",
                                 appropriation=m.RHO, arena_side=None, seed=7, days=0)
        return w, f"heritable=True rho={m.RHO}"
    if name == "exclusion":
        import sim_exclusion as m
        w, _ = m.run_exclusion(exclusion=True, owner_policy="claim",
                               appropriation=m.RHO, arena_side=None, seed=7, days=0)
        return w, f"exclusion=True rho={m.RHO}"
    if name == "trade":
        import sim_trade as m
        w, _ = m.run_trade(trade=True, owner_policy="claim",
                           appropriation=m.RHO, arena_side=None, seed=7, days=0)
        return w, f"trade=True rho={m.RHO}"
    if name == "synthesis":
        import sim_synthesis as m
        w, _ = m.run_synthesis(heritable=True, exclusion=True, trade=True,
                               owner_policy="claim", appropriation=m.RHO,
                               arena_side=None, seed=7, days=0)
        return w, f"herit+excl+trade rho={m.RHO}"
    if name == "legitimacy":
        import sim_legitimacy_probe as m
        w, _ = m.run_probe(formula=True, enforce=True, owner_policy="claim",
                           appropriation=m.RHO, arena_side=None, seed=7, days=0)
        return w, f"formula=True enforce=True rho={m.RHO} (ВСТАВКА-29 myth)"
    raise ValueError(f"unknown world {name!r}")


TOWER = ["comm", "appropriation", "institution", "inheritance",
         "exclusion", "trade", "synthesis", "legitimacy"]


def _make_polis(cfg_name, seed=7):
    """Phase 2 — the stage3 column. Reuses the vitok-2 config builders."""
    from stage3.run_artifact_f import _run  # noqa: F401  (import proves availability)
    from stage3.run_artifact_g import _cfgg
    from stage3.run_artifact_g2 import _cfgg2
    from stage3.run_artifact_g2d import _cfgg2d
    from stage3.intent import MockReflexMind
    if cfg_name == "off":
        return _cfgg(policy="off", arena=None, seed=seed, days=0), "pure polis (all seams off)"
    if cfg_name == "utility":
        return _cfgg(policy="utility", theta=0.5, arena=None, seed=seed, days=0), "intent utility@0.5"
    if cfg_name == "extort_rep":
        return _cfgg2(policy="reflex", extort=True, enforcers=3, extort_reputation=True,
                      arena=None, seed=seed, days=0), "extort+reputation (3 guards)"
    if cfg_name == "delegate_rep":
        return _cfgg2d(tooth="reputation", delegate_compliance_dl=0.5, arena=None,
                       seed=seed, days=0), "delegate reputation@0.5"
    if cfg_name == "full_g2":
        # extort + delegate + reputation together: _cfgg2 carries extort, delegate_* ride
        # through **over into PolisConfig (_cfgg2d hardcodes extort_on=False, so not it).
        return _cfgg2(policy="reflex", extort=True, enforcers=3, extort_reputation=True,
                      delegate_on=True, revoke_tooth="reputation", delegate_compliance_dl=0.5,
                      arena=None, seed=seed, days=0), "full G2 (extort+delegate+rep)"
    raise ValueError(f"unknown polis cfg {cfg_name!r}")


POLIS_CFGS = ["off", "utility", "extort_rep", "delegate_rep", "full_g2"]

# mod J×K audit arms (WO_longrun-audit-JK §2). Same _cfg builder as run_inherit_dynasty /
# run_frailty_dynasty, so LR-JK-ANCHOR reproduces the Ф3 table exactly (deterministic).
JK_ARMS = {
    "P00": dict(frailty="off",      inherit_on=False),   # base ≡ canon fork
    "PJ":  dict(frailty="gompertz", inherit_on=False),   # only J (senescence)
    "PK":  dict(frailty="off",      inherit_on=True),     # only K (inheritance)
    "PJK": dict(frailty="gompertz", inherit_on=True),     # J+K — the apex hypothesis lives here
}
JK_CFGS = ["P00", "PJ", "PK", "PJK"]
THETA_HOUSE = 0.5      # D5 land-apex threshold (WO §7.2: start 0.5; must NOT auto-fire PK/PJK,
                       # whose science top_house_share ≈ 0.11-0.22 < 0.5 — detector is meaningful)


def _make_polis_jk(arm, seed=7, rho=0.1):
    """The 2×2 J×K arm at the science config (rho claim, arena none). Mirrors
    run_inherit_dynasty._run EXACTLY so LR-JK-ANCHOR is an exact reproduction."""
    from stage3.run_artifact_f import _cfg
    cfg = _cfg(days=0, seed=seed, rho=rho, owner="claim", arena=None, **JK_ARMS[arm])
    a = JK_ARMS[arm]
    return cfg, f"{arm} frailty={a['frailty']} inherit={a['inherit_on']} rho={rho}"


# --------------------------------------------------------------------------- #
#  Metric extraction — the per-tick vector the detectors read.                 #
# --------------------------------------------------------------------------- #
def _gini(vals):
    v = sorted(x for x in vals if x == x and x >= 0)
    n = len(v)
    if n == 0:
        return float("nan")
    s = sum(v)
    if s <= 0:
        return 0.0
    cum = 0.0
    for i, x in enumerate(v):
        cum += (i + 1) * x
    return (2 * cum) / (n * s) - (n + 1) / n


def _reservoirs(w):
    soil = float(np.asarray(w.soil).sum()) if hasattr(w, "soil") else float("nan")
    plant = float(np.asarray(w.plant).sum()) if hasattr(w, "plant") else float("nan")
    body = float(sum(a.body for a in w.pop))
    art = float(w._artifacts.sum_mass()) if hasattr(w, "_artifacts") and w._artifacts else 0.0
    return soil, plant, body, art


def _owner_share(w):
    # None (not NaN) when the world has no ownership mechanic at all (e.g. canonical
    # comm) — so D9 does not mistake a legitimately-absent metric for a "metric lie".
    if not hasattr(w, "owner_ids"):
        return None, 0
    owners = set(w.owner_ids())
    ob = sum(a.body for a in w.pop if a.oid in owners)
    tot = sum(a.body for a in w.pop)
    share = (ob / tot) if tot > 0 else float("nan")
    return share, len(owners)


def _house_metrics(w):
    """mod K land axis (WO §3 D5). top_house_share = max(per_house)/sum(per_house) over
    w._cell_owner grouped by house(oid) — the run_inherit_dynasty._snapshot formula verbatim.
    Also n_owning_houses and the top house root (for the D5 freeze check) and max_gen over the
    top-5 territory owners (Ф3 metric). Returns (share, n_houses, top_root, max_gen).
    None-share when the world has no ownership/lineage at all (D9-safe)."""
    co = getattr(w, "_cell_owner", None)
    if co is None or not hasattr(w, "house"):
        return None, 0, None, 0
    if not co:
        return float("nan"), 0, None, 0
    per_house = {}
    for oid in co.values():
        h = w.house(oid)
        per_house[h] = per_house.get(h, 0) + 1
    tot = sum(per_house.values())
    top_root, top_cells = max(per_house.items(), key=lambda kv: (kv[1], -kv[0]))
    # max generation depth among the top-5 territory owners (Ф3 _snapshot)
    counts = w.territory_counts() if hasattr(w, "territory_counts") else {}
    top5 = [o for o, _ in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:5]]
    gen = getattr(w, "gen", {})
    max_gen = max((gen.get(o, 0) for o in top5), default=0)
    return top_cells / tot, len(per_house), top_root, max_gen


def _ledger_sizes(w):
    """D6 — monotone mechanic leaks. Sizes of any barred/marked/claim ledgers present, plus
    the mod J/K side-tables (WO §3): _house (lineage, PRE-REGISTERED as a dead-oid leak
    analog of _extort_marks — cumulative from birth log, never pruned), _blocks (frailty
    side-table, culled on death — check it prunes on BOTH death paths), _inherit_events
    (a monotone COUNTER, not memory — classify as counter, low priority)."""
    out = {}
    for attr in ("_extort_marks", "_delegate_marks", "_delegate_defections"):
        v = getattr(w, attr, None)
        if v is not None:
            out[attr] = len(v) if hasattr(v, "__len__") else int(v)
    h = getattr(w, "_house", None)
    if h is not None:
        out["_house"] = len(h)
    fr = getattr(w, "_frailty", None)
    if fr is not None and getattr(fr, "_blocks", None) is not None:
        out["_blocks"] = len(fr._blocks)
    ie = getattr(w, "_inherit_events", None)
    if ie is not None:
        out["_inherit_events"] = int(ie)
    return out


def _metrics(w):
    soil, plant, body, art = _reservoirs(w)
    share, n_owners = _owner_share(w)
    ths, n_houses, top_house, max_gen = _house_metrics(w)
    pop = len(w.pop)
    bodies = [a.body for a in w.pop]
    m = {
        "t": int(getattr(w, "t", -1)),
        "pop": pop,
        "drift": float(w.matter_drift()),
        "soil": soil, "plant": plant, "body": body, "art": art,
        "gini_body": _gini(bodies),
        "owner_share": share, "n_owners": n_owners,
        "min_body": min(bodies) if bodies else float("nan"),
        # mod K land axis (WO §3 D5)
        "top_house_share": ths, "n_owning_houses": n_houses,
        "top_house": (int(top_house) if top_house is not None else None), "max_gen": max_gen,
    }
    m.update({f"led_{k}": v for k, v in _ledger_sizes(w).items()})
    return m


# --------------------------------------------------------------------------- #
#  Detectors D1-D9 (code, not eye). Each returns a list of (tick, note) hits.  #
# --------------------------------------------------------------------------- #
def _round_vec(m):
    """The stationarity key: the metric vector rounded, so float noise below the
    quantum doesn't hide a frozen world (D4)."""
    keys = ("pop", "n_owners")
    fkeys = ("soil", "plant", "body", "art", "gini_body", "owner_share")

    def q(v):
        if v is None:
            return "none"
        return round(v, 6) if v == v else "nan"
    return (tuple(m[k] for k in keys), tuple(q(m[k]) for k in fkeys))


def audit(name, label, world, T, drift_budget, out_path, is_polis=False):
    hits = {f"D{i}": [] for i in range(1, 10)}
    seen_fp = {}
    stat_key = None
    stat_since = 0
    owner_set, owner_since, owner_flagged = frozenset(), 0, False
    top_house, top_house_since, top_house_flagged = None, 0, False    # mod K land-apex (D5)
    m0 = float(world.matter_drift())
    ledger_prev = {}
    termination = f"reached T={T}"
    peak_drift = 0.0
    f = out_path.open("w", encoding="utf-8")
    try:
        for step in range(1, T + 1):
            world.step()
            m = _metrics(world)
            f.write(json.dumps(m) + "\n")
            if step % 500 == 0:
                f.flush()

            # D1 invariants: drift budget, NaN/inf, negatives
            d = m["drift"]
            peak_drift = max(peak_drift, d)
            if d > drift_budget:
                hits["D1"].append((step, f"drift {d:.2e} > budget {drift_budget:.0e}"))
            for k in ("soil", "plant", "body", "art"):
                v = m[k]
                if v != v or math.isinf(v):
                    hits["D1"].append((step, f"{k} is {v}"))
                elif v < -1e-9:
                    hits["D1"].append((step, f"{k} negative: {v:.3e}"))
            if m["min_body"] == m["min_body"] and m["min_body"] < -1e-9:
                hits["D1"].append((step, f"min body negative {m['min_body']:.3e}"))

            # D2 extinction
            if m["pop"] == 0:
                soil, plant = m["soil"], m["plant"]
                hits["D2"].append((step, f"pop==0; mass in soil={soil:.2f} plant={plant:.2f}"))
                termination = f"extinction @ t={step}"
                break

            # D3 eternal cycle — repeated fingerprint on a deterministic substrate
            if step % FP_EVERY == 0:
                fp = world.state_fingerprint()
                if fp in seen_fp:
                    hits["D3"].append((step, f"fingerprint {fp} repeats t={seen_fp[fp]} (cycle len {step - seen_fp[fp]})"))
                    termination = f"cycle @ t={step} (period {step - seen_fp[fp]})"
                    break
                seen_fp[fp] = step

            # D4 stationarity — metric vector unchanged for W ticks
            key = _round_vec(m)
            if key == stat_key:
                if step - stat_since >= W_STATIONARY:
                    hits["D4"].append((step, f"metric vector frozen for {W_STATIONARY} ticks (since t={stat_since})"))
                    termination = f"stationary @ t={step} (frozen since {stat_since})"
                    break
            else:
                stat_key = key
                stat_since = step

            # D5 power fixation — corona-on-graveyard, monopoly, frozen owner-set
            share = m["owner_share"]
            if share is not None and share == share and share > 0.9 and m["pop"] < 5:
                hits["D5"].append((step, f"owner_share {share:.2f} with pop {m['pop']} (corona-on-graveyard)"))
            if m["n_owners"] == 1 and m["pop"] > 1:
                hits["D5"].append((step, f"single-owner monopoly, pop {m['pop']}"))
            if hasattr(world, "owner_ids"):
                oset = frozenset(world.owner_ids())
                if oset and oset == owner_set:
                    if step - owner_since >= W_STATIONARY and not owner_flagged:
                        hits["D5"].append((step, f"owner-set frozen ({len(oset)} owners) for {W_STATIONARY} ticks since t={owner_since}"))
                        owner_flagged = True
                else:
                    owner_set, owner_since, owner_flagged = oset, step, False
            # D5 mod-K land apex: a house monopolises land (top_house_share > θ) AND the top
            # house's IDENTITY is frozen ≥ W ticks ⇒ frozen dynastic apex (WO §3/L1).
            ths, th = m["top_house_share"], m["top_house"]
            if ths is not None and ths == ths and ths > THETA_HOUSE and th is not None:
                if th == top_house:
                    if step - top_house_since >= W_STATIONARY and not top_house_flagged:
                        hits["D5"].append((step, f"land apex: house {th} holds {ths:.2f} of owned "
                                                 f"land, frozen {W_STATIONARY} ticks since t={top_house_since}"))
                        top_house_flagged = True
                else:
                    top_house, top_house_since, top_house_flagged = th, step, False
            else:
                top_house, top_house_since, top_house_flagged = None, step, False

            # D6 monotone mechanic leaks — a ledger that only grows
            for k, v in m.items():
                if not k.startswith("led_"):
                    continue
                pv = ledger_prev.get(k)
                if pv is not None and v > pv:
                    ledger_prev[k] = v
                elif pv is None:
                    ledger_prev[k] = v

            # D9 metric lie on degenerate states — a NaN in a metric that SHOULD be defined
            if m["gini_body"] != m["gini_body"] and m["pop"] > 0:
                hits["D9"].append((step, f"gini_body is NaN with pop {m['pop']}"))
            if (m["owner_share"] is not None and m["owner_share"] != m["owner_share"]
                    and m["n_owners"] > 0):
                hits["D9"].append((step, f"owner_share NaN with {m['n_owners']} owners, pop {m['pop']}"))
    finally:
        f.close()

    # D6 verdict: did any ledger grow monotonically to a large fraction with no plateau?
    final = _metrics(world)
    for k, v in final.items():
        if k.startswith("led_") and isinstance(v, (int, float)) and v > 0:
            hits["D6"].append((final["t"], f"{k} ended at {v} (check monotone growth in jsonl)"))

    # collapse to fired-detectors summary
    fired = {d: h for d, h in hits.items() if h}
    return {
        "world": name, "label": label, "termination": termination,
        "final_t": final["t"], "final_pop": final["pop"],
        "peak_drift": peak_drift, "m0_drift": m0,
        "final": {k: final[k] for k in ("pop", "soil", "plant", "body", "art",
                                        "gini_body", "owner_share", "n_owners",
                                        "top_house_share", "n_owning_houses", "max_gen")
                  if k in final},
        "ledgers": {k[4:]: v for k, v in final.items() if k.startswith("led_")},
        "detectors": {d: h[:8] for d, h in fired.items()},
        "n_hits": {d: len(h) for d, h in fired.items()},
    }


# --------------------------------------------------------------------------- #
def _drift_budget(T):
    """Phase 0.3 — a per-run drift budget with headroom. Canon asserts <1e-9 at
    300; float error grows ~sqrt(T) at worst, so 1e-6 over 3000 is generous. A
    breach is itself a finding (numerical degradation) — never widened silently."""
    return 1e-6


def run_set(worlds, T, is_polis, jk=False, rho=0.1, seed=7):
    OUT_DIR.mkdir(exist_ok=True)
    budget = _drift_budget(T)
    kind = "J×K arms" if jk else ("Polis column" if is_polis else "tower")
    print(f"{HDR}\nlong-horizon audit — {kind} "
          f"| arena none | T={T} | {'rho='+str(rho)+' seed='+str(seed)+' | ' if jk else ''}"
          f"drift budget {budget:.0e} | W_stat={W_STATIONARY} | θ_house={THETA_HOUSE}\n{HDR}")
    results = []
    for name in worlds:
        t0 = time.monotonic()
        if jk:
            from stage3.polis import Polis
            from sim_eventlog import EventLog
            cfg, label = _make_polis_jk(name, seed=seed, rho=rho)
            world = Polis(EventLog(), cfg)
        elif is_polis:
            from stage3.run_artifact_f import _run  # noqa
            from stage3.polis import Polis
            from sim_eventlog import EventLog
            cfg, label = _make_polis(name)
            world = Polis(EventLog(), cfg)
        else:
            world, label = _make(name)
        tag_out = f"{name}_rho{rho}_s{seed}" if jk else name
        out = OUT_DIR / f"{tag_out}_T{T}.jsonl"
        res = audit(name, label, world, T, budget, out, is_polis or jk)
        res["secs"] = round(time.monotonic() - t0, 1)
        results.append(res)
        fired = ", ".join(f"{d}×{res['n_hits'][d]}" for d in sorted(res["detectors"])) or "clean"
        fin = res["final"]
        extra = (f" | osh={fin.get('owner_share')} ths={fin.get('top_house_share')} "
                 f"houses={fin.get('n_owning_houses')} maxGen={fin.get('max_gen')} "
                 f"inh={res['ledgers'].get('_inherit_events')}") if jk else ""
        print(f"  {name:>14} [{label[:30]:<30}] {res['termination']:<30} "
              f"pop={res['final_pop']:<4} drift≤{res['peak_drift']:.1e} {res['secs']}s | {fired}{extra}")
    tag = f"jk_rho{rho}_s{seed}" if jk else ("polis" if is_polis else "tower")
    (OUT_DIR / f"{tag}_summary_T{T}.json").write_text(
        json.dumps(results, indent=2), encoding="utf-8")
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tower", action="store_true")
    ap.add_argument("--polis", action="store_true")
    ap.add_argument("--jk", action="store_true", help="mod J×K audit arms (P00/PJ/PK/PJK)")
    ap.add_argument("--arms", type=str, default=None, help="comma list of JK arms (default all 4)")
    ap.add_argument("--rho", type=float, default=0.1, help="appropriation for --jk (0.1 / 0.5)")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--world", type=str, default=None)
    ap.add_argument("--T", type=int, default=3000)
    ap.add_argument("--budget", action="store_true", help="Phase 0.3/0.4 probe")
    args = ap.parse_args()

    if args.budget:
        _budget_probe(jk=args.jk, rho=args.rho, seed=args.seed)
        return
    if args.jk:
        arms = args.arms.split(",") if args.arms else JK_CFGS
        run_set(arms, args.T, is_polis=True, jk=True, rho=args.rho, seed=args.seed)
        return
    if args.world:
        is_p = args.world in POLIS_CFGS
        run_set([args.world], args.T, is_p)
        return
    if args.tower:
        run_set(TOWER, args.T, is_polis=False)
    if args.polis:
        run_set(POLIS_CFGS, args.T, is_polis=True)
    if not (args.tower or args.polis):
        run_set(TOWER, args.T, is_polis=False)
        run_set(POLIS_CFGS, args.T, is_polis=True)


def _budget_probe(jk=False, rho=0.1, seed=7):
    """Phase 0.3 (drift extrapolation) + 0.4 (time cost). With --jk, probes the PJK arm
    (J+K under mortality) — the heaviest, to size drift/time under senescence+inheritance."""
    if jk:
        from stage3.polis import Polis
        from sim_eventlog import EventLog
        print(f"{HDR}\nФ0 budget probe — PJK (J+K under mortality), rho={rho} seed={seed}, arena none\n{HDR}")
        for T in (300, 1000, 3000):
            cfg, _ = _make_polis_jk("PJK", seed=seed, rho=rho)
            w = Polis(EventLog(), cfg)
            t0 = time.monotonic(); peak = 0.0
            for _ in range(T):
                w.step()
                peak = max(peak, abs(float(w.matter_drift())))
                if len(w.pop) == 0:
                    break
            dt = time.monotonic() - t0
            print(f"  T={T:>4}: peak drift {peak:.2e} · {dt:.1f}s · pop {len(w.pop)} · "
                  f"inh_ev {getattr(w, '_inherit_events', 0)} · _house {len(getattr(w, '_house', {}))}")
        return
    print(f"{HDR}\nPhase 0.3/0.4 — drift + time budget probe (appropriation, arena none)\n{HDR}")
    for T in (300, 1000, 3000):
        w, _ = _make("appropriation")
        t0 = time.monotonic()
        peak = 0.0
        for _ in range(T):
            w.step()
            peak = max(peak, w.matter_drift())
            if len(w.pop) == 0:
                break
        dt = time.monotonic() - t0
        print(f"  T={T:>4}: peak drift {peak:.2e} · {dt:.1f}s · final pop {len(w.pop)} · t={w.t}")
    print("  -> extrapolate: if peak drift stays <1e-6 the LR-mass budget holds with headroom.")


if __name__ == "__main__":
    main()
