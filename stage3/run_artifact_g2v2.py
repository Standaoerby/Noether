"""
run_artifact_g2v2.py — mod G2 виток 2 (Фаза 1): framing the trophy — the compliance sweep.

Vitok-1 (Фаза 2, #46) found the michelsian hole opens through REPUTATION: the mark-ledger
reaped ~92% of the god-physics flow without the substrate cheat. But that stood on ONE knob
— a hardcoded compliance threshold (deception_lean <= 0.5). This vitok turns the observation
into a robust (or honestly conditional) thesis by sweeping the threshold and reading the
ACTUAL compliant fraction it induces against the reaped flow.

The threshold `delegate_compliance_dl` is now a parameter (default 0.5, read only when
delegate_on and tooth="reputation" — OFF worlds untouched). The compliant FRACTION (not the
threshold) is the social parameter: at 0.5 roughly half the delegates remit.

GATES:
  MG2V-REFACTOR  reputation @ defaults (box6, dl=0.5) reproduces the pre-refactor fingerprint
                 13586f6e bit-for-bit — the parameterisation shifted no behaviour.
  MG2V-OFF       all SEVEN святыни stand with the new parameter present (the four tower/mod-G
                 anchors + the two extort anchors + the delegate-auto anchor).
  MG2V-mass      every swept threshold keeps the four-term invariant (<1e-9).
  MG2V-replay    every swept threshold replays bit-for-bit (deterministic, no key).

PRE-REGISTERED (both outcome-formulations fixed BEFORE the run):
  HG2V-1  the compliance sweep, dl ∈ {0.3, 0.5, 0.7, 0.9}, frame of #46 (arena none, m=0.7,
          root auto). Print threshold -> ACTUAL compliant fraction -> A_flow -> owner_gap ->
          A_flow / god-ceiling (the auto flow measured in THIS session).
          (a) A_flow ~monotone in the compliant fraction, collapsing several-fold at 0.3 =>
              trophy CONDITIONAL: "reputational deterrence works in proportion to the
              compliant base" (still strong — the base is a social parameter).
          (b) A_flow holds >= ~50% of the god-ceiling even at a compliant MINORITY (0.3) =>
              trophy UNCONDITIONAL: reputational deterrence needs no majority.
          Watch 0.9 (near-saturation) => should approach the god-ceiling; if not, the
          mechanic has a hole to find.
"""
from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "Code"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from collections import defaultdict

from sim_eventlog import EventLog
from stage3.intent import MockReflexMind
from stage3.run_artifact_f import _cfg, _run
from stage3.run_artifact_f2 import _run_with_history
from stage3.run_artifact_f3 import MFV3_OFF_ANCHOR_STORECAP, MFV3_OFF_ANCHOR_VESSEL
from stage3.run_artifact_g import _cfgg, MG_UTILITY_ANCHOR, MG_LIVE_REPLAY_ANCHOR
from stage3.run_artifact_g2 import _cfgg2, MG2_REFLEX_ANCHOR, MG2_LIVE_REPLAY_ANCHOR
from stage3.run_artifact_g2d import _cfgg2d, MG2D_AUTO_ANCHOR

HDR = "=" * 78
THRESHOLDS = (0.3, 0.5, 0.7, 0.9)

# pre-refactor mini-anchor: reputation @ defaults (box6, dl=0.5) — captured before the literal
# 0.5 became a parameter; dl=0.5 must reproduce it exactly (gate MG2V-REFACTOR).
MG2V_REPUTATION_ANCHOR = "13586f6e803c61f6"


def _delegate_pool(w, t_hist):
    """The delegate population = historical owners minus the root and its guards (the class
    that could remit). Honest base for the compliant-fraction denominator."""
    root = w._delegate_root
    return sorted(o for o in t_hist
                  if o != root and o not in w._delegate_enforcer_ids)


def _compliant_fraction(w, pool, dl_thresh):
    if not pool:
        return float("nan")
    comp = sum(1 for o in pool if w.pawn(o).personality.deception_lean <= dl_thresh)
    return comp / len(pool)


# --------------------------------------------------------------------------- #
#  Gates                                                                       #
# --------------------------------------------------------------------------- #
def _gate_mg2v_refactor():
    w = _run(_cfgg2d(tooth="reputation", days=300), 300)       # box6 defaults, dl=0.5
    fp = w.state_fingerprint()
    ok = fp == MG2V_REPUTATION_ANCHOR
    print(f"MG2V-REFACTOR reputation @defaults dl=0.5 unchanged -> {'✓' if ok else '✗'}")
    print(f"          {fp} == {MG2V_REPUTATION_ANCHOR}")
    assert ok


def _gate_mg2v_off():
    checks = [
        ("store+cap", _cfgg(policy="off", days=300), 300, MFV3_OFF_ANCHOR_STORECAP),
        ("vessel", _cfg(artifacts=True, days=250), 250, MFV3_OFF_ANCHOR_VESSEL),
        ("utility", _cfgg(policy="utility", days=300), 300, MG_UTILITY_ANCHOR),
        ("live-rep", _cfgg(policy="live", days=300, intent_mind=MockReflexMind()), 300,
         MG_LIVE_REPLAY_ANCHOR),
        ("extort-refl", _cfgg2(policy="reflex", extort=True, days=300), 300, MG2_REFLEX_ANCHOR),
        ("extort-live", _cfgg2(policy="live", extort=True, days=300,
                               intent_mind=MockReflexMind()), 300, MG2_LIVE_REPLAY_ANCHOR),
        ("delegate-auto", _cfgg2d(tooth="auto", days=300), 300, MG2D_AUTO_ANCHOR),
    ]
    all_ok = True
    print("MG2V-OFF  the seven святыни stand with the new parameter present:")
    for name, cfg, days, anchor in checks:
        fp = _run(cfg, days).state_fingerprint()
        ok = fp == anchor
        all_ok = all_ok and ok
        print(f"          {name:>14}: {fp} == {anchor} -> {'✓' if ok else '✗'}")
    assert all_ok


def _gate_mg2v_mass():
    drifts = {}
    for dl in THRESHOLDS:
        w = _run(_cfgg2d(tooth="reputation", delegate_compliance_dl=dl, arena=None, days=300), 300)
        drifts[dl] = w.matter_drift()
    ok = all(d < 1e-9 for d in drifts.values())
    print(f"MG2V-mass invariant holds every threshold -> {'✓' if ok else '✗'}")
    print(f"          " + " · ".join(f"dl{dl} {drifts[dl]:.1e}" for dl in THRESHOLDS))
    assert ok


def _gate_mg2v_replay():
    ok = True
    fps = {}
    for dl in THRESHOLDS:
        a = _run(_cfgg2d(tooth="reputation", delegate_compliance_dl=dl, arena=None, days=300), 300)
        b = _run(_cfgg2d(tooth="reputation", delegate_compliance_dl=dl, arena=None, days=300), 300)
        fa, fb = a.state_fingerprint(), b.state_fingerprint()
        fps[dl] = fa
        ok = ok and (fa == fb)
    print(f"MG2V-replay every threshold replays bit-exact -> {'✓' if ok else '✗'}")
    for dl in THRESHOLDS:
        print(f"          dl{dl}: {fps[dl]}")
    assert ok


# --------------------------------------------------------------------------- #
#  Experiment (гипотезу правит прогон; both formulations fixed above)          #
# --------------------------------------------------------------------------- #
def _hg2v_1(seeds=(7, 8, 9), days=300):
    print(f"\n{HDR}\nHG2V-1 — the compliance sweep (arena none, m=0.7, root auto). The compliant\n"
          f"FRACTION (not the threshold) is the social parameter; god-ceiling = the auto flow\n"
          f"measured in THIS session. (means over seeds {seeds})\n{HDR}")
    god = {}
    for s in seeds:
        wa, _ia, _t = _run_with_history(_cfgg2d(tooth="auto", arena=None, seed=s, days=days), days)
        god[s] = wa._delegate_flow
    print(f"  god-ceiling (auto A_flow) mean over seeds: {sum(god.values())/len(god):.2f}")
    print(f"  {'dl':>5}{'compliant%':>12}{'A_flow':>9}{'owner_gap':>10}{'A/god':>8}")
    for dl in THRESHOLDS:
        agg = defaultdict(float); n = 0
        for s in seeds:
            w, integral, t_hist = _run_with_history(
                _cfgg2d(tooth="reputation", delegate_compliance_dl=dl,
                        arena=None, seed=s, days=days), days)
            assert w.matter_drift() < 1e-9, f"HG2V-1 leaked (dl{dl} s{s})"
            pool = _delegate_pool(w, t_hist)
            frac = _compliant_fraction(w, pool, dl)
            flow = w._delegate_flow
            a_int = integral.get(w._delegate_root, 0.0)
            gap = (flow / a_int) if a_int > 0 else float("nan")
            ratio = (flow / god[s]) if god[s] > 0 else float("nan")
            agg["frac"] += (frac if frac == frac else 0.0); agg["fracn"] += (1 if frac == frac else 0)
            agg["flow"] += flow
            agg["gap"] += (gap if gap == gap else 0.0); agg["gapn"] += (1 if gap == gap else 0)
            agg["ratio"] += (ratio if ratio == ratio else 0.0)
            n += 1
        fracm = (agg["frac"] / agg["fracn"]) if agg["fracn"] else float("nan")
        gapm = (agg["gap"] / agg["gapn"]) if agg["gapn"] else float("nan")
        print(f"  {dl:>5.1f}{fracm*100:>11.1f}%{agg['flow']/n:>9.2f}{gapm:>10.2f}"
              f"{agg['ratio']/n:>8.2f}")
    print("\n  read: (a) if A/god collapses several-fold at dl=0.3 => trophy CONDITIONAL on the")
    print("  compliant base; (b) if A/god holds >=~0.5 even at a compliant minority => trophy")
    print("  UNCONDITIONAL. dl=0.9 (near-saturation) should approach the god-ceiling (A/god→1).")


# --------------------------------------------------------------------------- #
def main():
    print(HDR)
    print("mod G2 виток 2 — Фаза 1: framing the trophy. Sweep the compliance threshold and")
    print("read the reaped flow against the ACTUAL compliant fraction it induces.")
    print(HDR)
    _gate_mg2v_refactor()
    _gate_mg2v_off()
    _gate_mg2v_mass()
    _gate_mg2v_replay()
    if "--hg1" in sys.argv or "--all" in sys.argv:
        _hg2v_1()
    print(f"\n{HDR}\nmod G2 vitok 2 Фаза 1 gates green: the parameterisation is behaviour-neutral")
    print("(MG2V-REFACTOR), the seven anchors stand (MG2V-OFF), the invariant holds and every")
    print("threshold replays (MG2V-mass/replay). The trophy meets its knob.")
    print(HDR)


if __name__ == "__main__":
    main()
