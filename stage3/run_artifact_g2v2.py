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
  MG2V-apex      (Фаза 2) the body-poor apex (delegate_root_select="nonowner") is genuinely
                 outside the owner caste while "auto" is the lowest owner; the nonowner world
                 keeps the invariant and replays under both reputation and auto teeth. The new
                 field defaults to "auto", so MG2V-REFACTOR/OFF already prove OFF-neutrality.
  MG2V-chain     (Фаза 3) delegate_depth=d builds exactly d-1 non-owner intermediaries between
                 base and root; the chained world keeps the invariant and replays at depth 2
                 and 3 under both teeth. delegate_depth defaults to 1 (the chain path is never
                 entered), so every anchor stands.

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
  HG2V-2  the body-poor apex — hold the #46/#47 frame (arena none, m=0.7, tooth reputation)
          and vary ONLY the apex: auto root (lowest owner, owner_gap≈0.32) vs nonowner root
          (lowest speaker outside owners+guards). Print A_flow, the root's own body integral,
          owner_gap and A/god on ONE time base.
          (a) nonowner owner_gap > 1 => power decoupled from stock (kinetic власть-метаресурс);
          (b) nonowner owner_gap <= 1 (NULL) => the apex accumulates in proportion to flow,
              power stays body-bound on this conservative substrate.
  HG2V-3  the chain depth — same frame, deepen A←B←C (delegate_depth ∈ {1,2,3}). Print the
          root's A_flow (and A/depth1), the intermediary strata's body integral and gross
          throughput.
          (a) A_flow holds within a modest factor at depth 2/3 => the chain extends control
              (охват wins);
          (b) A_flow decays ≈ m per level while a middle strata captures the skim => NULL for
              the root (затухание m^depth wins — the natural limit of hierarchy).
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


def _gate_mg2v_apex():
    """Фаза 2 — the body-poor apex. delegate_root_select defaults to 'auto', so every prior
    anchor is untouched (that neutrality is MG2V-REFACTOR/OFF, which run with the default). Here
    we prove the NEW branch: (1) structural — the 'nonowner' apex is genuinely outside the owner
    caste while the 'auto' apex is the lowest owner; (2) the nonowner world keeps the four-term
    invariant and replays bit-for-bit under both the michelsian (reputation) and the ceiling
    (auto) teeth."""
    wa = _run(_cfgg2d(tooth="reputation", arena=None, days=0), 0)                    # auto apex
    wn = _run(_cfgg2d(tooth="reputation", delegate_root_select="nonowner",
                      arena=None, days=0), 0)                                        # body-poor
    spk = sorted(wa.speaker); owners = set(spk[:wa._n_owners])
    auto_root, np_root = wa._delegate_root, wn._delegate_root
    structural = (auto_root in owners) and (np_root is not None) and (np_root not in owners)
    mass_ok, replay_ok = True, True
    for tooth in ("reputation", "auto"):
        a = _run(_cfgg2d(tooth=tooth, delegate_root_select="nonowner", arena=None, days=300), 300)
        b = _run(_cfgg2d(tooth=tooth, delegate_root_select="nonowner", arena=None, days=300), 300)
        mass_ok = mass_ok and a.matter_drift() < 1e-9
        replay_ok = replay_ok and a.state_fingerprint() == b.state_fingerprint()
    ok = structural and mass_ok and replay_ok
    print(f"MG2V-apex body-poor apex is a non-owner; mass+replay hold -> {'✓' if ok else '✗'}")
    print(f"          auto root {auto_root} owner={auto_root in owners} · "
          f"nonowner root {np_root} owner={np_root in owners} (want False)")
    print(f"          nonowner mass<1e-9: {mass_ok} · replay bit-exact: {replay_ok}")
    assert ok


def _gate_mg2v_chain():
    """Фаза 3 — the remittance chain. delegate_depth defaults to 1, so every anchor is untouched
    (MG2V-REFACTOR/OFF run at depth 1 and the chain path is never entered). Here we prove the
    NEW branch: (1) structural — depth d builds exactly d-1 intermediary nodes, all non-owners,
    disjoint from the root; (2) the chained world keeps the four-term invariant and replays
    bit-for-bit at depth 2 and 3 under both reputation and auto teeth."""
    w2 = _run(_cfgg2d(tooth="reputation", delegate_depth=2, arena=None, days=0), 0)
    w3 = _run(_cfgg2d(tooth="reputation", delegate_depth=3, arena=None, days=0), 0)
    spk = sorted(w2.speaker); owners = set(spk[:w2._n_owners])
    ch2, ch3 = w2._delegate_chain_ids, w3._delegate_chain_ids
    structural = (len(ch2) == 1 and len(ch3) == 2
                  and all(o not in owners and o != w2._delegate_root for o in ch2)
                  and all(o not in owners and o != w3._delegate_root for o in ch3))
    mass_ok, replay_ok = True, True
    for depth in (2, 3):
        for tooth in ("reputation", "auto"):
            a = _run(_cfgg2d(tooth=tooth, delegate_depth=depth, arena=None, days=300), 300)
            b = _run(_cfgg2d(tooth=tooth, delegate_depth=depth, arena=None, days=300), 300)
            mass_ok = mass_ok and a.matter_drift() < 1e-9
            replay_ok = replay_ok and a.state_fingerprint() == b.state_fingerprint()
    ok = structural and mass_ok and replay_ok
    print(f"MG2V-chain depth d builds d-1 non-owner intermediaries; mass+replay hold "
          f"-> {'✓' if ok else '✗'}")
    print(f"          depth2 chain {ch2} · depth3 chain {ch3} (root {w2._delegate_root}, "
          f"none are owners: {structural})")
    print(f"          depth2/3 mass<1e-9: {mass_ok} · replay bit-exact: {replay_ok}")
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


def _hg2v_2(seeds=(7, 8, 9), days=300):
    """Фаза 2 — the body-poor apex. Hold the #46/#47 frame (arena none, m=0.7, tooth
    reputation — the michelsian trophy) and vary ONLY who the apex is: the AUTO root (lowest
    owner — carries its own tribute as a reserve, owner_gap≈0.32) vs the NONOWNER root (lowest
    speaker outside owners+guards — reaps flow it never collected, holds no reserve). Same
    seeds, same time base, so the two owner_gap numbers are directly comparable.

    PRE-REGISTERED (both formulations fixed BEFORE the run):
      (a) nonowner owner_gap > 1  => power is DECOUPLED from any stock: the apex reaps more
          flow than its own body ever integrates — pure kinetic power, the direct
          operationalisation of "власть = метаресурс, не запас" (смычка с законом оборота).
      (b) nonowner owner_gap <= 1 (NULL) => even a body-poor apex builds a reserve in
          proportion to the flow it reaps (the remittance lands in its body and integrates
          faster than it is spent) — on this conservative substrate power does NOT decouple
          from body, and the michelsian flow still presupposes an accumulating apex.
      Control: the AUTO root printed on the same rows (expect owner_gap≈0.32)."""
    print(f"\n{HDR}\nHG2V-2 — the body-poor apex (arena none, m=0.7, tooth reputation). owner_gap\n"
          f"= A_flow / the root's OWN lifetime body integral; >1 => flow decoupled from any\n"
          f"reserve. god-ceiling = the auto-tooth flow, same time base. (means over seeds {seeds})\n{HDR}")
    god = {}
    for s in seeds:
        wg, _i, _t = _run_with_history(_cfgg2d(tooth="auto", arena=None, seed=s, days=days), days)
        god[s] = wg._delegate_flow
    print(f"  god-ceiling (auto A_flow) mean over seeds: {sum(god.values())/len(god):.2f}")
    print(f"  {'apex':>10}{'A_flow':>9}{'A_bodyInt':>11}{'owner_gap':>10}{'A/god':>8}")
    for sel in ("auto", "nonowner"):
        agg = defaultdict(float); n = 0
        for s in seeds:
            w, integral, _t = _run_with_history(
                _cfgg2d(tooth="reputation", delegate_root_select=sel,
                        arena=None, seed=s, days=days), days)
            assert w.matter_drift() < 1e-9, f"HG2V-2 leaked ({sel} s{s})"
            flow = w._delegate_flow; root = w._delegate_root
            a_int = integral.get(root, 0.0)
            gap = (flow / a_int) if a_int > 0 else float("nan")
            ratio = (flow / god[s]) if god[s] > 0 else float("nan")
            agg["flow"] += flow; agg["aint"] += a_int
            agg["gap"] += (gap if gap == gap else 0.0); agg["gapn"] += (1 if gap == gap else 0)
            agg["ratio"] += (ratio if ratio == ratio else 0.0); n += 1
        gapm = (agg["gap"] / agg["gapn"]) if agg["gapn"] else float("nan")
        print(f"  {sel:>10}{agg['flow']/n:>9.2f}{agg['aint']/n:>11.1f}{gapm:>10.2f}"
              f"{agg['ratio']/n:>8.2f}")
    print("\n  read: (a) nonowner owner_gap > 1 => kinetic power, flow without a reserve (власть")
    print("  как метаресурс); (b) owner_gap <= 1 => NULL, the apex accumulates in proportion to")
    print("  flow — power stays body-bound. Control: auto root owner_gap≈0.32 (carries its own).")


def _hg2v_3(seeds=(7, 8, 9), days=300):
    """Фаза 3 — the chain depth. Hold the #46/#47 frame (arena none, m=0.7, tooth reputation)
    and deepen the remittance chain A←B←C: base owners -> B_{d-1} -> ... -> B_1 -> root, m taken
    at every link. Print, per depth, the root's reaped A_flow (and its ratio to depth 1), the
    intermediary strata's lifetime body integral, and the gross mass the intermediaries handled.

    PRE-REGISTERED (both formulations fixed BEFORE the run):
      (a) root A_flow holds within a modest factor at depth 2/3 => the chain EXTENDS control
          without starving the apex — deep hierarchy scales extraction (расширение охвата wins).
      (b) root A_flow decays ≈ m per added level (m^depth) while the intermediaries accumulate
          the intercepted mass => NULL for the root ("цепь глубже 2 не кормит корень"): on a
          conservative substrate every link skims m, so hierarchy past depth 1 manufactures a
          middle-management strata rather than enriching the apex — the natural limit of
          extraction (затухание m^depth wins)."""
    print(f"\n{HDR}\nHG2V-3 — the chain depth A←B←C (arena none, m=0.7, tooth reputation). Share m\n"
          f"is taken at EVERY link, so the root sees m^depth of the base income; the (d-1)\n"
          f"intermediaries keep (1-m) of what they forward. (means over seeds {seeds})\n{HDR}")
    print(f"  {'depth':>6}{'A_flow':>9}{'A/d1':>7}{'midStrata∫':>12}{'midThru':>9}")
    ref = {}
    for depth in (1, 2, 3):
        agg = defaultdict(float); n = 0
        for s in seeds:
            w, integral, _t = _run_with_history(
                _cfgg2d(tooth="reputation", delegate_depth=depth,
                        arena=None, seed=s, days=days), days)
            assert w.matter_drift() < 1e-9, f"HG2V-3 leaked (depth{depth} s{s})"
            flow = w._delegate_flow
            mids = w._delegate_chain_ids
            mid_int = sum(integral.get(o, 0.0) for o in mids)
            mid_thru = sum(w._delegate_chain_recv.values())
            if depth == 1:
                ref[s] = flow
            ratio = (flow / ref[s]) if ref.get(s, 0.0) > 0 else float("nan")
            agg["flow"] += flow; agg["mint"] += mid_int; agg["thru"] += mid_thru
            agg["ratio"] += (ratio if ratio == ratio else 0.0); agg["rn"] += (1 if ratio == ratio else 0)
            n += 1
        rm = (agg["ratio"] / agg["rn"]) if agg["rn"] else float("nan")
        print(f"  {depth:>6}{agg['flow']/n:>9.2f}{rm:>7.2f}{agg['mint']/n:>12.1f}"
              f"{agg['thru']/n:>9.2f}")
    print("\n  read: (a) A/d1 stays near 1 at depth 2/3 => the chain extends control (охват);")
    print("  (b) A/d1 falls ≈ m per level while midStrata∫ rises => NULL for the root, a")
    print("  middle-management strata captures the skim (затухание m^depth — предел иерархии).")


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
    _gate_mg2v_apex()
    _gate_mg2v_chain()
    if "--hg1" in sys.argv or "--all" in sys.argv:
        _hg2v_1()
    if "--hg2" in sys.argv or "--all" in sys.argv:
        _hg2v_2()
    if "--hg3" in sys.argv or "--all" in sys.argv:
        _hg2v_3()
    print(f"\n{HDR}\nmod G2 vitok 2 gates green: the parameterisation is behaviour-neutral")
    print("(MG2V-REFACTOR), the seven anchors stand (MG2V-OFF), the invariant holds and every")
    print("threshold replays (MG2V-mass/replay), the body-poor apex is a non-owner (MG2V-apex),")
    print("and the remittance chain conserves and replays at depth (MG2V-chain). The trophy")
    print("meets its knob, loses its body, and grows a middle.")
    print(HDR)


if __name__ == "__main__":
    main()
