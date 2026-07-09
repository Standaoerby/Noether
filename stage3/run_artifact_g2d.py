"""
run_artifact_g2d.py — mod G2 (Фаза 2): DELEGATE / REVOKE — the michelsian hole.

EXTORT (Фаза 1) showed a selective predator class concentrates biomass with no title. But
the extortionist is STILL bound by presence — it must stand on the victim's cell. DELEGATE
breaks that last tether: a root A holds a delegation RIGHT over the tribute-collecting owners
(delegates B); each tick a delegate remits a share m of the tribute it collected up to A,
body→body, conserving. A reaps k cells at once WITHOUT being present anywhere — the
institutional bypass of the hard presence ceiling (VERIFY #1: legitimate tribute needs the
owner on the cell; the apparatus needs only its delegates there).

The relation is permission-only and mass-neutral; only the remittance moves mass. REVOKE has
TEETH — what actually makes a delegate remit (the sweep, Stan 2026-07-09 = full a/b/c, d=control):
  none        unenforceable: every delegate defects, A reaps nothing (delegate ≡ distributed
              ownership — the apparatus without a tooth is empty).
  reputation  the mark-ledger: a defecting (high-deception) delegate is marked and barred from
              the network; the compliant remit. Soft — A's flow caps at the compliant fraction.
  enforcer    spatial: a delegate remits only when a guard is co-located — the ceiling
              "turtles down" to the guard's own presence.
  auto        the ledger self-enforces (god-physics): full remittance. ⛔ CHEAT — the honesty
              control only, never a working regime.

GATES:
  MG2D-OFF   delegate_on=False -> the four prior anchors AND the extort-reflex anchor
             (ea07403d) bit-for-bit: the _appropriate instrumentation is transparent when off.
  MG2D-mass  every tooth keeps the four-term invariant (<1e-9); DELEGATE is alive under auto
             (root reaps flow > 0, fp differs from off).
  MG2D-replay every tooth replays bit-for-bit (deterministic structural mechanic, no key).
  MG2D-teeth the honesty control: under auto the root reaps EXACTLY m·Σincome (conserving) —
             the ledger moves precisely the intended mass, nothing created or lost.

PRE-REGISTERED (owner_gap is blind by design — a NEW axis: flow through the right-holder vs
its own BODY; denominator = the REAL owner_ids() class, урок mod F):
  HG2D-1  the teeth sweep — A's reaped flow, owner_gap, defections, concentration by tooth.
          Falsifiable: appropriation profile without breakthrough => the tooth is necessary,
          the apparatus empty; breakthrough only at (d) => no phase transition without the
          substrate cheat; breakthrough at (b)/(c) => a second conductivity of power.
  HG2D-2  dynasty vs bureaucracy — DELEGATE concentration delta vs the already-measured
          _house(25) inheritance delta (reproduced on this main). Institutional vs biological
          bypass of the presence ceiling.
"""
from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "Code"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from collections import defaultdict

from sim_eventlog import EventLog
from stage3.polis import Polis, PolisConfig
from stage3.run_artifact_f import _cfg, _run, _gini
from stage3.run_artifact_f2 import _run_with_history
from stage3.run_artifact_f3 import MFV3_OFF_ANCHOR_STORECAP, MFV3_OFF_ANCHOR_VESSEL
from stage3.run_artifact_g import _cfgg, MG_UTILITY_ANCHOR, MG_LIVE_REPLAY_ANCHOR
from stage3.run_artifact_g2 import MG2_REFLEX_ANCHOR

HDR = "=" * 78
TEETH = ("none", "reputation", "enforcer", "auto")

# mod-G2D anchor, captured from the first green run (delegate shapes the world -> own fp).
MG2D_AUTO_ANCHOR = "003f77d97fd304df"  # delegate auto @300 store+cap m0.7 box6 seed7 rho0.5

# already-measured dynastic baseline (mod 25 inheritance, REPRODUCED on this main; claim box6
# revert, E1/E2): the biological bypass of the presence ceiling. Its power is in TIME, not
# amount — raw concentration barely moves, persistence does.
HOUSE_BASE = dict(land_off=0.250, land_on=0.275,      # end top-house land share off->on
                  gini_off=0.375, gini_on=0.375,      # house-Gini off->on (flat)
                  distinct_off=10, distinct_on=6,     # distinct top-houses (fewer = dynastic)
                  gendepth_off=3, gendepth_on=5)      # gen-depth at the top


def _cfgg2d(tooth="auto", m=0.7, enforcers=0, on=True, **over):
    """DELEGATE on the vitok-2 substrate (store+capital ON, claim, rho0.5): tribute flows to
    owners, who remit m to the absent root. Intent OFF — DELEGATE is a structural ledger
    mechanic, not an intent verb. MG2D-OFF flips on=False for byte-identity."""
    return _cfgg(policy="off", extort_on=False, delegate_on=on, delegate_m=m,
                 revoke_tooth=tooth, delegate_enforcers=enforcers, **over)


def _dele_stats(w):
    """Root flow, defections, and the root oid."""
    return w._delegate_flow, w._delegate_defections, w._delegate_root


# --------------------------------------------------------------------------- #
#  Gates                                                                       #
# --------------------------------------------------------------------------- #
def _gate_mg2d_off():
    sc = _run(_cfgg2d(on=False, days=300), 300)                 # delegate off, store+cap frame
    # extort-reflex world (Фаза 1 anchor) must also stand: the _appropriate override is
    # transparent when delegate is off, so extort is unperturbed.
    from stage3.run_artifact_g2 import _cfgg2 as _cfg_extort
    ex = _run(_cfg_extort(policy="reflex", extort=True, days=300), 300)
    fsc, fex = sc.state_fingerprint(), ex.state_fingerprint()
    ok = (fsc == MFV3_OFF_ANCHOR_STORECAP and fex == MG2_REFLEX_ANCHOR
          and sc.matter_drift() < 1e-9)
    print(f"MG2D-OFF delegate off ≡ Фаза 1 (instrumentation transparent) -> {'✓' if ok else '✗'}")
    print(f"          store+cap {fsc} == {MFV3_OFF_ANCHOR_STORECAP}  ·  drift {sc.matter_drift():.1e}")
    print(f"          extort-refl {fex} == {MG2_REFLEX_ANCHOR}")
    assert ok


def _gate_mg2d_mass():
    off = _run(_cfgg2d(on=False, days=300), 300)
    drifts, fps, flows = {}, {}, {}
    for tooth in TEETH:
        w = _run(_cfgg2d(tooth=tooth, enforcers=(3 if tooth == "enforcer" else 0), days=300), 300)
        drifts[tooth] = w.matter_drift()
        fps[tooth] = w.state_fingerprint()
        flows[tooth], _d, _r = _dele_stats(w)
    alive = flows["auto"] > 0.0 and fps["auto"] != off.state_fingerprint()
    ok = all(d < 1e-9 for d in drifts.values()) and alive
    print(f"MG2D-mass invariant holds every tooth; delegate alive under auto -> {'✓' if ok else '✗'}")
    print(f"          drift " + " · ".join(f"{t} {drifts[t]:.1e}" for t in TEETH))
    print(f"          auto flow {flows['auto']:.2f} · fp {fps['auto']} != OFF "
          f"{off.state_fingerprint()} (alive: {alive})")
    assert ok


def _gate_mg2d_replay():
    fps = {}
    for tooth in TEETH:
        a = _run(_cfgg2d(tooth=tooth, enforcers=(3 if tooth == "enforcer" else 0), days=300), 300)
        b = _run(_cfgg2d(tooth=tooth, enforcers=(3 if tooth == "enforcer" else 0), days=300), 300)
        fa, fb = a.state_fingerprint(), b.state_fingerprint()
        assert fa == fb, f"MG2D-replay: tooth {tooth} non-deterministic ({fa} != {fb})"
        fps[tooth] = fa
    anchor = (fps["auto"] == MG2D_AUTO_ANCHOR) if MG2D_AUTO_ANCHOR != "PENDING" else True
    ok = anchor
    print(f"MG2D-replay every tooth replays bit-exact (deterministic, no key) -> {'✓' if ok else '✗'}")
    for t in TEETH:
        print(f"          {t:>10}: {fps[t]}")
    print(f"          auto anchor {MG2D_AUTO_ANCHOR}")
    assert ok
    return fps["auto"]


def _gate_mg2d_teeth():
    # honesty control: under auto the root reaps EXACTLY m·Σ(tribute income), conserving.
    w = Polis(EventLog(), _cfgg2d(tooth="auto", days=300))
    total_income = 0.0
    reaped = 0.0
    for _ in range(300):
        w.step()
        inc = w._delegate_m_income
        total_income += sum(v for o, v in inc.items() if o != w._delegate_root)
    reaped = w._delegate_flow
    expected = w._delegate_m * total_income
    # remittance is clamped to body, so reaped <= expected; equality holds while no delegate
    # is ever too poor to remit its share (measured, printed).
    rel = abs(reaped - expected) / expected if expected > 0 else 0.0
    ok = w.matter_drift() < 1e-9 and rel < 1e-9
    print(f"MG2D-teeth auto reaps exactly m·Σincome (ledger honest) -> {'✓' if ok else '✗'}")
    print(f"          reaped {reaped:.6f} vs m·Σincome {expected:.6f}  ·  rel {rel:.1e} "
          f"·  drift {w.matter_drift():.1e}")
    assert ok


# --------------------------------------------------------------------------- #
#  Experiments                                                                 #
# --------------------------------------------------------------------------- #
def _hg2d_1(seeds=(7, 8, 9), days=300):
    print(f"\n{HDR}\nHG2D-1 — the REVOKE teeth sweep. A = the absent root; owner_gap = flow the\n"
          f"root reaps / its OWN body integral (>1 => power decoupled from body). Concentration\n"
          f"= Gini of the lifetime body integral. (means over seeds {seeds})\n{HDR}")
    print(f"  {'arena':>7}{'tooth':>11}{'A_flow':>9}{'A_bodyInt':>10}{'owner_gap':>10}"
          f"{'defect':>8}{'Gini(∫)':>9}")
    for arena, tag in ((6, "box6"), (None, "none")):
        for tooth in TEETH:
            agg = defaultdict(float); n = 0
            for s in seeds:
                w, integral, _t = _run_with_history(
                    _cfgg2d(tooth=tooth, enforcers=(3 if tooth == "enforcer" else 0),
                            arena=arena, seed=s, days=days), days)
                assert w.matter_drift() < 1e-9, f"HG2D-1 leaked ({tag} {tooth} s{s})"
                flow, defect, root = _dele_stats(w)
                a_int = integral.get(root, 0.0)
                gap = (flow / a_int) if a_int > 0 else float("nan")
                agg["flow"] += flow; agg["aint"] += a_int
                agg["gap"] += (gap if gap == gap else 0.0); agg["gapn"] += (1 if gap == gap else 0)
                agg["defect"] += defect; agg["gini"] += _gini(list(integral.values()))
                n += 1
            gm = (agg["gap"] / agg["gapn"]) if agg["gapn"] else float("nan")
            print(f"  {tag:>7}{tooth:>11}{agg['flow']/n:>9.2f}{agg['aint']/n:>10.1f}{gm:>10.2f}"
                  f"{agg['defect']/n:>8.0f}{agg['gini']/n:>9.3f}")
    print("\n  read: none => A_flow≈0 (apparatus empty, tooth necessary). auto => full flow")
    print("  (the cheat ceiling). reputation/enforcer between => a real conductivity of power")
    print("  if owner_gap rises above the body-bound baseline without the substrate cheat.")


def _hg2d_2(seeds=(7, 8, 9), days=300):
    print(f"\n{HDR}\nHG2D-2 — dynasty vs bureaucracy: the concentration DELTA of the institutional\n"
          f"bypass (DELEGATE auto) vs the already-measured biological one (_house inheritance,\n"
          f"mod 25). Gini(∫) delegate-off vs auto, and the root's owner_gap (flow/own body).\n{HDR}")
    print(f"  {'arena':>7}{'Gini off':>9}{'Gini auto':>10}{'ΔGini':>8}{'owner_gap':>10}")
    for arena, tag in ((6, "box6"), (None, "none")):
        agg = defaultdict(float); n = 0
        for s in seeds:
            woff, ioff, _ = _run_with_history(_cfgg2d(on=False, arena=arena, seed=s, days=days), days)
            wau, iau, _ = _run_with_history(_cfgg2d(tooth="auto", arena=arena, seed=s, days=days), days)
            goff, gau = _gini(list(ioff.values())), _gini(list(iau.values()))
            flow, _d, root = _dele_stats(wau)
            a_int = iau.get(root, 0.0)
            gap = (flow / a_int) if a_int > 0 else float("nan")
            agg["goff"] += goff; agg["gau"] += gau
            agg["gap"] += (gap if gap == gap else 0.0); agg["gapn"] += (1 if gap == gap else 0)
            n += 1
        gm = (agg["gap"] / agg["gapn"]) if agg["gapn"] else float("nan")
        print(f"  {tag:>7}{agg['goff']/n:>9.3f}{agg['gau']/n:>10.3f}"
              f"{(agg['gau']-agg['goff'])/n:>8.3f}{gm:>10.2f}")
    hb = HOUSE_BASE
    print(f"\n  _house(25) biological baseline (reproduced on this main, claim box6 revert):")
    print(f"    top-house land share {hb['land_off']:.3f} -> {hb['land_on']:.3f} "
          f"(Δ{hb['land_on']-hb['land_off']:+.3f}); house-Gini {hb['gini_off']:.3f} -> "
          f"{hb['gini_on']:.3f} (flat)")
    print(f"    distinct top-houses {hb['distinct_off']} -> {hb['distinct_on']}; gen-depth "
          f"{hb['gendepth_off']} -> {hb['gendepth_on']} (dynasty concentrates in TIME, not amount)")
    print("  read: both bypasses barely move raw Gini. Dynasty's signature is PERSISTENCE")
    print("  (gen-depth, fewer houses); bureaucracy's is owner_gap (flow decoupled from body).")


# --------------------------------------------------------------------------- #
def main():
    print(HDR)
    print("mod G2 — Фаза 2: DELEGATE / REVOKE — control without presence. The root reaps its")
    print("delegates' collections through a permission ledger; the REVOKE tooth gives it teeth.")
    print(HDR)
    _gate_mg2d_off()
    _gate_mg2d_mass()
    _gate_mg2d_replay()
    _gate_mg2d_teeth()
    if "--hg1" in sys.argv or "--all" in sys.argv:
        _hg2d_1()
    if "--hg2" in sys.argv or "--all" in sys.argv:
        _hg2d_2()
    print(f"\n{HDR}\nmod G2 Фаза 2 gates green: delegate off ≡ Фаза 1 (MG2D-OFF), the invariant")
    print("holds every tooth and the apex reaps under auto (MG2D-mass), every tooth replays")
    print("(MG2D-replay), and the ledger is honest (MG2D-teeth). The hole in the ceiling.")
    print(HDR)


if __name__ == "__main__":
    main()
