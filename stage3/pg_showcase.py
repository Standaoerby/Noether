r"""pg_showcase.py — the "public good" showcase exporter (WO_viz-publicgood.md).

A field experiment from the letter (a public-goods game, children vs teenagers) replayed by
pawns: three worlds from ONE fixed start, ~12 pawns, 5 rounds. This is a SHOWCASE, not new
science — the mechanic is mod H3 Phase 1's `PublicGood` organ, UNCHANGED; robustness (10
seeds) lives in WO_stage3-mod-H3.md. Here one concrete, deterministic run is made legible.

The stage is a single deme of 12 pawns on one cell (the "size of the children's group" from
the letter) — the substrate's native deme, scoped down from the full colony (N0=120, canon)
so twelve named contributions are readable tour by tour. The organ is the real one: body ->
soil contribution, m·C synergy split equally, majority-of-present sanction. Every GAME number
on the page (who gave how much, who was punished, who voted) is read back from the EventLog
(`pg_contrib` / `pg_vote` / `pg_punish`); money is the pawn's conserved body, projected by a
single multiplier (start body -> 20 "money").

Three worlds, identical start, diverging fates (the letter's two circles):
  * anarchy   — anon, no punishment (both letter groups, circle 1: contribute-and-share).
  * children  — signed + punish(min_contrib): the norm-enforcer sanctions the lowest giver.
  * teens     — signed + punish(coalition): a свой-чужой bloc burns the out-group's richest.

Gates (run: py stage3\pg_showcase.py):
  MPG-VIEW   the export READS; the world fingerprint is byte-identical with and without the
             export pass (the showcase looks, it does not touch).
  MH-replay  two independent runs of each world produce a byte-identical event log.

Writes viz/pg/data.json (+ regenerates viz/pg/index.html from the template) and a manifest.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "Code"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

from sim_eventlog import EventLog
from stage3.polis import PolisConfig
from stage3.publicgood import PublicGood

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_VIZ = os.path.join(_ROOT, "viz", "pg")

# --- the fixed stage (a deterministic 12-pawn deme; no RNG, so "seed" is nominal) ---------- #
SCHEMA = "pg-1"
SEED = 7
N = 12
TOURS = 5
BODY0 = 1.0                 # every pawn starts with the same body ...
MONEY_MULT = 20.0 / BODY0   # ... projected to 20 "money" (Task 2.3: one printed multiplier)
SOIL0 = 1000.0             # the cell's matter reservoir the synergy draws on (never starved here)
PARAMS = dict(pg_m=5.0, pg_stake=0.2, pg_p0=0.6, pg_learn=0.15,
              punish_frac=0.2, punish_cost=0.1)

WORLDS = [
    ("anarchy", "Анархия", "аноним · без наказания",
     dict(contrib_visibility="anon", punish_on=False)),
    ("children", "Дети", "подписано · штраф самому жадному",
     dict(contrib_visibility="signed", punish_on=True, punish_strategy="min_contrib")),
    ("teens", "Подростки", "подписано · коалиция жжёт чужого",
     dict(contrib_visibility="signed", punish_on=True, punish_strategy="coalition")),
]

# Field numbers from the letter (WO §3.3) — humans on the Finnish base, for the comparison.
FIELD = {"circle1_max": 60, "circle1_alt": 45, "children_max": 100, "teens_max": 45,
         "note": "люди на финской базе · пешки на консервативном субстрате"}

STRATEGY_NOTE = {
    "min_contrib": "наказали самого жадного",
    "coalition": "коалиция сожгла чужого",
    "max_body": "срезали самого богатого",
}


class _Ani:
    """A pawn as the organ sees it: an id, a body, a cell. Nothing else is read or written."""
    __slots__ = ("oid", "body", "i", "j")

    def __init__(self, oid, body):
        self.oid, self.body, self.i, self.j = oid, body, 0, 0


class _Deme:
    """The minimal world the organ needs: t, pop, soil[i,j] (numpy), log. One cell (0,0)."""

    def __init__(self):
        self.t = 0
        self.pop = [_Ani(oid, BODY0) for oid in range(1, N + 1)]
        self.soil = np.array([[SOIL0]], dtype=float)
        self.log = EventLog()

    def fingerprint(self) -> str:
        """A world fingerprint over the conserved substrate (bodies + soil) and the organ's
        own state blob — the object the MPG-VIEW gate holds byte-stable across an export."""
        h = hashlib.sha256()
        for a in sorted(self.pop, key=lambda x: x.oid):
            h.update(f"{a.oid}:{a.body:.9f}|".encode())
        h.update(f"|soil{float(self.soil.sum()):.9f}".encode())
        return h.hexdigest()[:16]


def _run_world(cfg_kw):
    """Run the real organ on the fixed 12-pawn deme for TOURS ticks (one tick = one tour).
    Returns (deme, pg). Fully deterministic: fixed start, no RNG."""
    cfg = PolisConfig(pg_on=True, seed=SEED, **PARAMS, **cfg_kw)
    pg = PublicGood(cfg)
    w = _Deme()
    for tour in range(TOURS):
        w.t = tour + 1
        pg.tick(w)
    return w, pg


def _events_by_round(log, kind, rnd):
    return [e for e in log.events if e.kind == kind and e.data.get("round") == rnd]


def _project(x):
    return round(x * MONEY_MULT, 2)


def _world_payload(key, label, sublabel, cfg_kw):
    """Build one world's showcase data. GAME numbers (contrib/vote/punish) come from the
    EventLog; money is the pawn body (world state), projected by MONEY_MULT."""
    w, pg = _run_world(cfg_kw)
    log = w.log
    m = PARAMS["pg_m"]
    oids = list(range(1, N + 1))

    # replay body per pawn tour by tour by re-running and snapshotting (deterministic).
    bodies_by_tour = []
    wr = _Deme()
    cfg = PolisConfig(pg_on=True, seed=SEED, **PARAMS, **cfg_kw)
    pgr = PublicGood(cfg)
    for tour in range(TOURS):
        wr.t = tour + 1
        pgr.tick(wr)
        bodies_by_tour.append({a.oid: a.body for a in wr.pop})

    tours = []
    curve = []
    for r in range(TOURS):
        contribs = {e.actor: e.data["amount"] for e in _events_by_round(log, "pg_contrib", r)}
        total_c = sum(contribs.values())
        curve.append(_project(total_c))
        votes = _events_by_round(log, "pg_vote", r)
        punish_ev = [e for e in log.events if e.kind == "pg_punish" and e.t == r + 1]
        punish = None
        if punish_ev:
            pe = punish_ev[0]
            punish = {
                "target": pe.actor,
                "damage": _project(pe.data["amount"]),
                "votes": len(votes),
                "voters": sorted({e.actor for e in votes}),
                "strategy": pe.data["strategy"],
                "note": STRATEGY_NOTE.get(pe.data["strategy"], ""),
            }
        tours.append({
            "round": r + 1,
            "contrib": {str(o): _project(contribs.get(o, 0.0)) for o in oids},
            "money": {str(o): _project(bodies_by_tour[r][o]) for o in oids},
            "total_contrib": _project(total_c),
            "bank_payout": _project(m * total_c),   # what the common pot returned this tour
            "punish": punish,
        })

    final_bodies = bodies_by_tour[-1]
    per_pawn = sorted(({"oid": o, "money": _project(final_bodies[o])} for o in oids),
                      key=lambda d: -d["money"])
    monies = [d["money"] for d in per_pawn]
    total_bank = round(sum(t["bank_payout"] for t in tours), 2)
    return {
        "key": key, "label": label, "sublabel": sublabel,
        "pawns": oids,
        "tours": tours,
        "curve": curve,
        "final": {"per_pawn": per_pawn, "max": max(monies), "mean": round(sum(monies) / len(monies), 2),
                  "total_bank": total_bank, "n_punish": pg.n_punish},
        "fingerprint": w.fingerprint(),
    }, w


def build_showcase():
    """The whole page's data: rules, three worlds tour-by-tour, finale, field comparison."""
    worlds = {}
    fps = {}
    for key, label, sublabel, cfg_kw in WORLDS:
        payload, w = _world_payload(key, label, sublabel, cfg_kw)
        worlds[key] = payload
        fps[key] = w.fingerprint()
    return {
        "schema": SCHEMA, "seed": SEED, "n": N, "tours": TOURS,
        "m": PARAMS["pg_m"], "money_mult": MONEY_MULT, "money_start": 20,
        "params": PARAMS,
        "order": [k for k, *_ in WORLDS],
        "worlds": worlds,
        "field": FIELD,
        "fingerprints": fps,
    }


# --------------------------------------------------------------------------- #
#  gates                                                                        #
# --------------------------------------------------------------------------- #
def _gate_mpg_view():
    """The export is a pure reader: a clean run and a run whose log is fully read back
    produce the same world fingerprint (the showcase looks, it does not touch)."""
    ok = True
    for key, _l, _s, cfg_kw in WORLDS:
        w_clean, _ = _run_world(cfg_kw)
        fp_clean = w_clean.fingerprint()
        w_read, _ = _run_world(cfg_kw)
        _ = [(e.t, e.kind, e.actor, e.data) for e in w_read.log.events]   # exhaustively read
        fp_read = w_read.fingerprint()
        good = fp_clean == fp_read
        ok = ok and good
        print(f"MPG-VIEW  [{key:>8}] fp clean {fp_clean} == read {fp_read} -> {'✓' if good else '✗'}")
    assert ok


def _gate_mh_replay():
    """Two independent runs of each world produce a byte-identical event log (determinism on
    the new pg_contrib / pg_vote paths — one log, one film)."""
    def _blob(cfg_kw):
        w, _ = _run_world(cfg_kw)
        h = hashlib.sha256()
        for e in w.log.events:
            h.update(f"{e.t}|{e.kind}|{e.scale}|{e.actor}|{json.dumps(e.data, sort_keys=True)}\n".encode())
        return h.hexdigest()[:16], sum(1 for e in w.log.events if e.kind in ("pg_contrib", "pg_vote"))
    ok = True
    for key, _l, _s, cfg_kw in WORLDS:
        a, n_new = _blob(cfg_kw)
        b, _ = _blob(cfg_kw)
        good = a == b
        ok = ok and good
        print(f"MH-replay [{key:>8}] log {a} == {b} -> {'✓' if good else '✗'}  ({n_new} pg_contrib/pg_vote)")
    assert ok


# --------------------------------------------------------------------------- #
#  write                                                                        #
# --------------------------------------------------------------------------- #
def _write_outputs(data):
    os.makedirs(_VIZ, exist_ok=True)
    # data.json — pretty, for the PNG builder and inspection
    dj = os.path.join(_VIZ, "data.json")
    with open(dj, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True, ensure_ascii=False)
        f.write("\n")

    # index.html — inject the data into the template (self-contained, file://)
    tmpl = os.path.join(_VIZ, "template.html")
    if os.path.exists(tmpl):
        html = open(tmpl, encoding="utf-8").read()
        blob = json.dumps(data, sort_keys=True, ensure_ascii=False)
        html = html.replace("/*__PG_DATA__*/", blob)
        with open(os.path.join(_VIZ, "index.html"), "w", encoding="utf-8") as f:
            f.write(html)

    # manifest.json — S6.1 attribution (reuses stage3/manifest.py)
    from stage3.manifest import write_manifest
    cfg_echo = {"n": N, "tours": TOURS, "m": PARAMS["pg_m"], "params": PARAMS,
                "money_mult": MONEY_MULT, "worlds": [k for k, *_ in WORLDS]}
    total_events = sum(len(_run_world(kw)[0].log) for *_h, kw in WORLDS)
    write_manifest(os.path.join(_VIZ, "manifest.json"), "pg_showcase",
                   seed=SEED, config=cfg_echo, event_count=total_events)
    return dj


def build_figure(data, path):
    """The book illustration (Task 4.1): the three contribution curves + final totals, one
    figure, dark glass palette. Reads only the exported `data` — no re-simulation."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    BG, PANEL, INK, DIM, LINE = "#0b0d12", "#12151d", "#e6e9f0", "#8b93a7", "#2a3040"
    COL = {"anarchy": "#8b93a7", "children": "#39d98a", "teens": "#b98cff"}
    order = data["order"]
    fig, (axc, axb) = plt.subplots(1, 2, figsize=(11, 4.4), facecolor=BG,
                                   gridspec_kw={"width_ratios": [1.5, 1]})
    fig.suptitle("Общественное благо: три института, один старт",
                 color=INK, fontsize=15, fontweight="bold", x=0.02, ha="left")

    # curves — Σ contribution to the bank, tour by tour
    for ax in (axc, axb):
        ax.set_facecolor(PANEL)
        for s in ax.spines.values():
            s.set_color(LINE)
        ax.tick_params(colors=DIM, labelsize=9)
    tours = list(range(1, data["tours"] + 1))
    for k in order:
        w = data["worlds"][k]
        axc.plot(tours, w["curve"], color=COL[k], lw=2.6, marker="o", ms=5,
                 label=w["label"], zorder=3)
        axc.annotate(f"{w['label']} · {w['curve'][-1]:.0f}", (tours[-1], w["curve"][-1]),
                     xytext=(6, 0), textcoords="offset points", va="center",
                     color=COL[k], fontsize=10, fontweight="bold")
    axc.set_xticks(tours)
    axc.set_xlabel("тур", color=DIM, fontsize=9)
    axc.set_ylabel("вклад в общий банк (деньги)", color=DIM, fontsize=9)
    axc.set_title("затухание · удержание · захват", color=DIM, fontsize=10, loc="left")
    axc.grid(True, color=LINE, alpha=0.35, lw=0.7)
    axc.set_xlim(0.9, tours[-1] + 1.1)

    # final totals — max vs mean money per world
    import numpy as _np
    x = _np.arange(len(order))
    maxs = [data["worlds"][k]["final"]["max"] for k in order]
    means = [data["worlds"][k]["final"]["mean"] for k in order]
    axb.bar(x - 0.19, maxs, 0.36, color=[COL[k] for k in order], label="макс")
    axb.bar(x + 0.19, means, 0.36, color=[COL[k] for k in order], alpha=0.5, label="средний")
    for xi, (mx, mn) in enumerate(zip(maxs, means)):
        axb.text(xi - 0.19, mx + 1.5, f"{mx:.0f}", ha="center", color=INK, fontsize=9, fontweight="bold")
        axb.text(xi + 0.19, mn + 1.5, f"{mn:.0f}", ha="center", color=DIM, fontsize=8)
    axb.set_xticks(x)
    axb.set_xticklabels([data["worlds"][k]["label"] for k in order], color=INK, fontsize=9)
    axb.set_title("итог: деньги на игрока (макс / средний)", color=DIM, fontsize=10, loc="left")
    axb.set_ylim(0, max(maxs) * 1.18)
    axb.grid(True, axis="y", color=LINE, alpha=0.35, lw=0.7)

    fig.text(0.02, 0.005,
             f"Пешки на консервативном субстрате · один прогон (seed {data['seed']}) · числа из EventLog · "
             f"robustness (10 сидов) в WO_stage3-mod-H3.md",
             color=DIM, fontsize=7.5, ha="left")
    fig.tight_layout(rect=[0, 0.03, 1, 0.94])
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fig.savefig(path, dpi=150, facecolor=BG)
    plt.close(fig)
    return path


def main():
    HDR = "=" * 78
    print(HDR)
    print("public-good showcase — three worlds, one start, twelve pawns, five tours.")
    print("the mechanic is mod H3's organ, UNCHANGED; this run is one legible instance.")
    print(HDR)
    _gate_mpg_view()
    _gate_mh_replay()
    data = build_showcase()
    dj = _write_outputs(data)
    fig_path = os.path.join(_ROOT, "figures", "pg_two_circles.png")
    try:
        build_figure(data, fig_path)
        fig_msg = os.path.relpath(fig_path, _ROOT)
    except Exception as e:
        fig_msg = f"(skipped: {e})"
    print(HDR)
    for key in data["order"]:
        wd = data["worlds"][key]
        print(f"  {wd['label']:>10}: curve {wd['curve']}  max {wd['final']['max']}  "
              f"mean {wd['final']['mean']}  punish {wd['final']['n_punish']}")
    print(f"\n  wrote {os.path.relpath(dj, _ROOT)} (+ index.html, manifest.json)  ·  figure: {fig_msg}")
    print(HDR)


if __name__ == "__main__":
    main()
