"""
viz/schema.py — the read-only snapshot schema for the visualiser (PR-1, beta-core).

A `SnapFrame` is a pure, JSON-round-trippable record of one simulation tick, read straight
off a live world with NO mutation. The one hard requirement: body / gene are stored in the
SAME `.9f` format the canon's `state_fingerprint` hashes, so a snapshot is byte-compatible
with the number the conservation kernel signs — the viz shows exactly the measured run, not
a re-quantised copy. No numpy types ever reach JSON: everything is cast to plain float / int.

This module touches no canon. It only imports the grid/day constants for `meta()`.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, asdict


def _f9(v) -> float:
    """The canonical `.9f` quantisation used by `state_fingerprint` (f"{x:.9f}"), returned
    as a plain float. Guarantees f"{_f9(v):.9f}" == f"{v:.9f}" — byte-compatible with the
    number the canon hashes — while staying a JSON number (no numpy, no string)."""
    return float(f"{float(v):.9f}")


@dataclass
class SnapFrame:
    t: int
    agents: list          # [[oid, i, j, body(.9f), gene(.9f), age], ...] from w.pop (sorted by oid)
    cell_owner: dict      # {"i,j": oid} from w._cell_owner
    plant: list           # w.plant.tolist() (R x C)
    owner_ids: list       # sorted(list(w.owner_ids()))
    appropriated_total: float   # w._appropriated_total (.9f)


def frame_from_world(w, t) -> SnapFrame:
    """Read one frame off a live world. PURE: mutates nothing on `w` (only reads pop, the
    ownership ledger, the plant grid, owner ids, and the cumulative tribute)."""
    agents = [
        [int(a.oid), int(a.i), int(a.j), _f9(a.body), _f9(a.gene), int(a.age)]
        for a in sorted(w.pop, key=lambda x: x.oid)
    ]
    cell_owner = {
        f"{int(i)},{int(j)}": int(oid)
        for (i, j), oid in sorted(w._cell_owner.items())
    }
    plant = [[float(x) for x in row] for row in w.plant.tolist()]
    owner_ids = sorted(int(o) for o in w.owner_ids())
    return SnapFrame(
        t=int(t),
        agents=agents,
        cell_owner=cell_owner,
        plant=plant,
        owner_ids=owner_ids,
        appropriated_total=_f9(w._appropriated_total),
    )


def frames_to_jsonl(frames, path) -> str:
    """Write one JSON object per line (one line per frame). Returns the path written."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for fr in frames:
            fh.write(json.dumps(asdict(fr), separators=(",", ":"), sort_keys=True))
            fh.write("\n")
    return path


def frames_from_jsonl(path) -> list:
    """Read a `.snap.jsonl` back into a list of SnapFrame (round-trips frames_to_jsonl)."""
    out = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            out.append(SnapFrame(**json.loads(line)))
    return out


def meta(w) -> dict:
    """Static run metadata for the viewer (grid, horizon, current oases, seed). Pure read;
    no numpy types (oases as [[i,j], ...], everything float/int).

    The canon import is LOCAL to this function so that `frame_from_world` / `frames_*_jsonl`
    can be used (e.g. by viz/server.py) WITHOUT pulling Code/ into the importer — the reader
    side of the viz stays fully decoupled from the simulation."""
    _code = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Code")
    if _code not in sys.path:
        sys.path.insert(0, _code)
    from sim_comm import R, C, DAYS      # noqa: E402  (grid + horizon)
    return {
        "R": int(R),
        "C": int(C),
        "days": int(DAYS),
        "oases": sorted([[int(i), int(j)] for (i, j) in w.oases]),
        "seed": int(w.seed),
    }
