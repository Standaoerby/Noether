"""
sim_stage2.py — the minimal cognition layer, bolted onto the conserved world.

This is stage 2: a *mind* sits inside a pawn and decides where it moves. The
whole point of the build is to do this WITHOUT giving the mind any power it
should not have, and WITHOUT losing the two things the substrate already
guarantees — conservation and reproducibility. The nine principles we agreed on,
made concrete:

  1. Mind proposes, physics disposes.  A Mind never writes world state. It emits
     a typed intent (one migration step). `ActionAdapter` validates that intent
     against the legal-move menu computed by the substrate and executes it on the
     conserved grid. Beliefs are free; actions are not.
  2. Perspective = prompt, full log = truth.  A focal pawn is handed ONLY what it
     could know — its own bounded memory of cells it has visited plus the current
     cell. Never the global arrays. (Its belief can therefore be wrong; that is a
     feature, and a measurable one.)
  3. Nondeterminism quarantine.  Every decision is logged as a `cognition` event.
     `ReplayMind` rebuilds the world bit-for-bit from that log alone — it would
     work identically if the live mind had been a stochastic LLM. Reproducibility
     comes from making the mind's *outputs* part of conserved history, not from a
     deterministic model.
  4. Tiers + slow clock.  Only the focal lineage thinks, and only every
     THINK_EVERY days ("asleep" between). Everyone else is the cheap RuleMind
     substrate. Cognition is the expensive resource; we spend it sparingly.
  5. Typed I/O.  A Mind fills a fixed schema: {action, belief, rationale}. The
     legal-action menu is computed by the substrate, so a mind can only ever
     choose a LEGAL move. Free text lives only in `belief`/`rationale`.
  6. Layered memory.  Episodic memory = the per-cell observations a pawn has made
     (its perspective). Semantic memory = the one-line belief it maintains.
     Compressing episodic into belief is lossy and interpretive — Landauer
     applied to a mind, and where ideology would enter.
  7. Communication is events too.  (Not in this skeleton — but pawns would emit
     `communication` events that enter a receiver's perspective. The hook is the
     same `cognition`/`move` plumbing.)
  8. The loop closes conservatively and auditably; the mind is a *measurable*
     delta. We run the same world with cognition OFF (RuleMind on the focal
     lineage) vs ON (MockMind) from the SAME seed and measure what changed.
  9. Beliefs as data.  Beliefs are logged, so questions like "is the belief
     accurate?" become empirical.

The action space here is deliberately tiny — migration direction only — so the
plumbing is the star, not the policy. A real model (Claude via your WireGuard
path for focal pawns; a local Qwen3.6-35B-A3B behind vLLM with grammar-
constrained JSON for cohorts) drops into the `Mind` interface unchanged; see
`LLMMind` for the contract. Deterministic from seed. Pure stdlib + numpy.
"""

from __future__ import annotations

import hashlib
import os
import random
from collections import defaultdict, deque
from dataclasses import dataclass, field

import numpy as np

from sim_eventlog import (
    Animal, EventLog, MicroWorld, ROWS, COLS,
    RP, KP, KS, A_GR, KH, EFF, BASE, PEN, DEATH, REPRO, MUT, MIG, SEED,
)

# --------------------------------------------------------------------------- #
#  Geometry of choice                                                          #
# --------------------------------------------------------------------------- #
# Warm row 0 (295 K) -> cool row 4 (285 K). "N" = lower row index = warmer.
DIRS = {"N": (-1, 0), "S": (1, 0), "W": (0, -1), "E": (0, 1), "stay": (0, 0)}

DAYS = 360
THINK_EVERY = 10        # focal pawns think once per this many days ("sleep")


def legal_dirs(i, j):
    """The menu the substrate offers a pawn at (i, j): moves that stay on-grid,
    plus 'stay'. The mind may only choose from this set."""
    out = []
    for d, (di, dj) in DIRS.items():
        if d == "stay" or (0 <= i + di < ROWS and 0 <= j + dj < COLS):
            out.append(d)
    return out


# --------------------------------------------------------------------------- #
#  Typed I/O                                                                   #
# --------------------------------------------------------------------------- #
@dataclass
class Decision:
    action: str                 # one of DIRS keys
    belief: str = ""            # the pawn's evolving one-line "theory of world"
    rationale: str = ""         # why (free text; never touches state)


# --------------------------------------------------------------------------- #
#  Minds — all share one interface: decide(view, belief) -> Decision           #
# --------------------------------------------------------------------------- #
class Mind:
    kind = "base"

    def decide(self, view, belief) -> Decision:        # pragma: no cover
        raise NotImplementedError


class RuleMind(Mind):
    """The cheap default: no perception, no memory, no belief. Picks a random
    legal move. This is the focal lineage's 'unthinking' control. It moves on the
    same cadence as MockMind, so the ON/OFF contrast isolates the value of
    DIRECTION, not of moving more often. Its randomness is drawn from a SEPARATE
    generator (mind_rng), so it never perturbs the world's own RNG stream."""
    kind = "rule"

    def __init__(self, rng):
        self.rng = rng

    def decide(self, view, belief) -> Decision:
        moves = [d for d in view["legal"] if d != "stay"]
        action = self.rng.choice(moves) if moves else "stay"
        return Decision(action, belief="(no cognition)", rationale="random walk")


class MockMind(Mind):
    """A deterministic stand-in for an LLM focal agent. It reads ONLY what the
    pawn could know (bounded memory + current cell), keeps a one-line semantic
    belief, and emits a single typed migration step. Its policy is legible: head
    toward the best cell it remembers (smallest thermal mismatch to its own gene;
    remembered food breaks ties); if already there, follow an innate prior
    (warmer if my gene is above local T, cooler if below) to explore. This is the
    kind of competent, explainable behaviour we want a real model to match or
    beat — through the SAME interface, consuming NO randomness (so it is trivially
    replayable, which is the point)."""
    kind = "mock"

    def decide(self, view, belief) -> Decision:
        g = view["gene"]
        i, j = view["cell"]
        legal = view["legal"]
        mem = view["memory"]            # {(ci,cj): (T, food, last_day)}; incl. here

        # best remembered cell: minimise |gene - T|, prefer more remembered food
        best, best_key, bestT = None, None, None
        for (ci, cj), (T, food, _) in mem.items():
            key = (abs(g - T), -food)
            if best is None or key < best_key:
                best, best_key, bestT = (ci, cj), key, T

        if best is not None and best != (i, j):
            ti, tj = best
            if   ti < i: action = "N"
            elif ti > i: action = "S"
            elif tj < j: action = "W"
            else:        action = "E"
            why = f"toward remembered {best} (T {bestT - 273.15:.1f}C)"
        else:
            # at the best cell I know -> use innate prior, or explore for food
            T_here = view["T_here"]
            if g - T_here > 0.3 and "N" in legal:
                action, why = "N", "innate: want warmer -> N"
            elif g - T_here < -0.3 and "S" in legal:
                action, why = "S", "innate: want cooler -> S"
            elif "E" in legal and (i, j + 1) not in mem:
                action, why = "E", "explore E for food"
            elif "W" in legal and (i, j - 1) not in mem:
                action, why = "W", "explore W for food"
            else:
                action, why = "stay", "at optimum, hold"

        if action not in legal:         # defensive; mind shouldn't, physics says no
            action, why = "stay", why + " [clipped]"

        new_belief = (f"gene {g - 273.15:.1f}C; best-known {best} "
                      f"T {bestT - 273.15:.1f}C; seen {len(mem)} cells")
        return Decision(action, belief=new_belief, rationale=why)


class ReplayMind(Mind):
    """Replays decisions previously logged as `cognition` events. This is the
    nondeterminism quarantine in action: the world is reconstructed bit-for-bit
    from the LOG of a mind's outputs, not by re-running the mind. Hand it the
    cognition trail of a run that used a STOCHASTIC LLM and it reproduces that run
    exactly."""
    kind = "replay"

    def __init__(self, actions_by_oid):
        self.q = {oid: deque(seq) for oid, seq in actions_by_oid.items()}

    def decide(self, view, belief) -> Decision:
        action, bel = self.q[view["oid"]].popleft()    # fails loud if out of sync
        return Decision(action, belief=bel, rationale="replayed")


class LLMMind(Mind):
    """REAL model-backed focal mind. NOT exercised in the sandbox (no key, no
    egress, and we never pass keys into a sandbox). Run at home.

    Contract (identical to every other Mind):
      * input  = the bounded perspective `view` + the prior one-line `belief`
      * output = Decision(action in legal-menu, belief, rationale)

    The model fills a fixed JSON schema; the legal-action menu is computed by the
    substrate and injected into the prompt, so the model can only choose a LEGAL
    move (and we clip anyway). Free text lives only in belief/rationale. Every
    call is logged as a `cognition` event by the world, so the run stays
    replayable regardless of the model's nondeterminism — greedy decoding is a
    nicety, the replay log is the guarantee.

    Wiring (your stack):
      * focal tier  : Claude over your WireGuard path
                      client = anthropic.Anthropic(); model = "claude-sonnet-4-6"
                      (Opus only for the high-stakes / deception-study pawns)
      * cohort tier : local Qwen3.6-35B-A3B behind vLLM, OpenAI-compatible client,
                      grammar/JSON-constrained decoding bound to RESPONSE_SCHEMA.
    """
    kind = "llm"

    RESPONSE_SCHEMA = {
        "type": "object",
        "properties": {
            "action":    {"type": "string", "enum": list(DIRS.keys())},
            "belief":    {"type": "string"},
            "rationale": {"type": "string"},
        },
        "required": ["action", "belief", "rationale"],
    }

    SYSTEM = ("You are one animal in a colony. You may move one step per turn. "
              "Lower upkeep (and survival) comes from living where the local "
              "temperature matches your temperature gene. You only know what you "
              "have seen. Choose exactly one action from the legal menu and "
              "update your one-line belief about the world. Reply as JSON "
              "matching the schema; no prose outside it.")

    def __init__(self, model="claude-sonnet-4-6", client=None):
        self.model = model
        self.client = client

    def build_user_prompt(self, view, belief):
        """Bounded perspective -> prompt. This is principle 2 made literal."""
        g = view["gene"] - 273.15
        here = (f"You are at cell {view['cell']}, local T "
                f"{view['T_here'] - 273.15:.1f}C, food {view['food_here']:.1f}.")
        mem_lines = [f"  {c}: T {T - 273.15:.1f}C, food {food:.1f} (day {d})"
                     for c, (T, food, d) in sorted(view["memory"].items())]
        mem = "What you remember:\n" + ("\n".join(mem_lines) or "  (nothing yet)")
        return (f"Your temperature gene is {g:.1f}C.\n{here}\n{mem}\n"
                f"Your current belief: {belief or '(none)'}\n"
                f"Legal actions: {view['legal']}\n"
                f"Day {view['t']}. Choose one action and update your belief.")

    def decide(self, view, belief) -> Decision:
        if self.client is None:
            raise RuntimeError(
                "LLMMind needs a real client (Anthropic API or local vLLM). "
                "Run this at home; the sandbox cannot and must not call it.")
        # --- reference shape of a real call (kept inert here) ---------------
        # msg = self.client.messages.create(
        #     model=self.model, max_tokens=300, system=self.SYSTEM,
        #     messages=[{"role": "user",
        #                "content": self.build_user_prompt(view, belief)}],
        # )
        # data = json.loads(msg.content[0].text)         # vLLM: grammar-enforced
        # action = data["action"]
        # action = action if action in view["legal"] else "stay"   # physics says no
        # return Decision(action, belief=data["belief"],
        #                 rationale=data.get("rationale", ""))
        raise NotImplementedError("inert in sandbox by design")


# --------------------------------------------------------------------------- #
#  Mind proposes, physics disposes                                             #
# --------------------------------------------------------------------------- #
class ActionAdapter:
    """Validates a proposed move against the legal menu and executes it on the
    conserved substrate. Migration relocates a body between cells; it moves no
    matter into or out of any pool, so the global matter invariant is untouched.
    An illegal proposal is clipped to 'stay' — the substrate, not the mind, has
    the final say."""

    def apply(self, world, a, dec, legal):
        action = dec.action if dec.action in legal else "stay"
        di, dj = DIRS[action]
        if di == 0 and dj == 0:
            return
        fi, fj = a.i, a.j
        a.i += di
        a.j += dj
        world.log.emit(world.t, "move", "individual", where=(a.i, a.j),
                       actor=a.oid, data={"from": (fi, fj), "to": (a.i, a.j),
                                          "by": "mind"})


class Scheduler:
    """Tiers + slow clock. Only the focal lineage thinks, and only every
    `think_every` days. Everyone else is the cheap substrate."""

    def __init__(self, think_every=THINK_EVERY):
        self.think_every = think_every

    def thinks_today(self, world):
        return world.t % self.think_every == 0


# --------------------------------------------------------------------------- #
#  The world with minds in it                                                  #
# --------------------------------------------------------------------------- #
class MindWorld(MicroWorld):
    """MicroWorld, but the focal lineage's migration is routed through a Mind.
    Everything else — growth, grazing, upkeep, death, reproduction — is the base
    dynamics, untouched. The focal lineage is the set of founders that START in
    the coolest row (a deliberately hard start: cold, with random genes), plus
    all their descendants. Children inherit a COPY of a parent's memory and
    belief — the seed of cultural transmission."""

    def __init__(self, log, seed=SEED, mind=None, focal_row=ROWS - 1,
                 scheduler=None):
        super().__init__(log, seed)
        self.mind = mind
        self.adapter = ActionAdapter()
        self.scheduler = scheduler or Scheduler()
        # a separate RNG for minds, so cognition never disturbs world dynamics
        self.mind_rng = random.Random((seed * 2654435761) & 0xFFFFFFFF)
        self.focal = set()
        self.gen = {}            # oid -> generation depth (founder = 0)
        self.mem = {}            # oid -> {(i,j): (T, food, last_day)}  (episodic)
        self.belief = {}         # oid -> one-line semantic summary
        for a in self.pop:
            self.gen[a.oid] = 0
            if a.i == focal_row:
                self.focal.add(a.oid)
                self.mem[a.oid] = {}
                self.belief[a.oid] = ""
        self.founders = sorted(self.focal)

    # ---- perception (bounded; this is the pawn's perspective) ------------- #
    def _observe(self, a):
        self.mem.setdefault(a.oid, {})[(a.i, a.j)] = (
            float(self.T[a.i, a.j]), float(self.plant[a.i, a.j]), self.t)

    def _view(self, a, legal):
        return {"oid": a.oid, "gene": a.gene, "cell": (a.i, a.j),
                "T_here": float(self.T[a.i, a.j]),
                "food_here": float(self.plant[a.i, a.j]),
                "t": self.t, "legal": legal,
                "memory": dict(self.mem.get(a.oid, {}))}

    # ---- the step: base dynamics, mind-routed migration for focal pawns --- #
    def step(self):
        self.t += 1
        rng = self.rng

        # 1. plant growth from soil (conserved) — identical to base
        gP = RP * self.plant * (1 - self.plant / KP) * (self.soil / (self.soil + KS))
        gP = np.clip(gP, 0.0, self.soil)
        self.soil -= gP
        self.plant += gP

        # 2. grazing (plant -> body), shared per cell — identical to base
        bycell = defaultdict(list)
        for a in self.pop:
            bycell[(a.i, a.j)].append(a)
        for (i, j), members in bycell.items():
            avail = float(self.plant[i, j])
            n = len(members)
            for a in members:
                want = A_GR * a.body * (avail / (avail + KH))
                eat = max(0.0, min(want, avail / n, avail))
                avail -= eat
                a.body += EFF * eat
                self.soil[i, j] += (1 - EFF) * eat
                n -= 1
            self.plant[i, j] = avail

        # 3. upkeep / death / reproduction / migration
        think = self.scheduler.thinks_today(self)
        newpop = []
        for a in self.pop:
            mism = a.gene - self.T[a.i, a.j]
            up = (BASE + PEN * mism * mism) * a.body
            up = min(up, a.body)
            a.body -= up
            self.soil[a.i, a.j] += up
            a.age += 1

            if a.body < DEATH:
                self.soil[a.i, a.j] += a.body
                self.log.emit(self.t, "death", "individual", where=(a.i, a.j),
                              actor=a.oid, dm=-a.body,
                              data={"age": a.age, "cause": "starvation"})
                self.focal.discard(a.oid)
                self.mem.pop(a.oid, None)
                self.belief.pop(a.oid, None)
                continue

            if a.body >= REPRO:
                half = a.body / 2.0
                a.body = half
                child = Animal(self._next, a.i, a.j,
                               a.gene + rng.gauss(0.0, MUT), half)
                self.gen[child.oid] = self.gen.get(a.oid, 0) + 1
                self._next += 1
                self.log.emit(self.t, "birth", "individual", where=(a.i, a.j),
                              actor=child.oid, parent=a.oid,
                              data={"gene": child.gene})
                if a.oid in self.focal:
                    self.focal.add(child.oid)
                    self.mem[child.oid] = dict(self.mem.get(a.oid, {}))
                    self.belief[child.oid] = self.belief.get(a.oid, "")
                newpop.append(child)

            if a.oid in self.focal:
                # focal lineage: think (and maybe move) only on think-days
                if think:
                    self._observe(a)
                    legal = legal_dirs(a.i, a.j)
                    view = self._view(a, legal)
                    dec = self.mind.decide(view, self.belief.get(a.oid, ""))
                    self.log.emit(self.t, "cognition", "individual",
                                  where=(a.i, a.j), actor=a.oid,
                                  data={"action": dec.action,
                                        "belief": dec.belief,
                                        "rationale": dec.rationale})
                    self.belief[a.oid] = dec.belief
                    self.adapter.apply(self, a, dec, legal)
                # else: asleep — no migration today
            else:
                # everyone else: the base stochastic random-walk (world RNG)
                if rng.random() < MIG:
                    fi, fj = a.i, a.j
                    d = rng.randint(0, 3)
                    if d == 0 and a.i > 0:          a.i -= 1
                    elif d == 1 and a.i < ROWS - 1: a.i += 1
                    elif d == 2 and a.j > 0:        a.j -= 1
                    elif d == 3 and a.j < COLS - 1: a.j += 1
                    if (a.i, a.j) != (fi, fj):
                        self.log.emit(self.t, "move", "individual",
                                      where=(a.i, a.j), actor=a.oid,
                                      data={"from": (fi, fj), "to": (a.i, a.j)})
            newpop.append(a)

        self.pop = newpop
        self._record()

    # ---- audits & metrics ------------------------------------------------- #
    def state_fingerprint(self):
        """A bit-exact signature of the whole world state — census trajectory +
        every living body + total matter. Two runs with the same fingerprint are
        the same run."""
        h = hashlib.sha256()
        h.update(np.asarray(self.census).tobytes())
        for a in sorted(self.pop, key=lambda x: x.oid):
            h.update(f"{a.oid}|{a.gene:.9f}|{a.body:.9f}|{a.i}|{a.j}".encode())
        h.update(f"M{self._matter():.9f}".encode())
        return h.hexdigest()[:16]

    def focal_report(self):
        live = [a for a in self.pop if a.oid in self.focal]
        n = len(live)
        biomass = sum(a.body for a in live)
        if n:
            mismatch = sum(abs(a.gene - self.T[a.i, a.j]) for a in live) / n
            maxgen = max(self.gen.get(a.oid, 0) for a in live)
        else:
            mismatch, maxgen = float("nan"), 0
        return {"n": n, "biomass": biomass, "mismatch": mismatch, "maxgen": maxgen}


# --------------------------------------------------------------------------- #
#  Driver                                                                      #
# --------------------------------------------------------------------------- #
def run(mode, seed=SEED):
    """mode: 'off' (RuleMind on focal) | 'on' (MockMind on focal)."""
    log = EventLog()
    w = MindWorld(log, seed)
    w.mind = RuleMind(w.mind_rng) if mode == "off" else MockMind()
    for _ in range(DAYS):
        w.step()
    return w, log


def cognition_by_oid(log):
    by = defaultdict(list)
    for e in log.events:
        if e.kind == "cognition":
            by[e.actor].append((e.data["action"], e.data["belief"]))
    return by


def replay(seed, actions_by_oid):
    log = EventLog()
    w = MindWorld(log, seed)
    w.mind = ReplayMind(actions_by_oid)
    for _ in range(DAYS):
        w.step()
    return w, log


def main():
    line = "=" * 78
    print(line)
    print("STAGE 2 — a mind inside a pawn, on the conserved world")
    print(f"grid {ROWS}x{COLS}, warm row 0 (295K) -> cool row 4 (285K); focal "
          f"lineage starts in the COLD row; think every {THINK_EVERY} days; "
          f"{DAYS} days; seed {SEED}")
    print(line)

    # --- cognition OFF vs ON, same seed, same starting focal cohort -------- #
    w_off, _ = run("off")
    w_on, log_on = run("on")
    roff, ron = w_off.focal_report(), w_on.focal_report()

    n_focal0 = len(w_on.founders)
    print(f"\nfocal founders (born in the cold row): {n_focal0}\n")
    print(f"{'metric':<34}{'OFF (random walk)':>20}{'ON (mind)':>16}")
    print("-" * 70)
    def row(label, ko, kn, fmt="{:.3f}"):
        so = "extinct" if (isinstance(ko, float) and ko != ko) else fmt.format(ko)
        sn = "extinct" if (isinstance(kn, float) and kn != kn) else fmt.format(kn)
        print(f"{label:<34}{so:>20}{sn:>16}")
    row("living focal pawns", roff["n"], ron["n"], "{:d}")
    row("focal biomass (kg)", roff["biomass"], ron["biomass"])
    row("mean thermal mismatch (K)", roff["mismatch"], ron["mismatch"])
    row("deepest focal generation", roff["maxgen"], ron["maxgen"], "{:d}")

    # --- conservation holds in both ---------------------------------------- #
    print(f"\nmatter drift   OFF {w_off.matter_drift():.2e} kg   "
          f"ON {w_on.matter_drift():.2e} kg   (closed loop intact)")

    # --- the nondeterminism quarantine: replay ON from its cognition log --- #
    acts = cognition_by_oid(log_on)
    w_rp, _ = replay(SEED, acts)
    fp_on, fp_rp = w_on.state_fingerprint(), w_rp.state_fingerprint()
    n_cog = sum(len(v) for v in acts.values())
    print(f"\nreplay: rebuilt the ON world from {n_cog} logged cognition events "
          f"across {len(acts)} pawns")
    print(f"  ON  fingerprint {fp_on}")
    print(f"  RP  fingerprint {fp_rp}   ->  "
          f"{'BIT-IDENTICAL ✓' if fp_on == fp_rp else 'MISMATCH ✗'}")

    # --- one pawn's developing 'theory of the world' ----------------------- #
    if acts:
        star = max(acts, key=lambda o: len(acts[o]))
        trail = [e for e in log_on.events
                 if e.kind == "cognition" and e.actor == star]
        print(f"\nthe evolving belief of focal pawn #{star} "
              f"({len(trail)} thoughts) — its compressed theory of the world:")
        shown = trail[:: max(1, len(trail) // 6)][:6]
        for e in shown:
            print(f"  day {e.t:>4} @ {tuple(e.where)} act {e.data['action']:<4} "
                  f"| {e.data['belief']}")

    # invariants that MUST hold (the harness relies on these exits)
    assert w_off.matter_drift() < 1e-9, "OFF run leaked matter"
    assert w_on.matter_drift() < 1e-9, "ON run leaked matter"
    assert w_rp.matter_drift() < 1e-9, "replay run leaked matter"
    assert fp_on == fp_rp, "replay is not bit-identical to the ON run"

    print(f"\n{line}")
    print("mind proposes, physics disposes; perspective != truth; every thought "
          "logged & replayable; the mind is a measurable delta. deterministic "
          f"from seed {SEED}  ✓")


if __name__ == "__main__":
    main()
