"""run_mover_symmetry.py — MOVER-SYMMETRIC (D12): is the move rule spatially unbiased?

The question the spatial-drift WO ends at. Ф0 already closed the i axis with ecology (a thermal
cline 295->285 K along i, and 52% of pawns wanting a row COLDER than the box allows, so they
press against i=5). What Ф0 could NOT explain is the j axis: `T` is constant along j, the
oases inside the box sit at LOW j, and yet the mass sits at HIGH j (8.9% -> 30.4%).

So this probe tests the one thing left: does the mover itself carry a spatial preference?

THE INSTRUMENT, AND WHY IT NEEDS NO CANON. An unbiased move rule is EQUIVARIANT: mirror the
whole initial condition and the whole future must come out mirrored. We never read the move
rule; we mirror a world we own and check the behaviour. If the mirrored world does not mirror,
the rule is biased — proved without a line of the substrate.

WHAT MUST BE MIRRORED (Ф0 enumeration — four of these six were absent from the WO, and missing
any ONE would make an unbiased mover look broken):
    positions · plant · soil · T · KPc · oases · the directive cell.

TWO REFLECTIONS:
    R_j  (i, C-1-j)          — the sharp one. `T` is j-invariant, so the thermal answer is not
                               stirred into the thin j signal: R_j isolates the open axis.
    R_ij (R-1-i, C-1-j)      — the full point reflection (180 deg), for completeness of the
                               certificate.

WHAT THE CERTIFICATE COVERS, STATED SO IT IS NOT LATER READ WIDER THAN IT IS. Both R_j and the
180 deg rotation preserve the ROLES of the axes (i stays i, j stays j). They catch an absolute
directional bias — which is exactly the observed symptom. They do NOT cover i<->j anisotropy
(a tie-break that handles i-moves before j-moves); only a diagonal swap R_d would. There is no
symptom calling for R_d — a monotone +j gradient is not explained by anisotropy — so it is not
built. Green here means "certified against a directional bias under R_j and 180 deg on 8
seeds", never "fully symmetric".

SELF-TEST FIRST (SD-HOOK-IDENT). Before any verdict, the IDENTITY transform is run through the
same mirroring machinery. It must reproduce the baseline byte-for-byte. Without that, a red
result could be my hook perturbing the world rather than the mover being biased.

DIAGNOSIS WHEN RED (the WO requires naming WHICH, not just "broken"):
  (1) directional shift — positions диverge while the per-tick RNG draw COUNT still matches;
  (2) RNG drawn in spatial scan order — the draw count itself diverges, i.e. the tie-break
      consumes randomness by walking the grid rather than by oid.

Run:  py stage3/run_mover_symmetry.py            # quick probe: 1 seed, R_j
      py stage3/run_mover_symmetry.py --full     # 8 seeds, R_j and R_ij
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "Code"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sim_eventlog import EventLog                                   # noqa: E402
from stage3.polis import Polis                                      # noqa: E402
from stage3.viz_export import build_showcase_cfg                    # noqa: E402
from stage3.directive import Directive                              # noqa: E402
from sim_comm import R as GRID_R, C as GRID_C                       # noqa: E402

HDR = "=" * 78
SEEDS = (7, 11, 13, 17, 19, 23, 29, 31)
DAYS = 400
FIELDS = ("plant", "soil", "T", "KPc")     # every (R,C) field the world carries (Ф0 census)


# --------------------------------------------------------------------------- #
#  the reflections                                                             #
# --------------------------------------------------------------------------- #
class Refl:
    """A reflection of the grid: how a cell maps, and how a field flips."""

    def __init__(self, name, flip_i, flip_j):
        self.name, self.fi, self.fj = name, flip_i, flip_j

    def cell(self, i, j, R, C):
        return ((R - 1 - i) if self.fi else i, (C - 1 - j) if self.fj else j)

    def field(self, A):
        if self.fi:
            A = A[::-1, :]
        if self.fj:
            A = A[:, ::-1]
        return np.ascontiguousarray(A)


IDENT = Refl("identity", False, False)
R_J = Refl("R_j", False, True)
R_IJ = Refl("R_ij", True, True)


class _CountingRandom:
    """Transparent wrapper that counts draws. It DELEGATES every call to the real Random, so
    the stream is untouched — the count is the only thing added, and it is what tells a
    directional shift apart from randomness consumed in grid order."""

    def __init__(self, inner):
        object.__setattr__(self, "_inner", inner)
        object.__setattr__(self, "draws", 0)

    def __getattr__(self, name):
        inner = object.__getattribute__(self, "_inner")
        attr = getattr(inner, name)
        if callable(attr) and name in ("random", "randint", "randrange", "choice", "shuffle",
                                       "sample", "uniform", "gauss", "normalvariate",
                                       "expovariate", "betavariate", "getrandbits"):
            def counted(*a, **k):
                object.__setattr__(self, "draws",
                                   object.__getattribute__(self, "draws") + 1)
                return attr(*a, **k)
            return counted
        return attr

    def __setattr__(self, name, value):
        setattr(object.__getattribute__(self, "_inner"), name, value)


# --------------------------------------------------------------------------- #
#  building a world, optionally mirrored                                       #
# --------------------------------------------------------------------------- #
def build(seed, days, refl, count_rng=False):
    """Construct the world, then mirror its FULL initial condition on our own instance.

    Canon is never edited: we mutate public attributes of an object we own, exactly as the
    longrun-audit probes do. `arena_side=None` is mandatory — a corner-anchored box is not
    equivariant by construction and would make any mover look biased."""
    cfg = build_showcase_cfg(seed=seed, days=days, arena_side=None)
    # the directive names a cell (3,3) and t_awaken=100 makes it live — a symmetry break of
    # its own, so it is mirrored BEFORE the world is built, using the substrate's grid
    d = cfg.demerzel_directive
    if d is not None and d.payload.get("cell") is not None:
        c = d.payload["cell"]
        pay = dict(d.payload)
        pay["cell"] = refl.cell(c[0], c[1], GRID_R, GRID_C)
        cfg.demerzel_directive = Directive(goal=d.goal, payload=pay, target=d.target)
    w = Polis(EventLog(), cfg)
    R, C = w.soil.shape
    assert (R, C) == (GRID_R, GRID_C), "сетка мира разошлась с константами субстрата"
    for nm in FIELDS:
        A = getattr(w, nm, None)
        if isinstance(A, np.ndarray) and A.shape == (R, C):
            setattr(w, nm, refl.field(A))
    if isinstance(getattr(w, "oases", None), set):
        w.oases = {refl.cell(i, j, R, C) for (i, j) in w.oases}
    for a in w.pop:
        a.i, a.j = refl.cell(a.i, a.j, R, C)
    if count_rng:
        w.rng = _CountingRandom(w.rng)
    return w, R, C


def digest(w, R, C, refl=IDENT):
    """Canonical state digest. Applying `refl` maps a baseline digest into mirror space, so
    `digest(S_R) == digest(S, refl)` is the whole gate."""
    bodies = sorted((a.oid,) + refl.cell(a.i, a.j, R, C) + (round(float(a.body), 9),)
                    for a in w.pop)
    owners = sorted((refl.cell(i, j, R, C), o)
                    for (i, j), o in getattr(w, "_cell_owner", {}).items())
    h = hashlib.sha256()
    h.update(repr(bodies).encode())
    for nm in ("soil", "plant"):
        A = getattr(w, nm)
        h.update(np.round(refl.field(A), 9).tobytes())
    h.update(repr(owners).encode())
    return h.hexdigest()[:16]


def run_pair(seed, days, refl, verbose=True):
    """Baseline and mirrored, stepped in lockstep, comparing at EVERY tick — the first tick of
    divergence is far more diagnostic than a final-state mismatch."""
    wa, R, C = build(seed, days, IDENT, count_rng=True)
    wb, _, _ = build(seed, days, refl, count_rng=True)
    first_bad, draws_bad, detail = None, None, []
    for t in range(1, days + 1):
        da0 = wa.rng.draws
        db0 = wb.rng.draws
        wa.step()
        wb.step()
        if first_bad is None and digest(wa, R, C, refl) != digest(wb, R, C, IDENT):
            first_bad = t
            draws_bad = (wa.rng.draws - da0, wb.rng.draws - db0)
            # ONLY the first divergence is a clean sample: after it the two worlds are simply
            # different worlds, and every later mismatch is a consequence, not evidence.
            A = {a.oid: (a.i, a.j) for a in wa.pop}
            B = {a.oid: (a.i, a.j) for a in wb.pop}
            for o in sorted(A):
                if o not in B:
                    continue
                want = refl.cell(A[o][0], A[o][1], R, C)
                if want != B[o]:
                    detail.append({"oid": o, "base": A[o], "want": want, "got": B[o],
                                   "d_i": B[o][0] - want[0], "d_j": B[o][1] - want[1]})
    ok = first_bad is None
    return {"seed": seed, "refl": refl.name, "ok": ok, "first_bad": first_bad,
            "draws_at_bad": draws_bad,
            "total_draws": (wa.rng.draws, wb.rng.draws), "detail": detail,
            "digest_a": digest(wa, R, C, refl), "digest_b": digest(wb, R, C, IDENT)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--full", action="store_true", help="8 сидов, R_j и R_ij")
    ap.add_argument("--days", type=int, default=DAYS)
    args = ap.parse_args()

    print(HDR)
    print("MOVER-SYMMETRIC (D12) — эквивариантность правила хода")
    print(HDR)

    # ---- SD-HOOK-IDENT: the machinery must be a no-op under the identity --- #
    print("SD-HOOK-IDENT — зеркало-ТОЖДЕСТВО обязано воспроизвести базовый прогон:")
    r = run_pair(7, min(args.days, 120), IDENT)
    hook_ok = r["ok"]
    print(f"    seed=7, {min(args.days,120)} тиков: "
          + ("✓ бит-в-бит — машинерия мир не двигает" if hook_ok
             else f"✗ РАСХОЖДЕНИЕ на t={r['first_bad']}"))
    if not hook_ok:
        print(f"    ✗ хук сам портит прогон (первое расхождение t={r['first_bad']}) — "
              f"любой вердикт ниже был бы про хук, а не про мовер")
        raise SystemExit(1)

    refls = (R_J, R_IJ) if args.full else (R_J,)
    seeds = SEEDS if args.full else SEEDS[:1]
    print(f"\nMOVER-SYMMETRIC — сидов {len(seeds)}, отражений {len(refls)}, "
          f"горизонт {args.days} тиков:")
    rows, all_ok = [], True
    for refl in refls:
        for s in seeds:
            res = run_pair(s, args.days, refl)
            rows.append(res)
            all_ok = all_ok and res["ok"]
            if res["ok"]:
                print(f"    {refl.name:<5} seed={s:<3} ✓ эквивариантно  digest {res['digest_a']}")
            else:
                da, db = res["draws_at_bad"]
                nature = ("(2) розыгрыш ГСЧ по порядку скана — число розыгрышей за тик разошлось"
                          if da != db else
                          "(1) направленный сдвиг — розыгрышей поровну, разошлись ПОЗИЦИИ")
                dj = [d["d_j"] for d in res["detail"]]
                di = [d["d_i"] for d in res["detail"]]
                print(f"    {refl.name:<5} seed={s:<3} ✗ расхождение на t={res['first_bad']}; "
                      f"розыгрышей за тик {da} vs {db} -> природа {nature}")
                print(f"          разошлось пешек: {len(res['detail'])}; "
                      f"Δj {sorted(set(dj))} (сумма {sum(dj):+d}), Δi {sorted(set(di))} "
                      f"(сумма {sum(di):+d})")

    print(f"\n{HDR}")
    if all_ok:
        print("ВЕРДИКТ: мовер СЕРТИФИЦИРОВАН против направленного сдвига")
        print(f"  — под {', '.join(r.name for r in refls)} на {len(seeds)} сид(ах), {args.days} тиков.")
        print("  ГРАНИЦА: R_j и 180° сохраняют роли осей (i остаётся i). Анизотропия i<->j")
        print("  ими НЕ покрыта — её вскрыл бы только диагональный своп R_d, который не строим,")
        print("  потому что симптома под него нет. Читать как «против направленного сдвига»,")
        print("  а не как «полностью симметричен».")
    else:
        print("ВЕРДИКТ: в мовере ЕСТЬ пространственная зависимость — субстратный контаминант.")
        print("  Здесь НЕ чиним: фикс — отдельный канон-WO с ре-анкором V3-FP.")
    print(HDR)
    assert hook_ok, "SD-HOOK-IDENT: the mirroring machinery is not a no-op"
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
