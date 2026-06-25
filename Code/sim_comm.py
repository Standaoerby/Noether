"""
sim_comm.py — communication events: belief spreads, and can be shaped.

Stage 2 put a mind inside a pawn. This adds principle 7: communication is events
too. A pawn can broadcast a CLAIM about the world to whoever shares its cell. The
claim enters the receiver's perspective and is folded into its memory, so a pawn
can act on information it never observed. Claims may be truthful or not. That one
freedom turns the conserved substrate into a testbed for testimony, rhetoric, and
capture.

Why the world here is shaped as it is. Communication only matters when there is a
fact you cannot infer locally and that goes stale, on a map too large to scout
alone. So:
  * Temperature is a smooth gradient (warm row 0 -> cool last row). Anyone reads
    it from where they stand, so reports about it are worthless. It stays only as
    a survival pressure (upkeep): an oasis at the wrong latitude is a poor home.
  * FOOD is concentrated in a few OASES that RELOCATE every OASIS_PERIOD days, on
    a GRID x GRID map far too big to sweep between moves. Where food is *now* is
    the valuable, perishable, communicable fact. The desert is mildly survivable
    so no one starves merely for lack of news; the prize is the oasis bonus.

Contracts held:
  * Mind proposes, physics disposes. A message is pure data: no matter, no force.
    It changes only RECEIVERS' beliefs, hence their freely chosen moves.
    Conservation is asserted per regime. Relocating an oasis changes only a cell's
    carrying CAPACITY, never its biomass, so matter is never teleported.
  * Perspective != truth. A belief about a distant cell may rest on a lie. Direct
    sensation of the CURRENT cell always overrides hearsay.
  * Communication is logged (every claim a `communication` event, every move a
    `cognition` event). Deterministic minds replay by rerunning; a stochastic LLM
    speaker would replay from the log, as stage 2 proved.

Three regimes on one seed: none / honest (report true food) / deceptive (speakers
HIDE the oasis they sit on and cry food in the desert: claim = OASIS_CAP - true).
We measure what information did to the audience (listeners) and the elite
(speakers, who always know the truth), and how wrong the audience's beliefs are.
Standalone, deterministic, stdlib + numpy.
"""

from __future__ import annotations

import hashlib
import random
from collections import defaultdict

import numpy as np

from sim_eventlog import (
    Animal, EventLog,
    RP, KS, A_GR, KH, EFF, BASE, PEN, DEATH, REPRO, MUT, SEED,
)
from sim_stage2 import DIRS, Decision, ActionAdapter

# ---- world size & ecology (this experiment owns its own grid) ------------- #
R = 14                 # grid rows
C = 14                 # grid cols
N0 = 120               # founders
S0 = 70.0              # initial soil per cell
P0 = 8.0               # initial plant per cell
BODY0 = 0.5
T_WARM = 295.0
T_COOL = 285.0

# ---- oases & communication ------------------------------------------------ #
N_OASIS = 6
KP_LOW = 8.0           # desert carrying capacity: maintenance, not growth
KP_HIGH = 150.0        # oasis carrying capacity (the prize; reproduction happens here)
OASIS_CAP = KP_HIGH    # value the liar reflects food around
OASIS_PERIOD = 40      # oases relocate every this many days
DECAY_FRAC = 0.18      # max fraction of plant a cell sheds per step (fade, not collapse)
PEN_NAV = 0.05         # weight of thermal mismatch in the forager's cell score
SPEAKER_MOD = 4        # founders with oid % SPEAKER_MOD == 0 are speakers (~25%)

DAYS = 300
THINK_EVERY = 6


def legal_dirs(i, j):
    out = []
    for d, (di, dj) in DIRS.items():
        if d == "stay" or (0 <= i + di < R and 0 <= j + dj < C):
            out.append(d)
    return out


class ForagerMind:
    """Navigates toward the best cell it believes it knows, scoring a cell by
    believed food minus a thermal-mismatch penalty (temperature is public, read
    from the cell's row). With no useful memory it explores unvisited neighbours.
    Deterministic, consumes no randomness, so the run replays by rerunning."""

    def decide(self, view) -> Decision:
        g = view["gene"]
        i, j = view["cell"]
        legal = view["legal"]
        mem = view["memory"]            # {(ci,cj): (food_believed, day)}
        Trow = view["T_row"]

        def score(cell):
            ci, cj = cell
            food = mem[cell][0] if cell in mem else 0.0
            return food - PEN_NAV * (g - Trow[ci]) ** 2

        cands = set(mem) | {(i, j)}
        best = max(cands, key=score)

        if best != (i, j):
            ti, tj = best
            if   ti < i: action = "N"
            elif ti > i: action = "S"
            elif tj < j: action = "W"
            else:        action = "E"
            why = f"toward food at {best}"
        else:
            unseen = [d for d in legal if d != "stay"
                      and (i + DIRS[d][0], j + DIRS[d][1]) not in mem]
            action, why = (unseen[0], "explore") if unseen else ("stay", "best is here")

        if action not in legal:
            action, why = "stay", why + " [clipped]"
        belief = f"best food {best} ~{mem.get(best, (0.0,))[0]:.1f}; know {len(mem)}"
        return Decision(action, belief=belief, rationale=why)


class CommWorld:
    """Closed soil->plant->animal loop on a GRID x GRID map with moving oases and
    minds that forage by belief; a tagged subset broadcasts claims that reshape
    listeners' beliefs. regime in {'none','honest','deceptive'}."""

    def __init__(self, log, seed=SEED, regime="none"):
        assert regime in ("none", "honest", "deceptive")
        self.log = log
        self.regime = regime
        self.rng = random.Random(seed)
        self.seed = seed
        self.t = 0
        self._next = 0
        self.mind = ForagerMind()
        self.adapter = ActionAdapter()

        col = T_WARM - (T_WARM - T_COOL) * (np.arange(R) / (R - 1))
        self.T = col[:, None] * np.ones((R, C))
        self.Trow = [float(self.T[i, 0]) for i in range(R)]
        self.cells = [(i, j) for i in range(R) for j in range(C)]
        self.soil = np.full((R, C), S0)
        self.plant = np.full((R, C), P0)
        self.KPc = np.full((R, C), KP_LOW)
        self._place_oases(epoch=0)
        for (i, j) in self.oases:
            self.plant[i, j] = KP_HIGH

        self.pop: list[Animal] = []
        self.mem, self.belief, self.gen, self.from_hearsay = {}, {}, {}, {}
        self.speaker = set()
        for _ in range(N0):
            i = self.rng.randrange(R); j = self.rng.randrange(C)
            a = Animal(self._next, i, j, self.rng.uniform(T_COOL, T_WARM), BODY0)
            self.pop.append(a)
            self.gen[a.oid] = 0
            self.mem[a.oid] = {}
            self.belief[a.oid] = ""
            self.from_hearsay[a.oid] = set()
            if a.oid % SPEAKER_MOD == 0:
                self.speaker.add(a.oid)
            self.log.emit(0, "seed", "individual", where=(i, j), actor=a.oid,
                          parent=None, data={"gene": a.gene, "speaker": a.oid in self.speaker})
            self._next += 1

        self.M0 = self._matter()
        self.census = []
        self._record()

    # ---- conservation ----------------------------------------------------- #
    def _matter(self):
        return float(self.soil.sum() + self.plant.sum() + sum(a.body for a in self.pop))

    def matter_drift(self):
        return abs(self._matter() - self.M0)

    def _record(self):
        grid = np.zeros((R, C))
        for a in self.pop:
            grid[a.i, a.j] += 1
        self.census.append(grid.ravel().copy())

    # ---- moving oases ----------------------------------------------------- #
    def _place_oases(self, epoch):
        r = random.Random(self.seed * 1_000_003 + epoch * 9176 + 12345)
        self.oases = set(r.sample(self.cells, N_OASIS))
        self.KPc[:] = KP_LOW
        for (i, j) in self.oases:
            self.KPc[i, j] = KP_HIGH

    # ---- perception ------------------------------------------------------- #
    def _observe(self, a):
        self.mem[a.oid][(a.i, a.j)] = (float(self.plant[a.i, a.j]), self.t)
        self.from_hearsay[a.oid].discard((a.i, a.j))

    def _view(self, a, legal):
        return {"oid": a.oid, "gene": a.gene, "cell": (a.i, a.j),
                "legal": legal, "T_row": self.Trow, "memory": dict(self.mem[a.oid])}


    def step(self):
        self.t += 1
        rng = self.rng

        if self.t % OASIS_PERIOD == 0:
            self._place_oases(epoch=self.t // OASIS_PERIOD)

        # 1. plant growth/decay toward local capacity (conserved both directions)
        raw = RP * self.plant * (1 - self.plant / self.KPc) * (self.soil / (self.soil + KS))
        grow = np.minimum(np.maximum(raw, 0.0), self.soil)
        decay = np.minimum(np.maximum(-raw, 0.0), self.plant)
        decay = np.minimum(decay, DECAY_FRAC * self.plant)
        self.plant = self.plant + grow - decay
        self.soil = self.soil - grow + decay

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
                self.soil[i, j] += (1 - EFF) * eat; n -= 1
            self.plant[i, j] = avail

        # 3. upkeep / death / reproduction (no migration here)
        newpop = []
        for a in self.pop:
            mism = a.gene - self.T[a.i, a.j]
            up = min((BASE + PEN * mism * mism) * a.body, a.body)
            a.body -= up; self.soil[a.i, a.j] += up; a.age += 1
            if a.body < DEATH:
                self.soil[a.i, a.j] += a.body
                self.log.emit(self.t, "death", "individual", where=(a.i, a.j),
                              actor=a.oid, dm=-a.body, data={"age": a.age})
                for d in (self.mem, self.belief, self.from_hearsay):
                    d.pop(a.oid, None)
                self.speaker.discard(a.oid)
                continue
            if a.body >= REPRO:
                half = a.body / 2.0; a.body = half
                child = Animal(self._next, a.i, a.j, a.gene + rng.gauss(0.0, MUT), half)
                self.gen[child.oid] = self.gen.get(a.oid, 0) + 1
                self.mem[child.oid] = dict(self.mem.get(a.oid, {}))
                self.belief[child.oid] = self.belief.get(a.oid, "")
                self.from_hearsay[child.oid] = set(self.from_hearsay.get(a.oid, set()))
                if a.oid in self.speaker:
                    self.speaker.add(child.oid)
                self._next += 1
                self.log.emit(self.t, "birth", "individual", where=(a.i, a.j),
                              actor=child.oid, parent=a.oid, data={"gene": child.gene})
                newpop.append(child)
            newpop.append(a)
        self.pop = newpop

        # 4. think-days: speak -> sense -> move
        if self.t % THINK_EVERY == 0:
            here = defaultdict(list)
            for a in self.pop:
                here[(a.i, a.j)].append(a)

            if self.regime != "none":
                for (i, j), members in here.items():
                    speakers = [a for a in members if a.oid in self.speaker]
                    listeners = [a for a in members if a.oid not in self.speaker]
                    if not speakers or not listeners:
                        continue
                    for spk in speakers:
                        smem = self.mem[spk.oid]
                        if not smem:
                            continue
                        if self.regime == "honest":       # point to a real good spot
                            B = max(smem, key=lambda c: smem[c][0])
                            claim = smem[B][0]
                        else:                             # lure to a known-poor decoy
                            B = min(smem, key=lambda c: smem[c][0])
                            claim = OASIS_CAP
                        true_B = float(self.plant[B[0], B[1]])
                        self.log.emit(self.t, "communication", "individual",
                                      where=(i, j), actor=spk.oid,
                                      data={"cell": list(B), "claim_food": round(claim, 2),
                                            "true_food": round(true_B, 2),
                                            "truthful": self.regime == "honest",
                                            "heard_by": len(listeners)})
                        for L in listeners:               # naive trust about a remote cell
                            if B == (L.i, L.j):
                                continue
                            self.mem[L.oid][B] = (claim, self.t)
                            if abs(claim - true_B) > 1e-9:
                                self.from_hearsay[L.oid].add(B)
                            else:
                                self.from_hearsay[L.oid].discard(B)

            for a in self.pop:                          # sensation overrides hearsay
                self._observe(a)

            for a in self.pop:                          # cognition + migration
                legal = legal_dirs(a.i, a.j)
                dec = self.mind.decide(self._view(a, legal))
                self.log.emit(self.t, "cognition", "individual", where=(a.i, a.j),
                              actor=a.oid, data={"action": dec.action, "belief": dec.belief})
                self.belief[a.oid] = dec.belief
                self.adapter.apply(self, a, dec, legal)

        self._record()

    # ---- metrics ---------------------------------------------------------- #
    def state_fingerprint(self):
        h = hashlib.sha256()
        h.update(np.asarray(self.census).tobytes())
        for a in sorted(self.pop, key=lambda x: x.oid):
            h.update(f"{a.oid}|{a.gene:.9f}|{a.body:.9f}|{a.i}|{a.j}".encode())
        h.update(f"M{self._matter():.9f}".encode())
        return h.hexdigest()[:16]

    def _group(self, want_speaker):
        live = [a for a in self.pop if (a.oid in self.speaker) == want_speaker]
        n = len(live)
        return {"n": n, "biomass": sum(a.body for a in live),
                "body": (sum(a.body for a in live) / n) if n else float("nan"),
                "at_oasis": (sum(1 for a in live if (a.i, a.j) in self.oases) / n) if n else float("nan")}

    def listener_report(self): return self._group(False)
    def speaker_report(self):  return self._group(True)

    def belief_gap(self):
        errs = []
        for oid, cells in self.from_hearsay.items():
            if oid in self.speaker:
                continue
            for (i, j) in cells:
                b = self.mem[oid].get((i, j))
                if b is not None:
                    errs.append(abs(b[0] - float(self.plant[i, j])))
        return float(np.mean(errs)) if errs else 0.0


def run(regime, seed=SEED):
    log = EventLog()
    w = CommWorld(log, seed, regime)
    for _ in range(DAYS):
        w.step()
    return w, log


def main():
    line = "=" * 78
    print(line)
    print("COMMUNICATION EVENTS — belief spreads, and can be shaped")
    print(f"grid {R}x{C}; {N_OASIS} oases (cap {KP_HIGH:.0f}) move every "
          f"{OASIS_PERIOD}d; desert cap {KP_LOW:.0f}; ~1/{SPEAKER_MOD} speakers; "
          f"foragers navigate by belief; think every {THINK_EVERY}d; {DAYS}d; seed {SEED}")
    print(line)

    worlds = {r: run(r)[0] for r in ("none", "honest", "deceptive")}

    print(f"\n{'':<26}{'none (silence)':>16}{'honest':>12}{'deceptive':>12}")
    print("-" * 66)

    def show(label, fn, fmt="{:.3f}"):
        out = []
        for r in ("none", "honest", "deceptive"):
            v = fn(worlds[r])
            out.append("extinct" if (isinstance(v, float) and v != v) else fmt.format(v))
        print(f"{label:<26}{out[0]:>16}{out[1]:>12}{out[2]:>12}")

    print("AUDIENCE (listeners) — the public")
    show("  living", lambda w: w.listener_report()["n"], "{:d}")
    show("  biomass (kg)", lambda w: w.listener_report()["biomass"])
    show("  mean body (kg)", lambda w: w.listener_report()["body"])
    show("  fraction at an oasis", lambda w: w.listener_report()["at_oasis"])
    show("  belief error (food kg)", lambda w: w.belief_gap())
    print("ELITE (speakers) — who always know the truth")
    show("  living", lambda w: w.speaker_report()["n"], "{:d}")
    show("  biomass (kg)", lambda w: w.speaker_report()["biomass"])
    show("  mean body (kg)", lambda w: w.speaker_report()["body"])
    show("  fraction at an oasis", lambda w: w.speaker_report()["at_oasis"])

    print()
    for r in ("none", "honest", "deceptive"):
        d = worlds[r].matter_drift()
        print(f"matter drift [{r:<9}] {d:.2e} kg", end="   ")
        assert d < 1e-9, f"{r} leaked matter"
    print("(messages move no matter)")

    fp1 = worlds["deceptive"].state_fingerprint()
    fp2 = run("deceptive")[0].state_fingerprint()
    print(f"\nreplay: deceptive fingerprint {fp1} vs rerun {fp2} -> "
          f"{'BIT-IDENTICAL ✓' if fp1 == fp2 else 'MISMATCH ✗'}")
    assert fp1 == fp2, "communication run is not reproducible"

    log = run("deceptive")[1]
    comms = [e for e in log.events if e.kind == "communication"]
    if comms:
        lies = [e for e in comms if abs(e.data["claim_food"] - e.data["true_food"]) > 1]
        if lies:
            e = lies[len(lies) // 2]
            print(f"\nexample lie — day {e.t} @ {tuple(e.data['cell'])}: speaker "
                  f"#{e.actor} claims food {e.data['claim_food']} (true "
                  f"{e.data['true_food']}) to {e.data['heard_by']} listener(s)")
        print(f"communication events (deceptive run): {len(comms)}")

    print(f"\n{line}")
    print("a message is data, not force: it moves no matter and only reshapes "
          "beliefs. honest signal is a public good; a lie is extractive. "
          f"deterministic from seed {SEED}  ✓")


if __name__ == "__main__":
    main()
