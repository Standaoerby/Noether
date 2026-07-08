"""
viz_export.py — «Стеклянный полис»: the Glass-Polis EXPORTER (WO_glass-polis.md).

A PURE READER of a Polis run. It runs the showcase config, then reads the PUBLIC world
state (pop, soil, plant, _cell_owner, the ArtifactField, the DunbarRegistry) and the
EventLog from OUTSIDE — it never adds a hook inside the mechanics and never mutates the
world (gate V-OFF). Output is a self-describing data package under viz/glass/data/:

    meta.json        one object: schema, config, M0, grid, houses, event-type manifest
    snapshots.jsonl  one line per snapshot (every --every ticks): pawns/arts/owners/
                     soil/plant/known/god/metrics
    events.jsonl     one line per EventLog event — a DIRECT PROXY, no renaming of types

Determinism (the project standard, extended to viz): one log -> one film. Two runs with
the same CLI args produce byte-identical files (gate V-replay); the package SHA-256 is
printed as an anchor candidate. All floats are rounded (render 2-3 digits; metrics and the
invariant 6 digits — enough that |Σ − M0| < 1e-9 survives the rounding, since the sim
guarantees drift ≪ 1e-6). JSON is emitted with sorted keys and compact separators so the
byte stream is stable.

Nothing here changes the simulation by a byte. If the film "needs" a datum the world does
not expose, the answer is to read more public state — not to instrument the canon.

CLI:  py stage3\viz_export.py [--seed N] [--days N] [--out DIR] [--every K]
"""
from __future__ import annotations

import sys, os, json, hashlib, argparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "Code"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sim_eventlog import EventLog, REPRO
from stage3.polis import Polis, PolisConfig
from stage3.directive import Directive, IMPLANT
from stage3.pawn import phase_of

SCHEMA = "glass-1"
FIELD_EVERY = 10       # soil/plant full-grid cadence (between them the renderer interpolates)
TOP_KNOWN = 8          # Э-3: at most top-8 known-ties per pawn enter a snapshot

# --- event-type manifest (names VERBATIM from the code — never renamed) ------------- #
# Every type the EventLog can emit in the showcase run is classified into exactly one of
# these two sets (gate V-complete). "rendered" = the film draws a glyph/pulse for it;
# "ignored" = state that reaches the film another way (positions come from snapshots, the
# god's voice from the per-snapshot `god` field) or pure internal bookkeeping.
RENDERED = {
    "birth", "death",
    "artifact_write", "artifact_copy", "artifact_read",
    "artifact_store", "artifact_capital",
    "artifact_store_draw", "artifact_capital_boost", "artifact_ruin",
}
IGNORED = {
    "seed",           # founders — drawn implicitly as the t=0 population
    "move",           # positions are read from snapshots every tick
    "cognition",      # the mind's internal deliberation (no locus to draw)
    "communication",  # pawn claims/whispers — not a spatial glyph in this film
    "forget",         # the sphere's spatial-memory eviction (belief bookkeeping)
}


# --------------------------------------------------------------------------- #
#  helpers                                                                     #
# --------------------------------------------------------------------------- #
def _q(x, n):
    """Quantise to n decimals as a plain python float (numpy scalars -> float)."""
    return round(float(x), n)


def _gini(xs):
    """Standard Gini (0 = equal, →1 = concentrated). Empty -> 0.0; all-zero -> 0.0.
    Copy of run_artifact_f._gini, inlined to keep the exporter self-contained."""
    xs = sorted(float(x) for x in xs if x is not None)
    n = len(xs)
    if n == 0:
        return 0.0
    s = sum(xs)
    if s == 0:
        return 0.0
    cum = sum(i * x for i, x in enumerate(xs, 1))
    return (2 * cum) / (n * s) - (n + 1) / n


def _json_safe(obj, ndigits=6):
    """Recursively convert an EventLog `data` payload into a JSON-safe structure:
    tuples -> lists, numpy scalars -> python, floats rounded. Deterministic."""
    if isinstance(obj, dict):
        return {str(k): _json_safe(v, ndigits) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(v, ndigits) for v in obj]
    if isinstance(obj, bool):
        return obj
    if isinstance(obj, int):
        return int(obj)
    if isinstance(obj, float):
        return round(obj, ndigits)
    # numpy scalar or similar: try float, else str
    try:
        return round(float(obj), ndigits)
    except (TypeError, ValueError):
        return obj if isinstance(obj, str) else str(obj)


def _dumps(obj):
    """Stable JSON: sorted keys, compact separators -> byte-identical across runs."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


class _Houses:
    """Founding-lineage tracker built PURELY from the EventLog (no world hook). A pawn's
    'house' is the oid of the founder at the root of its birth chain: seeds are roots
    (their own house), every birth points at its parent, and we trace to the root. This is
    exactly the '_house founding line' the Dunbar layer refers to, reconstructed from the
    public log per the WO's reader rule."""

    def __init__(self, events):
        self.parent = {}          # oid -> parent oid (None for a founder/seed)
        for e in events:
            if e.kind == "seed" and e.actor is not None:
                self.parent.setdefault(e.actor, None)
            elif e.kind == "birth" and e.actor is not None:
                self.parent.setdefault(e.actor, e.parent)
        self._memo = {}

    def house(self, oid):
        seen = []
        cur = oid
        while True:
            if cur in self._memo:
                root = self._memo[cur]
                break
            p = self.parent.get(cur, None)
            if p is None:            # a founder (or an unknown root) -> its own house
                root = cur
                break
            seen.append(cur)
            cur = p
        for o in seen:
            self._memo[o] = root
        self._memo[oid] = root
        return root


# --------------------------------------------------------------------------- #
#  config                                                                      #
# --------------------------------------------------------------------------- #
def build_showcase_cfg(seed=7, days=400):
    """The showcase: everything the colony achieved in one run — appropriation economy,
    Dunbar social locus, the full artifact reservoir (vessel + store + capital), and a
    Demerzel that awakens ~tick 100 with an IMPLANT agenda. Signatures verified against
    PolisConfig; the IMPLANT example is the working one from run_polis.py."""
    return PolisConfig(
        appropriation=0.5, owner_policy="claim", arena_side=6,
        seed=seed, days=days,
        dunbar_K=15,                                   # mod-E demo default (ME-mass/replay)
        artifacts=True, store_on=True, capital_on=True, capital_rate=0.02,
        t_awaken=100,
        demerzel_directive=Directive(goal=IMPLANT, payload={"cell": (3, 3)}),
    )


def _cfg_manifest(cfg):
    """A JSON-safe echo of the config that drove the run (goes into meta.cfg)."""
    d = cfg.demerzel_directive
    return {
        "appropriation": cfg.appropriation, "owner_policy": cfg.owner_policy,
        "arena_side": cfg.arena_side, "seed": cfg.seed, "days": cfg.days,
        "dunbar_K": cfg.dunbar_K,
        "artifacts": cfg.artifacts, "store_on": cfg.store_on,
        "capital_on": cfg.capital_on, "capital_rate": cfg.capital_rate,
        "write_stasis": cfg.write_stasis, "write_stake": cfg.write_stake,
        "mat_decay": cfg.mat_decay, "sem_decay": cfg.sem_decay,
        "read_threshold": cfg.read_threshold, "salience0": cfg.salience0,
        "store_stake": cfg.store_stake, "store_draw_at": cfg.store_draw_at,
        "store_draw_rate": cfg.store_draw_rate, "store_access": cfg.store_access,
        "capital_stake": cfg.capital_stake, "capital_access": cfg.capital_access,
        "t_awaken": cfg.t_awaken,
        "demerzel_directive": (None if d is None else
                               {"goal": d.goal,
                                "cell": list(d.payload.get("cell")) if d.payload.get("cell") else None,
                                "target": d.target}),
        "REPRO": REPRO,
    }


# --------------------------------------------------------------------------- #
#  per-snapshot readers (pure reads of public state)                          #
# --------------------------------------------------------------------------- #
def _snapshot(w, t, want_fields):
    """Read one snapshot from the live world. Pure reads — nothing is mutated (V-OFF).
    `pawns` carry age-derived phase but NOT house yet (house is filled in a post-pass once
    the full lineage log is known)."""
    pop = sorted(w.pop, key=lambda a: a.oid)
    pawns = [[a.oid, a.i, a.j, _q(a.body, 3), phase_of(a.age)] for a in pop]

    af = w._artifacts
    arts = [[ar.aid, ar.kind, ar.i, ar.j, _q(ar.mass, 4), _q(ar.salience, 4),
             ar.maker_oid] for ar in sorted(af.artifacts, key=lambda a: a.aid)]

    owners = [[i, j, oid] for (i, j), oid in
              sorted(w._cell_owner.items(), key=lambda kv: (kv[0][0], kv[0][1]))]

    # Э-3: undirected known-edges, top-TOP_KNOWN per LIVE pawn by tie salience, deduped
    # (a<b keeps the stronger direction). Dead pawns' stale registries are not exported.
    alive = {a.oid for a in pop}
    edges = {}
    for a in pop:
        reg = w._dunbar.known.get(a.oid)
        if not reg:
            continue
        ranked = sorted(((o, rec[1]) for o, rec in reg.items() if o in alive),
                        key=lambda ov: (-ov[1], ov[0]))[:TOP_KNOWN]
        for o, sal in ranked:
            key = (a.oid, o) if a.oid < o else (o, a.oid)
            if sal > edges.get(key, -1.0):
                edges[key] = sal
    known = [[k[0], k[1], _q(v, 3)] for k, v in
             sorted(edges.items(), key=lambda kv: kv[0])]

    metrics = {
        "pop": len(pop),
        "gini_body": _q(_gini(a.body for a in pop), 6),
        "mass_vessel": _q(sum(ar.mass for ar in af.artifacts if ar.kind == "vessel"), 6),
        "mass_store": _q(sum(ar.mass for ar in af.artifacts if ar.kind == "store"), 6),
        "mass_capital": _q(sum(ar.mass for ar in af.artifacts if ar.kind == "capital"), 6),
        "invariant": _q(w._matter(), 6),   # Σ over all reservoirs; |Σ − M0| is the plaque
    }

    snap = {"t": t, "pawns": pawns, "arts": arts, "owners": owners,
            "known": known, "metrics": metrics}

    # god: only while the voice is live (awake AND the Demerzel body is present)
    dem_oid = w._demerzel_oid
    if w._awake and dem_oid is not None and w._death_t is None:
        dem = next((a for a in pop if a.oid == dem_oid), None)
        if dem is not None:
            push = {}
            for (loid, cell, amt) in w._decision_log.get(t, []):
                key = (int(cell[0]), int(cell[1]))
                push[key] = push.get(key, 0) + 1
            goal = w._directive.goal if w._directive is not None else None
            snap["god"] = {
                "oid": dem_oid, "i": dem.i, "j": dem.j, "goal": goal,
                "push": [[c[0], c[1], n] for c, n in sorted(push.items())],
            }

    if want_fields:
        snap["soil"] = [_q(v, 2) for v in w.soil.flatten().tolist()]
        snap["plant"] = [_q(v, 2) for v in w.plant.flatten().tolist()]
    return snap


def _event_row(e):
    where = None if e.where is None else [int(e.where[0]), int(e.where[1])]
    dm = None if e.dm is None else _q(e.dm, 6)
    return {"t": e.t, "type": e.kind, "actor": e.actor, "where": where,
            "dm": dm, "data": _json_safe(e.data or {})}


# --------------------------------------------------------------------------- #
#  the run + write                                                            #
# --------------------------------------------------------------------------- #
def run_capture(cfg, every):
    """Run the showcase and capture snapshots + events. Returns (w, snapshots, events).
    Reads only — the world fingerprint after this equals a clean run's (gate V-OFF)."""
    days = cfg.days
    w = Polis(EventLog(), cfg)
    snapshots = []
    for t in range(1, days + 1):
        w.step()
        if t % every == 0 or t == days:
            snapshots.append(_snapshot(w, t, want_fields=(t % FIELD_EVERY == 0 or t == 1)))
    return w, snapshots


def export(out_dir, seed=7, days=400, every=1, verbose=True):
    cfg = build_showcase_cfg(seed=seed, days=days)
    w, snapshots = run_capture(cfg, every)

    events = w.log.events
    houses = _Houses(events)
    # fill house into every pawn row: [oid,i,j,body,phase] -> [oid,i,j,body,house,phase]
    house_ids = set()
    for snap in snapshots:
        filled = []
        for (oid, i, j, body, phase) in snap["pawns"]:
            h = houses.house(oid)
            house_ids.add(h)
            filled.append([oid, i, j, body, h, phase])
        snap["pawns"] = filled

    # event-type completeness: every emitted type must be classified (gate V-complete)
    seen_types = sorted({e.kind for e in events})
    unclassified = [k for k in seen_types if k not in RENDERED and k not in IGNORED]
    if unclassified:
        raise SystemExit(f"viz_export: unclassified event type(s) {unclassified} — add "
                         f"them to RENDERED or IGNORED (never rename).")

    grid_rows, grid_cols = (int(w.soil.shape[0]), int(w.soil.shape[1]))
    meta = {
        "schema": SCHEMA, "seed": seed, "days": days,
        "arena_side": cfg.arena_side, "grid_rows": grid_rows, "grid_cols": grid_cols,
        "cfg": _cfg_manifest(cfg),
        "M0": _q(w.M0, 6),
        "houses": sorted(house_ids),
        "snapshot_every": every, "field_every": FIELD_EVERY,
        "event_types_rendered": sorted(k for k in seen_types if k in RENDERED),
        "event_types_ignored": sorted(k for k in seen_types if k in IGNORED),
        "n_snapshots": len(snapshots), "n_events": len(events),
    }

    os.makedirs(out_dir, exist_ok=True)
    files = {}
    files["meta.json"] = (_dumps(meta) + "\n").encode("utf-8")
    files["snapshots.jsonl"] = ("".join(_dumps(s) + "\n" for s in snapshots)).encode("utf-8")
    files["events.jsonl"] = ("".join(_dumps(_event_row(e)) + "\n" for e in events)).encode("utf-8")

    shas = {}
    total = 0
    for name in ("meta.json", "snapshots.jsonl", "events.jsonl"):
        blob = files[name]
        with open(os.path.join(out_dir, name), "wb") as fh:
            fh.write(blob)
        shas[name] = hashlib.sha256(blob).hexdigest()
        total += len(blob)

    pkg = hashlib.sha256()
    for name in ("meta.json", "snapshots.jsonl", "events.jsonl"):
        pkg.update(files[name])
    package_sha = pkg.hexdigest()

    if verbose:
        print(f"glass-polis export -> {out_dir}")
        print(f"  seed={seed} days={days} every={every}  grid={grid_rows}x{grid_cols}  "
              f"M0={meta['M0']}  fp={w.state_fingerprint()}")
        for name in ("meta.json", "snapshots.jsonl", "events.jsonl"):
            print(f"  {name:<16} {len(files[name]):>10} B  sha {shas[name][:16]}")
        print(f"  package          {total:>10} B  ({total/1e6:.2f} MB / 15 MB budget)")
        print(f"  package SHA-256  {package_sha}")
    return {"meta": meta, "shas": shas, "package_sha": package_sha,
            "total_bytes": total, "world": w}


def main():
    ap = argparse.ArgumentParser(description="Glass-Polis exporter (pure reader).")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--days", type=int, default=400)
    ap.add_argument("--every", type=int, default=1)
    ap.add_argument("--out", type=str, default=None)
    args = ap.parse_args()
    out = args.out or os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   "..", "viz", "glass", "data")
    out = os.path.normpath(out)
    export(out, seed=args.seed, days=args.days, every=args.every)


if __name__ == "__main__":
    main()
