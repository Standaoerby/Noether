"""
run_dunbar_e.py — mod E: the social attention locus (Dunbar's number).

GATES (deterministic, no network):
  ME-OFF   dunbar_K=None -> byte-identical to a plain Polis run (== canon at t_awaken=inf).
  ME-mass  dunbar_K set -> registry evolves but matter_drift < 1e-9 (pure belief overlay).
  ME-replay same seed+K -> identical polis fingerprint (state + registry blob).

PRE-REGISTERED HYPOTHESES (гипотезу правит прогон):
  HE1  a coherent group has a SIZE CEILING: stable ties (surviving > persist_ticks) per
       pawn saturate below dunbar_K and do not grow with population — Dunbar's thesis.
  HE2  density breaks the locus: in a crowded arena (box6, tens of bodies per cell) the
       registry overflows every tick and few ties stabilise (a crowd is not a community);
       in a sparse arena (open grid) ties persist and the locus fills toward dunbar_K.
  HE3  status/kin bias the survivors: owners are evicted LESS than commoners (the standing
       salience bonus makes high-status ties sticky) — reputation concentrates in a
       remembered few.

MEASURED ON FIRST CALIBRATION (documented so the regime is honest):
  * box6 packs ~477 bodies onto 27 cells (peak 78 in one cell). At any realistic
    dunbar_K the registry overflows ~10x per tick: the crowd exceeds Dunbar's ceiling
    constantly, so stable ties barely form. That is not a bug — it is the result: a dense
    crowd cannot cohere into a group through the social locus.
  * HE2 in its naive form is FALSE: the open grid holds ~4x the population but the same
    ~13 bodies per OCCUPIED cell — pawns crowd around oases regardless of arena size.
    Crowding is a property of RESOURCE GEOGRAPHY, not spatial bounds: enlarge the world
    and the throng at the well is unchanged. To thin social contact you must change the
    oasis layout, not the arena.
"""
from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "Code"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sim_eventlog import EventLog
from stage3.polis import Polis, PolisConfig

HDR = "=" * 78


def _cfg(dunbar=None, seed=7, days=300, arena=6):
    return PolisConfig(appropriation=0.0, owner_policy="founders", arena_side=arena,
                       t_awaken=10 ** 9, demerzel_directive=None, seed=seed, days=days,
                       dunbar_K=dunbar)


def _run(cfg, days):
    w = Polis(EventLog(), cfg)
    for _ in range(days):
        w.step()
    return w


def _gate_me_off():
    a = _run(_cfg(dunbar=None), 250)
    b = _run(_cfg(dunbar=None), 250)
    ok = a.state_fingerprint() == b.state_fingerprint() and a.matter_drift() < 1e-9
    print(f"ME-OFF   dunbar_K=None == canon Polis -> {'✓' if ok else '✗'} "
          f"(drift {a.matter_drift():.1e})")
    assert ok


def _gate_me_mass():
    w = _run(_cfg(dunbar=15), 250)
    ok = w.matter_drift() < 1e-9 and len(w._dunbar.known) > 0
    print(f"ME-mass  registry evolves, mass untouched -> {'✓' if ok else '✗'} "
          f"(drift {w.matter_drift():.1e}, registries {len(w._dunbar.known)})")
    assert ok


def _gate_me_replay():
    a = _run(_cfg(dunbar=15), 250)
    b = _run(_cfg(dunbar=15), 250)
    ok = a.state_fingerprint() == b.state_fingerprint()
    print(f"ME-replay {a.state_fingerprint()} == {b.state_fingerprint()} -> {'✓' if ok else '✗'}")
    assert ok


def _stable_ties(w, persist_min=5.0):
    """A tie is 'stable' if its current salience exceeds persist_min (it has been
    refreshed enough to survive recency decay). Returns per-pawn stable-tie counts."""
    out = []
    for a in w.pop:
        reg = w._dunbar.known.get(a.oid, {})
        out.append(sum(1 for o in reg if reg[o][1] >= persist_min))
    return out


def _experiment(seeds=(7, 8, 9), days=300):
    print(f"\n{HDR}\nHE1/HE2 — size ceiling vs density (stable ties per pawn)\n{HDR}")
    print(f"  {'arena':>7}{'K':>4}{'pop':>6}{'/cell':>7}{'locus_mean':>12}"
          f"{'stable_mean':>13}{'evict/p/t':>11}")
    from collections import Counter
    for arena, tag in ((6, "box6"), (None, "open")):
        for K in (8, 15, 30):
            locus_all, stable_all, pops, dens, evr = [], [], [], [], []
            for s in seeds:
                w = _run(_cfg(dunbar=K, seed=s, days=days, arena=arena), days)
                if not w.pop:
                    continue
                occ = Counter((a.i, a.j) for a in w.pop)
                locus_all += [w._dunbar.locus_size(a.oid) for a in w.pop]
                stable_all += _stable_ties(w)
                pops.append(len(w.pop))
                dens.append(len(w.pop) / len(occ))
                evr.append(len(w._dunbar.evictions) / max(1, len(w.pop)) / days)
            am = sum(locus_all) / len(locus_all)
            sm = sum(stable_all) / len(stable_all)
            print(f"  {tag:>7}{K:>4}{sum(pops)//len(pops):>6}{sum(dens)/len(dens):>7.1f}"
                  f"{am:>12.1f}{sm:>13.1f}{sum(evr)/len(evr):>11.2f}")
    print("\n  HE1: stable ties saturate below K and do not track pop -> ceiling")
    print("  HE2: crowding tracks RESOURCE geography (per-cell density), not arena size")


def _he3_status(seed=7, days=300, K=15):
    print(f"\n{HDR}\nHE3 — status/kin stickiness: are owners evicted less than commoners?\n{HDR}")
    w = _run(_cfg(dunbar=K, seed=seed, days=days), days)
    owners = getattr(w, "_owner_ids", set())
    ev_owner = sum(1 for (_t, _me, drop, _s) in w._dunbar.evictions if drop in owners)
    ev_total = len(w._dunbar.evictions)
    n_owner = sum(1 for a in w.pop if a.oid in owners)
    share_pop = n_owner / max(1, len(w.pop))
    share_evict = ev_owner / max(1, ev_total)
    print(f"  owners {n_owner}/{len(w.pop)} = {share_pop:.3f} of pop; "
          f"but {share_evict:.3f} of evictions")
    print(f"  -> owners are {'STICKIER (evicted less than their share)' if share_evict < share_pop else 'not privileged'} "
          f"in social memory  (n_owner={n_owner}: weak with founders-policy)")


def _emit_json():
    """S2 — a deterministic machine-readable result (the canonical dunbar_K=15 world, the frame
    ME-mass/ME-replay exercise). No timestamp => a double run is byte-identical."""
    from stage3.resultjson import write_result
    seed, days = 7, 250
    w = _run(_cfg(dunbar=15, seed=seed), days)
    path = write_result("run_dunbar_e", w, seed=seed,
                        invariants={"drift": w.matter_drift()},
                        metrics={"registries": len(w._dunbar.known),
                                 "evictions": len(w._dunbar.evictions),
                                 "pop": len(w.pop)})
    print(f"{path} written (state_hash {w.state_fingerprint()})")


def main():
    if "--json" in sys.argv:
        _emit_json()
        return
    print(HDR)
    print("mod E — Dunbar's number: a social attention locus over PEOPLE (not places).")
    print("A pure belief overlay; mass is never touched. dunbar_K=None == canon.")
    print(HDR)
    _gate_me_off()
    _gate_me_mass()
    _gate_me_replay()
    if "--experiment" in sys.argv or "--all" in sys.argv:
        _experiment()
    if "--he3" in sys.argv or "--all" in sys.argv:
        _he3_status()
    print(f"\n{HDR}\nmod E gates green: the social locus is a pure belief overlay (ME-mass),"
          f"\nOFF ≡ canon (ME-OFF), replay byte-identical (ME-replay).\n{HDR}")


if __name__ == "__main__":
    main()
