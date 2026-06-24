"""
sim_genetics.py — heritable information on the ecological axis.

Sits conceptually on top of sim_ecology: here, the "animals" carry a GENOME that
is copied (with error) on reproduction and filtered by selection. The point this
demonstrates is the one from our discussion of information:

    Evolution is an information process. Natural selection accumulates
    information about the environment INTO the genome — adaptation is the
    population "learning" its world. That information is built up slowly,
    tracked while the environment changes gradually, and LOST IRREVERSIBLY on
    extinction. The arrow of time, read at the level of meaning, is extinction.

We MEASURE the information. A population's gene distribution starts broad (high
entropy, knows nothing) and narrows around the environmental optimum (low
entropy = information gained). We report that gain in BITS. When the environment
shifts gradually, the population re-learns (information tracks). When it shifts
faster than selection can follow, the population dies and every bit it had
accumulated is gone — and would not come back even if the old environment did.

Conservation discipline is preserved: matter cycles in a closed loop
(resource -> body -> detritus -> resource), so total matter is exactly constant
— an invariant we assert, exactly as the energy/mass invariants in the kernel.
Energy throughput is abstracted into the decomposition rate (the engine that
keeps the loop turning); sim_ecology has the full solar/entropy treatment.

Determinism: a single seeded RNG drives all mutation and ordering, so the entire
evolutionary history is reproducible and replayable — which is exactly the
property the reversibility discussion turns on.

Pure stdlib.
"""

from __future__ import annotations

import math
import random
from statistics import mean, pstdev

SEED = 42
# reference spread of the initial (uninformed) gene distribution, used as the
# baseline against which information gain is measured. Uniform[270,310] -> ~11.5
PRIOR_STD = 40.0 / math.sqrt(12.0)


class Organism:
    __slots__ = ("temp_opt", "body", "age")

    def __init__(self, temp_opt, body):
        self.temp_opt = temp_opt     # the heritable gene under selection (K)
        self.body = body             # matter reserve (conserved)
        self.age = 0


class Evolver:
    # --- matter (closed loop, exactly conserved) ---------------------------
    TOTAL_MATTER = 8000.0
    DECOMP_RATE = 0.15          # detritus -> resource per generation (throughput)

    # --- feeding -----------------------------------------------------------
    FEED_MAX = 1.5              # max matter eaten per organism per generation
    FEED_HALFSAT = 1500.0       # resource at which feeding is half-max

    # --- metabolism + the selection pressure -------------------------------
    BASE_UPKEEP = 0.5           # matter spent on upkeep at perfect adaptation
    TEMP_PENALTY = 0.03         # extra upkeep per (K of climate mismatch)^2
    DEATH_THRESHOLD = 0.2       # body below this -> death

    # --- reproduction + mutation (the copy-with-error) ---------------------
    REPRO_THRESHOLD = 2.2       # body size required to split
    MUTATION_STD = 0.7          # K, gene copy error per reproduction

    def __init__(self, env_temp=290.0, n0=200):
        self.rng = random.Random(SEED)
        self.env_temp = env_temp
        self.pop = [Organism(self.rng.uniform(270.0, 310.0), 1.2)
                    for _ in range(n0)]
        self.detritus = 0.0
        self.resource = self.TOTAL_MATTER - sum(o.body for o in self.pop)

    def step(self):
        rng = self.rng

        # 1. DECOMPOSITION — detritus returns to the resource pool (throughput
        #    engine that keeps the matter loop turning)
        back = self.detritus * self.DECOMP_RATE
        self.detritus -= back
        self.resource += back

        # 2-4. feed, pay upkeep (with adaptation penalty), die, reproduce
        rng.shuffle(self.pop)        # deterministic given the seed; fair feeding
        survivors = []
        newborns = []
        for o in self.pop:
            # feed: Holling type-II draw from the shared resource (matter moves
            # resource -> body)
            desired = self.FEED_MAX * self.resource / (self.resource + self.FEED_HALFSAT)
            eat = min(desired, self.resource)
            self.resource -= eat
            o.body += eat

            # upkeep, rising quadratically with climate mismatch (matter moves
            # body -> detritus). THIS is selection: maladapted genomes bleed
            # matter and starve.
            mismatch = o.temp_opt - self.env_temp
            upkeep = self.BASE_UPKEEP + self.TEMP_PENALTY * mismatch * mismatch
            upkeep = min(upkeep, o.body)
            o.body -= upkeep
            self.detritus += upkeep
            o.age += 1

            # death (body -> detritus)
            if o.body < self.DEATH_THRESHOLD:
                self.detritus += o.body
                continue

            # reproduction: split body in half, child inherits the gene plus a
            # copy error (matter conserved: one body -> two halves)
            if o.body >= self.REPRO_THRESHOLD:
                half = o.body / 2.0
                o.body = half
                child = Organism(o.temp_opt + rng.gauss(0.0, self.MUTATION_STD), half)
                newborns.append(child)

            survivors.append(o)

        self.pop = survivors + newborns

    # --- measurement -------------------------------------------------------
    def stats(self):
        n = len(self.pop)
        if n == 0:
            return {"n": 0, "mean": float("nan"), "std": float("nan"),
                    "info_bits": 0.0, "error": float("nan")}
        genes = [o.temp_opt for o in self.pop]
        m = mean(genes)
        s = pstdev(genes) if n > 1 else 0.0
        # information accumulated about the environment, in bits, = how much the
        # gene distribution has narrowed below the uninformed prior
        info = max(0.0, math.log2(PRIOR_STD / s)) if s > 1e-9 else float("inf")
        return {"n": n, "mean": m, "std": s, "info_bits": info,
                "error": abs(m - self.env_temp)}

    def total_matter(self):
        return self.resource + sum(o.body for o in self.pop) + self.detritus


# --------------------------------------------------------------------------- #
#  Demo: accumulate -> track -> lose                                           #
# --------------------------------------------------------------------------- #

def demo():
    print("=" * 78)
    print("Evolution as information accumulated about the environment")
    print("One gene (temperature optimum) under selection. Population starts")
    print("knowing nothing (genes spread randomly over 270-310 K).")
    print("  Phase A  gen   0-149 : climate steady at 290 K  -> the population")
    print("                          LEARNS it (genes narrow, info rises).")
    print("  Phase B  gen 150-299 : climate warms slowly 290->~299 K -> selection")
    print("                          TRACKS it (info maintained through change).")
    print("  Phase C  gen 300+    : climate SHOCKS to 268 K (-31 K at once) ->")
    print("                          change outruns selection. Watch what happens")
    print("                          to the accumulated information.")
    print("=" * 78)

    ev = Evolver(env_temp=290.0, n0=200)
    m0 = ev.total_matter()

    print(f"{'gen':>4} {'env(K)':>7} {'pop':>5} {'gene_mean(K)':>13} "
          f"{'gene_std':>9} {'info(bits)':>11} {'adapt_err(K)':>13} {'matter':>9}")

    def row(gen):
        s = ev.stats()
        meanf = f"{s['mean']:.1f}" if s["n"] else "—"
        stdf = f"{s['std']:.2f}" if s["n"] else "—"
        errf = f"{s['error']:.2f}" if s["n"] else "—"
        print(f"{gen:>4} {ev.env_temp:>7.1f} {s['n']:>5} {meanf:>13} {stdf:>9} "
              f"{s['info_bits']:>11.2f} {errf:>13} {ev.total_matter():>9.1f}")

    for gen in range(461):
        if 150 <= gen < 300:
            ev.env_temp += 0.06            # gradual warming
        if gen == 300:
            ev.env_temp = 268.0            # abrupt climate shock
        if gen % 20 == 0:
            row(gen)
        ev.step()

    print("-" * 78)
    print(f"matter drift over whole run: {abs(ev.total_matter() - m0):.3e}  "
          f"(closed loop — matter is exactly conserved)")
    final = ev.stats()
    if final["n"] == 0:
        print("OUTCOME: EXTINCTION. Population is gone; every bit of information it")
        print("  had accumulated about its world is destroyed. If the climate now")
        print("  returned to 290 K, nothing remains to 'remember' it — the loss is")
        print("  irreversible. That is the second law wearing the mask of meaning.")
    else:
        print(f"OUTCOME: {final['n']} survivors re-adapting; gene_mean "
              f"{final['mean']:.1f} K racing toward the new optimum — information "
              f"being rebuilt from the survivors.")

    assert math.isclose(ev.total_matter(), m0, rel_tol=1e-9, abs_tol=1e-6), \
        "MATTER NOT CONSERVED"
    print("\nmatter conservation ✓  ·  evolution ran deterministically from "
          f"seed {SEED} (fully replayable)")


if __name__ == "__main__":
    demo()
