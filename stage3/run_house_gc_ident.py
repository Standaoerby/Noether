"""run_house_gc_ident.py — MK-HOUSE-GC-IDENT: the byte-identity gate for the _house dead-oid
GC (WO_polis-ledger-gc-v2, Fix A / audit finding L2a).

`_house` (the mod-25 lineage map ported into Polis) accumulates the oid of EVERY pawn ever
born and was never pruned: the longrun J+K audit measured 0 -> 40341 at T=3000, ×18 the
living population, monotone, no plateau — the direct analog of the `_extort_marks` leak
closed by `fix/mark-ledger-gc`.

`Polis._gc_houses()` prunes it to a REACHABILITY set (living ∪ current _cell_owner values),
called right after `_update_houses()` at the top of `step()`. The timing is the whole point:
house(dead) IS read (unlike a dead extort mark) — `_inherit_dead` resolves a dead owner's
bloodline heir by its house root, and because frailty culls senescence deaths AFTER
`_do_claims`, that read can land on tick T+1. Keeping every current cell-owner covers it;
folding births before pruning covers the parent-of-unfolded-birth read.

This harness PROVES the sweep is behaviourally inert: for every inherit-bearing configuration
it drives the world tick by tick, folds each tick's state_fingerprint into a rolling digest,
and records the final polis_fingerprint plus the science metrics. A before/after diff (main
vs this branch) must show:
  * fp stream + final polis fp + owner_share/top_house_share/inherit_events/pop/drift
    BIT-IDENTICAL   (the gate), while
  * `_house` collapses from ×N-the-population to ~the population   (the GC has teeth).

If ANY fingerprint or metric moves, a dead `_house` entry was gating something => the seam is
NOT neutral => STOP AND REPORT (WO §6 falsifier: "разбор тайминга").

Run:  py stage3/run_house_gc_ident.py --capture stage3/house_gc_baseline.json   # on main
      py stage3/run_house_gc_ident.py                                           # after the seam
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "Code"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sim_eventlog import EventLog                          # noqa: E402
from stage3.polis import Polis, polis_fingerprint         # noqa: E402
from stage3.run_artifact_f import _cfg                     # noqa: E402

HDR = "=" * 78
T = 800
SEED = 7
BASELINE = os.path.join(os.path.dirname(__file__), "house_gc_baseline.json")

ARMS = {
    "base":    dict(inherit_on=False, frailty="off"),        # OFF control: no _house at all
    "nodeath": dict(inherit_on=True,  frailty="off"),
    "mortal":  dict(inherit_on=True,  frailty="gompertz"),   # senescence => the T+1 estate lag
}


def _configs():
    """Every inherit-bearing frame the WO names: base/nodeath/mortal × rho{0.1,0.5} ×
    arena{field,box6}. `mortal` is the one that exercises the frailty one-tick estate lag."""
    out = []
    for arm, kw in ARMS.items():
        for rho in (0.1, 0.5):
            for arena, atag in ((None, "field"), (6, "box6")):
                out.append((f"{arm}/rho{rho}/{atag}",
                            _cfg(days=0, seed=SEED, rho=rho, owner="claim", arena=arena, **kw)))
    # a debt_house frame too: _house also exists under mod-H K2 (the GC must not disturb it)
    out.append(("debt_house/rho0.1/field",
                _cfg(days=0, seed=SEED, rho=0.1, owner="claim", arena=None,
                     debt_on=True, debt_house=True, debt_claim_inherits=True)))
    return out


def _drive(cfg, T):
    w = Polis(EventLog(), cfg)
    h = hashlib.sha256()
    max_drift = 0.0
    peak_house = 0
    for _ in range(T):
        w.step()
        h.update(w.state_fingerprint().encode())
        max_drift = max(max_drift, abs(float(w.matter_drift())))
        peak_house = max(peak_house, len(getattr(w, "_house", ()) or ()))
        if len(w.pop) == 0:
            break
    # science metrics that MUST NOT move
    co = getattr(w, "_cell_owner", {}) or {}
    per_house = {}
    for oid in co.values():
        r = w.house(oid)
        per_house[r] = per_house.get(r, 0) + 1
    tot = sum(per_house.values())
    owners = set(w.owner_ids())
    tb = sum(a.body for a in w.pop)
    return {
        "fp_stream": h.hexdigest()[:32],
        "polis_fp": polis_fingerprint(w),
        "pop": len(w.pop),
        "owner_share": round(sum(a.body for a in w.pop if a.oid in owners) / tb, 12) if tb else None,
        "top_house_share": round(max(per_house.values()) / tot, 12) if tot else None,
        "n_owning_houses": len(per_house),
        "inherit_events": int(getattr(w, "_inherit_events", 0)),
        "max_drift": max_drift,
        "house_final": len(getattr(w, "_house", ()) or ()),
        "house_peak": peak_house,
    }


def _run_all():
    return {name: _drive(cfg, T) for name, cfg in _configs()}


NEUTRAL = ("fp_stream", "polis_fp", "pop", "owner_share", "top_house_share",
           "n_owning_houses", "inherit_events")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--capture", type=str, default=None, help="record the pre-GC baseline (on main)")
    ap.add_argument("--check", type=str, default=None)
    args = ap.parse_args()

    if args.capture:
        out = _run_all()
        with open(args.capture, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2, sort_keys=True)
        print(f"{HDR}\nMK-HOUSE-GC-IDENT baseline (pre-GC), T={T} seed={SEED} -> {args.capture}")
        for n, r in sorted(out.items()):
            print(f"  {n:>26}: polis={r['polis_fp']} _house={r['house_final']:>6} "
                  f"(peak {r['house_peak']:>6}) pop={r['pop']:>4} osh={r['owner_share']}")
        print(HDR)
        return 0

    with open(args.check or BASELINE, encoding="utf-8") as f:
        base = json.load(f)
    now = _run_all()
    print(f"{HDR}\nMK-HOUSE-GC-IDENT — the _house sweep must be BIT-IDENTICAL (values shown)")
    print(f"{'config':>26} {'neutral?':>9}  {'_house before→after':>22}  polis_fp")
    ok = True
    for n in sorted(base):
        b, a = base[n], now.get(n, {})
        same = all(b.get(k) == a.get(k) for k in NEUTRAL)
        ok = ok and same
        shrink = f"{b['house_final']:>6} → {a.get('house_final'):>6}"
        print(f"  {n:>24}: {'✓' if same else '✗ DIVERGE':>9}  {shrink:>22}  "
              f"{a.get('polis_fp')} {'==' if b['polis_fp']==a.get('polis_fp') else '!='} {b['polis_fp']}")
        if not same:
            for k in NEUTRAL:
                if b.get(k) != a.get(k):
                    print(f"      {k}: before={b.get(k)} after={a.get(k)}")
    # the teeth: _house must actually shrink toward pop on the inherit arms
    teeth = [(n, base[n]["house_final"], now[n]["house_final"], now[n]["pop"])
             for n in sorted(base) if base[n]["house_final"] > 0]
    print(f"\n  GC teeth (inherit-bearing arms): _house before → after (pop)")
    for n, bh, ah, p in teeth:
        ratio_b = bh / p if p else 0
        print(f"    {n:>24}: {bh:>6} → {ah:>5}  pop={p:<5} (×{ratio_b:.1f} → ×{ah/p if p else 0:.1f})")
    print(f"\n  MK-HOUSE-GC-IDENT: {'✓ sweep is byte-identical (dead _house entries gated nothing)' if ok else '✗ STOP AND REPORT — timing analysis needed'}")
    assert ok, "MK-HOUSE-GC-IDENT: the _house GC changed the world"
    print(HDR)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
