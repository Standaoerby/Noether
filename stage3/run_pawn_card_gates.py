"""run_pawn_card_gates.py — E1 Ф1 gates: E1-VOFF / E1-DET / E1-FAITHFUL.

  E1-VOFF      a run under the card reader keeps its fingerprints — state_fingerprint AND
               polis_fingerprint equal a clean run's. The reader reads public state and the
               log; it never touches the world (the glass pattern).

  E1-DET       the same scene/seed yields a byte-identical card: the SHA-256 over the
               canonical dump (sorted keys, compact) repeats across independent runs.

  E1-FAITHFUL  Applies to the LOG-DERIVED cards. Replaying seed/birth/death from the journal
               ALONE must reproduce the live population exactly at every checkpoint — the
               `reconstruct_live` principle of sim_eventlog (its grid half is hard-wired to
               the 5×5 MicroWorld, so we reuse the principle, not the function, on the 14×14
               Polis). Chronicle/House stand on this.

  E1-FAITHFUL-OWN   (виток 2). Property moved from snapshots to the log, so the subgate that
               was vacuous in виток 1 becomes the sharpest one here. Two layers:
                 (a) LEDGER  — `replay_owners(log)` == the real `_cell_owner`, at EVERY tick,
                     not just checkpoints. This is the mirror claim itself.
                 (b) READER  — the log-derived `property_history` == a snapshot-derived oracle
                     of the same pawn. The oracle is the виток-1 code, kept HERE (deleted from
                     the card) precisely because it is now an INDEPENDENT source: snapshots
                     mirror `_cell_owner` directly, the card no longer sees them at all. Two
                     sources, one answer — or the gate is red.

Run:  py stage3/run_pawn_card_gates.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "Code"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sim_eventlog import EventLog                                       # noqa: E402
from stage3.polis import Polis, polis_fingerprint                       # noqa: E402
from stage3.viz_export import run_capture                               # noqa: E402
from stage3.pawn_card import (pawn_card, card_sha, replay_owners,       # noqa: E402
                              extort_share, power_flow, arc_inputs,
                              arc_from, arc_evidence, _arc_of,
                              ARC_INPUTS, _dig)
from stage3.export_pawn_card import e1_scene                            # noqa: E402

HDR = "=" * 78
FOCAL = 58          # the flagship: founder, 320 ticks a landholder, 174 seizures — and net NEGATIVE
CONTRAST = 42       # the contrast: preyed on 387 times, and the scene's actual sovereign (+190 kg)
CHECKPOINTS = (50, 150, 300, 400)


def _scene(days=400):
    """The E1 scene, imported from the exporter so gate and artifact can never drift apart.
    G2 ON *and* intent_policy='reflex' (without the intent layer the extort seam is skipped
    and the power projections come out empty — виток-1 Ф0), plus `faithful_ledger=True`
    (виток 2): with the mirror off there are no claim/lose/inherit events and Property would
    be empty rather than wrong, which is the failure mode a gate must not sleep through."""
    return e1_scene(seed=7, days=days)


class _ExtortProbe(Polis):
    """Wraps `_extort` on the stage3 side (canon and polis.py untouched — the `_do_claims` /
    `_appropriate` precedent) and records the REAL per-pawn body deltas the seizure produced.

    This is what makes PF-SHARE a verification instead of a reading: the card attributes each
    taker's share by replaying the documented split rule, and this probe measures what the
    bodies actually did. If the two disagree, the card is over-attributing — the exact class
    of error the виток-1 `mass_extorted` had."""

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.gain, self.loss = {}, {}          # (t, oid) -> mass

    def _extort(self, t):
        before = {a.oid: a.body for a in self.pop}
        super()._extort(t)                     # the mechanism runs unchanged
        for a in self.pop:
            d = a.body - before.get(a.oid, a.body)
            if d > 1e-12:
                self.gain[(t, a.oid)] = self.gain.get((t, a.oid), 0.0) + d
            elif d < -1e-12:
                self.loss[(t, a.oid)] = self.loss.get((t, a.oid), 0.0) - d


def _property_from_snapshots(snapshots, oid):
    """The виток-1 snapshot-derived Property, kept HERE as an independent oracle for
    E1-FAITHFUL-OWN(b). Verbatim logic; `owners` mirrors `_cell_owner` per tick."""
    timeline, held_ticks = [], 0
    for s in snapshots:
        cells = sorted((i, j) for (i, j, o) in s.get("owners", ()) if o == oid)
        if cells:
            held_ticks += 1
        timeline.append((s["t"], cells))
    tenures, cur = [], None
    for t, cells in timeline:
        if cells and cur is None:
            cur = {"from_t": t, "to_t": t, "peak_cells": len(cells), "cells_seen": set(cells)}
        elif cells:
            cur["to_t"] = t
            cur["peak_cells"] = max(cur["peak_cells"], len(cells))
            cur["cells_seen"] |= set(cells)
        elif cur is not None:
            cur["cells_seen"] = [list(c) for c in sorted(cur["cells_seen"])]
            tenures.append(cur); cur = None
    if cur is not None:
        cur["cells_seen"] = [list(c) for c in sorted(cur["cells_seen"])]
        tenures.append(cur)
    return {
        "tenures": tenures,
        "n_tenures": len(tenures),
        "ticks_holding": held_ticks,
        "peak_cells": max((len(c) for _t, c in timeline), default=0),
        "final_cells": [list(c) for c in (timeline[-1][1] if timeline else [])],
    }


def _clean_run(cfg):
    w = Polis(EventLog(), cfg)
    for _ in range(cfg.days):
        w.step()
    return w


def _live_from_log(events, T):
    """The reconstruct_live PRINCIPLE: replay individual seed/birth/death up to T from the
    journal alone -> the set of living oids."""
    live = set()
    for e in events:
        if e.t > T:
            break
        if e.scale != "individual":
            continue
        if e.kind in ("seed", "birth"):
            live.add(e.actor)
        elif e.kind == "death":
            live.discard(e.actor)
    return live


def main():
    print(HDR)
    print(f"E1 Ф1 — gates for the pawn card (scene: G2-ON + intent=reflex, focal oid={FOCAL})")
    print(HDR)
    cfg = _scene()

    # ---- E1-VOFF ---------------------------------------------------------- #
    w_read, snaps = run_capture(cfg, every=1)
    card = pawn_card(w_read.log, snaps, FOCAL)
    w_clean = _clean_run(_scene())
    sf_ok = w_read.state_fingerprint() == w_clean.state_fingerprint()
    pf_ok = polis_fingerprint(w_read) == polis_fingerprint(w_clean)
    print("E1-VOFF — the reader must not move the world:")
    print(f"    state_fingerprint  reader={w_read.state_fingerprint()} clean={w_clean.state_fingerprint()} {'✓' if sf_ok else '✗'}")
    print(f"    polis_fingerprint  reader={polis_fingerprint(w_read)} clean={polis_fingerprint(w_clean)} {'✓' if pf_ok else '✗'}")
    voff = sf_ok and pf_ok

    # ---- E1-FAITHFUL ------------------------------------------------------ #
    print("\nE1-FAITHFUL — log-replayed live set == real population at every checkpoint:")
    faithful = True
    w2 = Polis(EventLog(), _scene())
    for t in range(1, cfg.days + 1):
        w2.step()
        if t in CHECKPOINTS:
            real = {a.oid for a in w2.pop}
            fromlog = _live_from_log(w2.log.events, t)
            same = real == fromlog
            faithful = faithful and same
            print(f"    t={t:<4} real={len(real):<5} from-log={len(fromlog):<5} "
                  f"{'✓ идентичны' if same else f'✗ Δ={len(real ^ fromlog)}'}")

    # ---- E1-FAITHFUL-OWN (a): the ledger IS the ownership ------------------ #
    print("\nE1-FAITHFUL-OWN(a) — реплей claim/lose/inherit == _cell_owner, на КАЖДОМ тике:")
    w3 = Polis(EventLog(), _scene())
    owner, cur = {}, 0                      # incremental replay (same rule as replay_owners)
    own_ok, first_bad, n_ev = True, None, 0
    for t in range(1, cfg.days + 1):
        w3.step()
        ev = w3.log.events
        while cur < len(ev):
            e = ev[cur]; cur += 1
            if e.kind in ("claim", "inherit"):
                owner[tuple(e.where)] = e.actor; n_ev += 1
            elif e.kind == "lose":
                owner.pop(tuple(e.where), None); n_ev += 1
        real = {tuple(c): o for c, o in w3._cell_owner.items()}
        if owner != real:
            own_ok = False
            if first_bad is None:
                first_bad = (t, sorted(set(owner.items()) ^ set(real.items()))[:4])
        if t in CHECKPOINTS:                # and the SHIPPED function, not just this loop
            shipped = replay_owners(ev, upto=t)
            hit = shipped == real
            own_ok = own_ok and hit
            print(f"    t={t:<4} клеток по логу={len(shipped):<4} по _cell_owner={len(real):<4} "
                  f"{'✓ карта совпадает' if hit else '✗ РАСХОЖДЕНИЕ'}")
    print(f"    все {cfg.days} тиков, событий владения в логе={n_ev}: "
          f"{'✓ ни одного расхождения' if own_ok else f'✗ первое на t={first_bad[0]}: {first_bad[1]}'}")

    # ---- E1-FAITHFUL-OWN (b): reader vs independent snapshot oracle -------- #
    pr = card["property"]
    orc = _property_from_snapshots(snaps, FOCAL)
    keys = ("n_tenures", "ticks_holding", "peak_cells", "final_cells")
    read_ok = all(pr[k] == orc[k] for k in keys)
    ten_ok = ([(x["from_t"], x["to_t"], x["peak_cells"], x["cells_seen"]) for x in pr["tenures"]]
              == [(x["from_t"], x["to_t"], x["peak_cells"], x["cells_seen"]) for x in orc["tenures"]])
    read_ok = read_ok and ten_ok
    print(f"\nE1-FAITHFUL-OWN(b) — Property из ЛОГА vs независимый снимковый оракул (#{FOCAL}):")
    for k in keys:
        print(f"    {k:<14} лог={pr[k]}   снимки={orc[k]}  {'✓' if pr[k] == orc[k] else '✗'}")
    print(f"    tenures (от/до/пик/клетки) совпадают: {'✓' if ten_ok else '✗'}")
    print(f"    источник карточки: {pr['source']}   акты владения в карточке: {pr['n_acts']}")
    faithful_own = own_ok and read_ok

    # ---- PF-SHARE: the split rule, verified against real bodies ------------ #
    print("\nPF-SHARE — приписанная доля вымогателя vs РЕАЛЬНАЯ дельта тела:")
    wp = _ExtortProbe(EventLog(), _scene())
    for _ in range(cfg.days):
        wp.step()
    probe_clean = (wp.state_fingerprint() == w_clean.state_fingerprint()
                   and polis_fingerprint(wp) == polis_fingerprint(w_clean))
    print(f"    обёртка _extort прозрачна: state_fp {wp.state_fingerprint()} "
          f"{'✓' if probe_clean else '✗ ЗОНД СДВИНУЛ МИР'}")
    claimed = {}                       # (t, oid) -> share replayed from the log
    seized = {}                        # (t, oid) -> pooled loss the log ascribes to victims
    for e in wp.log.events:
        if e.kind != "extort":
            continue
        d = e.data or {}
        ts, vs = list(d.get("takers") or []), list(d.get("victims") or [])
        total = float(e.dm if e.dm is not None else (d.get("amount") or 0.0))
        for o in ts:
            claimed[(e.t, o)] = claimed.get((e.t, o), 0.0) + extort_share(total, ts, o)
        if len(vs) == 1:               # the only case the card claims is resolvable
            seized[(e.t, vs[0])] = seized.get((e.t, vs[0]), 0.0) + total
    worst_g = max((abs(v - wp.gain.get(k, 0.0)) for k, v in claimed.items()), default=0.0)
    miss_g = sorted(set(claimed) ^ set(wp.gain))
    worst_l = max((abs(v - wp.loss.get(k, 0.0)) for k, v in seized.items()), default=0.0)
    share_ok = (not miss_g) and worst_g < 1e-9 and worst_l < 1e-9
    print(f"    событий extort={sum(1 for e in wp.log.events if e.kind=='extort')}, "
          f"пар (тик,такер)={len(claimed)}, измеренных приростов={len(wp.gain)}")
    print(f"    max |приписано - реально получено|   = {worst_g:.3e}  "
          f"{'✓' if worst_g < 1e-9 else '✗'}   (несопоставленных пар: {len(miss_g)})")
    print(f"    max |приписано - реально утрачено|   = {worst_l:.3e}  "
          f"{'✓' if worst_l < 1e-9 else '✗'}   (только одиночные жертвы, n={len(seized)})")
    # and the mirror claim: multi-victim seizures are genuinely NOT resolvable from the log
    multi = [e for e in wp.log.events if e.kind == "extort"
             and len(((e.data or {}).get("victims") or [])) > 1]
    if multi:
        e0 = multi[0]
        vs0 = sorted((e0.data or {}).get("victims") or [])
        real = [round(wp.loss.get((e0.t, v), 0.0), 6) for v in vs0]
        print(f"    много-жертвенных событий={len(multi)}; пример t={e0.t}: жертвы {vs0}, "
              f"реально утрачено {real} — из лога (только пул {round(float(e0.dm), 6)}) не выводимо ✓")
    else:
        print(f"    много-жертвенных событий в этой сцене нет (n=0) — правило п.3 не активируется")

    # ---- PF-BALANCE: the flows close against the canonical aggregates ------ #
    everyone = sorted({a.oid for a in wp.pop} |
                      {e.actor for e in wp.log.events if e.actor is not None})
    sum_att = sum(power_flow(wp.log, o)["totals"]["extort_attributed"] for o in everyone)
    canon_ext = float(getattr(wp, "_extorted_total", 0.0))
    bal_ok = abs(sum_att - canon_ext) < 1e-6
    print(f"\nPF-BALANCE — Σ приписанных долей по ВСЕМ пешкам vs канон-агрегат:")
    print(f"    Σ extort_attributed = {sum_att:.6f}   _extorted_total = {canon_ext:.6f}  "
          f"{'✓ сходится' if bal_ok else '✗ РАСХОДИТСЯ'}")

    # ---- REP-FAITHFUL: mark/unmark replay == the real mark-ledgers --------- #
    print("\nREP-FAITHFUL — реплей mark/unmark == живое содержимое G2-реестров:")
    rep_ok, marked = True, {"extort": set(), "delegate": set()}
    for e in wp.log.events:
        if e.kind in ("mark", "unmark"):
            led = (e.data or {}).get("ledger")
            (marked[led].add if e.kind == "mark" else marked[led].discard)(e.actor)
    live = {a.oid for a in wp.pop}
    for led, attr in (("extort", "_extort_marks"), ("delegate", "_delegate_marks")):
        real = set(getattr(wp, attr, ()) or ()) & live
        hit = (marked[led] & live) == real
        rep_ok = rep_ok and hit
        print(f"    {led:<9} по логу={len(marked[led] & live):<5} в реестре={len(real):<5} "
              f"{'✓' if hit else '✗'}   (всего клейм в логе: {len(marked[led])})")

    power_ok = share_ok and bal_ok and rep_ok and probe_clean

    # ---- E1-ARC-BACKED: the label must be arithmetic, not assertion -------- #
    print("\nE1-ARC-BACKED — ярлык дуги подкреплён показанными числами (гейт честности D4):")
    arc_ok = True
    for oid in (FOCAL, CONTRAST):
        c = pawn_card(w_read.log, snaps, oid)
        inp, ev = arc_inputs(c), arc_evidence(c)
        label = _arc_of(c)
        # (1) the label is a pure function of the evidence — recompute it from that alone
        pure = arc_from(inp) == label
        # (2) every evidence value is a VERBATIM field of the card, none invented for the
        #     caption — re-dig each one by its declared path and compare
        verbatim = all(val == _dig(c, path)
                       for (_lab, val), (_lab2, path) in zip(ev, ARC_INPUTS))
        # (3) the discriminating number is LOAD-BEARING: flip it and the label must flip.
        #     A caption that survives its own numbers changing is decoration, not evidence.
        flipped = dict(inp)
        flipped["net"] = -abs(inp["net"]) - 1.0 if inp["net"] >= 0 else abs(inp["net"]) + 1.0
        moved = arc_from(flipped) != label
        arc_ok = arc_ok and pure and verbatim and moved
        print(f"    #{oid} «{label}»")
        print(f"        выводим из показанных чисел: {'✓' if pure else '✗'}; "
              f"все значения — поля карточки: {'✓' if verbatim else '✗'}")
        print(f"        нетто={inp['net']} несущее (перевернув знак -> «{arc_from(flipped)}»): "
              f"{'✓' if moved else '✗ ЯРЛЫК НЕ ЗАВИСИТ ОТ ЧИСЛА'}")
        print(f"        подкреплён: " + "; ".join(f"{k}={v}" for k, v in ev))

    # ---- E1-DET ----------------------------------------------------------- #
    w_b, snaps_b = run_capture(_scene(), every=1)
    card_b = pawn_card(w_b.log, snaps_b, FOCAL)
    det = card["sha"] == card_b["sha"] and card_sha(card) == card["sha"]
    print(f"\nE1-DET — same scene => byte-identical card:")
    print(f"    sha run A = {card['sha']}   sha run B = {card_b['sha']}  {'✓' if det else '✗'}")

    # ---- the card itself (sanity of the four projections) ------------------ #
    ch, ho, re_, pr = card["chronicle"], card["house"], card["relationships"], card["property"]
    print(f"\nкарточка oid={FOCAL}:")
    print(f"    chronicle : origin={ch['origin'] and ch['origin']['kind']} "
          f"death t={ch['death'] and ch['death']['t']} возраст={ch['death'] and ch['death']['age']} "
          f"актов={ch['n_acts']} потомков={len(ch['descendants'])}")
    print(f"    house     : root={ho['house_root']} основатель={ho['is_founder']} "
          f"глубина={ho['generation_depth']} детей={ho['n_children']} размер дома={ho['house_size']}")
    print(f"    relations : знал={re_['n_known']} говорил={re_['totals']['n_spoke']} "
          f"слышал={re_['totals']['n_heard']} вымогал={re_['totals']['n_extorted']}× "
          f"(брутто {re_['totals']['mass_extorted_gross']} кг) "
          f"у него отняли={re_['totals']['n_extorted_by']}×")
    print(f"    property  : владений={pr['n_tenures']} тиков с землёй={pr['ticks_holding']} "
          f"пик={pr['peak_cells']} клеток, финал={len(pr['final_cells'])}")
    rp, pw = card["reputation"], card["power"]
    print(f"    reputation: клеймён когда-либо={rp['ever_branded']} тиков под клеймом="
          f"{rp['ticks_branded']} реестры={sorted(rp['by_ledger']) or '—'}")
    r, T, co = pw["roles"], pw["totals"], pw["coincidence"]
    print(f"    power     : РОЛИ РАЗДЕЛЬНО — аппроприация: плательщик={r['appropriate']['payer']} "
          f"получатель={r['appropriate']['receiver']}; вымогательство: такер={r['extort']['taker']} "
          f"(из них actor={r['extort']['taker_as_actor']}) жертва={r['extort']['victim']}; "
          f"ремитта: отдал={r['delegate_remit']['remitter']} принял={r['delegate_remit']['root']}")
    print(f"                масса: рента уплачена={T['rent_paid']} получена={T['rent_received']}; "
          f"вымогательство брутто={T['extort_gross']} ПРИПИСАНО={T['extort_attributed']} "
          f"соло={T['extort_solo']}; нетто={T['net']}")
    print(f"                совпадение ролей: платил и отнимал в одном (тик,клетка) "
          f"{co['paid_and_took_same_tick_cell']}× из {co['of_n_paid']}; "
          f"жертва == рантье {co['victim_was_the_landlord']}×")

    ok = voff and faithful and faithful_own and power_ok and arc_ok and det
    print(f"\n  E1-VOFF {'✓' if voff else '✗'} · E1-FAITHFUL {'✓' if faithful else '✗'} · "
          f"E1-FAITHFUL-OWN {'✓' if faithful_own else '✗'} · PF-SHARE/BALANCE/REP "
          f"{'✓' if power_ok else '✗'} · E1-ARC-BACKED {'✓' if arc_ok else '✗'} · "
          f"E1-DET {'✓' if det else '✗'}")
    print(HDR)
    assert voff, "E1-VOFF: the reader moved the world"
    assert faithful, "E1-FAITHFUL: the log does not reproduce the live population"
    assert faithful_own, "E1-FAITHFUL-OWN: the ledger is not a mirror of ownership"
    assert power_ok, "PF-SHARE/PF-BALANCE/REP-FAITHFUL: the flow attribution does not hold"
    assert arc_ok, "E1-ARC-BACKED: the arc label is not backed by shown, load-bearing numbers"
    assert det, "E1-DET: the card is not deterministic"
    assert ok
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
