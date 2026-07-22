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
# S7 (WO_consolidation-sprint): version of the exporter's event-annotation layer. Stamped
# onto every row ONLY under --annotate; bump when the derived/seq semantics change.
DETECTOR_VERSION = "s7-1"
FIELD_EVERY = 10       # soil/plant full-grid cadence (between them the renderer interpolates)
TOP_KNOWN = 8          # Э-3: at most top-8 known-ties per pawn enter a snapshot
TOP_DENY = 12          # β-3: at most top-12 deny loci per snapshot (cumulative, from deny_loci)

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
    # mod G2 (β-3): power without ownership — only emitted when the mechanism is on, so on
    # the default showcase they are never seen and never enter meta.rendered (V-complete).
    "extort", "delegate_remit",
    # faithful ledger (E2): ownership transitions, the rent flow, branding. Emitted ONLY under
    # `faithful_ledger=True`, so the default showcase never sees them, they never enter
    # meta.event_types_rendered, and every β-3 anchor stays byte-identical — the same argument
    # that admitted mod-G2's two kinds above. All SIX are classified, including `inherit` and
    # `unmark`, of which this scene emits zero: V-complete only complains about kinds it
    # actually sees, so classifying just the four that show up would leave a trap armed for
    # the first run with `inherit_on`.
    "claim", "lose", "inherit", "appropriate", "mark", "unmark",
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
def build_showcase_cfg(seed=7, days=400, arena_side=6, intent_policy="off",
                       extort_on=False, delegate_on=False, revoke_tooth="none",
                       delegate_m=0.7, delegate_compliance_dl=0.5,
                       extort_enforcers=0, delegate_enforcers=0):
    """The showcase: everything the colony achieved in one run — appropriation economy,
    Dunbar social locus, the full artifact reservoir (vessel + store + capital), and a
    Demerzel that awakens ~tick 100 with an IMPLANT agenda. Signatures verified against
    PolisConfig; the IMPLANT example is the working one from run_polis.py.

    mod G2 knobs (β-3) default OFF => the config is IDENTICAL to the shipped showcase, so
    the default package is byte-for-byte the old film (gates V3-FP / V3-OLD). Turned on,
    they add the power-without-ownership layers (extort / delegate / marks / guard / deny)."""
    return PolisConfig(
        appropriation=0.5, owner_policy="claim", arena_side=arena_side,
        seed=seed, days=days,
        dunbar_K=15,                                   # mod-E demo default (ME-mass/replay)
        artifacts=True, store_on=True, capital_on=True, capital_rate=0.02,
        t_awaken=100,
        demerzel_directive=Directive(goal=IMPLANT, payload={"cell": (3, 3)}),
        intent_policy=intent_policy,
        extort_on=extort_on, delegate_on=delegate_on, revoke_tooth=revoke_tooth,
        delegate_m=delegate_m, delegate_compliance_dl=delegate_compliance_dl,
        extort_enforcers=extort_enforcers, delegate_enforcers=delegate_enforcers,
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
        # mod G2 (β-3): the power-without-ownership knobs — the renderer reads these to know
        # which layers to offer and to draw the root's "право-держатель" halo.
        "intent_policy": cfg.intent_policy,
        "extort_on": cfg.extort_on, "delegate_on": cfg.delegate_on,
        "revoke_tooth": cfg.revoke_tooth, "delegate_m": cfg.delegate_m,
        "delegate_compliance_dl": cfg.delegate_compliance_dl,
        "extort_enforcers": cfg.extort_enforcers, "delegate_enforcers": cfg.delegate_enforcers,
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

    # mod G2 (β-3): the power-without-ownership layers — read PUBLIC state only, and only
    # when the mechanism is live, so a run with no G2 has a byte-identical snapshot (V3-OLD).
    if w._delegate_on and w._delegate_marks:
        snap["marks"] = sorted(int(o) for o in w._delegate_marks)   # the branded (persistent)
    guard_ids = w._extort_enforcer_ids | w._delegate_enforcer_ids
    if guard_ids:
        gcells = sorted({(a.i, a.j) for a in pop if a.oid in guard_ids})
        if gcells:
            snap["guard"] = [[i, j] for (i, j) in gcells]           # the guard's shadow
    it = w._artifacts.intent
    if it is not None:
        loci = it.deny_loci()
        if loci:
            top = sorted(loci.items(), key=lambda kv: (-kv[1], kv[0][0], kv[0][1]))[:TOP_DENY]
            snap["deny"] = [[c[0], c[1], n] for c, n in top]        # frustration heatmap

    if want_fields:
        snap["soil"] = [_q(v, 2) for v in w.soil.flatten().tolist()]
        snap["plant"] = [_q(v, 2) for v in w.plant.flatten().tolist()]
    return snap


def _causal_rank(scale):
    """S7 within-tick ordering: primary emissions (individual-scale, produced by a mechanic
    as it acts) sort before derived detector events (deme/world-scale, reconstructed from
    state). Ties inside a rank are broken by `seq` (the write order) — a stable sort."""
    return 0 if scale == "individual" else 1


def _event_row(e, seq=None, annotate=False):
    """One events.jsonl row. Default (annotate=False) is byte-identical to the shipped film.
    With --annotate it gains three OPT-IN fields (S7): `seq` (write order in the log),
    `derived` (True for deme/world-scale detector events — the honest 'this was computed,
    not emitted' flag, per sim_eventlog's scale vocabulary), and `detector_version`."""
    where = None if e.where is None else [int(e.where[0]), int(e.where[1])]
    dm = None if e.dm is None else _q(e.dm, 6)
    row = {"t": e.t, "type": e.kind, "actor": e.actor, "where": where,
           "dm": dm, "data": _json_safe(e.data or {})}
    if annotate:
        row["seq"] = seq
        row["derived"] = e.scale in ("deme", "world")
        row["detector_version"] = DETECTOR_VERSION
    return row


def _aggregate_events(events, top_k=TOP_DENY):
    """`--events agg`: collapse the raw event stream into ONE row per tick — per-type counts
    and Σdm, plus the top-K loci (cells) per type by |Σdm| then count. Exactly what the film's
    layers and sparklines read (remit/extort sums per tick, spatial loci); the raw per-event
    list is dropped. Deterministic (sorted keys/loci). Layer-equivalent to raw (gate V3-AGG)."""
    by_t = {}
    for e in events:
        row = by_t.setdefault(e.t, {})
        rec = row.setdefault(e.kind, {"n": 0, "dm": 0.0, "cells": {}})
        rec["n"] += 1
        # round EACH event's dm to 6dp BEFORE summing — the same rounding the raw events.jsonl
        # carries, so the agg equals what the renderer would sum from the raw stream exactly
        # (gate V3-AGG: layer-equivalent, not merely close).
        dm = 0.0 if e.dm is None else round(float(e.dm), 6)
        rec["dm"] += dm
        if e.where is not None:
            c = (int(e.where[0]), int(e.where[1]))
            cc = rec["cells"].setdefault(c, [0, 0.0])
            cc[0] += 1
            cc[1] += dm
    out = []
    for t in sorted(by_t):
        sums, loci = {}, {}
        for kind in sorted(by_t[t]):
            rec = by_t[t][kind]
            sums[kind] = {"n": rec["n"], "dm": _q(rec["dm"], 6)}
            top = sorted(rec["cells"].items(),
                         key=lambda kv: (-abs(kv[1][1]), -kv[1][0], kv[0]))[:top_k]
            if top:
                loci[kind] = [[c[0], c[1], v[0], _q(v[1], 6)] for c, v in top]
        out.append({"t": t, "sums": sums, "loci": loci})
    return out


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


# --------------------------------------------------------------------------- #
#  E2 — the pawn SLICE mode                                                    #
# --------------------------------------------------------------------------- #
# The E1 scene does not fit the film budget: 945 pawns by the end, Dunbar edges growing
# quadratically (1 468 200 edges over the run), package 57 MB against a 15 MB budget. But ~85%
# of that weight is what a pawn-slice never draws. The slice keeps the story whole — all 400
# days, every tick, full precision — and drops only the undrawn.
#
# WHAT SURVIVES, AND WHY IT IS NOT FOCUS-FILTERED. `known` is cut to edges touching a focus
# (×221). Ownership and power events are NOT: they stay GLOBAL. Replaying who owns the cell the
# focus is standing on needs every claim in the colony, not the focus's own — of 175 claims in
# this scene only 3 involve the two foci, so a focus-only filter would keep 1.7% of the
# ownership ledger and the map would disintegrate on the first tick (gate E2-SYNC).
SLICE_KINDS = {
    "claim", "lose", "inherit",            # the ownership ledger — GLOBAL, replayed to a map
    "appropriate", "extort", "delegate_remit",   # the flows — GLOBAL, roles read per event
    "mark", "unmark",                      # branding — GLOBAL
    "birth", "death",                      # the population line (reconstruct_live)
}


def _slice_guard(out_dir):
    """The §5.5 invariant, enforced rather than agreed: a slice may NEVER be written into the
    shipped showcase directory. `viz/glass/data` carries the β-3 anchors (events.jsonl
    2735d669…); a slice landing there would overwrite them with a filtered package and the
    anchors would die quietly. Cheap structural guard beats a comment asking nicely."""
    shipped = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                            "..", "viz", "glass", "data"))
    if os.path.normcase(os.path.normpath(os.path.abspath(out_dir))) == os.path.normcase(shipped):
        raise SystemExit("viz_export: refusing to write a SLICE into the shipped showcase "
                         f"directory {shipped} — it carries the β-3 anchors. Use "
                         "viz/slice/data (or any other path).")


def export(out_dir, seed=7, days=400, every=1, verbose=True, cfg=None, events_mode="raw",
           annotate=False, sort_events=False, slice_foci=None):
    """Export a package. `cfg` (a PolisConfig) overrides the default showcase — used to ship
    the G2 layers and the split-screen presets; when None the default showcase is built from
    seed/days (byte-identical to the shipped film). `events_mode`: "raw" (one line per event,
    default) or "agg" (one line per tick: per-type sums + top-K loci; gate V3-AGG).

    S7 (opt-in, raw only; defaults keep events.jsonl byte-identical to β-3):
      * `annotate` — stamp each row with seq / derived / detector_version.
      * `sort_events` — re-order rows by (t, causal_order, seq) for consumers wanting a
        canonical chronology; `seq` still records the original write order, so it is a
        pure permutation (no row gained or lost).

    E2 (opt-in): `slice_foci` — a list of oids. Turns the package into a pawn SLICE: events
    restricted to `SLICE_KINDS` (globally — see the note above), `known` restricted to edges
    touching a focus, and a `slice` block added to meta. `slice_foci=None` is the default and
    every existing caller keeps its byte-identical output."""
    if slice_foci:
        _slice_guard(out_dir)
    if cfg is None:
        cfg = build_showcase_cfg(seed=seed, days=days)
    else:
        seed, days = cfg.seed, cfg.days
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

    # ---- E2 slice: cut the undrawn, keep the story whole --------------------- #
    slice_meta = None
    if slice_foci:
        foci = sorted(int(o) for o in slice_foci)
        fset = set(foci)
        n_ev0, n_edge0 = len(events), 0
        kept_kinds = sorted({e.kind for e in events} & SLICE_KINDS)
        dropped_kinds = sorted({e.kind for e in events} - SLICE_KINDS)
        events = [e for e in events if e.kind in SLICE_KINDS]
        n_edge1 = 0
        for snap in snapshots:
            edges = snap.get("known", ())
            n_edge0 += len(edges)
            snap["known"] = [e for e in edges if e[0] in fset or e[1] in fset]
            n_edge1 += len(snap["known"])
        slice_meta = {
            "foci": foci,
            "event_kinds_kept": kept_kinds,
            "event_kinds_dropped": dropped_kinds,
            "n_events_before": n_ev0, "n_events_after": len(events),
            "known_edges_before": n_edge0, "known_edges_after": n_edge1,
            # said out loud so a consumer can never mistake a slice for the full film
            "note": ("pawn slice: ownership/power/branding events are GLOBAL (a focus-only "
                     "filter would break the ownership replay); `known` is focus-only; "
                     "positions come from snapshots, so `move` is dropped as elsewhere"),
        }

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
        # mod G2 (β-3): who the apex is (root of the remit lines; may be off the ownership
        # map — that IS the michelsian image) and the guard caste (the shadow layer).
        "events_mode": events_mode,
        "delegate_root": (int(w._delegate_root) if w._delegate_root is not None else None),
        "guard_ids": sorted(int(o) for o in (w._extort_enforcer_ids | w._delegate_enforcer_ids)),
    }
    if slice_meta is not None:
        meta["slice"] = slice_meta

    os.makedirs(out_dir, exist_ok=True)
    files = {}
    files["meta.json"] = (_dumps(meta) + "\n").encode("utf-8")
    if slice_foci:
        # the slice directory is SELF-CONTAINED: the front needs one path, not two. Lazy
        # import — pawn_card imports `_Houses` from this module, so a top-level import would
        # be circular. The card is the E1 artifact verbatim (same reader, same SHA), so slice
        # and card can never tell two different stories about the same pawn.
        from stage3.pawn_card import pawn_card as _card, narrate_card, _arc_of, arc_evidence
        cards = {}
        for oid in sorted(int(o) for o in slice_foci):
            c = _card(w.log, snapshots, oid)
            cards[str(oid)] = {"card": c, "arc": _arc_of(c),
                               "arc_evidence": arc_evidence(c),
                               "narrative": narrate_card(c)}
        files["cards.json"] = (_dumps({"foci": sorted(int(o) for o in slice_foci),
                                       "entries": cards}) + "\n").encode("utf-8")
    files["snapshots.jsonl"] = ("".join(_dumps(s) + "\n" for s in snapshots)).encode("utf-8")
    if events_mode == "agg":
        agg = _aggregate_events(events)
        files["events.jsonl"] = ("".join(_dumps(r) + "\n" for r in agg)).encode("utf-8")
    else:
        indexed = list(enumerate(events))                    # (seq, event) in write order
        if sort_events:
            indexed = sorted(indexed, key=lambda p: (p[1].t, _causal_rank(p[1].scale), p[0]))
        files["events.jsonl"] = ("".join(
            _dumps(_event_row(e, seq=seq, annotate=annotate)) + "\n"
            for seq, e in indexed)).encode("utf-8")

    # `cards.json` only exists for a slice, so the showcase's file list — and therefore its
    # package SHA — is unchanged; for a slice the card is PART of the artifact and must be
    # inside the anchor, or the front could be served a card from a different run.
    names = ("meta.json", "snapshots.jsonl", "events.jsonl") + (
        ("cards.json",) if "cards.json" in files else ())
    shas = {}
    total = 0
    for name in names:
        blob = files[name]
        with open(os.path.join(out_dir, name), "wb") as fh:
            fh.write(blob)
        shas[name] = hashlib.sha256(blob).hexdigest()
        total += len(blob)

    pkg = hashlib.sha256()
    for name in names:
        pkg.update(files[name])
    package_sha = pkg.hexdigest()

    if verbose:
        print(f"glass-polis export -> {out_dir}")
        print(f"  seed={seed} days={days} every={every}  grid={grid_rows}x{grid_cols}  "
              f"M0={meta['M0']}  fp={w.state_fingerprint()}")
        for name in names:
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
    ap.add_argument("--arena", type=str, default="6", help="arena_side (int) or 'none'")
    ap.add_argument("--events", choices=("raw", "agg"), default="raw")
    # S7 (opt-in; default OFF => events.jsonl byte-identical to the shipped film).
    ap.add_argument("--annotate", action="store_true",
                    help="stamp each raw event row with seq / derived / detector_version")
    ap.add_argument("--sort", action="store_true", dest="sort_events",
                    help="order raw rows by (t, causal_order, seq) — a pure permutation")
    # mod G2 (β-3) layer switches — default OFF => byte-identical to the shipped showcase.
    ap.add_argument("--intent", choices=("off", "reflex", "utility", "live"), default="off")
    ap.add_argument("--extort", action="store_true")
    ap.add_argument("--delegate", action="store_true")
    ap.add_argument("--tooth", choices=("none", "reputation", "enforcer", "auto"), default="none")
    ap.add_argument("--m", type=float, default=0.7)
    ap.add_argument("--compliance", type=float, default=0.5)
    ap.add_argument("--extort-enforcers", type=int, default=0)
    ap.add_argument("--delegate-enforcers", type=int, default=0)
    # faithful ledger (E2): without it the journal carries no ownership transition and no rent
    # flow, so a pawn-slice would have nothing to draw. Default OFF keeps β-3 byte-identical.
    ap.add_argument("--faithful-ledger", action="store_true", dest="faithful_ledger")
    # E2: --slice 58,42 turns the package into a pawn slice and defaults the output to
    # viz/slice/data — never the shipped showcase (guarded, not merely defaulted).
    ap.add_argument("--slice", type=str, default=None, dest="slice_foci",
                    help="comma-separated focal oids -> pawn-slice package (E2)")
    args = ap.parse_args()
    foci = ([int(x) for x in args.slice_foci.split(",") if x.strip()]
            if args.slice_foci else None)
    default_out = ("..", "viz", "slice", "data") if foci else ("..", "viz", "glass", "data")
    out = args.out or os.path.join(os.path.dirname(os.path.abspath(__file__)), *default_out)
    out = os.path.normpath(out)
    arena = None if str(args.arena).lower() == "none" else int(args.arena)
    cfg = build_showcase_cfg(
        seed=args.seed, days=args.days, arena_side=arena, intent_policy=args.intent,
        extort_on=args.extort, delegate_on=args.delegate, revoke_tooth=args.tooth,
        delegate_m=args.m, delegate_compliance_dl=args.compliance,
        extort_enforcers=args.extort_enforcers, delegate_enforcers=args.delegate_enforcers)
    # a slice without the ledger would have no ownership transition and no rent flow to draw
    cfg.faithful_ledger = args.faithful_ledger or bool(foci)
    export(out, every=args.every, cfg=cfg, events_mode=args.events,
           annotate=args.annotate, sort_events=args.sort_events, slice_foci=foci)


if __name__ == "__main__":
    main()
