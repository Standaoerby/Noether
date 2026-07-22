"""run_slice_gates.py — E2 gates (Ф1-Ф3): E2-VOFF / E2-DET / E2-SYNC / E2-HONEST.

  E2-VOFF   the slice export is a READER: a run under it keeps state_fingerprint AND
            polis_fingerprint equal to a clean run's. Same glass pattern as V-OFF / E1-VOFF.

  E2-DET    same scene + same foci -> byte-identical package (package SHA over
            meta.json + snapshots.jsonl + events.jsonl, the anchor a slice can be pinned by).

  E2-SYNC   the core of E2, and the one that decides whether the game LIES about what is
            happening. Everything the slice shows must reduce to ONE tick T:
              (a) OWNERSHIP — replaying claim/lose/inherit from the SLICE package up to T
                  equals the snapshot's `owners` at T. Not sampled: every tick.
              (b) POSITION  — the focus appears in the snapshot at T exactly while it is
                  alive by the journal (birth/seed .. death), and nowhere else.
              (c) GLOBALITY — the invariant that makes (a) possible at all. The slice cuts
                  `known` to focus edges, but ownership events stay GLOBAL: of 175 claims in
                  this scene only 3 involve a focus, so a focus-only ledger would keep 1.7%
                  of it. The gate proves the shipped package is not focus-filtered by
                  showing the replay reconstructs cells the focus never touched.

  E2-HONEST (Ф3) no caption without an EVENT AT ITS OWN TICK. The caption layer is a
            projection of the same events the map draws — generated once at export time and
            shipped inside the package, never composed on the client — so a line can be held
            to the event that licenses it. Also checks that every caption carries the numbers
            it stands on, that the flow pruning is DECLARED rather than silent, and that the
            E1 card anchors did not move (captions live in the entry, not inside `card`).

These read the PACKAGE ON DISK, not an in-memory object — the artifact is what the front
consumes, so the artifact is what gets gated. The ownership replay uses the SHIPPED
`pawn_card.replay_owners`, not a copy, so the gate cannot drift from the reader.

Run:  py stage3/run_slice_gates.py
"""
from __future__ import annotations

import json
import os
import sys
from collections import namedtuple

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "Code"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sim_eventlog import EventLog                                       # noqa: E402
from stage3.polis import Polis, polis_fingerprint                       # noqa: E402
from stage3 import viz_export as vx                                     # noqa: E402
from stage3.pawn_card import replay_owners                              # noqa: E402
from stage3.export_pawn_card import e1_scene                            # noqa: E402

HDR = "=" * 78
FOCI = [58, 42]
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SLICE_DIR = os.path.join(ROOT, "viz", "slice", "data")

# the shape `replay_owners` reads: kind / where / t. The package rows carry `type`, so the
# adapter is one line and the SHIPPED replay is what runs.
_Row = namedtuple("_Row", "t kind where actor data")


def _rows(path):
    out = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            e = json.loads(line)
            w = e.get("where")
            out.append(_Row(e["t"], e["type"], tuple(w) if w else None,
                            e.get("actor"), e.get("data") or {}))
    return out


def _snaps(path):
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh]


def _clean(cfg):
    w = Polis(EventLog(), cfg)
    for _ in range(cfg.days):
        w.step()
    return w


def main():
    print(HDR)
    print(f"E2 — gates for the pawn slice (scene: E1 виток-2, foci={FOCI})")
    print(HDR)
    cfg = e1_scene(seed=7, days=400)

    # ---- export A (and E2-VOFF against a clean run) ------------------------ #
    a = vx.export(SLICE_DIR, cfg=e1_scene(seed=7, days=400), every=1,
                  slice_foci=FOCI, verbose=False)
    w_read = a["world"]
    w_clean = _clean(e1_scene(seed=7, days=400))
    sf = w_read.state_fingerprint() == w_clean.state_fingerprint()
    pf = polis_fingerprint(w_read) == polis_fingerprint(w_clean)
    voff = sf and pf
    print("E2-VOFF — экспорт слайса мир не двигает:")
    print(f"    state_fingerprint  {w_read.state_fingerprint()} vs {w_clean.state_fingerprint()} "
          f"{'✓' if sf else '✗'}")
    print(f"    polis_fingerprint  {polis_fingerprint(w_read)} vs {polis_fingerprint(w_clean)} "
          f"{'✓' if pf else '✗'}")

    sm = a["meta"]["slice"]
    print(f"\nпакет: события {sm['n_events_before']} -> {sm['n_events_after']}, "
          f"рёбра known {sm['known_edges_before']} -> {sm['known_edges_after']}")
    # every file of the package, cards.json included — a budget check that quietly omits a
    # member of the artifact is a budget check that under-reports
    total = sum(os.path.getsize(os.path.join(SLICE_DIR, f)) for f in a["shas"])
    print(f"       {total/1e6:.2f} МБ из бюджета 15 МБ "
          f"{'✓' if total < 15e6 else '✗ ПРЕВЫШЕН'}")

    # ---- E2-DET ------------------------------------------------------------ #
    import tempfile
    b = vx.export(os.path.join(tempfile.gettempdir(), "e2_det_probe"),
                  cfg=e1_scene(seed=7, days=400), every=1, slice_foci=FOCI, verbose=False)
    det = a["package_sha"] == b["package_sha"]
    print(f"\nE2-DET — та же сцена и фокусы => байт-идентичный пакет:")
    print(f"    package SHA A = {a['package_sha'][:32]}")
    print(f"    package SHA B = {b['package_sha'][:32]}  {'✓' if det else '✗'}")

    # ---- E2-SYNC ----------------------------------------------------------- #
    print("\nE2-SYNC — всё показанное сводится к ОДНОМУ тику T:")
    ev = _rows(os.path.join(SLICE_DIR, "events.jsonl"))
    snaps = _snaps(os.path.join(SLICE_DIR, "snapshots.jsonl"))

    # (a) ownership: replay from the package == the snapshot's owners, EVERY tick
    owner, cur, bad_own, checked = {}, 0, None, 0
    for s in snaps:
        t = s["t"]
        while cur < len(ev) and ev[cur].t <= t:
            e = ev[cur]; cur += 1
            if e.kind in ("claim", "inherit"):
                owner[e.where] = e.actor
            elif e.kind == "lose":
                owner.pop(e.where, None)
        real = {(i, j): o for (i, j, o) in s["owners"]}
        checked += 1
        if owner != real and bad_own is None:
            bad_own = (t, sorted(set(owner.items()) ^ set(real.items()))[:4])
    own_ok = bad_own is None
    print(f"    (a) владение: реплей пакета == owners снимка на всех {checked} тиках  "
          f"{'✓' if own_ok else f'✗ первое расхождение t={bad_own[0]}: {bad_own[1]}'}")

    # and the SHIPPED reader must agree with this loop at the end of the run
    shipped = replay_owners(ev)
    ship_ok = shipped == owner
    print(f"        та же карта из pawn_card.replay_owners (общий с карточкой ридер): "
          f"{'✓' if ship_ok else '✗'}  (клеток {len(shipped)})")

    # (b) position: the focus is in the snapshot exactly while it is alive
    pos_ok = True
    for oid in FOCI:
        # no silent fallback: a missing origin event must SHOW, not default to 0 — that
        # default is what let a caption stand at t=0 with nothing in the package behind it
        origin = [e.t for e in ev if e.kind in ("birth", "seed") and e.actor == oid]
        if not origin:
            pos_ok = False
            print(f"    (b) позиция #{oid}: ✗ в пакете НЕТ события рождения/посева")
            continue
        born = origin[0]
        died = next((e.t for e in ev if e.kind == "death" and e.actor == oid), None)
        present = {s["t"] for s in snaps if any(p[0] == oid for p in s["pawns"])}
        expect = {s["t"] for s in snaps
                  if s["t"] >= born and (died is None or s["t"] < died)}
        hit = present == expect
        pos_ok = pos_ok and hit
        print(f"    (b) позиция #{oid}: в снимках на {len(present)} тиках, жива по журналу на "
              f"{len(expect)} (born={born}, death={died})  "
              f"{'✓' if hit else f'✗ Δ={len(present ^ expect)}'}")

    # (c) globality: the ledger is NOT focus-filtered — prove it by counting cells the replay
    #     reconstructs that no focus ever owned. A focus-only slice could not produce them.
    fset = set(FOCI)
    focus_cells = {e.where for e in ev if e.kind in ("claim", "inherit") and e.actor in fset}
    all_cells = {e.where for e in ev if e.kind in ("claim", "inherit")}
    n_claims = sum(1 for e in ev if e.kind == "claim")
    n_focus_claims = sum(1 for e in ev if e.kind == "claim" and e.actor in fset)
    glob_ok = len(all_cells - focus_cells) > 0 and n_claims > n_focus_claims
    print(f"    (c) глобальность реестра: claim всего {n_claims}, из них у фокуса "
          f"{n_focus_claims}; клеток вне фокуса {len(all_cells - focus_cells)}  "
          f"{'✓ не focus-only' if glob_ok else '✗ РЕЕСТР УРЕЗАН ДО ФОКУСА'}")

    # (d) FLOWS: the card's power rows and the package's events must agree tick by tick.
    #     The front draws arrows from `cards.json` — the card already carries the ATTRIBUTED
    #     share (split rule replayed and verified against real bodies by PF-SHARE), so the JS
    #     never re-does that arithmetic and cannot drift from it. The price of that choice is
    #     that the two files of the package must say the same thing, which is what this checks.
    cards = json.load(open(os.path.join(SLICE_DIR, "cards.json"), encoding="utf-8"))
    flow_ok = True
    for oid in FOCI:
        P = cards["entries"][str(oid)]["card"]["power"]
        card_at = {}
        for role, rows in (("paid", P["paid"]), ("got", P["received"]),
                           ("took", P["extorted"]), ("lost", P["extorted_by"]),
                           ("remit", P["remitted"]), ("recv", P["received_remit"])):
            for r in rows:
                card_at.setdefault(r["t"], []).append(role)
        pkg_at = {}
        for e in ev:
            d = e.data or {}
            if e.kind == "appropriate":
                if any(o == oid for o, _v in d.get("payers", ())):
                    pkg_at.setdefault(e.t, []).append("paid")
                if any(o == oid for o, _v in d.get("receivers", ())):
                    pkg_at.setdefault(e.t, []).append("got")
            elif e.kind == "extort":
                if oid in (d.get("takers") or []):
                    pkg_at.setdefault(e.t, []).append("took")
                if oid in (d.get("victims") or []):
                    pkg_at.setdefault(e.t, []).append("lost")
            elif e.kind == "delegate_remit":
                if e.actor == oid:
                    pkg_at.setdefault(e.t, []).append("remit")
                if d.get("root") == oid:
                    pkg_at.setdefault(e.t, []).append("recv")
        same = ({t: sorted(v) for t, v in card_at.items()}
                == {t: sorted(v) for t, v in pkg_at.items()})
        flow_ok = flow_ok and same
        n = sum(len(v) for v in card_at.values())
        print(f"    (d) потоки #{oid}: карточка {n} ролей на {len(card_at)} тиках == события "
              f"пакета {sum(len(v) for v in pkg_at.values())} на {len(pkg_at)}  "
              f"{'✓ тик-в-тик' if same else '✗ РАСХОЖДЕНИЕ'}")
        # and the mass the front will draw is the ATTRIBUTED one, not the pooled gross
        T = P["totals"]
        print(f"        рисуется приписанное: вымогательство {T['extort_attributed']} кг "
              f"(брутто по тем же событиям {T['extort_gross']}), рента ±"
              f"{T['rent_received']}/{T['rent_paid']}, нетто {T['net']}")

    sync = own_ok and ship_ok and pos_ok and glob_ok and flow_ok

    # ---- E2-HONEST: no caption without an event at its own tick ------------- #
    print("\nE2-HONEST — подпись подкреплена событием ТОГО ЖЕ тика, не мотивом:")
    # caption kind -> the event kind(s) that may license it
    LICENCE = {
        "seed": ("seed",), "birth": ("birth",), "death": ("death",),
        "claim": ("claim",), "taken": ("claim", "inherit"), "lose": ("lose",),
        "inherit": ("inherit",), "bequeathed": ("inherit",),
        "mark": ("mark",), "unmark": ("unmark",),
        "rent_paid": ("appropriate",), "rent_got": ("appropriate",),
        "extort_took": ("extort",), "extort_lost": ("extort",),
    }
    by_t = {}
    for e in ev:
        by_t.setdefault(e.t, set()).add(e.kind)
    honest = True
    for oid in FOCI:
        caps = cards["entries"][str(oid)]["captions"]
        unbacked = [c for c in caps["items"]
                    if not (set(LICENCE.get(c["kind"], ())) & by_t.get(c["t"], set()))]
        # every caption must also carry the numbers it stands on (no bare assertion)
        naked = [c for c in caps["items"] if not c.get("backing")]
        # and the pruning must be declared, never silent
        declared = ("flow_folded" in caps and "rule" in caps)
        hit = not unbacked and not naked and declared
        honest = honest and hit
        print(f"    #{oid}: врезок {caps['n']}, без события того же тика {len(unbacked)}, "
              f"без подкрепляющих чисел {len(naked)}, свёртка объявлена "
              f"{'да' if declared else 'НЕТ'}  {'✓' if hit else '✗'}")
        print(f"        потоков-событий {caps['flow_events']} -> в подписи "
              f"{caps['flow_captioned']}, свёрнуто {caps['flow_folded']} "
              f"(правило: {caps['rule']})")
        if unbacked:
            print(f"        ✗ пример: t={unbacked[0]['t']} [{unbacked[0]['kind']}] "
                  f"{unbacked[0]['text'][:70]}")
    # the E1 card SHA must NOT have moved: captions live in the entry, not in the card
    anch = {"58": "aa87881cc8b26a60", "42": "c538e24f8f08817b"}
    sha_ok = all(cards["entries"][o]["card"]["sha"] == a for o, a in anch.items())
    honest = honest and sha_ok
    print(f"    якоря карточки E1 не сдвинулись: "
          + ", ".join(f"#{o} {cards['entries'][o]['card']['sha']}" for o in sorted(anch))
          + f"  {'✓' if sha_ok else '✗ ЯКОРЬ УЕХАЛ'}")
    ok = voff and det and sync and honest
    print(f"\n  E2-VOFF {'✓' if voff else '✗'} · E2-DET {'✓' if det else '✗'} · "
          f"E2-SYNC {'✓' if sync else '✗'} · E2-HONEST {'✓' if honest else '✗'}")
    print(HDR)
    assert voff, "E2-VOFF: the slice export moved the world"
    assert det, "E2-DET: the slice package is not deterministic"
    assert sync, "E2-SYNC: map / ownership / position do not reduce to one tick"
    assert honest, "E2-HONEST: a caption is not backed by an event at its own tick"
    assert ok
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
