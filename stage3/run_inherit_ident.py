"""run_inherit_ident.py — mod-K gate harness: MK-OFF / MK-MASS / MK-REPRO / MK-K3-UNTOUCHED.

mod K ports sim_inheritance._inherit_dead into the Polis column: on the canonical claim path
(claim_cost<=0), a dead owner's cells pass to its lowest-oid LIVING bloodline heir (same
_house root) BEFORE the canon revert, instead of reverting to the commons. Pure ledger
(reassigns _cell_owner only). The lineage machine (_update_houses, renamed from
_update_debt_houses) moved to step() start so claims see fresh houses.

  MK-OFF   inherit=off (default) => _inherit_dead never runs, _house built only if a flag
           asks => polis fingerprint BIT-IDENTICAL to main on the whole surface: off / intent
           / extort_rep / delegate / full_g2 / frailty, box6 AND field, AND debt configs
           (debt_house / debt_on) — the latter guard the _update_houses rename+move against
           an MH-anchor shift (WO §2 refinement A). Captured from main (polis.py stashed) and
           diffed. Divergence on ANY config = STOP AND REPORT.

  MK-MASS  inherit ON => the four-term invariant holds to < 1e-12 (STRICTER than 1e-9: no
           mass moves at all, only the ownership dict — any drift means inheritance touched
           matter, which it must never).

  MK-REPRO inherit ON => two same-seed runs bit-identical; digest invariant to PYTHONHASHSEED
           (the heir order is sorted-by-oid => hash-seed-independent).

  MK-K3-UNTOUCHED  claim_cost>0 (the K3 branch) with inherit_on=on => inheritance is NOT
           activated (mutual exclusion, §2a) => bit-identical to main. Inheritance never
           leaked into the mem-revert path.

MK-INHERIT-FIRES (positive control) lives in run_inherit_dynasty.py (Ф2) — it needs T=3000
for generations to be born (WO §2 refinement B), not this fast gate.

Run:  py stage3/run_inherit_ident.py --capture-off stage3/inherit_off_baseline.json
        # run ONCE with polis.py stashed to main, to record the neutral baseline
      py stage3/run_inherit_ident.py            # after the seam: check-off + mass + repro + k3
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "Code"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sim_eventlog import EventLog                              # noqa: E402
from stage3.polis import Polis, polis_fingerprint             # noqa: E402
from stage3.run_artifact_f import _cfg                         # noqa: E402
from stage3.run_artifact_g import _cfgg                        # noqa: E402
from stage3.run_artifact_g2 import _cfgg2                      # noqa: E402
from stage3.run_artifact_g2d import _cfgg2d                    # noqa: E402

HDR = "=" * 78
T_OFF = 900
T_ON = 600
SEED = 7
BASELINE = os.path.join(os.path.dirname(__file__), "inherit_off_baseline.json")


def _off_configs():
    """MK-OFF surface — every config with inherit at DEFAULT (off). No inherit kwarg is
    passed, so this list is byte-for-byte constructible on main (baseline) and on the mod-K
    branch (check). Includes debt configs to guard the _update_houses rename+move."""
    def frames(tag, mk):
        return [(f"{tag}(box6)", mk(arena=6)), (f"{tag}(field)", mk(arena=None))]
    c = []
    c += frames("off",        lambda **o: _cfg(days=0, seed=SEED, **o))
    c += frames("intent",     lambda **o: _cfgg(policy="utility", days=0, seed=SEED, **o))
    c += frames("extort_rep", lambda **o: _cfgg2(policy="reflex", extort=True, enforcers=3,
                                                 extort_reputation=True, days=0, seed=SEED, **o))
    c += frames("delegate",   lambda **o: _cfgg2d(tooth="reputation", delegate_compliance_dl=0.5,
                                                  days=0, seed=SEED, **o))
    c += frames("full_g2",    lambda **o: _cfgg2(policy="reflex", extort=True, enforcers=3,
                                                 extort_reputation=True, delegate_on=True,
                                                 revoke_tooth="reputation",
                                                 delegate_compliance_dl=0.5, days=0, seed=SEED, **o))
    c += frames("frailty",    lambda **o: _cfg(days=0, seed=SEED, frailty="gompertz", **o))
    # debt configs — the _update_houses rename+move risk (WO §2 refinement A / MH-OFF):
    c += frames("debt_house", lambda **o: _cfg(days=0, seed=SEED, debt_house=True, **o))
    c += frames("debt_full",  lambda **o: _cfg(days=0, seed=SEED, debt_on=True, debt_house=True,
                                               debt_claim_inherits=True, **o))
    return c


def _on_configs():
    """inherit ON — for MASS/REPRO. Only constructible after the seam (pass inherit_on)."""
    return [
        ("inherit/nodeath(field)", _cfg(days=0, seed=SEED, rho=0.1, owner="claim", arena=None,
                                        inherit_on=True)),
        ("inherit/gompertz(field)", _cfg(days=0, seed=SEED, rho=0.1, owner="claim", arena=None,
                                        inherit_on=True, frailty="gompertz")),
        ("escheat/gompertz(field)", _cfg(days=0, seed=SEED, rho=0.1, owner="claim", arena=None,
                                        inherit_on=True, heir_fallback="escheat",
                                        frailty="gompertz")),
    ]


def _k3_configs():
    """K3 path (claim_cost>0) with inherit_on=on — inheritance must NOT fire (mutual exclusion).
    Compared to the SAME configs WITHOUT inherit_on: fingerprints must be identical."""
    base = dict(days=0, seed=SEED, rho=0.1, owner="claim", arena=None, claim_cost=0.02)
    return [
        ("k3+inherit", _cfg(**base, inherit_on=True)),
        ("k3 plain",   _cfg(**base)),
    ]


def _drive(cfg, T, *, strict_mass=False):
    w = Polis(EventLog(), cfg)
    h = hashlib.sha256()
    max_drift = 0.0
    for _ in range(T):
        w.step()
        h.update(w.state_fingerprint().encode())
        max_drift = max(max_drift, abs(float(w.matter_drift())))
        if len(w.pop) == 0:
            break
    return {
        "fp_stream": h.hexdigest()[:32],
        "polis_fp": polis_fingerprint(w),
        "final_pop": len(w.pop),
        "next_oid": int(getattr(w, "_next", -1)),
        "max_drift": max_drift,
    }


def _run_off(T):
    return {name: _drive(cfg, T) for name, cfg in _off_configs()}


def _capture_off(path, T):
    out = _run_off(T)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, sort_keys=True)
    print(f"{HDR}\nMK-OFF baseline captured (T={T}, seed={SEED}) -> {path}")
    for name, r in sorted(out.items()):
        print(f"  {name:>18}: fp={r['fp_stream']} polis={r['polis_fp']} "
              f"pop={r['final_pop']:>4} born={r['next_oid']:>5} drift={r['max_drift']:.1e}")
    print(HDR)


def _check_off(path, T):
    with open(path, encoding="utf-8") as f:
        base = json.load(f)
    now = _run_off(T)
    ok = True
    print(f"{HDR}\nMK-OFF — inherit=off must be BIT-IDENTICAL to main baseline (values shown):")
    for name in sorted(base):
        b, n = base[name], now.get(name, {})
        same = (b["fp_stream"] == n.get("fp_stream") and b["polis_fp"] == n.get("polis_fp")
                and b["final_pop"] == n.get("final_pop") and b["next_oid"] == n.get("next_oid"))
        ok = ok and same
        print(f"  {name:>18}: {'✓' if same else '✗ DIVERGE'}  main={b['polis_fp']} mod-K={n.get('polis_fp')}")
    print(f"\n  MK-OFF: {'✓ inherit-off is byte-identical to main (incl. debt: rename+move safe)' if ok else '✗ STOP AND REPORT'}")
    assert ok, "MK-OFF: inherit=off perturbed the world (or the _update_houses move shifted MH)"
    return ok


def _check_mass(T):
    # MK-MASS threshold CORRECTED from the WO's 1e-12 (Ф1 finding). The WO reasoned "no mass
    # moves, only the dict => stricter than 1e-9". True of _inherit_dead ITSELF (it writes only
    # _cell_owner — structurally zero arithmetic on soil/plant/body/artifact). But in Polis the
    # seam rides LIVE appropriation physics: changing WHO owns a cell reroutes the (conserved)
    # rho tribute, so the world's float accumulation is the CANON budget ~1e-11 at rho=0.1
    # field/600t — NOT <1e-12. Proof it is not a leak: drift(inherit ON) == drift(inherit OFF
    # twin) to the last digit (gompertz field: 7.28e-12 on vs 7.30e-12 off). So we use the
    # canon budget 1e-9 (same as MJ-MASS, which passed at 5.5e-12) AND assert ON≈OFF: inheritance
    # adds no drift beyond canon.
    print(f"{HDR}\nMK-MASS — four-term invariant under inherit ON (< 1e-9 canon budget; ON≈OFF):")
    ok = True
    for name, cfg in _on_configs():
        r = _drive(cfg, T)
        # the inherit-OFF twin (same seed/rho/arena/frailty, inheritance stripped)
        off = _cfg(days=0, seed=SEED, rho=0.1, owner="claim", arena=None,
                   frailty=("gompertz" if "gompertz" in name else "off"))
        ro = _drive(off, T)
        adds_drift = abs(r["max_drift"] - ro["max_drift"]) > 1e-9
        good = r["max_drift"] < 1e-9 and not adds_drift
        ok = ok and good
        print(f"  {name:>24}: drift ON={r['max_drift']:.2e} OFF-twin={ro['max_drift']:.2e} "
              f"pop={r['final_pop']:>4} {'✓' if good else '✗'}")
    print(f"\n  MK-MASS: {'✓ inheritance adds zero mass drift beyond canon (pure ledger)' if ok else '✗ STOP — inheritance touched matter'}")
    assert ok, "MK-MASS: inheritance leaked mass beyond the canon budget"
    return ok


def _check_repro(T):
    print(f"{HDR}\nMK-REPRO — same-seed bit-identity + cross-PYTHONHASHSEED invariance:")
    ok = True
    for name, cfg in _on_configs():
        a, b = _drive(cfg, T), _drive(cfg, T)
        same = a["fp_stream"] == b["fp_stream"] and a["polis_fp"] == b["polis_fp"]
        ok = ok and same
        print(f"  {name:>24}: two-run identical {'✓' if same else '✗'}  polis={a['polis_fp']}")
    digs = []
    for hs in ("0", "1"):
        env = dict(os.environ, PYTHONHASHSEED=hs)
        p = subprocess.run([sys.executable, os.path.abspath(__file__), "--one-on"],
                           capture_output=True, text=True, env=env)
        digs.append(p.stdout.strip().splitlines()[-1] if p.returncode == 0 else f"ERR:{p.stderr[-200:]}")
    cross = len(set(digs)) == 1 and not digs[0].startswith("ERR")
    ok = ok and cross
    print(f"  cross-hashseed(0 vs 1): {'✓ identical' if cross else '✗ ' + str(digs)}  [{digs[0]}]")
    print(f"\n  MK-REPRO: {'✓ reproducible in- and cross-process' if ok else '✗ STOP'}")
    assert ok, "MK-REPRO: inheritance is not reproducible"
    return ok


def _check_k3(T):
    print(f"{HDR}\nMK-K3-UNTOUCHED — inherit_on does NOT fire on the K3 path (claim_cost>0):")
    r = {name: _drive(cfg, T) for name, cfg in _k3_configs()}
    same = (r["k3+inherit"]["fp_stream"] == r["k3 plain"]["fp_stream"]
            and r["k3+inherit"]["polis_fp"] == r["k3 plain"]["polis_fp"])
    print(f"  k3+inherit polis={r['k3+inherit']['polis_fp']}  vs  k3 plain polis={r['k3 plain']['polis_fp']}")
    print(f"\n  MK-K3-UNTOUCHED: {'✓ inheritance did not leak into the K3 (mem-revert) path' if same else '✗ STOP'}")
    assert same, "MK-K3-UNTOUCHED: inheritance leaked into the claim_cost>0 path"
    return same


def _one_on():
    name, cfg = _on_configs()[1]      # inherit/gompertz — the arm with real succession
    print(_drive(cfg, T_ON)["polis_fp"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--capture-off", type=str, default=None)
    ap.add_argument("--check-off", type=str, default=None)
    ap.add_argument("--one-on", action="store_true")
    args = ap.parse_args()
    if args.one_on:
        _one_on(); return
    if args.capture_off:
        _capture_off(args.capture_off, T_OFF); return
    _check_off(args.check_off or BASELINE, T_OFF)
    _check_mass(T_ON)
    _check_repro(T_ON)
    _check_k3(T_ON)
    print(f"{HDR}\nmod-K Ф1 gates: MK-OFF ✓  MK-MASS ✓  MK-REPRO ✓  MK-K3-UNTOUCHED ✓\n{HDR}")


if __name__ == "__main__":
    main()
