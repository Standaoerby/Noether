r"""sweep.py — pg-lab robustness sweep + the HL4 three-layer table (WO_pg-lab.md §2).

Runs the lab over 3 modes × seeds 7-16 (robustness from birth — the lab is cheap), reports
per-mode medians, and assembles the cross-layer table field · lab · substrate. The
substrate layer is read from the ACCEPTED showcase (viz/pg/data.json) so the comparison is
against real, merged numbers; the field layer is the letter's (pg_lab.FIELD). The gap
lab↔substrate is the measured contribution of the tower's physics (metabolism + demography).

Pre-registered predictions are in lab/PREREG.md; this prints which branch each landed in.
"""
from __future__ import annotations

import json
import os
import statistics as st

from lab.pg_lab import MODES, FIELD, play, _summ

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEEDS = list(range(7, 17))     # 7..16 — ten seeds


def _median_curve(curves):
    return [round(st.median(c[i] for c in curves), 2) for i in range(len(curves[0]))]


def sweep():
    """Return {mode_key: {max, mean, curve, slope, n_punish, raw}} — medians over SEEDS."""
    out = {}
    for key, label, sub, vis, strat in MODES:
        summ = [_summ(play(vis, strat, s)) for s in SEEDS]
        curves = [x["curve"] for x in summ]
        med_curve = _median_curve(curves)
        out[key] = {
            "label": label, "sublabel": sub,
            "max": round(st.median(x["max"] for x in summ), 2),
            "mean": round(st.median(x["mean"] for x in summ), 2),
            "curve": med_curve,
            "slope": round(med_curve[-1] - med_curve[0], 2),
            "peak_to_end": round(med_curve[-1] - max(med_curve), 2),
            "n_punish": int(st.median(x["n_punish"] for x in summ)),
        }
    return out


def _substrate_layer():
    """The substrate showcase numbers, from the accepted viz/pg/data.json (seed 7 run)."""
    p = os.path.join(_ROOT, "viz", "pg", "data.json")
    if not os.path.exists(p):
        return None
    d = json.load(open(p, encoding="utf-8"))
    return {k: {"max": d["worlds"][k]["final"]["max"], "mean": d["worlds"][k]["final"]["mean"],
                "curve": d["worlds"][k]["curve"]} for k in ("anarchy", "children", "teens")}


def hl4_table(lab):
    """Assemble the field · lab · substrate rows per mode."""
    sub = _substrate_layer()
    rows = []
    for key, label, *_ in MODES:
        f = FIELD.get(key, {})
        field_max = f.get("max")
        rows.append({
            "key": key, "label": label,
            "field_max": field_max,
            "lab_max": lab[key]["max"], "lab_mean": lab[key]["mean"],
            "sub_max": (sub[key]["max"] if sub else None),
            "sub_mean": (sub[key]["mean"] if sub else None),
            # the physics contribution: how far the lab runs from the substrate
            "physics_gap_max": (round(lab[key]["max"] - sub[key]["max"], 1) if sub else None),
        })
    return rows, sub is not None


def run_sweep():
    HDR = "=" * 78
    lab = sweep()
    print(HDR)
    print(f"pg-lab SWEEP — 3 modes × seeds {SEEDS[0]}-{SEEDS[-1]} (medians)")
    print(HDR)
    for key, label, *_ in MODES:
        r = lab[key]
        curve = "  ".join(f"{c:7.1f}" for c in r["curve"])
        trend = "рост" if r["slope"] > 1 else ("затухание" if r["peak_to_end"] < -1 else "плато")
        print(f"  {label:>10}: вклад [{curve} ]  макс {r['max']:7.1f}  средн {r['mean']:7.1f}  "
              f"наклон {r['slope']:+7.1f} ({trend})")
    print(HDR)
    print("HL4 — три слоя: поле · лаборатория · субстрат  (макс на игрока)")
    rows, have_sub = hl4_table(lab)
    print(f"  {'режим':>10} | {'поле':>8} | {'лаб макс/средн':>16} | {'субстрат макс/средн':>20} | физика Δмакс")
    for r in rows:
        fm = f"~{r['field_max']}" if r['field_max'] else "—"
        lm = f"{r['lab_max']:.0f}/{r['lab_mean']:.0f}"
        sm = f"{r['sub_max']:.0f}/{r['sub_mean']:.0f}" if r['sub_max'] is not None else "—"
        pg = f"{r['physics_gap_max']:+.0f}" if r['physics_gap_max'] is not None else "—"
        print(f"  {r['label']:>10} | {fm:>8} | {lm:>16} | {sm:>20} | {pg}")
    print(HDR)
    # pre-reg evaluation
    print("пре-рег (lab/PREREG.md):")
    a = lab["anarchy"]; c = lab["children"]; t = lab["teens"]
    print(f"  HL1 анон:       наклон {a['slope']:+.0f}, peak→end {a['peak_to_end']:+.0f} -> "
          f"{'затухание после пика (а)' if a['peak_to_end'] < -1 else 'разобрать (б)'}")
    print(f"  HL2 дети:       макс {c['max']:.0f} vs поле ~{FIELD['children']['max']} -> "
          f"{'порядок поля (а)' if c['max'] <= 150 else 'разгон выше — вклад физики (б)'}")
    print(f"  HL3 подростки:  макс {t['max']:.0f} vs анон {a['max']:.0f}; средн {t['mean']:.0f} vs дети {c['mean']:.0f} -> "
          f"{'≈анон и беднее детей (а)' if t['max'] < c['max'] and t['mean'] < c['mean'] else 'разобрать (б)'}")
    if have_sub:
        print(f"  HL4 физика:     дети Δмакс {rows[1]['physics_gap_max']:+.0f}, "
              f"подростки Δмакс {rows[2]['physics_gap_max']:+.0f} "
              f"(лаб бежит горячее субстрата — метаболизм/демография съели этот разрыв)")
    else:
        print("  HL4: viz/pg/data.json не найден — слой субстрата пропущен")
    print(HDR)
    return {"lab": lab, "rows": rows, "seeds": SEEDS}


if __name__ == "__main__":
    import sys
    sys.path.insert(0, _ROOT)
    run_sweep()
