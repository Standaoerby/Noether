"""run_faithful_ledger_gates.py — faithful-ledger Ф1 gates: FL-FP-NEUTRAL + FL-PROPERTY-FAITHFUL.

  FL-FP-NEUTRAL       turning the mirror ON must not move the world: state_fingerprint stream,
                      polis_fingerprint, _cell_owner, _house, pop, _appropriated_total all
                      byte-identical to a run with it OFF. (Ф0 proved emission cannot move a
                      fingerprint; this re-proves it for the REAL emitter, not a junk probe.)

  FL-PROPERTY-FAITHFUL (core) — replaying ONLY the emitted claim/lose/inherit events must
                      reproduce `_cell_owner` EXACTLY at EVERY tick. This is the
                      `reconstruct_live` principle applied to ownership: if the replay drifts
                      by one cell on one tick, the journal is still not a mirror => STOP.

  OFF-invariance      with faithful_ledger=False not one new event is emitted, so every
                      existing anchor (including β-3's events.jsonl 2735d669…) is untouched.

Run:  py stage3/run_faithful_ledger_gates.py
"""
from __future__ import annotations

import hashlib
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "Code"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sim_eventlog import EventLog                                   # noqa: E402
from stage3.polis import Polis, polis_fingerprint                   # noqa: E402
from stage3.viz_export import build_showcase_cfg                    # noqa: E402

HDR = "=" * 78
DAYS = 250
LEDGER_KINDS = ("claim", "lose", "inherit", "mark", "unmark", "appropriate")
TOL = 1e-9


def _fl_mass(w):
    """FL-MASS, both halves (WO §3 as refined for variant A):
      (a) per-cell internal balance — Σ paid == Σ got == dm in every `appropriate` event;
      (b) the log does not lie about the flow — Σ dm over the log == Δ `_appropriated_total`.
    `appropriate` is a DERIVED deme event, so `dm` reports the magnitude moved in that cell;
    the direction is read from payers/receivers."""
    gross = 0.0
    bad_cells = []
    n = 0
    for e in w.log.events:
        if e.kind != "appropriate":
            continue
        n += 1
        paid = sum(v for _o, v in e.data["payers"])
        got = sum(v for _o, v in e.data["receivers"])
        gross += e.dm
        if abs(paid - got) > TOL or abs(paid - e.dm) > TOL:
            bad_cells.append((e.t, e.where, paid, got, e.dm))
    total = float(getattr(w, "_appropriated_total", 0.0))
    return {"n_events": n, "gross": gross, "canon_total": total,
            "delta": abs(gross - total), "bad_cells": bad_cells}


def scene(days=DAYS, ledger=False, inherit=False, frailty="off", marks=False):
    c = build_showcase_cfg(seed=7, days=days, extort_on=True, delegate_on=True,
                           revoke_tooth="reputation", extort_enforcers=3,
                           delegate_enforcers=2, intent_policy="reflex")
    c.faithful_ledger = ledger
    c.inherit_on = inherit
    c.frailty = frailty
    if marks:
        c.extort_reputation = True      # else the mark-ledgers never populate
    return c


def _drive(cfg, check_replay=False):
    """Run, folding a fingerprint stream. When check_replay, rebuild ownership from the
    emitted events after every tick and compare to the live `_cell_owner`."""
    w = Polis(EventLog(), cfg)
    h = hashlib.sha256()
    replay = {}          # cell -> oid, rebuilt from events alone
    rmark = {"extort": set(), "delegate": set()}   # marks rebuilt from events alone
    cursor = 0
    mismatches, mark_mismatches = [], []
    for _ in range(cfg.days):
        w.step()
        h.update(w.state_fingerprint().encode())
        if check_replay:
            for e in w.log.events[cursor:]:
                if e.kind in ("claim", "inherit"):
                    replay[tuple(e.where)] = e.actor
                elif e.kind == "lose":
                    replay.pop(tuple(e.where), None)
                elif e.kind == "mark":
                    rmark[e.data["ledger"]].add(e.actor)
                elif e.kind == "unmark":
                    rmark[e.data["ledger"]].discard(e.actor)
            cursor = len(w.log.events)
            if replay != {tuple(k): v for k, v in w._cell_owner.items()}:
                real = {tuple(k): v for k, v in w._cell_owner.items()}
                diff = {c for c in set(replay) | set(real) if replay.get(c) != real.get(c)}
                mismatches.append((w.t, len(diff), sorted(diff)[:3]))
            # marks: the GC sweeps dead oids WITHOUT an unmark (that is not an un-branding),
            # so the replay is compared over the LIVING set — which is what the world holds.
            live = {a.oid for a in w.pop}
            for tag, real_set in (("extort", set(getattr(w, "_extort_marks", ()) or ())),
                                  ("delegate", set(getattr(w, "_delegate_marks", ()) or ()))):
                if (rmark[tag] & live) != (real_set & live):
                    mark_mismatches.append((w.t, tag,
                                            len((rmark[tag] & live) ^ (real_set & live))))
    kinds = {}
    for e in w.log.events:
        if e.kind in LEDGER_KINDS:
            kinds[e.kind] = kinds.get(e.kind, 0) + 1
    return w, h.hexdigest()[:16], mismatches, kinds, mark_mismatches


def _state(w):
    return {"polis_fp": polis_fingerprint(w), "cells": len(w._cell_owner),
            "cellmap": sorted(w._cell_owner.items()), "pop": len(w.pop),
            "house": sorted((getattr(w, "_house", {}) or {}).items()),
            "appr": round(float(getattr(w, "_appropriated_total", 0.0)), 6),
            "inh": int(getattr(w, "_inherit_events", 0))}


def main():
    print(HDR)
    print("faithful-ledger Ф1 — гейты зеркала (FL-FP-NEUTRAL / FL-PROPERTY-FAITHFUL)")
    print(HDR)
    ok = True

    for tag, kw in (("владение без наследования", dict(inherit=False, frailty="off")),
                    ("наследование+сенесценция", dict(inherit=True, frailty="gompertz")),
                    ("клейма (extort_reputation)", dict(inherit=True, frailty="gompertz", marks=True))):
        w_off, s_off, _, k_off, _ = _drive(scene(ledger=False, **kw))
        w_on, s_on, mism, k_on, mmis = _drive(scene(ledger=True, **kw), check_replay=True)
        A, B = _state(w_off), _state(w_on)

        neutral = (s_off == s_on) and A == B
        faithful = not mism
        off_clean = not k_off                      # OFF emits nothing new
        marks_ok = not mmis
        ok = ok and neutral and faithful and off_clean and marks_ok

        print(f"\n[{tag}]")
        print(f"  FL-FP-NEUTRAL   fp-поток {s_off} vs {s_on} {'✓' if s_off == s_on else '✗'} · "
              f"polis_fp {'✓' if A['polis_fp'] == B['polis_fp'] else '✗'} · "
              f"cellmap {'✓' if A['cellmap'] == B['cellmap'] else '✗'} · "
              f"_house {'✓' if A['house'] == B['house'] else '✗'} · "
              f"pop/appr {'✓' if (A['pop'], A['appr']) == (B['pop'], B['appr']) else '✗'}")
        print(f"  OFF-инвариантность: событий зеркала при faithful_ledger=False = "
              f"{sum(k_off.values())} {'✓' if off_clean else '✗'}")
        print(f"  эмитировано (ON): {dict(sorted(k_on.items())) or 'нет'}")
        if faithful:
            print(f"  FL-PROPERTY-FAITHFUL ✓ реплей == _cell_owner на ВСЕХ {DAYS} тиках "
                  f"(итог {B['cells']} клеток, наследований {B['inh']})")
        else:
            print(f"  FL-PROPERTY-FAITHFUL ✗ расхождений на {len(mism)} тиках; первые: {mism[:3]}")
        print(f"  FL-MARK-FAITHFUL {'✓ реплей клейм == живые клейма на всех тиках' if marks_ok else f'✗ расхождений {len(mmis)}: {mmis[:3]}'}")
        m = _fl_mass(w_on)
        mass_ok = (not m["bad_cells"]) and m["delta"] < 1e-6
        ok = ok and mass_ok
        print(f"  FL-MASS  (а) баланс по клетке Σpaid==Σgot==dm: "
              f"{'✓ во всех ' + str(m['n_events']) + ' событиях' if not m['bad_cells'] else '✗ ' + str(len(m['bad_cells'])) + ' битых: ' + str(m['bad_cells'][:2])}")
        print(f"           (б) Σ dm по логу = {m['gross']:.6f} · канон _appropriated_total = "
              f"{m['canon_total']:.6f} · Δ = {m['delta']:.2e} {'✓' if m['delta'] < 1e-6 else '✗'}")

    print(f"\n{HDR}")
    print(f"Ф1: {'✓ журнал стал зеркалом владения — и мир не сдвинулся' if ok else '✗ СТОП'}")
    print(HDR)
    assert ok, "Ф1: mirror is not faithful or not neutral"
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
