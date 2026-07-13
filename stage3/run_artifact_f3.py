"""
run_artifact_f3.py — mod F (виток 3, v2): «Запасу — время, зрению — орган».

Vitok 2 froze WEALTH into detachable matter but left it OUTSIDE the information loop: a
cell's memory saw `plant` and was blind to a granary on it, so finding-6 stayed
conditional ("a store nobody knows about does not save"). v1 tried a post-hoc memory write
and was behaviourally INERT (kept in git history as a reference; diagnosed there). v2 adds
two OFF-by-default flags, both byte-identical to vitok 2 when off:

  store_settle  a store minted THIS tick is not drawable until the next (born_t < t) — a
                physical settling pause. It moves no mass, only delays the transfer one
                tick, so the object STANDS long enough to be seen and navigated to. Fixes
                the v1 diagnosis (b): a store annihilated at the point of demand.
  store_vision  an ORGAN inside canonical perception — Polis overrides _observe to call the
                canonical super()._observe first (true plant, freshness, hearsay drop) and
                THEN fold the drawable standing store on the pawn's OWN cell into its
                cell-memory. Order is correct by construction (observe → decide → move),
                fixing v1 diagnosis (a). Store-only, own-cell-only, access-filtered in the
                eyes (a locked foreign granary is invisible as value). Belief, never mass.

GATES (deterministic, no network):
  MFv3-OFF     both flags False -> byte-identical to vitok 2 (41bb81b4 @300 store+capital,
               48d9729d vessel-only @250). The _observe override MUST be transparent when off.
  MFv3-mass    settle+vision ON (open): four-term invariant holds (<1e-9); the injection is
               belief-only — plant at a store cell is unchanged by observing it.
  MFv3-belief  the _observe contract: on a standing accessible store, mem[cell] becomes
               (true_plant + drawable, t) exactly; for a barred stranger it stays canonical.
  MFv3-alive   the anti-void gate (v1's lesson): settle+vision ON, arena none, 300 ticks ->
               fingerprint != both-OFF fingerprint AND stores actually stand (>0 ticks).
  MFv3-replay  settle+vision ON replays bit-for-bit (anchor below).
  regression   the vitok-2 battery (MF-*/MFv2-*/ME-*) re-runs green.

PRE-REGISTERED EXPERIMENTS (гипотезу правит прогон; honest bases from tick one):
  HV0  the lifetime of a reserve — with settle ON, the standing-tick distribution of
       stores (box6 vs arena none), time-to-first-draw, time-to-ruin. The value itself is
       a new axis of the world.
  HV1  finding-6 factorised — A={off,off} (vitok 2) vs B={settle,off} (the reserve lives
       but is unseen) vs C={settle,vision} (lives and is seen), two arenas, seeds 7/8/9.
       B-A = the contribution of standing; C-B = the contribution of information.
  HV2  word-of-mouth — in world C only, the share of canonical claims whose target cell
       carries a standing store, against the baseline share in world A (chance).
"""
from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "Code"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from collections import defaultdict

from sim_eventlog import EventLog
from stage3.polis import Polis, PolisConfig
from stage3.run_artifact_f import _cfg, _run, _gini, _deaths_births
from stage3.run_artifact_f2 import _cfg2, _life_stats, _run_with_history

HDR = "=" * 78

# vitok-2 anchors (must stand bit-for-bit when the vitok-3 flags are OFF)
MFV3_OFF_ANCHOR_STORECAP = "41bb81b486d77c7e"   # store+capital ON @300 (settle/vision OFF)
MFV3_OFF_ANCHOR_VESSEL = "48d9729d3cba98e2"     # vessel-only @250
# vitok-3 replay anchor (settle+vision ON, defaults: box6 rho0.5 claim open @300)
MFV3_REPLAY_ANCHOR = "f7561a60d73bd6f0"


def _cfg3(settle=False, vision=False, **over):
    """Vitok-3 config on the vitok-2 frame (store+capital ON, open, rho0.5 claim box6)."""
    return _cfg2(store=True, capital=True, store_settle=settle, store_vision=vision, **over)


def _run_standing(cfg, days):
    """Run and count ticks on which at least one store stands (mass>0) at end of step."""
    w = Polis(EventLog(), cfg)
    standing = 0
    for _ in range(days):
        w.step()
        if any(a.kind == "store" and a.mass > 0.0 for a in w._artifacts.artifacts):
            standing += 1
    return w, standing


# --------------------------------------------------------------------------- #
#  Gates                                                                       #
# --------------------------------------------------------------------------- #
def _gate_mfv3_off():
    a = _run(_cfg3(settle=False, vision=False, days=300), 300)
    b = _run(_cfg(artifacts=True, days=250), 250)             # vessel-only frame
    fa, fb = a.state_fingerprint(), b.state_fingerprint()
    ok = (fa == MFV3_OFF_ANCHOR_STORECAP and fb == MFV3_OFF_ANCHOR_VESSEL
          and a.matter_drift() < 1e-9)
    print(f"MFv3-OFF  both flags off ≡ vitok 2 (override transparent) -> {'✓' if ok else '✗'}")
    print(f"           store+cap {fa} == {MFV3_OFF_ANCHOR_STORECAP}")
    print(f"           vessel    {fb} == {MFV3_OFF_ANCHOR_VESSEL}  ·  drift {a.matter_drift():.1e}")
    assert ok


def _gate_mfv3_mass():
    # settle+vision ON at open access; the invariant holds and the injection is belief-only.
    w = _run(_cfg3(settle=True, vision=True, days=300), 300)
    drift_ok = w.matter_drift() < 1e-9
    # belief-only proof: observing a store cell must NOT change plant there.
    from stage3.vision import observe_stores
    af = w._artifacts
    scell = next(((a.i, a.j) for a in af.artifacts if a.kind == "store" and a.mass > 0.0), None)
    plant_ok = True
    if scell is not None:
        pawn = next((p for p in w.pop if (p.i, p.j) == scell), None)
        if pawn is not None:
            before = float(w.plant[scell[0], scell[1]])
            observe_stores(w, pawn)
            plant_ok = float(w.plant[scell[0], scell[1]]) == before
    ok = drift_ok and plant_ok
    print(f"MFv3-mass settle+vision ON: invariant holds, plant untouched -> {'✓' if ok else '✗'} "
          f"(drift {w.matter_drift():.1e}, draws {len(af.draws)}, stores {len(af.stores)})")
    assert ok


def _gate_mfv3_belief():
    # the _observe contract, tested directly at observe-time (owner access so a store both
    # stands and stratifies: the owner sees it, a stranger on the cell does not).
    w = Polis(EventLog(), _cfg3(settle=True, vision=True, store_access="owner", days=120))
    af = w._artifacts
    proven_boost = proven_barred = False
    for _ in range(120):
        w.step()
        stores_here = defaultdict(list)
        for art in af.artifacts:
            if art.kind == "store" and art.mass > 0.0:
                stores_here[(art.i, art.j)].append(art)
        for a in sorted(w.pop, key=lambda x: x.oid):
            here = stores_here.get((a.i, a.j))
            if not here:
                continue
            dr = sum(x.mass for x in here if af._access_ok(w, x, a, af.store_access))
            plant = float(w.plant[a.i, a.j])
            w._observe(a)                                   # runs canonical + vision
            got = w.mem[a.oid][(a.i, a.j)][0]
            if dr > 0.0 and abs(got - (plant + dr)) < 1e-9:
                proven_boost = True
            if dr == 0.0 and abs(got - plant) < 1e-9:       # barred stranger -> canonical
                proven_barred = True
        if proven_boost and proven_barred:
            break
    ok = proven_boost and proven_barred
    print(f"MFv3-belief mem = plant+drawable for accessor, canonical for barred -> "
          f"{'✓' if ok else '✗'} (boost {proven_boost}, barred {proven_barred})")
    assert ok


def _gate_mfv3_alive():
    # v1's lesson: the instrument must not be void. On arena none with settle+vision ON,
    # the world must DIFFER from both-off AND stores must actually stand.
    off = _run(_cfg3(settle=False, vision=False, arena=None, days=300), 300)
    on, standing = _run_standing(_cfg3(settle=True, vision=True, arena=None, days=300), 300)
    differ = on.state_fingerprint() != off.state_fingerprint()
    ok = differ and standing > 0
    print(f"MFv3-alive (arena none) fp≠OFF and stores stand -> {'✓' if ok else '✗'} "
          f"(on {on.state_fingerprint()} vs off {off.state_fingerprint()}, standing {standing}/300)")
    if not ok:
        print("           FAIL: empty instrument — STOP and report (do not tune params).")
    assert ok


def _gate_mfv3_replay():
    a = _run(_cfg3(settle=True, vision=True, days=300), 300)
    b = _run(_cfg3(settle=True, vision=True, days=300), 300)
    fa, fb = a.state_fingerprint(), b.state_fingerprint()
    ok = fa == fb and fa == MFV3_REPLAY_ANCHOR
    print(f"MFv3-replay {fa} == {fb} == {MFV3_REPLAY_ANCHOR} -> {'✓' if ok else '✗'}")
    assert ok


def _gate_regression():
    print(f"\n--- vitok-2 regression (MFv2-*/MF-*/ME-*) ---")
    from stage3.run_artifact_f2 import (_gate_mfv2_off, _gate_mfv2_mass,
                                        _gate_mfv2_semantic, _gate_mfv2_replay,
                                        _gate_regression as _f2_regression)
    _gate_mfv2_off(); _gate_mfv2_mass(); _gate_mfv2_semantic(); _gate_mfv2_replay()
    _f2_regression()


# --------------------------------------------------------------------------- #
#  Experiments (гипотезу правит прогон)                                        #
# --------------------------------------------------------------------------- #
def _store_lifetimes(w, days):
    """Per-store (standing_ticks, ticks_to_first_draw|nan) from the artifact logs. A store
    that never became a ruin stood until `days` (right-censored, marked)."""
    af = w._artifacts
    born = {s[1]: s[0] for s in af.stores}                  # aid -> born tick
    store_aids = set(born)
    ruin_t = {r[1]: r[0] for r in af.ruins if r[1] in store_aids}
    first_draw = {}
    for (t, aid, _dr, _amt, _mk) in af.draws:
        if aid in store_aids and aid not in first_draw:
            first_draw[aid] = t
    standing, to_draw, censored = [], [], 0
    for aid, bt in born.items():
        end = ruin_t.get(aid)
        if end is None:
            standing.append(days - bt); censored += 1
        else:
            standing.append(end - bt)
        if aid in first_draw:
            to_draw.append(first_draw[aid] - bt)
    return standing, to_draw, censored


def _dist(xs):
    xs = sorted(xs)
    if not xs:
        return (0, float("nan"), float("nan"), float("nan"))
    n = len(xs)
    return (n, sum(xs) / n, xs[n // 2], xs[-1])


def _hv0(seeds=(7, 8, 9), days=300):
    print(f"\n{HDR}\nHV0 — the lifetime of a reserve (store_settle ON): how long does a store\n"
          f"STAND? (n · mean · median · max standing-ticks; and ticks-to-first-draw)\n{HDR}")
    print(f"  {'arena':>7}{'seed':>5}{'stores':>8}{'stand_mean':>11}{'stand_med':>10}"
          f"{'stand_max':>10}{'censored':>9}{'draw_mean':>10}{'draw_med':>9}")
    for arena, tag in ((6, "box6"), (None, "none")):
        for s in seeds:
            w, _st = _run_standing(_cfg3(settle=True, vision=False, arena=arena,
                                         seed=s, days=days), days)
            assert w.matter_drift() < 1e-9
            standing, to_draw, cens = _store_lifetimes(w, days)
            n, smean, smed, smax = _dist(standing)
            _dn, dmean, dmed, _dmax = _dist(to_draw)
            print(f"  {tag:>7}{s:>5}{n:>8}{smean:>11.1f}{smed:>10.0f}{smax:>10.0f}"
                  f"{cens:>9}{dmean:>10.1f}{dmed:>9.0f}")
    print("\n  read: standing-ticks with settle ON is the reserve's new lifetime; box6 vs")
    print("  none contrasts a crowded demand point with a sparse one (v1: standing ~0).")


def _survival_metrics(w):
    """HG1-style: deaths, median life, draws, Σdrawn, and own% (share of drawn mass caught
    by the HISTORICAL territorial owner class — honest full-history base)."""
    deaths, med = _life_stats(w)
    af = w._artifacts
    ndraw = len(af.draws)
    by_drawer = defaultdict(float)
    for (_t, _aid, dr, amt, _mk) in af.draws:
        by_drawer[dr] += amt
    tot = sum(by_drawer.values())
    return deaths, med, ndraw, tot, by_drawer


def _hv1(seeds=(7, 8, 9), days=300):
    print(f"\n{HDR}\nHV1 — finding-6 factorised: A(off,off)=vitok2 · B(settle,off)=reserve\n"
          f"lives unseen · C(settle,vision)=lives & seen. B−A = standing; C−B = information.\n"
          f"(own% = share of Σdrawn caught by the HISTORICAL owner class)\n{HDR}")
    print(f"  {'arena':>7}{'world':>7}{'deaths':>8}{'med.life':>9}{'draws':>7}"
          f"{'Σdrawn':>9}{'own%':>7}")
    for arena, tag in ((6, "box6"), (None, "none")):
        agg = {k: defaultdict(float) for k in ("A", "B", "C")}
        cnt = defaultdict(int)
        for s in seeds:
            for label, (se, vi) in (("A", (False, False)), ("B", (True, False)),
                                    ("C", (True, True))):
                w, _int, T = _run_with_history(
                    _cfg3(settle=se, vision=vi, arena=arena, seed=s, days=days), days)
                assert w.matter_drift() < 1e-9, f"HV1 leaked ({tag} {label} s{s})"
                deaths, med, ndraw, tot, by_drawer = _survival_metrics(w)
                own = (sum(v for o, v in by_drawer.items() if o in T) / tot
                       if tot > 0 else float("nan"))
                agg[label]["deaths"] += deaths; agg[label]["med"] += med
                agg[label]["draws"] += ndraw; agg[label]["tot"] += tot
                agg[label]["own"] += (own if own == own else 0.0)
                agg[label]["own_n"] += (1 if own == own else 0)
                cnt[label] += 1
        for label in ("A", "B", "C"):
            c = cnt[label]
            ownm = (agg[label]["own"] / agg[label]["own_n"]) if agg[label]["own_n"] else float("nan")
            print(f"  {tag:>7}{label:>7}{agg[label]['deaths']/c:>8.0f}{agg[label]['med']/c:>9.1f}"
                  f"{agg[label]['draws']/c:>7.0f}{agg[label]['tot']/c:>9.2f}{ownm:>7.2f}")
    print("\n  read: within each arena compare B−A (does a standing reserve alone move")
    print("  deaths/draws?) and C−B (does SEEING it add anything?). own% = who the rescue")
    print("  lands on. Arena contrasts crowded (box6) vs sparse (none) demand geometry.")


def _claims_on_stores(w):
    """Share of canonical `communication` claims whose TARGET cell carried a standing store
    (mass>0) at the claim's tick. Pure read of the log + reconstructed store standing per
    tick; no channel is touched."""
    # reconstruct which cells hold a standing store at each tick from the artifact logs is
    # heavy; instead re-run is avoided — we read the live world's per-tick store presence by
    # scanning events: a store stands on cell C during [born_t, ruin_t). Build intervals.
    af = w._artifacts
    born = {s[1]: (s[0], (s[3])) for s in af.stores}         # aid -> (born_t, (i,j))
    ruin_t = {r[1]: r[0] for r in af.ruins}
    # cell -> list of (start,end) standing intervals
    intervals = defaultdict(list)
    for aid, (bt, cell) in born.items():
        et = ruin_t.get(aid, w.t + 1)
        intervals[tuple(cell)].append((bt, et))
    def standing_at(cell, t):
        for (bt, et) in intervals.get(tuple(cell), ()):
            if bt <= t < et:
                return True
        return False
    n_claims = n_on_store = 0
    for e in w.log.events:
        if e.kind != "communication":
            continue
        n_claims += 1
        cell = e.data.get("cell")
        if cell is not None and standing_at((int(cell[0]), int(cell[1])), e.t):
            n_on_store += 1
    return n_claims, n_on_store


def _hv2(seeds=(7, 8, 9), days=300):
    print(f"\n{HDR}\nHV2 — word-of-mouth: share of canonical claims whose target cell carries\n"
          f"a STANDING store. World C (settle+vision) vs world A (vitok 2, chance baseline).\n"
          f"A rise = the map of reserves rode the social net with NO new channel.\n{HDR}")
    print(f"  {'arena':>7}{'seed':>5}{'A claims':>9}{'A on-store':>11}{'A %':>7}"
          f"{'C claims':>9}{'C on-store':>11}{'C %':>7}")
    for arena, tag in ((6, "box6"), (None, "none")):
        for s in seeds:
            wa = _run(_cfg3(settle=False, vision=False, arena=arena, seed=s, days=days), days)
            wc = _run(_cfg3(settle=True, vision=True, arena=arena, seed=s, days=days), days)
            na, sa = _claims_on_stores(wa)
            nc, sc = _claims_on_stores(wc)
            pa = (sa / na) if na else float("nan")
            pc = (sc / nc) if nc else float("nan")
            print(f"  {tag:>7}{s:>5}{na:>9}{sa:>11}{pa:>7.3f}{nc:>9}{sc:>11}{pc:>7.3f}")
    print("\n  note: baseline A = vitok 2 (both flags off) — its stores annihilate at the")
    print("  point of demand, so any claim-on-store is chance. C adds standing + sight. The")
    print("  showcase regime is 'deceptive' (speakers broadcast their WORST known cell), so")
    print("  a high-value store is not a natural claim target — read the share against that.")


def _context_metric(seeds=(7, 8, 9), days=300):
    """Share of pawns that lived to at least one think-tick (age >= THINK_EVERY). With
    med.life 4-5 and THINK_EVERY=6, cognition may be a privilege of the long-lived — the
    interpretive frame for every HV. Printed, not fixed."""
    from sim_comm import THINK_EVERY
    print(f"\n{HDR}\ncontext (THINK_EVERY={THINK_EVERY}): share of lives reaching >=1 think-tick\n{HDR}")
    for arena, tag in ((6, "box6"), (None, "none")):
        fr = []
        for s in seeds:
            w = _run(_cfg3(settle=True, vision=True, arena=arena, seed=s, days=days), days)
            death, birth = _deaths_births(w)
            lifes = [death[o] - birth[o] for o in death if o in birth]
            if lifes:
                fr.append(sum(1 for L in lifes if L >= THINK_EVERY) / len(lifes))
        m = sum(fr) / len(fr) if fr else float("nan")
        print(f"  {tag:>7}  lived>=1 think-tick: {m:.3f}")
    print("  read: if this is small, cognition (and thus vision) can only touch a minority")
    print("  — the frame within which any HV1 C−B effect must be read.")


def _emit_json():
    """S2 — a deterministic machine-readable result (the canonical settle+vision world, the
    frame MFv3-replay exercises). No timestamp => a double run is byte-identical."""
    from stage3.resultjson import write_result
    seed, days = 7, 300
    w = _run(_cfg3(settle=True, vision=True, seed=seed, days=days), days)
    af = w._artifacts
    path = write_result("run_artifact_f3", w, seed=seed,
                        invariants={"drift": w.matter_drift()},
                        metrics={"stores": len(af.stores), "capitals": len(af.capitals),
                                 "draws": len(af.draws), "boosts": len(af.boosts),
                                 "pop": len(w.pop)})
    print(f"{path} written (state_hash {w.state_fingerprint()})")


def main():
    if "--json" in sys.argv:
        _emit_json()
        return
    print(HDR)
    print("mod F — vitok 3 (v2): store_settle (grain put away for a day) + store_vision")
    print("(an organ inside canonical perception). Both OFF => byte-identical to vitok 2.")
    print(HDR)
    _gate_mfv3_off()
    _gate_mfv3_mass()
    _gate_mfv3_belief()
    _gate_mfv3_alive()
    _gate_mfv3_replay()
    if "--regression" in sys.argv or "--all" in sys.argv:
        _gate_regression()
    if "--hv0" in sys.argv or "--all" in sys.argv:
        _hv0()
    if "--hv1" in sys.argv or "--all" in sys.argv:
        _hv1(); _context_metric()
    if "--hv2" in sys.argv or "--all" in sys.argv:
        _hv2()
    print(f"\n{HDR}\nmod F vitok 3 v2 gates green: OFF ≡ vitok 2 (MFv3-OFF), invariant holds")
    print("(MFv3-mass), the _observe contract writes plant+drawable (MFv3-belief), the")
    print("instrument is alive (MFv3-alive), and the run replays bit-exact (MFv3-replay).")
    print(HDR)


if __name__ == "__main__":
    main()
