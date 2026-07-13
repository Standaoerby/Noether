"""run_mark_gc_ident.py — MG2V-GC-IDENT: the byte-identity gate for the dead-oid
mark-ledger GC (WO_mark-ledger-gc).

The mark of a dead pawn gates nobody: pawns are mortal and oids are NEVER reused
(sim_comm._next is a monotonic counter), so a dead oid can never re-enter as a
living actor. Reclaiming dead oids from the two mark-ledgers (_extort_marks,
_delegate_marks) is therefore behaviourally inert BY CONSTRUCTION.

This harness PROVES that: for every G2 configuration it drives the world tick by
tick and folds each tick's state_fingerprint() into a rolling digest, then records
the final polis_fingerprint(). The fingerprint stream is captured with the mark-set
sizes on the side, so a before/after diff (main vs fix branch) shows:
  * the fingerprint stream + final polis fp are BIT-IDENTICAL  (the gate), while
  * the mark-set shrinks from cumulative-dead to living-barred (the GC has teeth).

If any fingerprint diverges, the GC is NOT neutral => a dead oid was influencing a
live decision => STOP AND REPORT: that is a finding graver than the leak itself.

Run:  py stage3/run_mark_gc_ident.py            # prints a self-contained digest
      py stage3/run_mark_gc_ident.py --json OUT # also writes the digest as JSON
Arena=None (the full field) is used so turnover is real and the GC actually fires;
a modest T keeps the gate fast while still burying many marked pawns.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "Code"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sim_eventlog import EventLog                       # noqa: E402
from stage3.polis import Polis, polis_fingerprint       # noqa: E402
from stage3.run_artifact_g2 import _cfgg2               # noqa: E402
from stage3.run_artifact_g2d import _cfgg2d             # noqa: E402

HDR = "=" * 78
T = 1500          # long enough that many marked pawns die (GC fires), short enough to be quick
SEED = 7


def _configs():
    """The WO's G2 surface: extort+reputation, delegate rep@0.5, full G2, chain depth 2/3,
    plus the two box6 anchor frames (default arena) that MG2V-REFACTOR/extrep pin. Every
    frame that ever writes a mark is represented, on both arenas."""
    A = None      # the full 14x14 field (real turnover -> real deaths -> the GC fires)
    return [
        ("extort_rep(field)",  _cfgg2(policy="reflex", extort=True, enforcers=3,
                                       extort_reputation=True, arena=A, seed=SEED, days=0)),
        ("delegate_rep(field)", _cfgg2d(tooth="reputation", delegate_compliance_dl=0.5,
                                        arena=A, seed=SEED, days=0)),
        ("full_g2(field)",     _cfgg2(policy="reflex", extort=True, enforcers=3,
                                      extort_reputation=True, delegate_on=True,
                                      revoke_tooth="reputation", delegate_compliance_dl=0.5,
                                      arena=A, seed=SEED, days=0)),
        ("delegate_depth2",    _cfgg2d(tooth="reputation", delegate_depth=2,
                                       arena=A, seed=SEED, days=0)),
        ("delegate_depth3",    _cfgg2d(tooth="reputation", delegate_depth=3,
                                       arena=A, seed=SEED, days=0)),
        # box6 anchor frames (default arena) — the exact configs MG2V-REFACTOR (13586f6e)
        # and MG2V-extrep pin; proven byte-identical here too.
        ("delegate_rep(box6)", _cfgg2d(tooth="reputation", delegate_compliance_dl=0.5,
                                       seed=SEED, days=0)),
        ("extort_rep(box6)",   _cfgg2(policy="reflex", extort=True, enforcers=3,
                                      extort_reputation=True, seed=SEED, days=0)),
    ]


def _drive(cfg, T):
    """Step the world T ticks, folding each tick's state_fingerprint() into a rolling
    sha256 (the same substrate hash D3 uses for cycle detection). Returns the stream
    digest, the final polis fingerprint, the final mark-set sizes, and turnover facts."""
    w = Polis(EventLog(), cfg)
    h = hashlib.sha256()
    peak_marks_e = peak_marks_d = 0
    for _ in range(T):
        w.step()
        h.update(w.state_fingerprint().encode())
        peak_marks_e = max(peak_marks_e, len(w._extort_marks))
        peak_marks_d = max(peak_marks_d, len(w._delegate_marks))
        if len(w.pop) == 0:
            break
    return {
        "fp_stream": h.hexdigest()[:32],
        "polis_fp": polis_fingerprint(w),
        "final_t": int(w.t),
        "final_pop": len(w.pop),
        "next_oid": int(getattr(w, "_next", -1)),   # total ever born (monotonic) => deaths = born - alive
        "n_extort_marks": len(w._extort_marks),
        "n_delegate_marks": len(w._delegate_marks),
        "peak_extort_marks": peak_marks_e,
        "peak_delegate_marks": peak_marks_d,
        "drift": float(w.matter_drift()),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", type=str, default=None, help="write the digest to this path")
    args = ap.parse_args()

    print(HDR)
    print(f"MG2V-GC-IDENT digest — T={T}, seed={SEED}. fp_stream folds every tick's "
          f"state_fingerprint;")
    print("polis_fp is the final substrate+voice hash. Diff this against the pre-fix run: the")
    print("fingerprints MUST be bit-identical (neutrality); the mark-sets may shrink (the GC).")
    print(HDR)
    out = {}
    ok_drift = True
    for name, cfg in _configs():
        r = _drive(cfg, T)
        out[name] = r
        ok_drift = ok_drift and r["drift"] < 1e-9
        print(f"  {name:>20}: fp={r['fp_stream']} polis={r['polis_fp']} "
              f"pop={r['final_pop']:>3} born={r['next_oid']:>4} "
              f"marks(e/d)={r['n_extort_marks']}/{r['n_delegate_marks']} "
              f"peak(e/d)={r['peak_extort_marks']}/{r['peak_delegate_marks']} drift={r['drift']:.1e}")
    print(f"\n  mass invariant holds every config (<1e-9): {'✓' if ok_drift else '✗ STOP'}")
    assert ok_drift, "MG2V-GC-IDENT: a config leaked mass"
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2, sort_keys=True)
        print(f"  digest -> {args.json}")
    print(HDR)


if __name__ == "__main__":
    main()
