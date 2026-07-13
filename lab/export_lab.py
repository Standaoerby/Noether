r"""export_lab.py — pg-lab -> the showcase (WO_pg-lab.md §3): reuse, not reinvention.

Emits the lab's seed-7 run into the SAME pg-1 data schema the substrate showcase uses, then
injects it into the SAME viz/pg/template.html to produce viz/pg/index_lab.html (with a badge
that names the laboratory conditions). Also builds figures/pg_three_layers.png — the
field · lab · substrate replication illustration — and S6.1 manifests for both artifacts.

Gate MPG-VIEW-analog: the export is a pure reader — the exported numbers equal a fresh
`play()` of the same seed (the export does not perturb the game).
"""
from __future__ import annotations

import hashlib
import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# make `lab` importable, and `Code/` too — only so we can reuse stage3/manifest.py (S6.1)
# for the artifact manifests (WO §3.3); the lab engine itself has no tower dependency.
sys.path.insert(0, os.path.join(_ROOT, "Code"))
sys.path.insert(0, _ROOT)

from lab.pg_lab import MODES, N, TOURS, START, BANK_MULT, PUNISH_FRAC, LEARN, P0_LO, P0_HI, play
from lab.sweep import sweep, hl4_table
_VIZ = os.path.join(_ROOT, "viz", "pg")
SEED = 7
SCHEMA = "pg-1"
BADGE = "лабораторные условия письма: банк ×2, кошельки замкнуты, без метаболизма"

STRATEGY_NOTE = {"min_contrib": "наказали самого жадного",
                 "coalition": "коалиция сожгла чужого", "max_body": "срезали самого богатого"}
# the letter's field numbers, in the substrate showcase's `field` shape (for the finale table)
FIELD = {"circle1_max": 60, "circle1_alt": 45, "children_max": 100, "teens_max": 45,
         "self_label": "лаборатория (стол)",
         "note": ("люди за столом (письмо) · лаборатория в тех же условиях (банк ×2). Разрыв с "
                  "полем — не условия, а сила стратегии: лаб берёт ~43% компаунд-потолка (640), "
                  "дети письма ~16%. Порядок институтов держится; величины читать качественно.")}


def _r2(x):
    return round(float(x), 2)


def _game_fp(game):
    h = hashlib.sha256()
    for t in game["tours"]:
        for o in sorted(t["contribs"]):
            h.update(f"{t['round']}|{o}|{t['contribs'][o]:.9f}|{t['wallets'][o]:.9f}".encode())
    return h.hexdigest()[:16]


def _world_payload(key, label, sublabel, vis, strat, game):
    oids = list(range(1, N + 1))
    tours, curve = [], []
    for t in game["tours"]:
        curve.append(_r2(t["total_contrib"]))
        punish = None
        if t["vote"]:
            v = t["vote"]
            punish = {"target": v["target"], "damage": _r2(v["fine"]), "votes": v["votes"],
                      "voters": sorted(v["voters"]), "strategy": v["strategy"],
                      "note": STRATEGY_NOTE.get(v["strategy"], "")}
        tours.append({
            "round": t["round"],
            "contrib": {str(o): _r2(t["contribs"][o]) for o in oids},
            "money": {str(o): _r2(t["wallets"][o]) for o in oids},
            "total_contrib": _r2(t["total_contrib"]),
            "bank_payout": _r2(t["bank_payout"]),
            "punish": punish,
        })
    finals = game["wallets"]
    per_pawn = sorted(({"oid": o, "money": _r2(finals[o])} for o in oids), key=lambda d: -d["money"])
    monies = [d["money"] for d in per_pawn]
    return {"key": key, "label": label, "sublabel": sublabel, "pawns": oids,
            "tours": tours, "curve": curve,
            "final": {"per_pawn": per_pawn, "max": max(monies), "mean": _r2(sum(monies) / len(monies)),
                      "total_bank": _r2(sum(t["bank_payout"] for t in game["tours"])),
                      "n_punish": sum(1 for t in game["tours"] if t["vote"])},
            "fingerprint": _game_fp(game)}


def build_lab_data():
    worlds, fps = {}, {}
    for key, label, sublabel, vis, strat in MODES:
        g = play(vis, strat, SEED)
        worlds[key] = _world_payload(key, label, sublabel, vis, strat, g)
        fps[key] = worlds[key]["fingerprint"]
    return {
        "schema": SCHEMA, "seed": SEED, "n": N, "tours": TOURS,
        "m": BANK_MULT, "money_mult": 1, "money_start": int(START),
        "params": {"bank_mult": BANK_MULT, "punish_frac": PUNISH_FRAC, "learn": LEARN,
                   "p0_band": [P0_LO, P0_HI]},
        "order": [k for k, *_ in MODES],
        "badge": BADGE,
        "prov_note": f"лабораторный близнец · seed {SEED} · условия письма (банк ×2, без метаболизма)",
        "foot": ("pg-lab · public goods · Noether. Лабораторный близнец витрины: условия письма "
                 "(банк ×2, замкнутые кошельки, штраф сжигается, БЕЗ метаболизма). Неконсервативно "
                 "по замыслу — деньги создаются банком и жгутся штрафом (гейт LAB-CONS). "
                 f"Свип 10 сидов + три слоя (поле·лаб·субстрат) — в figures/pg_three_layers.png и "
                 "lab/PREREG.md. Деньги = кошелёк (старт 20)."),
        "worlds": worlds, "field": FIELD, "fingerprints": fps,
    }


def _gate_mpg_view(data):
    """The export reads only: exported per-world final numbers equal a fresh play() (the
    export never perturbs the game)."""
    ok = True
    for key, _l, _s, vis, strat in MODES:
        fresh = _game_fp(play(vis, strat, SEED))
        good = fresh == data["worlds"][key]["fingerprint"]
        ok = ok and good
        print(f"MPG-VIEW  [{key:>8}] export fp {data['worlds'][key]['fingerprint']} == fresh {fresh} -> {'✓' if good else '✗'}")
    assert ok


def build_three_layer_figure(path):
    """figures/pg_three_layers.png — field · lab · substrate, max money per mode (WO §3.2)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    BG, PANEL, INK, DIM, LINE = "#0b0d12", "#12151d", "#e6e9f0", "#8b93a7", "#2a3040"
    C_FIELD, C_LAB, C_SUB = "#6cc5ff", "#ffcf5c", "#b98cff"
    lab = sweep()
    rows, have_sub = hl4_table(lab)
    labels = [r["label"] for r in rows]
    field = [r["field_max"] or 0 for r in rows]
    labv = [r["lab_max"] for r in rows]
    subv = [r["sub_max"] or 0 for r in rows]

    fig, ax = plt.subplots(figsize=(9.5, 4.6), facecolor=BG)
    ax.set_facecolor(PANEL)
    for s in ax.spines.values():
        s.set_color(LINE)
    ax.tick_params(colors=DIM, labelsize=10)
    x = np.arange(len(labels))
    w = 0.26
    for off, vals, col, name in ((-w, field, C_FIELD, "поле (письмо)"),
                                 (0.0, labv, C_LAB, "лаборатория (×2, без метаболизма)"),
                                 (w, subv, C_SUB, "субстрат (башня)")):
        bars = ax.bar(x + off, vals, w, color=col, label=name)
        for xi, v in zip(x + off, vals):
            if v:
                ax.text(xi, v + max(labv) * 0.012, f"{v:.0f}", ha="center", color=INK, fontsize=8.5, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, color=INK, fontsize=11)
    ax.set_ylabel("макс денег на игрока", color=DIM, fontsize=10)
    ax.set_title("Три слоя одной игры: поле · лаборатория · субстрат", color=INK, fontsize=14,
                 fontweight="bold", loc="left")
    ax.grid(True, axis="y", color=LINE, alpha=0.35, lw=0.7)
    leg = ax.legend(facecolor=PANEL, edgecolor=LINE, labelcolor=INK, fontsize=9, loc="upper left")
    leg.get_frame().set_alpha(0.9)
    fig.text(0.01, 0.055,
             "Институт-эффект (дети ≫ подростки ≈ анархия) держится во всех трёх слоях; величины читать качественно.",
             color=DIM, fontsize=8, ha="left")
    fig.text(0.01, 0.012,
             "Лаб компаундит как письмо (потолок 640), но агенты кооперируют сильнее детей (~43% vs ~16%) — разрыв с полем это стратегия. Сиды 7–16.",
             color=DIM, fontsize=8, ha="left")
    fig.tight_layout(rect=[0, 0.10, 1, 1])
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fig.savefig(path, dpi=150, facecolor=BG)
    plt.close(fig)
    return path


def write_outputs():
    data = build_lab_data()
    _gate_mpg_view(data)
    os.makedirs(_VIZ, exist_ok=True)
    with open(os.path.join(_VIZ, "data_lab.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True, ensure_ascii=False)
        f.write("\n")
    # index_lab.html — inject into the SAME template
    tmpl = open(os.path.join(_VIZ, "template.html"), encoding="utf-8").read()
    html = tmpl.replace("/*__PG_DATA__*/", json.dumps(data, sort_keys=True, ensure_ascii=False))
    with open(os.path.join(_VIZ, "index_lab.html"), "w", encoding="utf-8") as f:
        f.write(html)
    # figure
    fig_path = os.path.join(_ROOT, "figures", "pg_three_layers.png")
    build_three_layer_figure(fig_path)
    # manifests (S6.1) for both artifacts
    from stage3.manifest import write_manifest
    total_events = sum(len(play(vis, strat, SEED)["tours"]) * N for _k, _l, _s, vis, strat in MODES)
    cfg_echo = {"n": N, "tours": TOURS, "bank_mult": BANK_MULT, "seeds": list(range(7, 17)),
                "conditions": "letter: bank x2, closed wallets, no metabolism"}
    write_manifest(os.path.join(_VIZ, "manifest_lab.json"), "pg_lab_showcase",
                   seed=SEED, config=cfg_echo, event_count=total_events)
    write_manifest(os.path.join(_ROOT, "figures", "pg_three_layers.manifest.json"), "pg_three_layers",
                   seed=SEED, config=cfg_echo, event_count=total_events)
    return data, fig_path


def main():
    HDR = "=" * 78
    print(HDR)
    print("pg-lab export — the letter's conditions into the shared showcase (reuse, not reinvent)")
    print(HDR)
    data, fig_path = write_outputs()
    print(f"  wrote viz/pg/data_lab.json · viz/pg/index_lab.html · viz/pg/manifest_lab.json")
    print(f"  figure {os.path.relpath(fig_path, _ROOT)} (+ manifest)")
    print(HDR)


if __name__ == "__main__":
    import sys
    sys.path.insert(0, _ROOT)
    main()
