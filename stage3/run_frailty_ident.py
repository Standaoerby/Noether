"""run_frailty_ident.py — mod-J gate harness: MJ-OFF / MJ-MASS / MJ-REPRO.

mod J adds senescence (stage3/frailty.py) as a side-table over the tower's Animal:
each pawn holds a hidden count of intact redundancy blocks; blocks fail stochastically
each tick; death at intact==0. Eating repairs `body`, NEVER blocks — the stake becomes
unredeemable and uncomputable from the body (the ВСТАВКА-27 lesson, gate MJ-NOREAD,
tested separately in run_frailty_noread.py).

This harness proves the machinery is neutral when OFF and conservative/reproducible
when ON:

  MJ-OFF   frailty="off" (the default) => the FrailtyField is inert: no side-table, no
           RNG draw, no cull, fingerprint_blob()==b"". The per-tick state_fingerprint
           stream and the final polis_fingerprint are BIT-IDENTICAL to a run with the
           frailty machinery absent (== current main). Proven by capturing a baseline
           BEFORE the seam was written (--capture-off, while polis.py == main) and
           diffing after (--check-off). Divergence on ANY config = STOP AND REPORT.

  MJ-MASS  frailty ON => the four-term invariant (soil+plant+Σbody+Σartifact.mass)
           holds every tick (drift < 1e-9): the senescence death deposits a.body into
           soil exactly like the canonical body<DEATH path — mass is moved, never made.

  MJ-REPRO frailty ON => two same-seed runs are bit-identical (fp_stream + polis_fp),
           and the digest is invariant to PYTHONHASHSEED (0 vs 1, cross-process): the
           frailty RNG is its own seeded stream, and every draw iterates a sorted order,
           so hash randomization cannot leak in.

The OFF surface is the WO's MJ-OFF list: off / intent / extort_rep / delegate / full_g2,
each on box6 (bounded arena) AND the full field (arena=None, real turnover).

Run:  py stage3/run_frailty_ident.py --capture-off stage3/frailty_off_baseline.json
        # run ONCE while polis.py == main to record the neutral baseline
      py stage3/run_frailty_ident.py            # after the seam: check-off + mass + repro
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
T_OFF = 1000      # long enough for real turnover on the field; frailty is inert here
T_ON = 600        # long enough that many pawns exhaust their blocks (senescence fires)
SEED = 7
BASELINE = os.path.join(os.path.dirname(__file__), "frailty_off_baseline.json")


def _off_configs():
    """The MJ-OFF surface — every config with frailty at its DEFAULT (off). No frailty
    kwarg is passed, so this list is byte-for-byte constructible on main (baseline) and
    on the mod-J branch (check). box6 (arena=6) and the full field (arena=None)."""
    def frames(tag, mk):
        return [(f"{tag}(box6)", mk(arena=6)), (f"{tag}(field)", mk(arena=None))]
    cfgs = []
    cfgs += frames("off",        lambda **o: _cfg(days=0, **o))
    cfgs += frames("intent",     lambda **o: _cfgg(policy="utility", days=0, **o))
    cfgs += frames("extort_rep", lambda **o: _cfgg2(policy="reflex", extort=True,
                                                    enforcers=3, extort_reputation=True,
                                                    days=0, **o))
    cfgs += frames("delegate",   lambda **o: _cfgg2d(tooth="reputation",
                                                     delegate_compliance_dl=0.5,
                                                     days=0, **o))
    cfgs += frames("full_g2",    lambda **o: _cfgg2(policy="reflex", extort=True,
                                                    enforcers=3, extort_reputation=True,
                                                    delegate_on=True,
                                                    revoke_tooth="reputation",
                                                    delegate_compliance_dl=0.5,
                                                    days=0, **o))
    return cfgs


def _on_configs():
    """Frailty ON — the same substrate frames, one per arm. Only constructible AFTER the
    seam exists (they pass frailty=). Used for MASS/REPRO, never for the OFF baseline."""
    return [
        ("gompertz(field)", _cfg(days=0, arena=None, frailty="gompertz")),
        ("gompertz(box6)",  _cfg(days=0, arena=6,    frailty="gompertz")),
        ("flat(field)",     _cfg(days=0, arena=None, frailty="flat")),
    ]


def _drive(cfg, T):
    """Step T ticks (or until extinction), folding each tick's state_fingerprint into a
    rolling sha256. Returns the stream digest, final polis fp, turnover facts, max drift,
    and (when frailty is on) the senescence death count."""
    w = Polis(EventLog(), cfg)
    h = hashlib.sha256()
    max_drift = 0.0
    for _ in range(T):
        w.step()
        h.update(w.state_fingerprint().encode())
        max_drift = max(max_drift, abs(float(w.matter_drift())))
        if len(w.pop) == 0:
            break
    sen = sum(1 for e in w.log.events
              if e.kind == "death" and (e.data or {}).get("cause") == "senescence")
    return {
        "fp_stream": h.hexdigest()[:32],
        "polis_fp": polis_fingerprint(w),
        "final_t": int(w.t),
        "final_pop": len(w.pop),
        "next_oid": int(getattr(w, "_next", -1)),
        "max_drift": max_drift,
        "senescence_deaths": sen,
    }


def _run_off(T):
    return {name: _drive(cfg, T) for name, cfg in _off_configs()}


# --------------------------------------------------------------------------- #
#  Modes                                                                       #
# --------------------------------------------------------------------------- #
def _capture_off(path, T):
    out = _run_off(T)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, sort_keys=True)
    print(f"{HDR}\nMJ-OFF baseline captured (T={T}, seed={SEED}) -> {path}")
    for name, r in sorted(out.items()):
        print(f"  {name:>18}: fp={r['fp_stream']} polis={r['polis_fp']} "
              f"pop={r['final_pop']:>3} born={r['next_oid']:>4} drift={r['max_drift']:.1e}")
    print(HDR)


def _check_off(path, T):
    with open(path, encoding="utf-8") as f:
        base = json.load(f)
    now = _run_off(T)
    ok = True
    print(f"{HDR}\nMJ-OFF check — frailty=off must be BIT-IDENTICAL to baseline {os.path.basename(path)}")
    for name in sorted(base):
        b, n = base[name], now.get(name, {})
        same = (b["fp_stream"] == n.get("fp_stream")
                and b["polis_fp"] == n.get("polis_fp")
                and b["final_pop"] == n.get("final_pop")
                and b["next_oid"] == n.get("next_oid"))
        ok = ok and same
        mark = "✓" if same else "✗ DIVERGE"
        print(f"  {name:>18}: {mark}  polis {n.get('polis_fp')} vs {b['polis_fp']}")
    print(f"\n  MJ-OFF: {'✓ frailty-off is neutral (bit-identical to main)' if ok else '✗ STOP AND REPORT'}")
    assert ok, "MJ-OFF: frailty=off perturbed the world — the machinery is NOT inert"
    return ok


def _check_mass(T):
    print(f"{HDR}\nMJ-MASS — four-term invariant under frailty ON (drift < 1e-9)")
    ok = True
    for name, cfg in _on_configs():
        r = _drive(cfg, T)
        good = r["max_drift"] < 1e-9
        ok = ok and good
        print(f"  {name:>16}: max_drift={r['max_drift']:.1e} senescence={r['senescence_deaths']:>4} "
              f"pop={r['final_pop']:>3} {'✓' if good else '✗'}")
    print(f"\n  MJ-MASS: {'✓ mass conserved every tick, every arm' if ok else '✗ STOP'}")
    assert ok, "MJ-MASS: frailty leaked mass"
    return ok


def _check_repro(T):
    print(f"{HDR}\nMJ-REPRO — same-seed bit-identity + cross-PYTHONHASHSEED invariance")
    ok = True
    for name, cfg in _on_configs():
        a = _drive(cfg, T)
        b = _drive(cfg, T)
        same = a["fp_stream"] == b["fp_stream"] and a["polis_fp"] == b["polis_fp"]
        ok = ok and same
        print(f"  {name:>16}: two-run identical {'✓' if same else '✗'}  "
              f"fp={a['fp_stream']} polis={a['polis_fp']} senescence={a['senescence_deaths']}")
    # cross-process: PYTHONHASHSEED 0 vs 1 must yield the same digest for one on-config
    digs = []
    for hs in ("0", "1"):
        env = dict(os.environ, PYTHONHASHSEED=hs)
        p = subprocess.run([sys.executable, os.path.abspath(__file__), "--one-on"],
                           capture_output=True, text=True, env=env)
        digs.append(p.stdout.strip().splitlines()[-1] if p.returncode == 0 else f"ERR:{p.stderr[-200:]}")
    cross = len(set(digs)) == 1 and not digs[0].startswith("ERR")
    ok = ok and cross
    print(f"  cross-hashseed(0 vs 1): {'✓ identical' if cross else '✗ ' + str(digs)}  [{digs[0]}]")
    print(f"\n  MJ-REPRO: {'✓ reproducible in- and cross-process' if ok else '✗ STOP'}")
    assert ok, "MJ-REPRO: frailty is not reproducible"
    return ok


def _one_on():
    """Print a single deterministic digest line (for the cross-hashseed subprocess check)."""
    name, cfg = _on_configs()[0]
    print(_drive(cfg, T_ON)["polis_fp"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--capture-off", type=str, default=None,
                    help="record the neutral baseline (run while polis.py == main)")
    ap.add_argument("--check-off", type=str, default=None,
                    help="assert frailty=off is bit-identical to this baseline")
    ap.add_argument("--one-on", action="store_true", help="internal: print one on-config digest")
    args = ap.parse_args()

    if args.one_on:
        _one_on(); return
    if args.capture_off:
        _capture_off(args.capture_off, T_OFF); return
    # default post-implementation mode: the full gate battery
    _check_off(args.check_off or BASELINE, T_OFF)
    _check_mass(T_ON)
    _check_repro(T_ON)
    print(f"{HDR}\nmod-J Ф1 gates: MJ-OFF ✓  MJ-MASS ✓  MJ-REPRO ✓\n{HDR}")


if __name__ == "__main__":
    main()
