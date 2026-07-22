"""run_pawn_card_gates.py — E1 Ф1 gates: E1-VOFF / E1-DET / E1-FAITHFUL.

  E1-VOFF      a run under the card reader keeps its fingerprints — state_fingerprint AND
               polis_fingerprint equal a clean run's. The reader reads public state and the
               log; it never touches the world (the glass pattern).

  E1-DET       the same scene/seed yields a byte-identical card: the SHA-256 over the
               canonical dump (sorted keys, compact) repeats across independent runs.

  E1-FAITHFUL  (reformulated after the Ф0 finding — WO §5). Applies to the LOG-DERIVED cards.
               Replaying seed/birth/death from the journal ALONE must reproduce the live
               population exactly at every checkpoint — the `reconstruct_live` principle of
               sim_eventlog (its grid half is hard-wired to the 5×5 MicroWorld, so we reuse
               the principle, not the function, on the 14×14 Polis). Chronicle/House stand on
               this. PropertyHistory is snapshot-derived and is NOT cross-checked here: the
               log carries no ownership event at all, so comparing a snapshot to itself would
               be vacuous — its correctness rests on E1-VOFF (the snapshot mirrors the real
               `_cell_owner`, and the reader mutated nothing).

Run:  py stage3/run_pawn_card_gates.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "Code"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sim_eventlog import EventLog                                       # noqa: E402
from stage3.polis import Polis, polis_fingerprint                       # noqa: E402
from stage3.viz_export import build_showcase_cfg, run_capture           # noqa: E402
from stage3.pawn_card import pawn_card, card_sha                        # noqa: E402

HDR = "=" * 78
FOCAL = 58          # the hero (WO §7.2): founder, 320 ticks a landholder, 105 extortions
CHECKPOINTS = (50, 150, 300, 400)


def _scene(days=400):
    """The E1 scene: G2 ON *and* intent_policy='reflex' — without the intent layer the
    extort seam is skipped entirely and the power projections come out empty (Ф0)."""
    return build_showcase_cfg(seed=7, days=days, extort_on=True, delegate_on=True,
                              revoke_tooth="reputation", extort_enforcers=3,
                              delegate_enforcers=2, intent_policy="reflex")


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
          f"({re_['totals']['mass_extorted']} кг) у него отняли={re_['totals']['n_extorted_by']}×")
    print(f"    property  : владений={pr['n_tenures']} тиков с землёй={pr['ticks_holding']} "
          f"пик={pr['peak_cells']} клеток, финал={len(pr['final_cells'])}")

    ok = voff and faithful and det
    print(f"\n  E1-VOFF {'✓' if voff else '✗'} · E1-FAITHFUL {'✓' if faithful else '✗'} · E1-DET {'✓' if det else '✗'}")
    print(HDR)
    assert voff, "E1-VOFF: the reader moved the world"
    assert faithful, "E1-FAITHFUL: the log does not reproduce the live population"
    assert det, "E1-DET: the card is not deterministic"
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
