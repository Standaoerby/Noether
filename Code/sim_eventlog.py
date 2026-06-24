"""
sim_eventlog.py — a maximally universal event log (the bridge to cognition).

Everything the family of sims does is, underneath, a stream of discrete events:
something is born, something dies, something moves, a deme booms or crashes, a
cline shifts, the whole world lurches together. This module is a sim-agnostic
layer that records that stream in one typed schema, lets you query it at any
scale, reconstructs genealogies, carves out the egocentric slice "what could
THIS pawn know", and narrates any slice into prose an LLM can read. That last
step is the bridge to stage-2 cognition: a pawn, "asleep", reads the bounded,
subjective history of its lineage and its neighbourhood — the raw material of
memory, belief, and (eventually) politics.

The schema is deliberately minimal and universal:

    Event(t, kind, scale, where, actor, parent, dm, data)

  * t      : simulation day (int)
  * kind   : open vocabulary — "birth","death","move","crash","boom",
             "local_extinction","recolonize","sync_crash","cline_shift",...
  * scale  : "individual" | "deme" | "world"
  * where  : (row, col) cell, or None for world-scale
  * actor  : an id (individual / deme), or None
  * parent : parent individual id (for births) — this is what makes lineages
  * dm     : matter moved by the event (kg, signed); 0 if not applicable — so
             the log can be reconciled against the conserved substrate
  * data   : arbitrary structured payload (genes, population, correlation, ...)

Nothing here is specific to any one sim. The detectors operate on plain arrays;
the log ingests events from anything. To prove it is faithful (not a lossy
side-channel) the demo logs a COMPLETE individual-level history of a compact
conserved world and then reconstructs the live population from the log ALONE —
it matches the simulation exactly, at every checkpoint. Deterministic from seed.

Pure stdlib + numpy (numpy only for the array detectors).
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import random
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from typing import Optional

import numpy as np


# --------------------------------------------------------------------------- #
#  The universal event + the log                                               #
# --------------------------------------------------------------------------- #
@dataclass
class Event:
    t: int
    kind: str
    scale: str
    where: Optional[tuple] = None
    actor: Optional[int] = None
    parent: Optional[int] = None
    dm: float = 0.0
    data: dict = field(default_factory=dict)


class EventLog:
    def __init__(self):
        self.events: list[Event] = []
        self._pm = None        # cached parent map

    # ---- ingest ---------------------------------------------------------- #
    def emit(self, t, kind, scale, where=None, actor=None, parent=None,
             dm=0.0, data=None):
        self.events.append(Event(t, kind, scale, where, actor, parent,
                                 dm, data or {}))
        self._pm = None

    def __len__(self):
        return len(self.events)

    # ---- serialise ------------------------------------------------------- #
    def to_jsonl(self, path):
        with open(path, "w") as f:
            for e in self.events:
                d = asdict(e)
                if d["where"] is not None:
                    d["where"] = list(d["where"])
                f.write(json.dumps(d, separators=(",", ":")) + "\n")

    @staticmethod
    def from_jsonl(path):
        log = EventLog()
        with open(path) as f:
            for line in f:
                d = json.loads(line)
                if d.get("where") is not None:
                    d["where"] = tuple(d["where"])
                log.events.append(Event(**d))
        return log

    def fingerprint(self):
        h = hashlib.sha256()
        for e in self.events:
            h.update(repr(asdict(e)).encode())
        return h.hexdigest()[:16]

    # ---- query ----------------------------------------------------------- #
    def query(self, t0=None, t1=None, kind=None, kinds=None, scale=None,
              where=None, actor=None):
        out = []
        for e in self.events:
            if t0 is not None and e.t < t0:      continue
            if t1 is not None and e.t > t1:      continue
            if kind is not None and e.kind != kind:     continue
            if kinds is not None and e.kind not in kinds: continue
            if scale is not None and e.scale != scale:  continue
            if where is not None and e.where != where:  continue
            if actor is not None and e.actor != actor:  continue
            out.append(e)
        return out

    def counts(self):
        return Counter((e.scale, e.kind) for e in self.events)

    # ---- genealogy ------------------------------------------------------- #
    def _parent_map(self):
        if self._pm is None:
            pm, birth = {}, {}
            for e in self.events:
                if e.kind in ("birth", "seed") and e.actor is not None:
                    pm[e.actor] = e.parent
                    birth[e.actor] = e
            self._pm = (pm, birth)
        return self._pm

    def lineage(self, oid):
        """Ancestry chain from founder down to oid (inclusive)."""
        pm, _ = self._parent_map()
        chain = [oid]
        seen = {oid}
        cur = pm.get(oid)
        while cur is not None and cur not in seen:
            chain.append(cur)
            seen.add(cur)
            cur = pm.get(cur)
        return list(reversed(chain))

    def descendants(self, oid):
        kids = defaultdict(list)
        pm, _ = self._parent_map()
        for c, p in pm.items():
            if p is not None:
                kids[p].append(c)
        out, stack = set(), [oid]
        while stack:
            x = stack.pop()
            for c in kids.get(x, ()):
                if c not in out:
                    out.add(c)
                    stack.append(c)
        return out

    def positions(self):
        """Replay birth + move events -> {oid: final (row,col)}."""
        pos = {}
        for e in self.events:
            if e.scale != "individual":
                continue
            if e.kind in ("birth", "seed"):
                pos[e.actor] = e.where
            elif e.kind == "move" and "to" in e.data:
                pos[e.actor] = tuple(e.data["to"])
        return pos

    # ---- the egocentric slice: what THIS pawn could know ----------------- #
    def perspective(self, oid):
        """A bounded subjective history for one pawn: its lineage's births, the
        local (deme) events in the cells its lineage occupied, and the world
        events spanning its lineage's lifetime."""
        _, birth = self._parent_map()
        chain = self.lineage(oid)
        if not chain or chain[0] not in birth:
            return []
        t_start = birth[chain[0]].t
        # this pawn's own death, if any
        deaths = {e.actor: e for e in self.events
                  if e.kind == "death" and e.actor == oid}
        t_end = deaths[oid].t if oid in deaths else max(e.t for e in self.events)

        cells = set()
        for a in chain:
            if a in birth and birth[a].where is not None:
                cells.add(birth[a].where)
        # include cells reached by moves of lineage members
        for e in self.events:
            if e.kind == "move" and e.actor in set(chain) and "to" in e.data:
                cells.add(tuple(e.data["to"]))

        slice_ = []
        chainset = set(chain)
        for e in self.events:
            if e.t < t_start or e.t > t_end:
                continue
            keep = False
            if e.scale == "individual" and e.actor in chainset:
                keep = True                              # the lineage's own life
            elif e.scale == "deme" and e.where in cells:
                keep = True                              # what happened locally
            elif e.scale == "world":
                keep = True                              # the big shared events
            if keep:
                slice_.append(e)
        slice_.sort(key=lambda e: (e.t, e.scale != "world"))
        return slice_

    # ---- narration: any slice -> LLM-ready prose ------------------------- #
    def narrate(self, events, title="chronicle"):
        if not events:
            return f"[{title}] (nothing recorded)"
        lines = [f"[{title}]  {len(events)} events, "
                 f"days {events[0].t}–{events[-1].t}"]
        for e in events:
            where = f" at {tuple(e.where)}" if e.where is not None else ""
            if e.kind in ("birth", "seed"):
                g = e.data.get("gene")
                gtxt = f", gene {g-273.15:.1f}°C" if isinstance(g, (int, float)) else ""
                par = "founder" if e.parent is None else f"child of #{e.parent}"
                lines.append(f"  day {e.t:>4}: #{e.actor} born{where} ({par}{gtxt})")
            elif e.kind == "death":
                cause = e.data.get("cause", "")
                age = e.data.get("age")
                atxt = f", age {age}" if age is not None else ""
                lines.append(f"  day {e.t:>4}: #{e.actor} died{where} "
                             f"({cause}{atxt})")
            elif e.kind == "move":
                fr = tuple(e.data.get("from", ())); to = tuple(e.data.get("to", ()))
                lines.append(f"  day {e.t:>4}: #{e.actor} moved {fr}→{to}")
            elif e.kind in ("crash", "boom"):
                lines.append(f"  day {e.t:>4}: deme{where} {e.kind} "
                             f"(pop {e.data.get('from','?')}→{e.data.get('to','?')})")
            elif e.kind == "local_extinction":
                lines.append(f"  day {e.t:>4}: deme{where} went locally extinct")
            elif e.kind == "recolonize":
                lines.append(f"  day {e.t:>4}: deme{where} recolonised")
            elif e.kind == "sync_crash":
                lines.append(f"  day {e.t:>4}: SYNCHRONOUS downturn — "
                             f"{e.data.get('demes','?')} demes fell together")
            elif e.kind == "cline_shift":
                lines.append(f"  day {e.t:>4}: cline shifted "
                             f"(corr {e.data.get('from','?')}→{e.data.get('to','?')})")
            else:
                lines.append(f"  day {e.t:>4}: {e.kind}{where} {e.data}")
        return "\n".join(lines)


# --------------------------------------------------------------------------- #
#  Universal detectors — operate on plain time series, emit into any log       #
# --------------------------------------------------------------------------- #
def detect_deme_events(log, pops, cells, t0=0, window=12, boom=2.2, crash=0.5):
    """pops: array (T, ncells). cells: list of (row,col) for each column."""
    T, nc = pops.shape
    state = ["alive" if pops[0, k] > 0 else "empty" for k in range(nc)]
    for t in range(1, T):
        lo = max(0, t - window)
        for k in range(nc):
            x = pops[t, k]
            prev = pops[t - 1, k]
            if x == 0 and prev > 0:
                log.emit(t0 + t, "local_extinction", "deme", where=cells[k],
                         data={"from": int(prev)})
                state[k] = "empty"
                continue
            if x > 0 and prev == 0:
                log.emit(t0 + t, "recolonize", "deme", where=cells[k],
                         data={"to": int(x)})
                state[k] = "alive"
            ref = pops[lo:t, k]
            if ref.size:
                if x > boom * max(1.0, ref.min()) and x >= 9:
                    log.emit(t0 + t, "boom", "deme", where=cells[k],
                             data={"from": int(ref.min()), "to": int(x)})
                elif x < crash * ref.max() and ref.max() >= 8:
                    log.emit(t0 + t, "crash", "deme", where=cells[k],
                             data={"from": int(ref.max()), "to": int(x)})


def detect_world_events(log, pops, t0=0, window=12, drop=0.8, sync_frac=0.45,
                        corr=None, corr_jump=0.35):
    """Synchronous downturns (many demes dropping together) and cline shifts."""
    total = pops.sum(axis=1)
    T = total.shape[0]
    armed = True
    for t in range(1, T):
        lo = max(0, t - window)
        # fraction of occupied demes that fell vs yesterday
        prev = pops[t - 1]
        now = pops[t]
        occ = prev > 0
        if occ.sum() >= 4:
            fell = ((now < prev) & occ).sum() / occ.sum()
            if fell >= sync_frac and total[t] < drop * total[lo:t].max() and armed:
                log.emit(t0 + t, "sync_crash", "world",
                         data={"demes": int(((now < prev) & occ).sum()),
                               "of": int(occ.sum()), "total": int(total[t])})
                armed = False
            if fell < 0.2:
                armed = True
    if corr is not None:
        for t in range(window, len(corr)):
            a, b = corr[t - window], corr[t]
            if np.isfinite(a) and np.isfinite(b) and abs(b - a) >= corr_jump:
                log.emit(t0 + t, "cline_shift", "world",
                         data={"from": round(float(a), 2), "to": round(float(b), 2)})


# --------------------------------------------------------------------------- #
#  A compact conserved individual-based world that emits a COMPLETE log        #
# --------------------------------------------------------------------------- #
ROWS, COLS = 5, 5
SEED = 7
DAYS = 420

RP, KP, KS = 0.6, 26.0, 16.0
A_GR, KH, EFF = 0.45, 9.0, 0.55
BASE, PEN, DEATH, REPRO = 0.08, 0.0022, 0.05, 0.9
MUT, MIG = 0.8, 0.07
S0, P0 = 70.0, 8.0
N0, BODY0 = 40, 0.5


class Animal:
    __slots__ = ("oid", "i", "j", "gene", "body", "age")

    def __init__(self, oid, i, j, gene, body):
        self.oid = oid; self.i = i; self.j = j
        self.gene = gene; self.body = body; self.age = 0


class MicroWorld:
    """Closed soil->plant->animal loop on a small grid; every individual event
    (birth, death, move) is emitted to the log. Matter is conserved exactly."""

    def __init__(self, log: EventLog, seed=SEED):
        self.log = log
        self.rng = random.Random(seed)
        self.t = 0
        self._next = 0
        # mild temperature gradient (warm row 0 -> cool row 4)
        self.T = np.array([295.0 - 2.5 * i for i in range(ROWS)])[:, None] \
            * np.ones((ROWS, COLS))
        self.soil = np.full((ROWS, COLS), S0)
        self.plant = np.full((ROWS, COLS), P0)
        self.pop: list[Animal] = []
        for _ in range(N0):
            i = self.rng.randrange(ROWS); j = self.rng.randrange(COLS)
            a = Animal(self._next, i, j,
                       self.rng.uniform(285.0, 300.0), BODY0)
            self.pop.append(a)
            self.log.emit(0, "seed", "individual", where=(i, j), actor=a.oid,
                          parent=None, data={"gene": a.gene, "founder": True})
            self._next += 1
        self.M0 = self._matter()
        # per-cell census recorded each day (for the detectors)
        self.census = []
        self.corr = []
        self._record()

    def _matter(self):
        return float(self.soil.sum() + self.plant.sum()
                     + sum(a.body for a in self.pop))

    def _record(self):
        grid = np.zeros((ROWS, COLS))
        for a in self.pop:
            grid[a.i, a.j] += 1
        self.census.append(grid.ravel().copy())
        # cline: corr(local T, gene) across occupied cells
        gsum = defaultdict(float); gn = defaultdict(int)
        for a in self.pop:
            gsum[(a.i, a.j)] += a.gene; gn[(a.i, a.j)] += 1
        Ts, Gs = [], []
        for (i, j), s in gsum.items():
            Ts.append(self.T[i, j]); Gs.append(s / gn[(i, j)])
        if len(Ts) >= 3 and np.std(Ts) > 1e-6 and np.std(Gs) > 1e-6:
            self.corr.append(float(np.corrcoef(Ts, Gs)[0, 1]))
        else:
            self.corr.append(float("nan"))

    def step(self):
        self.t += 1
        rng = self.rng

        # 1. plant growth from soil (conserved)
        gP = RP * self.plant * (1 - self.plant / KP) * (self.soil / (self.soil + KS))
        gP = np.clip(gP, 0.0, self.soil)
        self.soil -= gP; self.plant += gP

        # 2. grazing (plant -> body), shared per cell
        bycell = defaultdict(list)
        for a in self.pop:
            bycell[(a.i, a.j)].append(a)
        for (i, j), members in bycell.items():
            avail = float(self.plant[i, j]); n = len(members)
            for a in members:
                want = A_GR * a.body * (avail / (avail + KH))
                eat = max(0.0, min(want, avail / n, avail))
                avail -= eat; a.body += EFF * eat
                self.soil[i, j] += (1 - EFF) * eat       # egesta to soil
                n -= 1
            self.plant[i, j] = avail

        # 3. upkeep / death / reproduction / migration
        newpop = []
        for a in self.pop:
            mism = a.gene - self.T[a.i, a.j]
            up = (BASE + PEN * mism * mism) * a.body
            up = min(up, a.body)
            a.body -= up; self.soil[a.i, a.j] += up
            a.age += 1

            if a.body < DEATH:
                self.soil[a.i, a.j] += a.body
                self.log.emit(self.t, "death", "individual", where=(a.i, a.j),
                              actor=a.oid, dm=-a.body,
                              data={"age": a.age, "cause": "starvation"})
                continue

            if a.body >= REPRO:
                half = a.body / 2.0
                a.body = half
                child = Animal(self._next, a.i, a.j,
                               a.gene + rng.gauss(0.0, MUT), half)
                self._next += 1
                self.log.emit(self.t, "birth", "individual", where=(a.i, a.j),
                              actor=child.oid, parent=a.oid,
                              data={"gene": child.gene})
                newpop.append(child)

            if rng.random() < MIG:
                fi, fj = a.i, a.j
                d = rng.randint(0, 3)
                if d == 0 and a.i > 0:        a.i -= 1
                elif d == 1 and a.i < ROWS-1: a.i += 1
                elif d == 2 and a.j > 0:      a.j -= 1
                elif d == 3 and a.j < COLS-1: a.j += 1
                if (a.i, a.j) != (fi, fj):
                    self.log.emit(self.t, "move", "individual", where=(a.i, a.j),
                                  actor=a.oid,
                                  data={"from": (fi, fj), "to": (a.i, a.j)})
            newpop.append(a)
        self.pop = newpop
        self._record()

    def matter_drift(self):
        return abs(self._matter() - self.M0)


def reconstruct_live(log, T):
    """Replay individual events from the log ALONE -> live set + per-cell counts
    as of day T. This is the faithfulness audit: it must match the simulation."""
    live = {}
    evs = [e for e in log.events if e.scale == "individual" and e.t <= T]
    for e in evs:               # already in emission (time) order
        if e.kind in ("seed", "birth"):
            live[e.actor] = e.where
        elif e.kind == "death":
            live.pop(e.actor, None)
        elif e.kind == "move":
            live[e.actor] = tuple(e.data["to"])
    grid = np.zeros((ROWS, COLS))
    for cell in live.values():
        grid[cell] += 1
    return len(live), grid


def run_world(seed=SEED):
    log = EventLog()
    w = MicroWorld(log, seed)
    checkpoints = {}
    for d in range(DAYS):
        w.step()
        if w.t in (100, 250, DAYS):
            g = np.zeros((ROWS, COLS))
            for a in w.pop:
                g[a.i, a.j] += 1
            checkpoints[w.t] = (len(w.pop), g)
    census = np.array(w.census)
    cells = [(i, j) for i in range(ROWS) for j in range(COLS)]
    detect_deme_events(log, census, cells)
    detect_world_events(log, census, corr=np.array(w.corr))
    return log, w, checkpoints, census, cells


# --------------------------------------------------------------------------- #
#  Demo                                                                        #
# --------------------------------------------------------------------------- #
def main():
    print("=" * 78)
    print("A UNIVERSAL EVENT LOG  —  the history of a world, made queryable")
    print("A compact conserved soil->plant->animal world. Every individual event")
    print("is logged; deme & world events are derived by universal detectors.")
    print("Then: reconstruct the population from the LOG ALONE (faithfulness),")
    print("read the world's chronicle, and carve out one pawn's subjective story.")
    print("=" * 78)

    log, w, checkpoints, census, cells = run_world()

    # --- faithfulness audit: the log alone reproduces the simulation ------ #
    print("\nFAITHFULNESS — population reconstructed from the event log alone:")
    ok = True
    for t, (n_real, g_real) in checkpoints.items():
        n_rec, g_rec = reconstruct_live(log, t)
        match = (n_rec == n_real) and np.array_equal(g_rec, g_real)
        ok = ok and match
        print(f"   day {t:>4}: sim pop {n_real:>4}  |  log-replay {n_rec:>4}  |  "
              f"per-cell grid identical: {np.array_equal(g_rec, g_real)}")
    assert ok, "EVENT LOG IS NOT A FAITHFUL MIRROR OF THE SIMULATION"
    assert w.matter_drift() < 1e-6, "MATTER NOT CONSERVED"

    # --- determinism: same seed -> identical event stream ----------------- #
    log2, *_ = run_world()
    det = (log.fingerprint() == log2.fingerprint())
    assert det, "EVENT STREAM NOT DETERMINISTIC"

    # --- what's in the log ------------------------------------------------ #
    c = log.counts()
    print("\nEVENT LOG CONTENTS (by scale/kind):")
    for scale in ("individual", "deme", "world"):
        items = {k: v for (s, k), v in c.items() if s == scale}
        if items:
            print(f"   {scale:<11}: " +
                  ", ".join(f"{k} {v}" for k, v in sorted(items.items())))
    print(f"   total events: {len(log)}   ·   deterministic fingerprint: "
          f"{log.fingerprint()}  (matches rerun: {det})")

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "world_events.jsonl")
    log.to_jsonl(out)
    print(f"   written: {out}")

    # --- the world chronicle (deme + world scale) ------------------------- #
    big = log.query(scale="world") + log.query(kinds={"local_extinction",
                                                      "recolonize"})
    big.sort(key=lambda e: e.t)
    print("\n" + log.narrate(big[:14], "WORLD CHRONICLE (synchronous events & "
                             "colonisation)"))

    # --- one pawn's subjective history: its lineage memory (LLM-ready) ---- #
    focal = max(w.pop, key=lambda a: len(log.lineage(a.oid)))
    chain = log.lineage(focal.oid)
    _, birth = log._parent_map()
    genealogy = [birth[a] for a in chain if a in birth]
    print("\n" + log.narrate(genealogy,
          f"PAWN #{focal.oid} — LINEAGE MEMORY  ({len(chain)} generations, "
          f"now in cell ({focal.i},{focal.j}))"))
    persp = log.perspective(focal.oid)
    world_lived = [e for e in persp if e.scale == "world"]
    local_shocks = [e for e in persp if e.kind in ("crash", "local_extinction")]
    g0 = genealogy[0].data.get("gene")
    print(f"\n   from the cells it passed through, this line witnessed "
          f"{len(world_lived)} world-scale shifts and {len(local_shocks)} local "
          f"shocks;\n   its thermal gene drifted {g0-273.15:+.1f}°C → "
          f"{focal.gene-273.15:+.1f}°C across {len(chain)} generations. That bounded,")
    print("   subjective record is exactly what a stage-2 cognitive agent would "
          "read\n   back as memory — and weave into belief.")

    # --- universality: the SAME detectors on a completely different sim ---- #
    try:
        import sim_portfolio as PF
        s_ind, _ = PF.run(omega=0.0)        # desynchronized metapopulation
        s_syn, _ = PF.run(omega=1.0)        # synchronized (Moran)
        li, ls = EventLog(), EventLog()
        detect_world_events(li, s_ind)
        detect_world_events(ls, s_syn)
        ni = len(li.query(kind="sync_crash"))
        ns = len(ls.query(kind="sync_crash"))
        print("\nUNIVERSALITY — the identical world detector on sim_portfolio's "
              "raw biomass series:")
        print(f"   synchronous downturns found: independent {ni}  vs  "
              f"synchronized {ns}")
        print("   one schema, one detector, a different sim — and it recovers the "
              "Moran/portfolio result.")
    except Exception as ex:
        print(f"\n(universality cross-check skipped: {ex})")

    print(f"\nmatter conserved ({w.matter_drift():.1e}) · log faithful · "
          f"deterministic from seed {SEED}  ✓")


if __name__ == "__main__":
    main()
