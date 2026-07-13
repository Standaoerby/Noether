"""
run_glass_v3.py — V3-* gates for viz β-3 (WO_viz-beta3.md): the power-without-ownership
layers (extort / delegate-remit / marks / guard / deny) and event aggregation.

Same discipline as run_glass_v: the exporter is a pure READER, so the gates prove it does
not perturb the world (even with G2 on), that the aggregated stream is layer-equivalent to
the raw one, and that the film's numbers equal the runner's science (the viz never lies).

  V3-FP    export fp == clean-run fp on TWO configs — the canonical showcase AND the full
           G2 stack (intent reflex + extort + delegate reputation). Pure reader with G2 on.
  V3-OLD   the schema validator passes on BOTH an old-style package (no G2 fields) and a
           full G2 package — the renderer's contract is backward-compatible (missing layers
           default to empty; the default view is unchanged).
  V3-AGG   the agg package is LAYER-EQUIVALENT to raw: per-tick per-type sums and loci
           recomputed from the raw events match the agg rows exactly (data, not bytes).
  V3-NUM   the film does not lie to the science: Σ remit dm == runner A_flow (_delegate_flow),
           Σ extort dm == Σseized (_extorted_total), final marks == |mark-set|.

Run:  py stage3\run_glass_v3.py
"""
from __future__ import annotations

import sys, os, json, hashlib, tempfile, shutil

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "Code"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sim_eventlog import EventLog, Event
from stage3.polis import Polis
from stage3 import viz_export as vx
from stage3.run_glass_v import _gate_v_schema, _load_pkg

HDR = "=" * 78
_DAYS = 140
_SEED = 7
# S7 anchor: sha256 of the DEFAULT events.jsonl (canonical showcase, seed 7, days 140). The
# opt-in annotation must never move this byte — the "β-3 reproduced byte-for-byte" gate.
_EVENTS_ANCHOR = "2735d66961152a056fa89206bd74a2a0c59115c0b5f16b16560ae429cc12e323"


def _full_g2_cfg(days=_DAYS, seed=_SEED, arena_side=6, events=None):
    """The full power-without-ownership stack for the gates: intent live-reflex so EXTORT is
    confirmed, extort ON with a guard corps, delegate ON with the reputation tooth."""
    return vx.build_showcase_cfg(
        seed=seed, days=days, arena_side=arena_side, intent_policy="reflex",
        extort_on=True, extort_enforcers=3,
        delegate_on=True, revoke_tooth="reputation")


def _clean_fp(cfg):
    w = Polis(EventLog(), cfg)
    for _ in range(cfg.days):
        w.step()
    return w.state_fingerprint()


def _export_tmp(cfg=None, seed=_SEED, days=_DAYS, events_mode="raw"):
    d = tempfile.mkdtemp(prefix="glass_v3_")
    res = vx.export(d, seed=seed, days=days, every=1, verbose=False, cfg=cfg,
                    events_mode=events_mode)
    meta, snaps, events = _load_pkg(d)
    shutil.rmtree(d, ignore_errors=True)
    return res, meta, snaps, events


# --------------------------------------------------------------------------- #
def _gate_v3_fp():
    canon = vx.build_showcase_cfg(seed=_SEED, days=_DAYS)
    full = _full_g2_cfg()
    ok = True
    for name, cfg in (("canonical", canon), ("full-G2", full)):
        res, _m, _s, _e = _export_tmp(cfg=cfg)
        fp_exp = res["world"].state_fingerprint()
        fp_clean = _clean_fp(cfg)
        good = fp_exp == fp_clean
        ok = ok and good
        print(f"V3-FP     [{name:>9}] export {fp_exp} == clean {fp_clean} -> {'✓' if good else '✗'}")
    assert ok


def _gate_v3_old():
    # full G2 package: schema must validate WITH the new layers present.
    _r, meta_g, snaps_g, events_g = _export_tmp(cfg=_full_g2_cfg())
    _gate_v_schema(meta_g, snaps_g, events_g)                 # asserts inside
    # old-style package: strip every G2 field from meta + snapshots — the renderer contract
    # (and the validator) must still hold (missing layers default to empty).
    meta_old = {k: v for k, v in meta_g.items()
                if k not in ("events_mode", "delegate_root", "guard_ids")}
    snaps_old = [{k: v for k, v in s.items() if k not in ("marks", "guard", "deny")}
                 for s in snaps_g]
    _gate_v_schema(meta_old, snaps_old, events_g)            # asserts inside
    print(f"V3-OLD    schema valid WITH and WITHOUT G2 fields (backward-compatible) -> ✓")


def _gate_v3_agg():
    cfg = _full_g2_cfg()
    _rr, _mr, _sr, events_raw = _export_tmp(cfg=cfg, events_mode="raw")
    _ra, _ma, _sa, agg_rows = _export_tmp(cfg=cfg, events_mode="agg")
    # recompute the agg from the raw events using the exporter's own aggregator, then compare
    # to the shipped agg rows (layer data, not file bytes).
    class _E:  # minimal shim so _aggregate_events can read the raw rows back
        __slots__ = ("t", "kind", "where", "dm")

        def __init__(self, r):
            self.t = r["t"]; self.kind = r["type"]
            self.where = None if r["where"] is None else (r["where"][0], r["where"][1])
            self.dm = r["dm"]
    recomputed = vx._aggregate_events([_E(r) for r in events_raw])
    ok = (recomputed == agg_rows)
    print(f"V3-AGG    agg rows == raw re-aggregated (layer-equivalent) -> {'✓' if ok else '✗'} "
          f"({len(agg_rows)} ticks)")
    if not ok:
        # find first divergence for the report
        for i, (x, y) in enumerate(zip(recomputed, agg_rows)):
            if x != y:
                print(f"            first diff at row {i}: t={y.get('t')}")
                break
    assert ok


def _gate_v3_num():
    cfg = _full_g2_cfg()
    res, meta, snaps, events = _export_tmp(cfg=cfg)
    w = res["world"]
    remit_sum = sum(e["dm"] for e in events if e["type"] == "delegate_remit" and e["dm"])
    extort_sum = sum(e["dm"] for e in events if e["type"] == "extort" and e["dm"])
    last_marks = snaps[-1].get("marks", [])
    tol = 1e-4                                               # events.jsonl dm rounded to 6dp
    ok_remit = abs(remit_sum - w._delegate_flow) < tol
    ok_extort = abs(extort_sum - w._extorted_total) < tol
    ok_marks = len(last_marks) == len(w._delegate_marks)
    ok = ok_remit and ok_extort and ok_marks
    print(f"V3-NUM    the film matches the science -> {'✓' if ok else '✗'}")
    print(f"          Σremit {remit_sum:.4f} == A_flow {w._delegate_flow:.4f} ({ok_remit})")
    print(f"          Σextort {extort_sum:.4f} == Σseized {w._extorted_total:.4f} ({ok_extort})")
    print(f"          marks(frame) {len(last_marks)} == mark-set {len(w._delegate_marks)} ({ok_marks})")
    assert ok


def _gate_v3_s7():
    """S7 (WO_consolidation-sprint): opt-in event annotation. The default export is
    byte-for-byte the β-3 film (anchor); --annotate is a STRICT superset (adds exactly
    seq / derived / detector_version, changes no existing field); --sort is a pure
    permutation ordered by (t, causal_order, seq); `derived` truthfully tracks deme/world
    scale (per sim_eventlog's vocabulary), not a vacuous constant."""
    cfg = vx.build_showcase_cfg(seed=_SEED, days=_DAYS)

    def _events(**kw):
        d = tempfile.mkdtemp(prefix="glass_v3s7_")
        vx.export(d, seed=_SEED, days=_DAYS, every=1, verbose=False, cfg=cfg, **kw)
        blob = open(os.path.join(d, "events.jsonl"), "rb").read()
        rows = [json.loads(x) for x in blob.decode("utf-8").splitlines()]
        shutil.rmtree(d, ignore_errors=True)
        return blob, rows

    base_b, base = _events()
    ann_b, ann = _events(annotate=True)
    _srt_b, srt = _events(annotate=True, sort_events=True)
    extra = {"seq", "derived", "detector_version"}

    sha = hashlib.sha256(base_b).hexdigest()
    ok_anchor = sha == _EVENTS_ANCHOR
    ok_superset = all(set(r) == set(base[i]) | extra for i, r in enumerate(ann))
    ok_strip = all({k: v for k, v in r.items() if k not in extra} == base[i]
                   for i, r in enumerate(ann))
    ok_seq = all(r["seq"] == i for i, r in enumerate(ann))
    ok_ver = all(r["detector_version"] == vx.DETECTOR_VERSION for r in ann)
    ok_perm = sorted(map(vx._dumps, srt)) == sorted(map(vx._dumps, ann))
    ok_ord = all((srt[i]["t"], int(srt[i]["derived"]), srt[i]["seq"])
                 <= (srt[i + 1]["t"], int(srt[i + 1]["derived"]), srt[i + 1]["seq"])
                 for i in range(len(srt) - 1))
    # `derived` is real: synthetic events of each scale flag correctly.
    dd = {sc: vx._event_row(Event(5, "x", sc), seq=0, annotate=True)["derived"]
          for sc in ("individual", "deme", "world")}
    ok_derived = dd == {"individual": False, "deme": True, "world": True}

    ok = all([ok_anchor, ok_superset, ok_strip, ok_seq, ok_ver, ok_perm, ok_ord, ok_derived])
    print(f"V3-S7     opt-in annotation safe -> {'✓' if ok else '✗'}")
    print(f"          default events.jsonl == β-3 anchor {sha[:16]} ({ok_anchor})")
    print(f"          --annotate strict superset (+seq/derived/detector_version) ({ok_superset and ok_strip})")
    print(f"          seq==write-order ({ok_seq}) · detector_version={vx.DETECTOR_VERSION} ({ok_ver})")
    print(f"          --sort pure permutation, (t,causal,seq)-ordered ({ok_perm and ok_ord})")
    print(f"          derived tracks scale {dd} ({ok_derived})")
    assert ok


def main():
    print(HDR)
    print("viz β-3 V3-gates — the power-without-ownership layers; the reader stays pure and")
    print("the film never lies to the science.")
    print(HDR)
    _gate_v3_fp()
    _gate_v3_old()
    _gate_v3_agg()
    _gate_v3_num()
    _gate_v3_s7()
    print(f"\n{HDR}\nviz β-3 V3-gates green: pure reader with G2 on (V3-FP), backward-compatible")
    print("schema (V3-OLD), agg layer-equivalent to raw (V3-AGG), film == science (V3-NUM),")
    print("opt-in event annotation byte-safe (V3-S7).")
    print(HDR)


if __name__ == "__main__":
    main()
