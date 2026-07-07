"""
run_artifact_f2.py — mod F (vitok 2): store + capital — detachable, accumulable mass.

Vitok 1 (vessel) froze KNOWLEDGE into matter; vitok 2 freezes WEALTH. Two new kinds on
the same dual-layer Artifact chassis (semantically mute: payload {}, salience 0.0):

  store    a printable mass reserve — a hungry pawn (body < store_draw_at) on the cell
           draws min(mass, store_draw_rate) BACK into its body: the inverse of writing.
  capital  a productivity tool — a pawn on the cell extracts
           extra = min(soil, capital_rate·Σtool_mass) from the SOIL into its body.
           Capital NEVER creates mass: it opens a reservoir (soil) the canonical eat
           (which grazes PLANT) cannot reach — irrigation/deep tillage. Productivity is
           proportional to remaining tool mass: material decay IS amortisation.

Mint cascade (deterministic, one mint per pawn per tick — every mint resets dwell), in
descending wealth-floor order: capital (2·REPRO) > store (1.5·REPRO) > vessel (REPRO).
The floors are a measured calibration (tick-p99 body ≈ 4.7 at rho0.5 claim box6, while
p90 sits BELOW REPRO: mass lives in a narrow top — HF3's substrate, reused).

GATES (deterministic, no network):
  MFv2-OFF      store_on=capital_on=False -> byte-identical to vitok 1 (vessel anchor),
                and artifacts=False -> byte-identical to the mod-E Polis (canon anchors).
  MFv2-mass     store+capital ON at the HARSHEST flow (capital_rate=0.10, open access):
                mints, draws and harvests all fire, yet the four-term invariant holds
                (< 1e-9). The sharpest edge is capital: any multiplier that MINTED mass
                instead of moving it would break Σ here.
  MFv2-semantic store/capital are semantically MUTE: salience stays 0.0, payload stays
                empty, no read/copy ever touches a non-vessel aid, and with mat_decay=0
                every mass movement is a pure transfer (drift < 1e-9).
  MFv2-replay   same seed -> identical fingerprint (kind enters the blob only for
                non-vessel objects, so the vitok-1 vessel term is byte-unchanged).
  regression    the full vitok-1 gate battery (MF-*) re-runs green.

MEASURED ON FIRST CALIBRATION (documented so the regime is honest):
  * open capital at rate=0.10 is a demographic PUMP: pop_end 390 vs 156 OFF (seed 7,
    300 ticks) — the soil reservoir (~71/cell) dwarfs plant, and an open tool floods
    the body pool. rate=0.02 is the minimally-invasive default; the rate grid is HG2's
    experimental axis, not a constant to hide.
  * at rate=0.02 pop_end DROPS below OFF (110 vs 156): mints pull mass out of the
    living pool, the faster store/capital decay (3x/5x) bleeds it into soil, and
    without a strong tool the flow never comes back — material culture as a net SINK
    of biomass. A finding candidate, logged for the thread.

PRE-REGISTERED HYPOTHESES (гипотезу правит прогон):
  HG1  store is a survival buffer, but a SELECTIVE one: ON lowers deaths / raises
       median life vs OFF, yet the draw volume concentrates (Gini of drawn mass;
       owner-class share of draws). Access owner vs open shifts WHO is saved.
  HG2  capital is a divergence RATCHET: ON makes Gini(body) GROW over time (the
       tool-holder extracts faster, so wealth compounds), OFF plateaus. Trajectory of
       Gini(body) by tick; the rate grid spans pump-to-sink.
  HG3  THE MAIN TROPHY — a NEW stratum or a MIRROR? Overlap of the elite sets:
       capital-makers / top-harvesters / store-makers / top-drawers vs the territorial
       owner class (owner_ids(), the REAL class — never _owner_ids) vs vessel-makers.
       Orthogonal (low overlap) => detached wealth is a NEW axis of stratification;
       coincident => capital mirrors land (an honest NULL, also a result).
"""
from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "Code"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from collections import defaultdict

from sim_eventlog import EventLog, REPRO
from stage3.polis import Polis, PolisConfig
from stage3.run_artifact_f import (_cfg, _run, _run_with_body_integral, _gini,
                                   _deaths_births, _gate_mf_off, _gate_mf_mass,
                                   _gate_mf_semantic, _gate_mf_replay,
                                   MF_OFF_ANCHOR_RHO0, MF_OFF_ANCHOR_CLAIM)

HDR = "=" * 78

# --- vitok-2 anchors (measured; cite verbatim, like SAL_SPHERE / CANON_COMM) ------- #
MF_VESSEL_ANCHOR = "48d9729d3cba98e2"   # vitok-1 replay @ 250 ticks (store/capital OFF)
MFV2_REPLAY_ANCHOR = "41bb81b486d77c7e"  # store+capital ON @ 300 ticks (defaults: open, rate 0.02)


def _cfg2(store=False, capital=False, **over):
    """Vitok-2 config on top of the vitok-1 default frame (rho0.5 claim box6 seed7)."""
    kw = dict(artifacts=True, store_on=store, capital_on=capital)
    kw.update(over)
    return _cfg(**kw)


# --------------------------------------------------------------------------- #
#  Gates                                                                       #
# --------------------------------------------------------------------------- #
def _gate_mfv2_off():
    # store/capital OFF => byte-identical to vitok 1 on the SAME 250-tick frame the
    # vessel anchor was cut on; artifacts=False re-checked via the vitok-1 gate below.
    w = _run(_cfg2(store=False, capital=False, days=250), 250)
    fp = w.state_fingerprint()
    ok = fp == MF_VESSEL_ANCHOR and w.matter_drift() < 1e-9
    print(f"MFv2-OFF  store/capital OFF ≡ vitok-1 vessel -> {'✓' if ok else '✗'}")
    print(f"           {fp} == {MF_VESSEL_ANCHOR}  ·  drift {w.matter_drift():.1e}")
    assert ok


def _gate_mfv2_mass():
    # the HARSHEST flow: open capital at rate 0.10 (the demographic pump) + stores.
    # Every channel fires (mint/draw/harvest) and the four-term invariant still holds.
    w = _run(_cfg2(store=True, capital=True, capital_rate=0.10, days=300), 300)
    af = w._artifacts
    drawn = sum(d[3] for d in af.draws)
    extra = sum(b[3] for b in af.boosts)
    ok = (w.matter_drift() < 1e-9 and af.stores and af.capitals
          and af.draws and af.boosts)
    print(f"MFv2-mass store+capital ON (harshest: rate 0.10) -> {'✓' if ok else '✗'} "
          f"(drift {w.matter_drift():.1e}; stores {len(af.stores)}, draws {len(af.draws)} "
          f"Σ{drawn:.1f}, capitals {len(af.capitals)}, boosts {len(af.boosts)} Σ{extra:.1f})")
    assert ok


def _gate_mfv2_semantic():
    # store/capital are semantically MUTE: salience 0.0, payload {}, never read/copied;
    # with mat_decay=0 every movement of mass is a pure transfer (drift < 1e-9).
    w = _run(_cfg2(store=True, capital=True, mat_decay=0.0, days=300), 300)
    af = w._artifacts
    nonv = [a for a in af.artifacts if a.kind != "vessel"]
    nonv_aids = ({a[1] for a in af.stores} | {a[1] for a in af.capitals})
    read_aids = {r[1] for r in af.reads}
    mute = (all(a.salience == 0.0 and not a.payload for a in nonv)
            and not (nonv_aids & read_aids))
    ok = mute and w.matter_drift() < 1e-9 and nonv
    print(f"MFv2-semantic store/capital mute (salience 0, unread) -> {'✓' if ok else '✗'} "
          f"(non-vessel alive {len(nonv)}, reads into them {len(nonv_aids & read_aids)}, "
          f"drift {w.matter_drift():.1e})")
    assert ok


def _gate_mfv2_replay():
    global MFV2_REPLAY_ANCHOR
    a = _run(_cfg2(store=True, capital=True, days=300), 300)
    b = _run(_cfg2(store=True, capital=True, days=300), 300)
    fa, fb = a.state_fingerprint(), b.state_fingerprint()
    anchor_ok = (MFV2_REPLAY_ANCHOR == "PLACEHOLDER") or (fa == MFV2_REPLAY_ANCHOR)
    ok = fa == fb and anchor_ok
    tail = "" if MFV2_REPLAY_ANCHOR != "PLACEHOLDER" else "  (anchor to be cut: set MFV2_REPLAY_ANCHOR)"
    print(f"MFv2-replay {fa} == {fb} -> {'✓' if ok else '✗'}{tail}")
    assert ok


def _gate_regression():
    print(f"\n--- vitok-1 regression (MF-*) ---")
    _gate_mf_off(); _gate_mf_mass(); _gate_mf_semantic(); _gate_mf_replay()


# --------------------------------------------------------------------------- #
#  Experiments (гипотезу правит прогон)                                        #
# --------------------------------------------------------------------------- #
def _life_stats(w):
    """(deaths, median lifespan) from the event log; lifespans for closed lives only."""
    death, birth = _deaths_births(w)
    spans = sorted(death[o] - birth[o] for o in death if o in birth)
    med = spans[len(spans) // 2] if spans else float("nan")
    return len(death), med


def _hg1(seeds=(7, 8, 9), days=300):
    print(f"\n{HDR}\nHG1 — is the store a survival buffer, and WHOSE survival does it buy?\n"
          f"(OFF vs ON-open vs ON-owner · deaths & median life = the buffer; Gini of the\n"
          f"drawn mass & the owner-class share of it = the selectivity)\n{HDR}")
    print(f"  {'seed':>5}{'regime':>10}{'deaths':>8}{'med.life':>10}{'draws':>8}"
          f"{'Σdrawn':>9}{'G_draw':>8}{'own%':>7}")
    for s in seeds:
        rows = []
        for label, kw in (("OFF", dict(store=False)),
                          ("open", dict(store=True, store_access="open")),
                          ("owner", dict(store=True, store_access="owner"))):
            w = _run(_cfg2(seed=s, days=days, **kw), days)
            af = w._artifacts
            deaths, med = _life_stats(w)
            if af.draws:
                by_drawer = defaultdict(float)
                for (_t, _aid, drawer, amount, _mk) in af.draws:
                    by_drawer[drawer] += amount
                g = _gini(by_drawer.values())
                owners = set(w.owner_ids())        # the REAL territorial class
                tot = sum(by_drawer.values())
                own = (sum(v for o, v in by_drawer.items() if o in owners) / tot
                       if tot > 0 else float("nan"))
                rows.append((label, deaths, med, len(af.draws), tot, g, own))
            else:
                rows.append((label, deaths, med, 0, 0.0, float("nan"), float("nan")))
        for (label, deaths, med, nd, tot, g, own) in rows:
            print(f"  {s:>5}{label:>10}{deaths:>8}{med:>10}{nd:>8}{tot:>9.1f}"
                  f"{g:>8.3f}{own:>7.2f}")
    print("\n  read: the buffer question is deaths/med.life ON vs OFF; the selectivity")
    print("  question is G_draw (who drinks from the heap) and own% (how much of the")
    print("  rescue lands on the territorial class). owner-access is the locked barn.")


def _hg2(seed=7, seeds=(7, 8, 9), days=300):
    print(f"\n{HDR}\nHG2 — is capital a divergence RATCHET? Gini(body) trajectory, OFF vs ON\n"
          f"(rate grid on seed {seed}; the headline rate 0.02 across seeds)\n{HDR}")
    ticks = (50, 100, 150, 200, 250, 300)

    def _traj(cfg):
        w = Polis(EventLog(), cfg)
        out = []
        for t in range(1, days + 1):
            w.step()
            if t in ticks:
                out.append(_gini(a.body for a in w.pop))
        return w, out

    print(f"  {'run':>16}" + "".join(f"{f'G@{t}':>9}" for t in ticks)
          + f"{'slope':>9}{'pop':>6}")
    for label, kw in (("OFF", dict(capital=False)),
                      ("ON r=0.02", dict(capital=True, capital_rate=0.02)),
                      ("ON r=0.05", dict(capital=True, capital_rate=0.05)),
                      ("ON r=0.10", dict(capital=True, capital_rate=0.10))):
        w, tr = _traj(_cfg2(seed=seed, days=days, **kw))
        assert w.matter_drift() < 1e-9, f"HG2 cell leaked matter ({label})"
        print(f"  {label:>16}" + "".join(f"{g:>9.3f}" for g in tr)
              + f"{tr[-1] - tr[0]:>+9.3f}{len(w.pop):>6}")
    print(f"\n  headline (rate 0.02) across seeds:")
    print(f"  {'seed':>5}{'G@300 OFF':>11}{'G@300 ON':>10}{'Δ':>8}")
    for s in seeds:
        _, t_off = _traj(_cfg2(seed=s, days=days, capital=False))
        _, t_on = _traj(_cfg2(seed=s, days=days, capital=True, capital_rate=0.02))
        print(f"  {s:>5}{t_off[-1]:>11.3f}{t_on[-1]:>10.3f}{t_on[-1] - t_off[-1]:>+8.3f}")


def _overlap(a: set, b: set):
    """(|A∩B|/|A|, Jaccard) — conditional overlap first: with elite sets of very
    different sizes Jaccard alone under-reads containment."""
    if not a or not b:
        return float("nan"), float("nan")
    inter = len(a & b)
    return inter / len(a), inter / len(a | b)


def _hg3(seeds=(7, 8, 9), days=300):
    """THE MAIN TROPHY. Elite sets on ONE population base (everyone who lived):
        T  territorial owners  owner_ids() at run end (the REAL class — never _owner_ids)
        V  vessel-makers       oids with surviving vessel mass
        Cm capital-makers      oids that minted a tool
        Ch top-harvesters      top-|Cm| oids by Σextra received (size-matched to Cm)
        Sm store-makers        oids that minted a store
        Sd top-drawers         top-|Sm| oids by Σmass drawn (size-matched to Sm)
    Tautology guard: the mints are body-gated, so 'makers are rich' is the rule read
    back. The non-tautological cells are the FLOW elites (Ch, Sd — open access lets the
    poor drink) vs T, and the maker-axes vs EACH OTHER."""
    print(f"\n{HDR}\nHG3 — detached wealth: a NEW stratum, or a MIRROR of land?\n"
          f"(cond = |A∩B|/|A| read 'share of A inside B' · J = Jaccard · store+capital ON,\n"
          f"open access, rate 0.02)\n{HDR}")
    pairs = (("Cm", "T"), ("Ch", "T"), ("Sm", "T"), ("Sd", "T"),
             ("Cm", "V"), ("Cm", "Sm"), ("Ch", "Sd"))
    print(f"  {'seed':>5}{'|T|':>5}{'|V|':>5}{'|Cm|':>5}{'|Ch|':>5}{'|Sm|':>5}{'|Sd|':>5}"
          + "".join(f"{a + '→' + b:>10}" for (a, b) in pairs))
    acc = {p: [] for p in pairs}
    for s in seeds:
        w, integral = _run_with_body_integral(
            _cfg2(store=True, capital=True, capital_rate=0.02, seed=s, days=days), days)
        af = w._artifacts
        T = set(w.owner_ids())
        V = {a.maker_oid for a in af.artifacts if a.kind == "vessel"}
        Cm = {c[2] for c in af.capitals}
        Sm = {st[2] for st in af.stores}
        by_h, by_d = defaultdict(float), defaultdict(float)
        for (_t, oid, _cell, extra, _cm) in af.boosts:
            by_h[oid] += extra
        for (_t, _aid, drawer, amount, _mk) in af.draws:
            by_d[drawer] += amount
        Ch = set(sorted(by_h, key=lambda o: (-by_h[o], o))[:max(len(Cm), 1)])
        Sd = set(sorted(by_d, key=lambda o: (-by_d[o], o))[:max(len(Sm), 1)])
        S = dict(T=T, V=V, Cm=Cm, Ch=Ch, Sm=Sm, Sd=Sd)
        row = f"  {s:>5}{len(T):>5}{len(V):>5}{len(Cm):>5}{len(Ch):>5}{len(Sm):>5}{len(Sd):>5}"
        for p in pairs:
            cond, j = _overlap(S[p[0]], S[p[1]])
            acc[p].append((cond, j))
            row += f"{cond:>6.2f}/{j:>3.2f}"
        print(row)
    print(f"\n  means:")
    for p in pairs:
        cs = [c for (c, _j) in acc[p] if c == c]
        js = [j for (_c, j) in acc[p] if j == j]
        cm = sum(cs) / len(cs) if cs else float("nan")
        jm = sum(js) / len(js) if js else float("nan")
        print(f"    {p[0]}→{p[1]:<3} cond {cm:.2f}  J {jm:.2f}")
    print("\n  read: maker-axes (Cm,Sm) inside T = wealth-gate mirroring land (expected,")
    print("  the tautology cell). The trophy cells are the FLOW elites: Ch→T and Sd→T low")
    print("  => detached wealth flows to a set ORTHOGONAL to territory (a new stratum);")
    print("  high => the tool and the heap feed the landlords again (an honest mirror).")


# --------------------------------------------------------------------------- #
#  Main                                                                        #
# --------------------------------------------------------------------------- #
def main():
    print(HDR)
    print("mod F — vitok 2: store + capital. Detached, accumulable mass on the vessel")
    print("chassis: a store un-prints into a hungry body (mass→body), a capital opens")
    print("the soil reservoir (soil→body, NEVER minting mass). Mint cascade by wealth:")
    print("capital(2·REPRO) > store(1.5·REPRO) > vessel(REPRO). OFF ≡ vitok 1 (MFv2-OFF).")
    print(HDR)
    _gate_mfv2_off()
    _gate_mfv2_mass()
    _gate_mfv2_semantic()
    _gate_mfv2_replay()
    if "--regression" in sys.argv or "--all" in sys.argv:
        _gate_regression()
    if "--hg1" in sys.argv or "--all" in sys.argv:
        _hg1()
    if "--hg2" in sys.argv or "--all" in sys.argv:
        _hg2()
    if "--hg3" in sys.argv or "--all" in sys.argv:
        _hg3()
    print(f"\n{HDR}\nmod F vitok 2 gates green: store/capital OFF ≡ vitok 1 (MFv2-OFF), the")
    print("four-term invariant survives the harshest pump (MFv2-mass), the new kinds are")
    print(f"semantically mute (MFv2-semantic), and the run replays bit-exact (MFv2-replay).\n{HDR}")


if __name__ == "__main__":
    main()
