"""
run_glass_v.py — V-* gates for «Стеклянный полис» (WO_glass-polis.md §6).

Same style as run_artifact_f2: deterministic, no network, every gate prints a line and
asserts. The viz layer is a READER, so the gates prove (a) it does not perturb the world,
(b) it replays byte-for-byte, and (c) the data package is internally consistent and honest
about what it renders.

  V-OFF        the export run's state_fingerprint == a clean run of the same config with no
               export — the exporter is a pure reader (no hook, no mutation).
  V-replay     two exports with the same args -> byte-identical package (SHA-256 printed;
               anchor candidate).
  V-invariant  every snapshot has |metrics.invariant − M0| < 1e-9 (the conserved substrate
               survives, quantised to 6 digits — the sim guarantees drift ≪ 1e-6).
  V-complete   the set of event types in events.jsonl == rendered ∪ ignored from meta, and
               rendered ∩ ignored == ∅ (every emitted type classified exactly once).
  V-schema     structural validator (stdlib only): field types, coordinate bounds, kind ∈
               {vessel,store,capital}, monotone t.
  regression   the п.0.2 anchor battery bit-for-bit (vessel / OFF≡canon ×2 / MFv2 / Dunbar).

Run:  py stage3\run_glass_v.py            (from repo root or stage3/)
"""
from __future__ import annotations

import sys, os, json, tempfile, shutil, hashlib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "Code"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sim_eventlog import EventLog
from stage3.polis import Polis, PolisConfig
from stage3 import viz_export as vx

HDR = "=" * 78

# п.0.2 regression anchors — cite verbatim (measured; any drift = stop, revert, dissect).
ANCHORS = [
    ("vessel replay (store/capital OFF) @250", "48d9729d3cba98e2",
     dict(appropriation=0.5, owner_policy="claim", arena_side=6, t_awaken=10 ** 9,
          demerzel_directive=None, seed=7, days=250, dunbar_K=None, artifacts=True), 250),
    ("OFF ≡ canon rho0 founders @250", "aa43ddad2ffded8e",
     dict(appropriation=0.0, owner_policy="founders", arena_side=6, t_awaken=10 ** 9,
          demerzel_directive=None, seed=7, days=250, dunbar_K=None, artifacts=False), 250),
    ("OFF ≡ canon rho.5 claim @250", "961290bbe9eeaa54",
     dict(appropriation=0.5, owner_policy="claim", arena_side=6, t_awaken=10 ** 9,
          demerzel_directive=None, seed=7, days=250, dunbar_K=None, artifacts=False), 250),
    ("MFv2 store+capital ON @300", "41bb81b486d77c7e",
     dict(appropriation=0.5, owner_policy="claim", arena_side=6, t_awaken=10 ** 9,
          demerzel_directive=None, seed=7, days=300, dunbar_K=None, artifacts=True,
          store_on=True, capital_on=True, capital_rate=0.02), 300),
    ("Dunbar ME-replay dunbar_K=15 @250", "ca28db691bdb2600",
     dict(appropriation=0.0, owner_policy="founders", arena_side=6, t_awaken=10 ** 9,
          demerzel_directive=None, seed=7, days=250, dunbar_K=15), 250),
]

# a small, fast frame for the reader gates (the film is proven separately by the full
# export; here we only need enough ticks that every channel fires).
_V_DAYS = 140
_V_SEED = 7


def _clean_fp(cfg):
    w = Polis(EventLog(), cfg)
    for _ in range(cfg.days):
        w.step()
    return w.state_fingerprint()


def _load_pkg(out_dir):
    meta = json.load(open(os.path.join(out_dir, "meta.json"), encoding="utf-8"))
    snaps = [json.loads(l) for l in open(os.path.join(out_dir, "snapshots.jsonl"),
                                         encoding="utf-8") if l.strip()]
    events = [json.loads(l) for l in open(os.path.join(out_dir, "events.jsonl"),
                                          encoding="utf-8") if l.strip()]
    return meta, snaps, events


# --------------------------------------------------------------------------- #
#  Gates                                                                       #
# --------------------------------------------------------------------------- #
def _gate_v_off():
    # the exporter runs the world and reads it; the resulting fingerprint must equal a
    # clean run of the identical config that never saw the exporter.
    cfg = vx.build_showcase_cfg(seed=_V_SEED, days=_V_DAYS)
    tmp = tempfile.mkdtemp(prefix="glass_off_")
    try:
        res = vx.export(tmp, seed=_V_SEED, days=_V_DAYS, every=1, verbose=False)
        fp_export = res["world"].state_fingerprint()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    fp_clean = _clean_fp(vx.build_showcase_cfg(seed=_V_SEED, days=_V_DAYS))
    ok = fp_export == fp_clean
    print(f"V-OFF      export ≡ clean run (pure reader) -> {'✓' if ok else '✗'}")
    print(f"            {fp_export} == {fp_clean}")
    assert ok


def _gate_v_replay():
    a = tempfile.mkdtemp(prefix="glass_a_")
    b = tempfile.mkdtemp(prefix="glass_b_")
    try:
        ra = vx.export(a, seed=_V_SEED, days=_V_DAYS, every=1, verbose=False)
        rb = vx.export(b, seed=_V_SEED, days=_V_DAYS, every=1, verbose=False)
    finally:
        shutil.rmtree(a, ignore_errors=True)
        shutil.rmtree(b, ignore_errors=True)
    ok = (ra["package_sha"] == rb["package_sha"] and ra["shas"] == rb["shas"])
    print(f"V-replay   two exports byte-identical -> {'✓' if ok else '✗'}")
    print(f"            package SHA {ra['package_sha']}")
    assert ok


def _gate_v_invariant(meta, snaps):
    M0 = meta["M0"]
    worst = 0.0
    for s in snaps:
        d = abs(s["metrics"]["invariant"] - M0)
        worst = max(worst, d)
    ok = worst < 1e-9 and len(snaps) > 0
    print(f"V-invariant |Σ − M0| < 1e-9 in all {len(snaps)} snapshots -> {'✓' if ok else '✗'} "
          f"(worst {worst:.1e})")
    assert ok


def _gate_v_complete(meta, events):
    rendered = set(meta["event_types_rendered"])
    ignored = set(meta["event_types_ignored"])
    seen = {e["type"] for e in events}
    disjoint = not (rendered & ignored)
    covers = seen == (rendered | ignored)
    ok = disjoint and covers
    print(f"V-complete events == rendered ∪ ignored, disjoint -> {'✓' if ok else '✗'} "
          f"(types {len(seen)}, rendered {len(rendered)}, ignored {len(ignored)})")
    if not ok:
        print(f"            missing {seen - (rendered | ignored)} | extra "
              f"{(rendered | ignored) - seen} | overlap {rendered & ignored}")
    assert ok


def _gate_v_schema(meta, snaps, events):
    """Structural validator — stdlib only, no jsonschema dependency."""
    R, C = meta["grid_rows"], meta["grid_cols"]
    KINDS = {"vessel", "store", "capital"}
    PHASES = {"INFANT", "MATURE", "ELDER"}
    errs = []

    def inb(i, j):
        return 0 <= i < R and 0 <= j < C

    last_t = -1
    for s in snaps:
        t = s["t"]
        if not isinstance(t, int) or t <= last_t:      # strictly monotone t
            errs.append(f"t not monotone at {t}")
        last_t = t
        for p in s["pawns"]:
            oid, i, j, body, house, phase = p
            if not (isinstance(oid, int) and inb(i, j) and isinstance(body, (int, float))
                    and isinstance(house, int) and phase in PHASES):
                errs.append(f"bad pawn {p} @t{t}"); break
        for ar in s["arts"]:
            aid, kind, i, j, mass, sal, maker = ar
            if not (isinstance(aid, int) and kind in KINDS and inb(i, j)
                    and mass >= 0.0 and sal >= 0.0):
                errs.append(f"bad art {ar} @t{t}"); break
        for (i, j, oid) in s["owners"]:
            if not inb(i, j):
                errs.append(f"owner OOB {(i, j)} @t{t}"); break
        for e in s["known"]:
            if not (len(e) == 3 and isinstance(e[0], int) and isinstance(e[1], int)):
                errs.append(f"bad known {e} @t{t}"); break
        m = s["metrics"]
        if not (m["pop"] >= 0 and 0.0 <= m["gini_body"] <= 1.0):
            errs.append(f"bad metrics @t{t}")
        if "soil" in s and len(s["soil"]) != R * C:
            errs.append(f"soil len {len(s['soil'])} != {R*C} @t{t}")
        if "plant" in s and len(s["plant"]) != R * C:
            errs.append(f"plant len {len(s['plant'])} != {R*C} @t{t}")
        if "god" in s and not inb(s["god"]["i"], s["god"]["j"]):
            errs.append(f"god OOB @t{t}")

    for e in events:
        if not (isinstance(e["t"], int) and isinstance(e["type"], str)):
            errs.append(f"bad event {e}"); break
        if e["where"] is not None and not inb(e["where"][0], e["where"][1]):
            errs.append(f"event where OOB {e['where']}"); break

    ok = not errs
    print(f"V-schema   structure/bounds/kinds/monotone-t -> {'✓' if ok else '✗'}"
          + ("" if ok else f"  ({len(errs)} errs, first: {errs[0]})"))
    assert ok


def _gate_regression():
    print(f"\n--- п.0.2 regression anchors (bit-for-bit) ---")
    all_ok = True
    for (label, anchor, kw, days) in ANCHORS:
        fp = _clean_fp(PolisConfig(**kw))
        ok = fp == anchor
        all_ok &= ok
        print(f"  {label:<40} {fp} == {anchor} -> {'✓' if ok else '✗'}")
    assert all_ok, "regression anchor drift — STOP, revert, dissect (WO §0.2)"


def main():
    print(HDR)
    print("Glass-Polis V-gates — the viz layer is a pure reader; one log -> one film.")
    print(HDR)
    # one export for the content gates (V-invariant/complete/schema read the same package)
    tmp = tempfile.mkdtemp(prefix="glass_v_")
    try:
        vx.export(tmp, seed=_V_SEED, days=_V_DAYS, every=1, verbose=False)
        meta, snaps, events = _load_pkg(tmp)
    finally:
        _keep = tmp  # keep until after reads
    try:
        _gate_v_off()
        _gate_v_replay()
        _gate_v_invariant(meta, snaps)
        _gate_v_complete(meta, events)
        _gate_v_schema(meta, snaps, events)
        _gate_regression()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # the shipped package SHA (the film Stan actually views), printed as the anchor.
    print(f"\n{HDR}\nshipping package (seed 7, 400 days, every 1):")
    out = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                        "..", "viz", "glass", "data"))
    res = vx.export(out, seed=7, days=400, every=1, verbose=True)
    print(f"{HDR}\nGlass-Polis V-gates green: pure reader (V-OFF), byte-identical replay")
    print("(V-replay), invariant survives (V-invariant), event manifest complete")
    print(f"(V-complete), schema valid (V-schema), п.0.2 anchors stand (regression).\n{HDR}")


if __name__ == "__main__":
    main()
