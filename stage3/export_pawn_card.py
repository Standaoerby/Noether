"""export_pawn_card.py — E1 Ф3: pre-export the pawn-card package (front A) and the
self-contained card artifact (front B).

GUARDRAIL (WO Ф3): the viz endpoint must NEVER run a simulation to answer a request. This
exporter is the only thing that runs the world; it writes a deterministic package to
`viz/runs/<name>.card.json`, and `/pawn/{oid}` merely reads it (the same registry pattern the
snapshot runs already use). No canon risk reaches the front.

Outputs:
  A  viz/runs/<name>.card.json   — package: meta + one entry per exported oid (projections +
                                   the Ф2 narrative verbatim). Served by viz/server.py.
  B  viz/figures/pawn_<oid>.html — a self-contained artifact (inline CSS, no network, no JS
                                   deps) for the book / sharing.

The narrative is copied in VERBATIM — it passed the honesty gate in Ф2, so the front renders
facts + the classified arc and does no editorialising of its own.

Run:  py stage3/export_pawn_card.py                 # hero 58 + contrast 42
      py stage3/export_pawn_card.py --oids 58,42,7
"""
from __future__ import annotations

import argparse
import html
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "Code"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from stage3.pawn_card import (pawn_card, narrate_card, _arc_of, _dumps,   # noqa: E402
                              CARD_VERSION)
from stage3.viz_export import build_showcase_cfg, run_capture             # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "viz"))
from card_render import render_html                                       # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNS_DIR = os.path.join(ROOT, "viz", "runs")
FIG_DIR = os.path.join(ROOT, "viz", "figures")
DEFAULT_OIDS = (58, 42)          # hero (власть) + contrast (жертва), WO §7.2


def e1_scene(seed=7, days=400):
    """G2-ON *and* intent_policy='reflex' — without the intent layer the extort seam is
    skipped and the power projections come out empty (Ф0 finding, WO §7.4)."""
    return build_showcase_cfg(seed=seed, days=days, extort_on=True, delegate_on=True,
                              revoke_tooth="reputation", extort_enforcers=3,
                              delegate_enforcers=2, intent_policy="reflex")


def build_package(oids, seed=7, days=400, every=1):
    cfg = e1_scene(seed, days)
    w, snaps = run_capture(cfg, every)
    entries = {}
    for oid in oids:
        card = pawn_card(w.log, snaps, oid)
        entries[str(oid)] = {
            "card": card,
            "arc": _arc_of(card),
            "narrative": narrate_card(card),
        }
    pkg = {
        "package": "e1_pawn_cards",
        "card_version": CARD_VERSION,
        "scene": {"seed": seed, "days": days, "arena_side": cfg.arena_side,
                  "extort_on": True, "delegate_on": True, "intent_policy": "reflex",
                  "note": "extort requires intent_policy != off (Ф0)"},
        "oids": sorted(int(o) for o in oids),
        "entries": entries,
    }
    return pkg


# --------------------------------------------------------------------------- #
#  B — self-contained HTML artifact                                            #
# --------------------------------------------------------------------------- #
# rendering lives in viz/card_render.py (canon-free, shared with the server)
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--oids", type=str, default=",".join(str(o) for o in DEFAULT_OIDS))
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--days", type=int, default=400)
    ap.add_argument("--name", type=str, default="e1_pawn_cards")
    args = ap.parse_args()
    oids = [int(x) for x in args.oids.split(",") if x.strip()]

    pkg = build_package(oids, seed=args.seed, days=args.days)
    os.makedirs(RUNS_DIR, exist_ok=True)
    os.makedirs(FIG_DIR, exist_ok=True)

    # A — the package the endpoint reads (deterministic: sorted keys, compact)
    a_path = os.path.join(RUNS_DIR, f"{args.name}.card.json")
    with open(a_path, "w", encoding="utf-8") as f:
        f.write(_dumps(pkg))
    print(f"A  пакет -> {os.path.relpath(a_path, ROOT)}  ({len(_dumps(pkg))} байт)")

    # B — the self-contained artifacts
    for oid in oids:
        e = pkg["entries"][str(oid)]
        b_path = os.path.join(FIG_DIR, f"pawn_{oid}.html")
        with open(b_path, "w", encoding="utf-8") as f:
            f.write(render_html(e, pkg["scene"]))
        print(f"B  карточка #{oid} ({e['arc']}) -> {os.path.relpath(b_path, ROOT)}  "
              f"sha {e['card']['sha']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
