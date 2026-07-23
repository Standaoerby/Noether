"""run_j_residual.py — Track A: is the +j skew a footprint of appropriation?

The last open item of the spatial-drift adjudication. Inside the box the mass sits at HIGH j
(j=0 ~8.9% -> j=5 ~30.4%) and nothing established explains it — the argument is the SIGN:
`T` is flat along j; the oases inside the box sit at LOW j; and the mover (a real defect,
certified by MOVER-SYMMETRIC) drifts toward DECREASING j. All three are silent or pull the
other way. The remaining hypothesis is economic: ownership / appropriation.

SCENE — box6, NOT the open arena. MOVER-SYMMETRIC needed `arena_side=None` because a
corner-anchored box is not equivariant by construction. This probe is the opposite: the
phenomenon LIVES in the box, and the observation being explained was measured there. An open
arena would measure a different thing.

THE CONFOUND, FOUND BEFORE THE RUN. `polis.py:389` — `_rho_extort = appropriation if
cfg.rho_extort is None`. So a naive rho=0 switches off appropriation AND extortion together,
and a green result could not be attributed to appropriation. Hence three arms:

    A  appropriation=0.5, rho_extort=None (=0.5)   baseline; the SANITY GATE
    B  appropriation=0.0, rho_extort=None (=0.0)   both off
    C  appropriation=0.0, rho_extort=0.5 explicit  appropriation off, extortion ALIVE

SANITY GATE FIRST. Arm A must reproduce the observed skew (ratio >= 2.0 and a monotone rise
over the last three columns). If it does not, the run is a misconfiguration, not a result —
we would be explaining a phenomenon this run does not contain. STOP, no verdict.

The verdict matrix over (B, C) is pre-registered in WO_spatial-drift-probe.md, committed
before this file was ever executed.

Read-only: the probe drives its own loop over worlds it owns and reads public positions.
Canon and polis.py are untouched.

Run:  py stage3/run_j_residual.py            # 2 seeds (quick)
      py stage3/run_j_residual.py --full     # 8 seeds
"""
from __future__ import annotations

import argparse
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "Code"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sim_eventlog import EventLog                                   # noqa: E402
from stage3.polis import Polis                                      # noqa: E402
from stage3.viz_export import build_showcase_cfg                    # noqa: E402

HDR = "=" * 78
SEEDS = (7, 11, 13, 17, 19, 23, 29, 31)
DAYS = 400
WINDOW = 151            # the transient (clamp-in ~5 ticks + relaxation ~45) is excluded
BOX = 6

ARMS = (
    ("A", 0.5, None, "база: рента и вымогательство живы"),
    ("B", 0.0, None, "оба выключены (rho_extort наследует 0)"),
    ("C", 0.0, 0.5, "рента выключена, вымогательство ЖИВО"),
)


def scene(seed, rho, rho_ext, days=DAYS):
    """The E2 scene, with the appropriation knobs as the only thing that varies."""
    cfg = build_showcase_cfg(seed=seed, days=days, arena_side=BOX, intent_policy="reflex",
                             extort_on=True, delegate_on=True, revoke_tooth="reputation",
                             extort_enforcers=3, delegate_enforcers=2)
    cfg.appropriation = rho
    cfg.rho_extort = rho_ext
    cfg.faithful_ledger = True
    return cfg


def occupancy(cfg):
    """Body-ticks per column j inside the box, over the post-transient window. The SAME
    measure the original observation was taken with — a different measure would compare
    different things, which is the trap this whole thread keeps circling."""
    w = Polis(EventLog(), cfg)
    col, row, n = Counter(), Counter(), 0
    for t in range(1, cfg.days + 1):
        w.step()
        if t < WINDOW:
            continue
        for a in w.pop:
            if a.i < BOX and a.j < BOX:
                col[a.j] += 1
                row[a.i] += 1
                n += 1
    return col, row, n, len(w.pop)


def shares(cnt, n):
    return [100.0 * cnt[k] / n if n else 0.0 for k in range(BOX)]


def skew(sh):
    """ratio j=5 over j=0, the headline number of the observation."""
    return (sh[5] / sh[0]) if sh[0] > 0 else float("inf")


def monotone_tail(sh):
    """the last three columns must rise — the observation is a gradient, not one hot cell"""
    return sh[3] <= sh[4] <= sh[5]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--full", action="store_true")
    ap.add_argument("--days", type=int, default=DAYS)
    args = ap.parse_args()
    seeds = SEEDS if args.full else SEEDS[:2]

    print(HDR)
    print(f"Track A — +j-остаток: необходима ли аппроприация? (box6, окно t>={WINDOW})")
    print(HDR)

    res = {}
    for tag, rho, rho_ext, note in ARMS:
        print(f"\nплечо {tag} — rho={rho}, rho_extort={rho_ext if rho_ext is not None else 'None(=rho)'} — {note}")
        per_seed = []
        for s in seeds:
            cfg = scene(s, rho, rho_ext, args.days)
            col, row, n, pop = occupancy(cfg)
            sh = shares(col, n)
            per_seed.append(sh)
            print(f"    seed={s:<3} pop={pop:<5} доли по j: "
                  + " ".join(f"{x:5.1f}%" for x in sh)
                  + f"   j5/j0 = {skew(sh):5.2f}x")
        mean = [sum(p[k] for p in per_seed) / len(per_seed) for k in range(BOX)]
        res[tag] = mean
        print(f"    СРЕДНЕЕ  ({len(seeds)} сид.)      "
              + " ".join(f"{x:5.1f}%" for x in mean)
              + f"   j5/j0 = {skew(mean):5.2f}x  монотонный хвост: "
              + ("да" if monotone_tail(mean) else "НЕТ"))

    # ---- SANITY GATE ------------------------------------------------------- #
    a = res["A"]
    sane = skew(a) >= 2.0 and monotone_tail(a)
    print(f"\n{HDR}")
    print("САНИТИ-ГЕЙТ — плечо A обязано воспроизвести наблюдение:")
    print(f"    j5/j0 = {skew(a):.2f}x (нужно >= 2.0), монотонный хвост "
          f"{'да' if monotone_tail(a) else 'НЕТ'}  ->  "
          + ("✓ явление в прогоне ЕСТЬ" if sane else "✗ СТОП: мисконфиг, не результат"))
    if not sane:
        print("    Вердикт НЕ выносится: объяснять нечего, явления в этом прогоне нет.")
        print(HDR)
        return 2

    # ---- verdict ----------------------------------------------------------- #
    gone = {t: skew(res[t]) < 2.0 or not monotone_tail(res[t]) for t in ("B", "C")}
    print(f"\nперекос под B (оба выкл): {'ИСЧЕЗ' if gone['B'] else 'ДЕРЖИТСЯ'} "
          f"(j5/j0 = {skew(res['B']):.2f}x)")
    print(f"перекос под C (рента выкл, вымогательство живо): "
          f"{'ИСЧЕЗ' if gone['C'] else 'ДЕРЖИТСЯ'} (j5/j0 = {skew(res['C']):.2f}x)")
    print()
    if gone["B"] and gone["C"]:
        print("ВЕРДИКТ: аппроприация НЕОБХОДИМА для +j — и только это.")
        print("  rho=0 меняет мир целиком (выживание, плотность, тела): канал НЕ изолирован.")
        print("  Кандидат в книгу — «пространственная концентрация как след аппроприации»,")
        print("  с пометкой, что прямая тяга vs через плотность — отдельный вопрос.")
    elif gone["B"] and not gone["C"]:
        print("ВЕРДИКТ: не рента, а ВЫМОГАТЕЛЬСТВО. Перекос переживает выключение ренты,")
        print("  но не выключение изъятия. Гипотеза уточняется, а не падает.")
    elif not gone["B"] and not gone["C"]:
        print("ВЕРДИКТ: гипотеза ПАДАЕТ — ни аппроприация, ни вымогательство не необходимы.")
        print("  НЕ «значит решётка»: мовер снят (он тянет к −j).")
        print("  Следующие подозреваемые поимённо: директива (3,3) при t_awaken=100;")
        print("  геометрия KPc/оазисов.")
    else:
        print("ВЕРДИКТ: НЕСОГЛАСОВАННО с моделью ослабления (B держится, C исчез).")
        print("  Докладываю как есть, без натяжки. Это отдельная загадка.")
    print(HDR)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
