"""run_faithful_ledger_probe.py — faithful-ledger Ф0: feasibility + fp-safety.

The WO's Ф0 asks two questions before a single event is emitted:

  (1) Is emission fp-SAFE? The claim is that the log is not part of any fingerprint, so
      appending events cannot move an anchor. Reading the code says yes — `state_fingerprint`
      hashes census+pop+matter, `appropriation_fingerprint` hashes rho/owner_policy/
      _appropriated_total/counts, `polis_fingerprint` adds _voice_log/_groom_log/_typed_log
      (separate attributes, NOT the EventLog). But there is one state-AFFECTING log reader:
      `_update_houses` scans `self.log.events` to build `_house`, which drives inheritance and
      therefore `_cell_owner`. So this probe does not argue — it INJECTS junk events every
      tick and checks that nothing moves, including in the worst case (_house active).

  (2) What is recoverable WITHOUT touching canon? Ownership / inheritance / marks come from
      diffing public state. The WO assumed per-pair APPROPRIATION attribution needs a canon
      edit (only the `_appropriated_total` scalar is published). This probe tests that premise
      by wrapping `_appropriate` in a Polis subclass — the same stage3 override path `_do_claims`
      already uses (precedent: MH2-OFF) — and diffing bodies around `super()._appropriate()`.

Run:  py stage3/run_faithful_ledger_probe.py
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
DAYS = 200
PROBE_KINDS = ("claim", "lose", "inherit", "mark", "appropriate")   # the proposed vocabulary


def scene(days=DAYS, inherit=False, frailty="off"):
    c = build_showcase_cfg(seed=7, days=days, extort_on=True, delegate_on=True,
                           revoke_tooth="reputation", extort_enforcers=3,
                           delegate_enforcers=2, intent_policy="reflex")
    c.inherit_on = inherit
    c.frailty = frailty
    return c


class _FlowProbe(Polis):
    """Wraps `_appropriate` on the stage3 side (canon untouched) and recovers the per-cell
    payer/receiver deltas the canonical routine leaves unpublished."""

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.flows = []
        self._probe_paid = 0.0

    def _appropriate(self):
        before = {a.oid: a.body for a in self.pop}
        pos = {a.oid: (a.i, a.j) for a in self.pop}
        super()._appropriate()                       # canon does the work, unchanged
        paid = 0.0
        for a in self.pop:
            d = a.body - before.get(a.oid, a.body)
            if abs(d) > 1e-12:
                self.flows.append((self.t, pos[a.oid], a.oid, d))
                if d < 0:
                    paid += -d
        self._probe_paid = paid


def _drive(cls, cfg, inject=False):
    w = cls(EventLog(), cfg)
    h = hashlib.sha256()
    paid = 0.0
    for _ in range(cfg.days):
        w.step()
        if inject:
            for k in PROBE_KINDS:
                w.log.emit(w.t, k, "individual", where=(1, 1), actor=999999,
                           dm=0.0, data={"probe": True})
        h.update(w.state_fingerprint().encode())
        paid += getattr(w, "_probe_paid", 0.0)
    return w, h.hexdigest()[:16], paid


def _state_of(w):
    return {
        "polis_fp": polis_fingerprint(w),
        "state_fp": w.state_fingerprint(),
        "cells": len(w._cell_owner),
        "cellmap": sorted(w._cell_owner.items()),
        "owners": len(w.owner_ids()),
        "house": len(getattr(w, "_house", {}) or {}),
        "housemap": sorted((getattr(w, "_house", {}) or {}).items()),
        "pop": len(w.pop),
        "inherit_events": int(getattr(w, "_inherit_events", 0)),
        "appropriated": round(float(getattr(w, "_appropriated_total", 0.0)), 6),
    }


def main():
    print(HDR)
    print("faithful-ledger Ф0 — можно ли эмитить, ничего не сдвинув, и что видно без канона")
    print(HDR)

    ok = True
    # ---- (1) fp-safety, including the worst case (_house active) ------------ #
    for tag, kw in (("_house ВЫКЛ", dict(inherit=False, frailty="off")),
                    ("_house АКТИВЕН (inherit+gompertz)", dict(inherit=True, frailty="gompertz"))):
        wa, sa, _ = _drive(Polis, scene(**kw), inject=False)
        wb, sb, _ = _drive(Polis, scene(**kw), inject=True)
        A, B = _state_of(wa), _state_of(wb)
        same = (sa == sb) and A == B
        ok = ok and same
        print(f"\n[1] впрыск {len(PROBE_KINDS)} событий/тик · {tag}")
        print(f"    fp-поток   {sa} vs {sb}  {'✓' if sa == sb else '✗'}")
        print(f"    polis_fp   {A['polis_fp']} vs {B['polis_fp']}  {'✓' if A['polis_fp'] == B['polis_fp'] else '✗'}")
        print(f"    _cell_owner карта идентична: {'✓' if A['cellmap'] == B['cellmap'] else '✗'}  "
              f"(клеток {A['cells']})")
        print(f"    _house карта идентична:      {'✓' if A['housemap'] == B['housemap'] else '✗'}  "
              f"(записей {A['house']}, наследований {A['inherit_events']})")
        print(f"    pop/appropriated: {A['pop']}/{A['appropriated']} vs {B['pop']}/{B['appropriated']}  "
              f"{'✓' if (A['pop'], A['appropriated']) == (B['pop'], B['appropriated']) else '✗'}")

    # ---- (2) are appropriation pairs recoverable without canon? ------------- #
    cfg = scene()
    wc, sc, _ = _drive(Polis, cfg)
    wp, sp, paid = _drive(_FlowProbe, scene(), inject=False)
    C, P = _state_of(wc), _state_of(wp)
    transparent = (sc == sp) and C == P
    balances = abs(paid - P["appropriated"]) < 1e-6
    ok = ok and transparent and balances
    print(f"\n[2] пары аппроприации через обёртку _appropriate (stage3-путь, канон не тронут)")
    print(f"    обёртка прозрачна: fp-поток {sc} vs {sp} {'✓' if sc == sp else '✗'}; "
          f"состояние идентично {'✓' if C == P else '✗'}")
    print(f"    собрано дельт-записей: {len(wp.flows)}")
    print(f"    Σ уплаченного по дельтам = {paid:.6f}")
    print(f"    канонический агрегат     = {P['appropriated']:.6f}")
    print(f"    сходится: {'✓ дельты тел == канон-агрегат' if balances else '✗'}")

    print(f"\n{HDR}")
    print("ВЫВОД Ф0:")
    print("  • эмиссия событий fp-НЕЙТРАЛЬНА — лог не входит ни в один отпечаток, и"
          " _update_houses\n    фильтрует по kind (курсор монотонен), так что впрыск не двигает даже _house;")
    print("  • claim/lose/inherit/mark — восстановимы диффом публичного состояния (канон не нужен);")
    print("  • ПАРЫ аппроприации ТОЖЕ восстановимы без канона — обёртка _appropriate по образцу"
          "\n    _do_claims даёт плательщиков/получателей по клетке, сходясь с _appropriated_total.")
    print(HDR)
    assert ok, "Ф0: emission is NOT neutral, or the flow probe does not balance"
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
