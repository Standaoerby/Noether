"""
run_artifact_g2.py — mod G2 (Фаза 1): EXTORT — вербы контроля без владения.

Vitok 1 asked whether personality touches matter (it does: it can extinguish the cultural
ratchet). mod G2 asks the harder question — can one seize what one does not own? EXTORT is
the FIRST non-artifact verb: a conserving body→body seizure from a co-present owner, the
reverse-signed tribute (module 23 inverted). It rides the appropriation infrastructure and
the SAME intent layer as the artifact verbs (approve → note_ok), so all policies see it and
the deny sources stay apart.

THE ILLEGITIMACY GATE (VERIFY #3, sim_institution._do_challenges): EXTORT fires ONLY when a
guard (the enforcer caste — the M_e lowest-oid founder speakers after the owner block) is
NOT co-located on the cell. Crime lives in the shadow of presence. "Guard everywhere"
(saturated surveillance) closes the gate on every cell → the verb never fires.

GATES (deterministic, no network):
  MG2-OFF     extort_on=False -> ALL FOUR anchors bit-for-bit (vitok-2 41bb81b4 / 48d9729d,
              mod-G utility 12069a0e / live-replay ef879149): the verb does not exist.
  MG2-mass    every extort policy keeps the four-term invariant (<1e-9; body→body is
              conserving by construction); and EXTORT is ALIVE (fp differs from OFF, and
              mass is actually seized).
  MG2-illegit a fully-guarded world (extort_guard_everywhere) is byte-identical to the
              no-verb world: the gate is airtight — no seizure survives a present guard.
  MG2-replay  a live extort run's via-log replays bit-for-bit with no key; determinism holds.

PRE-REGISTERED (гипотезу правит прогон; honest bases from tick one — lifetime body
integrals, historical owner_ids() union, base rates; demography is an OUTCOME):
  HG2-1  does ILLEGITIMATE capture build a stratum? Concentration (Gini of the lifetime body
         integral; biomass share of the extortionist class vs its base rate) WITH extort vs
         WITHOUT, both arenas. Non-NULL => legitimacy is secondary for the physics of
         appropriation. NULL => appropriation is indifferent to the ground of right.
  HG2-2  the cost of illegitimacy. The guard suppresses EXTORT by what fraction, against the
         legitimate-challenge baseline reproduced on this main (966 -> 122, surviving 0.126)?
         Sharper or softer suppression = the measurable price of doing it without a title.
  HG2-3  DEFERRED: reputation smychka needs a mini-ledger (VERIFY #2: no gossip/reputation in
         the Polis inheritance chain) — design to be confirmed by Stan before coding.
"""
from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "Code"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from collections import defaultdict

from sim_eventlog import EventLog
from stage3.polis import Polis, PolisConfig
from stage3.intent import EXTORT, MockReflexMind
from stage3.run_artifact_f import _cfg, _run, _gini
from stage3.run_artifact_f2 import _cfg2, _life_stats, _run_with_history
from stage3.run_artifact_f3 import MFV3_OFF_ANCHOR_STORECAP, MFV3_OFF_ANCHOR_VESSEL
from stage3.run_artifact_g import _cfgg, MG_UTILITY_ANCHOR, MG_LIVE_REPLAY_ANCHOR

HDR = "=" * 78

# legitimate-challenge baseline, reproduced on this main (sim_institution, enforce off->on,
# claim box6 sigma0.5): successful ownership flips 966 -> 122, i.e. the guard let 0.126
# survive. The yardstick for HG2-2's cost of illegitimacy.
LEGIT_CHALLENGE_OFF = 966
LEGIT_CHALLENGE_ON = 122
LEGIT_SURVIVING = LEGIT_CHALLENGE_ON / LEGIT_CHALLENGE_OFF   # 0.126

# mod-G2 anchors, captured from the first green run (extort shapes the world -> own fp).
MG2_REFLEX_ANCHOR = "ea07403d00f6b19e"       # extort reflex @300 store+cap rho0.5 box6 seed7
MG2_LIVE_REPLAY_ANCHOR = "ad66c5bf0a98b655"  # extort live(MockReflex) @300, same frame


def _cfgg2(policy="reflex", extort=True, rho_extort=None, enforcers=0,
           guard_everywhere=False, **over):
    """mod-G2 on the vitok-2 substrate with an intent policy. Extort ON by default (the
    runner studies the verb); MG2-OFF flips extort=False for byte-identity. owner_policy is
    the default 'claim' so a co-present territorial owner is a real victim."""
    return _cfgg(policy=policy, extort_on=extort, rho_extort=rho_extort,
                 extort_enforcers=enforcers, extort_guard_everywhere=guard_everywhere, **over)


def _extort_stats(w):
    """Seizure count, Σ seized mass, and the set of oids that ever took by EXTORT."""
    ev = w._extort_events
    takers = set()
    for (_t, _cell, _victims, tk, _amt) in ev:
        takers.update(tk)
    return len(ev), w._extorted_total, takers


# --------------------------------------------------------------------------- #
#  Gates                                                                       #
# --------------------------------------------------------------------------- #
def _gate_mg2_off():
    sc = _run(_cfgg2(policy="off", extort=False, days=300), 300)
    ve = _run(_cfg(artifacts=True, days=250, intent_policy="off", extort_on=False), 250)
    ut = _run(_cfgg2(policy="utility", extort=False, days=300), 300)
    lv = _run(_cfgg2(policy="live", extort=False, days=300, intent_mind=MockReflexMind()), 300)
    fsc, fve, fut, flv = (sc.state_fingerprint(), ve.state_fingerprint(),
                          ut.state_fingerprint(), lv.state_fingerprint())
    ok = (fsc == MFV3_OFF_ANCHOR_STORECAP and fve == MFV3_OFF_ANCHOR_VESSEL
          and fut == MG_UTILITY_ANCHOR and flv == MG_LIVE_REPLAY_ANCHOR
          and sc.matter_drift() < 1e-9)
    print(f"MG2-OFF  extort off ≡ mod G (verb does not exist) -> {'✓' if ok else '✗'}")
    print(f"          store+cap {fsc} == {MFV3_OFF_ANCHOR_STORECAP}")
    print(f"          vessel    {fve} == {MFV3_OFF_ANCHOR_VESSEL}")
    print(f"          utility   {fut} == {MG_UTILITY_ANCHOR}")
    print(f"          live-rep  {flv} == {MG_LIVE_REPLAY_ANCHOR}  ·  drift {sc.matter_drift():.1e}")
    assert ok


def _gate_mg2_mass():
    off = _run(_cfgg2(policy="reflex", extort=False, days=300), 300)
    drifts, fps, seized = {}, {}, {}
    for pol, kw in (("reflex", {}), ("utility", {}),
                    ("live", dict(intent_mind=MockReflexMind()))):
        w = _run(_cfgg2(policy=pol, extort=True, days=300, **kw), 300)
        drifts[pol] = w.matter_drift()
        fps[pol] = w.state_fingerprint()
        _n, seized[pol], _t = _extort_stats(w)
    alive = fps["reflex"] != off.state_fingerprint() and seized["reflex"] > 0.0
    ok = all(d < 1e-9 for d in drifts.values()) and alive
    print(f"MG2-mass invariant holds every policy; extort is alive -> {'✓' if ok else '✗'}")
    print(f"          drift reflex {drifts['reflex']:.1e} · utility {drifts['utility']:.1e} · "
          f"live {drifts['live']:.1e}")
    print(f"          Σseized reflex {seized['reflex']:.2f} · fp {fps['reflex']} != OFF "
          f"{off.state_fingerprint()} (alive: {alive})")
    assert ok


def _gate_mg2_illegit():
    # a fully-guarded world (saturated surveillance) must equal the no-verb world.
    guarded = _run(_cfgg2(policy="reflex", extort=True, guard_everywhere=True, days=300), 300)
    noverb = _run(_cfgg2(policy="reflex", extort=False, days=300), 300)
    n_ev, seized, _t = _extort_stats(guarded)
    fg, fn = guarded.state_fingerprint(), noverb.state_fingerprint()
    ok = (fg == fn) and n_ev == 0 and seized == 0.0
    print(f"MG2-illegit guard everywhere ≡ no verb (crime dies in the light) -> {'✓' if ok else '✗'}")
    print(f"          guarded {fg} == no-verb {fn}  ·  seizures {n_ev}, Σ {seized:.1f}")
    assert ok


def _gate_mg2_replay():
    w1 = _run(_cfgg2(policy="live", extort=True, days=300, intent_mind=MockReflexMind()), 300)
    w2 = _run(_cfgg2(policy="live", extort=True, days=300, intent_mind=MockReflexMind()), 300)
    log = w1._artifacts.intent.request_log
    wr = _run(_cfgg2(policy="live", extort=True, days=300, intent_replay=log), 300)
    f1, f2, fr = w1.state_fingerprint(), w2.state_fingerprint(), wr.state_fingerprint()
    det, rep = (f1 == f2), (f1 == fr)
    anchor = (f1 == MG2_LIVE_REPLAY_ANCHOR) if MG2_LIVE_REPLAY_ANCHOR != "PENDING" else True
    ok = det and rep and anchor
    print(f"MG2-replay live via-log replays bit-exact, no key -> {'✓' if ok else '✗'}")
    print(f"          mind-run {f1} == {f2} (determinism: {det})")
    print(f"          replay   {fr} == {f1} (via-log: {rep})  ·  anchor {MG2_LIVE_REPLAY_ANCHOR}")
    assert ok
    return f1


def _gate_mg2_reflex_anchor():
    a = _run(_cfgg2(policy="reflex", extort=True, days=300), 300)
    b = _run(_cfgg2(policy="reflex", extort=True, days=300), 300)
    fa, fb = a.state_fingerprint(), b.state_fingerprint()
    anchor = (fa == MG2_REFLEX_ANCHOR) if MG2_REFLEX_ANCHOR != "PENDING" else True
    ok = (fa == fb) and anchor
    print(f"MG2-refl  extort reflex replays bit-exact -> {'✓' if ok else '✗'}")
    print(f"          {fa} == {fb}  ·  anchor {MG2_REFLEX_ANCHOR}")
    assert ok
    return fa


# --------------------------------------------------------------------------- #
#  Experiments (гипотезу правит прогон)                                        #
# --------------------------------------------------------------------------- #
def _hg2_1(seeds=(7, 8, 9), days=300):
    print(f"\n{HDR}\nHG2-1 — does ILLEGITIMATE capture build a stratum? Concentration of the\n"
          f"lifetime body integral (Gini) and the biomass share of the extortionist class\n"
          f"(vs its base rate = |class|/pop), extort OFF vs ON, under reflex (EVERYONE seizes)\n"
          f"and utility (only the deception-led SELECT to). (means over seeds {seeds})\n{HDR}")
    print(f"  {'arena':>7}{'policy':>8}{'extort':>8}{'Gini(∫)':>9}{'seiz':>7}{'Σseized':>9}"
          f"{'exClass':>8}{'classShr':>9}{'baseRt':>8}")
    for arena, tag in ((6, "box6"), (None, "none")):
        for policy in ("reflex", "utility"):
            for extort in (False, True):
                agg = defaultdict(float)
                n = 0
                for s in seeds:
                    w, integral, _t = _run_with_history(
                        _cfgg2(policy=policy, extort=extort, arena=arena, seed=s, days=days), days)
                    assert w.matter_drift() < 1e-9, f"HG2-1 leaked ({tag} {policy} extort={extort} s{s})"
                    g = _gini(list(integral.values()))
                    nseiz, seized, takers = _extort_stats(w)
                    pop = len(integral) or 1
                    tot = sum(integral.values())
                    classshr = (sum(integral[o] for o in takers if o in integral) / tot
                                if tot and takers else 0.0)
                    agg["gini"] += g; agg["seiz"] += nseiz; agg["seized"] += seized
                    agg["exn"] += len(takers); agg["classshr"] += classshr
                    agg["base"] += len(takers) / pop
                    n += 1
                print(f"  {tag:>7}{policy:>8}{str(extort):>8}{agg['gini']/n:>9.3f}"
                      f"{agg['seiz']/n:>7.0f}{agg['seized']/n:>9.2f}{agg['exn']/n:>8.0f}"
                      f"{agg['classshr']/n:>9.3f}{agg['base']/n:>8.3f}")
    print("\n  read: reflex = universal seizure (mob, levels the owner stratum); utility =")
    print("  a SELECT predator class. Compare Gini(OFF) vs Gini(ON) within each policy, and")
    print("  classShr vs baseRt — does the SELECT class hold biomass ABOVE chance (a stratum)?")


def _hg2_2(seeds=(7, 8, 9), days=300, enforcers=3):
    print(f"\n{HDR}\nHG2-2 — the cost of illegitimacy. The guard ({enforcers}-corps) suppresses\n"
          f"EXTORT by what fraction, vs the legitimate-challenge baseline on this main\n"
          f"(966 -> 122, surviving {LEGIT_SURVIVING:.3f})? reflex policy. (means over seeds {seeds})\n{HDR}")
    print(f"  {'arena':>7}{'guards':>7}{'seizures':>10}{'Σseized':>10}")
    surviving = {}
    for arena, tag in ((6, "box6"), (None, "none")):
        row = {}
        for ng in (0, enforcers):
            agg = defaultdict(float)
            for s in seeds:
                w = _run(_cfgg2(policy="reflex", extort=True, enforcers=ng,
                                arena=arena, seed=s, days=days), days)
                assert w.matter_drift() < 1e-9
                nseiz, seized, _t = _extort_stats(w)
                agg["seiz"] += nseiz; agg["seized"] += seized
            n = len(seeds)
            row[ng] = (agg["seiz"] / n, agg["seized"] / n)
            print(f"  {tag:>7}{ng:>7}{row[ng][0]:>10.0f}{row[ng][1]:>10.2f}")
        base_seiz = row[0][0]
        surviving[tag] = (row[enforcers][0] / base_seiz) if base_seiz else float("nan")
    print(f"\n  surviving fraction of EXTORT under guards (seizure count on/off):")
    for tag in ("box6", "none"):
        sv = surviving[tag]
        verdict = ("costlier than legitimate" if sv < LEGIT_SURVIVING
                   else "cheaper than legitimate") if sv == sv else "n/a"
        print(f"    {tag:>5}: {sv:.3f}  vs legitimate {LEGIT_SURVIVING:.3f}  -> {verdict}")
    print("  caveat: the guard caste is drawn from the potential-taker pool, so a small part")
    print("  of the drop is composition, not suppression — a per-taker rate is the vitok-2 fix.")


# --------------------------------------------------------------------------- #
def _emit_json():
    """S2 — a deterministic machine-readable result (the canonical extort-reflex world, the
    frame MG2-refl anchors). No timestamp => a double run is byte-identical."""
    from stage3.resultjson import write_result
    seed, days = 7, 300
    w = _run(_cfgg2(policy="reflex", extort=True, seed=seed, days=days), days)
    n_seiz, seized, takers = _extort_stats(w)
    path = write_result("run_artifact_g2", w, seed=seed,
                        invariants={"drift": w.matter_drift()},
                        metrics={"seizures": n_seiz, "extorted_total": seized,
                                 "takers": len(takers), "pop": len(w.pop)})
    print(f"{path} written (state_hash {w.state_fingerprint()})")


# --------------------------------------------------------------------------- #
def main():
    if "--json" in sys.argv:
        _emit_json()
        return
    print(HDR)
    print("mod G2 — Фаза 1: EXTORT — control without ownership. A conserving body→body")
    print("seizure from a co-present owner, gated by the intent layer and the guard's shadow.")
    print(HDR)
    _gate_mg2_off()
    _gate_mg2_mass()
    _gate_mg2_illegit()
    _gate_mg2_replay()
    _gate_mg2_reflex_anchor()
    if "--hg1" in sys.argv or "--all" in sys.argv:
        _hg2_1()
    if "--hg2" in sys.argv or "--all" in sys.argv:
        _hg2_2()
    print(f"\n{HDR}\nmod G2 Фаза 1 gates green: extort off ≡ mod G (MG2-OFF), the invariant")
    print("holds and the verb is alive (MG2-mass), a guarded world equals the no-verb world")
    print("(MG2-illegit), and a live run replays bit-exact (MG2-replay). Crime in the shadow.")
    print(HDR)


if __name__ == "__main__":
    main()
