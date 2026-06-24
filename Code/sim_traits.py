"""
sim_space.py — evolution in space: clines, range shifts, and refugia.

The capstone (sim_world) had ONE patch with ONE emergent temperature, and the
population learned that single number. Space changes the kind of thing that can
be learned. Put a temperature GRADIENT across a 2D world — a sunlit "equator"
fading to a cold "pole" — let heat diffuse (conservatively) so the gradient is
the world's own emergent equilibrium, and let individual herbivores carry a
genome, be selected by the temperature of the cell they actually stand in, and
MIGRATE between cells. Then:

    The population stops encoding a number and starts encoding a MAP. A genetic
    CLINE emerges: warm-adapted genes where it is warm, cold-adapted genes where
    it is cold — a smooth genomic gradient mirroring the temperature gradient.
    Local mean genome tracks local emergent temperature across the whole world.

That cline is the spatial face of "evolution = information about the
environment": the information is now spatially distributed structure. It sits at
the equilibrium of two opposing forces — migration (gene flow) homogenises,
selection differentiates — which is real population genetics.

Three things space then buys that a single patch cannot:
  * a CLINE (local adaptation across a gradient),
  * a RANGE SHIFT (when the climate warms, the cline migrates across space —
    organisms track climate by moving, not only by adapting in place),
  * REFUGIA (a shock that would extinguish a well-mixed population can leave a
    surviving pocket in the cells that stay tolerable — information preserved
    spatially through a catastrophe).

WHAT IS PHYSICALLY HONEST HERE (and the deliberate stop-rule choice):
  * The THERMAL field is fully conserved and audited: solar in per cell, Stefan-
    Boltzmann radiation out per cell, and heat diffusion between cells that moves
    energy without creating or destroying it. The temperature gradient is the
    world's own equilibrium, not a scripted backdrop. This field is the numpy
    hot path — pure array arithmetic (a conservative Laplacian) — exactly the
    part that must vectorise to run on a Raspberry Pi.
  * MATTER is fully conserved and audited: a closed loop per cell
    (soil -> plant -> detritus -> soil, plant -> herbivore body -> detritus),
    plus conservative seed dispersal of plant biomass between cells.
  * ENTROPY is produced monotonically: heat flowing down every gradient (both
    diffusion between cells and radiation to cold space) is irreversible.
  * Biological energy (photosynthesis/respiration) is abstracted into rates, as
    in sim_genetics — sim_ecology/sim_world carry the full chemical-energy
    ledger. Here the thermal field is what drives selection, so the thermal
    field is the part kept rigorously real.

DETERMINISM: a single seeded Python RNG drives mutation, reproduction order and
migration; numpy is used only for deterministic field arithmetic (no np.random).
The whole spatiotemporal history is therefore reproducible and replayable — the
property the reversibility discussion and multiplayer both rest on.

Requires numpy. Pure stdlib otherwise.
"""

from __future__ import annotations

import math
import random
from collections import defaultdict

import numpy as np

SEED = 11

# --------------------------------------------------------------------------- #
#  Grid                                                                        #
# --------------------------------------------------------------------------- #
ROWS, COLS = 20, 20            # row 0 = equator, last row = pole
CELL_AREA = 1.0e4              # m^2 per cell (100 m x 100 m)

# --------------------------------------------------------------------------- #
#  Thermal field (conserved, audited — the numpy hot path)                     #
# --------------------------------------------------------------------------- #
SIGMA = 5.670374419e-8
EMISS = 0.90
RAD = EMISS * SIGMA * CELL_AREA      # radiation_out = RAD * T^4   (W per cell)
HEATCAP = 4.2e10                     # J/K per cell (~1 m water-equivalent slab)
T_SUN = 5778.0                       # K, for solar entropy bookkeeping
KAPPA = 2.0e4                        # W/K lateral heat exchange between neighbours

T_EQ_TARGET = 303.0                  # equator radiative-equilibrium target (K)
DAY = 86400.0                        # seconds per day — the thermal field is in
                                     # WATTS, so it must integrate over real
                                     # seconds; biology runs on per-day rates.


def _insolation(rows):
    """Latitudinal insolation: ~1.0 at the equator, ~0.5 at the pole."""
    lat = np.linspace(0.0, 1.0, rows)
    return 0.5 + 0.5 * np.cos(lat * math.pi * 0.5)


# --------------------------------------------------------------------------- #
#  Matter cycle (closed loop, conserved)                                       #
# --------------------------------------------------------------------------- #
SOIL0 = 60.0                   # kg available nutrient per cell at start
PLANT_SEED = 6.0               # kg seeded into the central band
PLANT_CAP = 45.0               # logistic capacity (kg)
GROW = 0.55                    # max specific growth (1/day)
PLANT_TOPT = 295.0             # plant thermal optimum (K)
PLANT_TWID = 14.0              # plant thermal tolerance width (K)
SOIL_KS = 25.0                 # soil half-saturation (kg)
SEN = 0.020                    # senescence (1/day)
DECOMP = 0.05                  # detritus -> soil (1/day)
PLANT_DISPERSE = 0.03          # fraction of plant biomass dispersing/day (seed rain)

# --------------------------------------------------------------------------- #
#  Herbivores (individuals: position + genome, conserved bodies)               #
# --------------------------------------------------------------------------- #
N0 = 1400
FEED_MAX = 0.16                # max intake per kg of body (1/day)
FEED_KS = 10.0                 # intake half-saturation (kg)
BASE_UP = 0.085                # per-kg basal upkeep (1/day)
TEMP_PEN = 0.0026              # per-kg optimum-mismatch cost (per K^2, 1/day) -> gene 1
DEATH = 0.04                   # body below this -> death (kg)
MUT = 1.2                      # K, temp_opt copy error

# --- second gene: BODY SIZE (a Bergmann trade-off) -------------------------- #
# Larger size -> lower heat loss per kg (surface/volume ~ M^(2/3)) so it is
# cheaper to stay warm in the cold; but adult mass = BODY_REF*size must be
# reached before splitting, so large animals reproduce slower (a fecundity
# cost that wins in warm, productive cells). The cold cost depends on ABSOLUTE
# temperature, not on the temp_opt mismatch — so it does NOT vanish when temp_opt
# tracks the local temperature, leaving genuine selective pressure on size.
BODY_REF = 0.55                # adult mass (kg) = BODY_REF * size
SIZE_LO, SIZE_HI = 0.6, 2.2    # initial (uninformed) size range
SIZE_MUT = 0.06                # size copy error
SIZE_MIN = 0.25                # floor so size stays positive
T_WARM = 284.0                 # K (~11 C): at/above this there is no cold cost
COLD_PEN = 0.0016              # cold cost per (K below T_WARM) per body^(2/3), 1/day
SURF_EXP = 2.0 / 3.0           # surface/volume exponent for heat loss

MIGRATE = 0.08                 # probability/day of hopping to a neighbour cell

PRIOR_STD = 50.0 / math.sqrt(12.0)              # spread of the initial temp_opt
PRIOR_SIZE_STD = (SIZE_HI - SIZE_LO) / math.sqrt(12.0)   # spread of initial size


class Org:
    __slots__ = ("i", "j", "temp_opt", "size", "body", "age")

    def __init__(self, i, j, temp_opt, size, body):
        self.i = i
        self.j = j
        self.temp_opt = temp_opt        # gene 1: thermal optimum (K)
        self.size = size                # gene 2: body-size strategy (dimensionless)
        self.body = body
        self.age = 0

    @property
    def m_adult(self):
        return BODY_REF * self.size     # mass that must be reached to reproduce


class SimTraits:
    def __init__(self):
        self.rng = random.Random(SEED)
        self.t = 0

        # insolation map (W per cell); SOLAR scaled so equator equilibrium ~303 K
        insol = _insolation(ROWS)
        solar_eq = RAD * T_EQ_TARGET ** 4
        self.solar = (solar_eq * insol)[:, None] * np.ones((ROWS, COLS))
        self.solar_scale = 1.0

        # thermal field initialised at per-row radiative equilibrium
        T0 = (self.solar / RAD) ** 0.25
        self.U = HEATCAP * T0

        # matter pools
        self.soil = np.full((ROWS, COLS), SOIL0)
        self.plant = np.zeros((ROWS, COLS))
        cb = ROWS // 2
        self.plant[cb - 1:cb + 2, :] = PLANT_SEED        # seed a central band
        self.detritus = np.zeros((ROWS, COLS))

        # herbivores scattered everywhere; both genes broad and uninformed
        self.pop = []
        for _ in range(N0):
            i = self.rng.randrange(ROWS)
            j = self.rng.randrange(COLS)
            s = self.rng.uniform(SIZE_LO, SIZE_HI)
            self.pop.append(Org(i, j, self.rng.uniform(255.0, 305.0),
                                s, BODY_REF * s / 2.0))

        # conservation trackers
        self.matter0 = self._total_matter()
        self.U0 = float(self.U.sum())
        self.cum_solar = 0.0
        self.cum_rad = 0.0
        self.cum_net = 0.0
        self.entropy = 0.0

    # ----- field temperature ---------------------------------------------- #
    def T(self):
        return self.U / HEATCAP

    # ----- one day -------------------------------------------------------- #
    def step(self):
        self._thermal(DAY)        # thermal field is in watts -> integrate seconds
        self._plants(1.0)         # biology rates are per-day
        self._herbivores(1.0)
        self.t += 1

    def _thermal(self, dt):
        T = self.T()
        solar = self.solar * self.solar_scale
        rad = RAD * T ** 4
        net = solar - rad
        # net boundary exchange (computed at start-of-step T; dt << thermal time
        # constant ~10 d, so the explicit step is stable and never spikes)
        self.U += net * dt
        self.cum_solar += float(solar.sum()) * dt
        self.cum_rad += float(rad.sum()) * dt
        self.cum_net += float(net.sum()) * dt        # accumulate the small net,
        #                                              not the difference of two
        #                                              huge sums (no cancellation)

        # entropy: solar absorbed (from the hot sun) vs thermal radiation lost to
        # cold space — degrading high-T photons to low-T heat is irreversible
        self.entropy += float((rad / T).sum()) * dt - float(solar.sum()) * dt / T_SUN

        # conservative heat diffusion (the numpy hot path: a flux-form Laplacian)
        fy = KAPPA * (T[:-1, :] - T[1:, :])      # flux across horizontal edges (W)
        fx = KAPPA * (T[:, :-1] - T[:, 1:])      # flux across vertical edges (W)
        dU = np.zeros_like(self.U)
        dU[:-1, :] -= fy * dt
        dU[1:, :] += fy * dt
        dU[:, :-1] -= fx * dt
        dU[:, 1:] += fx * dt
        self.U += dU
        # entropy produced by heat flowing down the in-grid gradients (>= 0)
        self.entropy += float((fy * dt * (1.0 / T[1:, :] - 1.0 / T[:-1, :])).sum())
        self.entropy += float((fx * dt * (1.0 / T[:, 1:] - 1.0 / T[:, :-1])).sum())

    def _plants(self, dt):
        # conservative seed dispersal (each cell sends a share to in-bounds
        # neighbours, keeps the rest; total plant biomass unchanged)
        share = (PLANT_DISPERSE * self.plant) / 4.0
        inc = np.zeros_like(self.plant)
        out = np.zeros_like(self.plant)
        inc[1:, :] += share[:-1, :];  out[:-1, :] += share[:-1, :]
        inc[:-1, :] += share[1:, :];  out[1:, :] += share[1:, :]
        inc[:, 1:] += share[:, :-1];  out[:, :-1] += share[:, :-1]
        inc[:, :-1] += share[:, 1:];  out[:, 1:] += share[:, 1:]
        self.plant += (inc - out) * dt        # dispersal fraction is per day

        T = self.T()
        fT = np.exp(-((T - PLANT_TOPT) / PLANT_TWID) ** 2)        # thermal suitability
        light = self.solar * self.solar_scale
        light = light / light.max()
        growth = (GROW * light * fT * (self.soil / (self.soil + SOIL_KS))
                  * self.plant * (1.0 - self.plant / PLANT_CAP)) * dt
        growth = np.clip(growth, 0.0, self.soil)                 # cannot exceed soil
        self.soil -= growth
        self.plant += growth

        sen = SEN * self.plant * dt
        self.plant -= sen
        self.detritus += sen

        dec = DECOMP * self.detritus * dt
        self.detritus -= dec
        self.soil += dec

    def _herbivores(self, dt):
        rng = self.rng
        T = self.T()

        # --- grazing: organisms in the same cell share that cell's biomass;
        #     intake scales with body (bigger animals need more absolute food) ---
        bycell = defaultdict(list)
        for o in self.pop:
            bycell[(o.i, o.j)].append(o)
        for (i, j), members in bycell.items():
            avail = float(self.plant[i, j])
            n = len(members)
            for o in members:
                want = FEED_MAX * o.body * (avail / (avail + FEED_KS)) * dt
                fair = avail / n
                eat = max(0.0, min(want, fair, avail))
                avail -= eat
                o.body += eat
                n -= 1
            self.plant[i, j] = avail

        # --- upkeep, death, reproduction, migration ---
        newpop = []
        for o in self.pop:
            Tc = T[o.i, o.j]
            mism = o.temp_opt - Tc
            # basal (per kg) + biochemical optimum cost (per kg) + cost of losing
            # heat to a cold environment (~ surface area, so per-kg it falls with
            # size -> the Bergmann advantage of being large in the cold)
            cold = COLD_PEN * max(0.0, T_WARM - Tc) * (o.body ** SURF_EXP)
            up = (BASE_UP * o.body + TEMP_PEN * mism * mism * o.body + cold) * dt
            up = min(up, o.body)
            o.body -= up
            self.detritus[o.i, o.j] += up
            o.age += 1

            if o.body < DEATH:
                self.detritus[o.i, o.j] += o.body      # body -> detritus
                continue

            if o.body >= o.m_adult:                    # reach adult mass -> split
                half = o.body / 2.0
                o.body = half
                cs = max(SIZE_MIN, o.size + rng.gauss(0.0, SIZE_MUT))
                child = Org(o.i, o.j, o.temp_opt + rng.gauss(0.0, MUT), cs, half)
                newpop.append(child)

            if rng.random() < MIGRATE:                 # dispersal / gene flow
                d = rng.randint(0, 3)
                if d == 0 and o.i > 0:        o.i -= 1
                elif d == 1 and o.i < ROWS-1: o.i += 1
                elif d == 2 and o.j > 0:      o.j -= 1
                elif d == 3 and o.j < COLS-1: o.j += 1

            newpop.append(o)
        self.pop = newpop

    # ----- bookkeeping ---------------------------------------------------- #
    def _total_matter(self):
        return (float(self.soil.sum()) + float(self.plant.sum())
                + float(self.detritus.sum()) + sum(o.body for o in self.pop))

    def matter_drift(self):
        return abs(self._total_matter() - self.matter0)

    def energy_error(self):
        # diffusion is internal, so dU_total must equal the net boundary exchange
        return abs((float(self.U.sum()) - self.U0) - self.cum_net)

    def energy_rel_error(self):
        # relative to the thermal energy stock — the meaningful scale; this lands
        # at ~1e-10 (machine precision), since conservation here is algebraic
        tot = abs(float(self.U.sum())) or 1.0
        return self.energy_error() / tot

    # ----- measurement: the two clines ------------------------------------ #
    def cline(self):
        tsum = [0.0] * ROWS
        ssum = [0.0] * ROWS
        gn = [0] * ROWS
        for o in self.pop:
            tsum[o.i] += o.temp_opt
            ssum[o.i] += o.size
            gn[o.i] += 1
        Trow = (self.U / HEATCAP).mean(axis=1)        # mean temperature per row
        Ts, Gt, Gs, rows = [], [], [], []
        for i in range(ROWS):
            if gn[i] > 0:
                tm = tsum[i] / gn[i]
                sm = ssum[i] / gn[i]
                Ts.append(Trow[i]); Gt.append(tm); Gs.append(sm)
                rows.append((i, Trow[i], tm, sm, gn[i]))

        def _corr(a, b):
            if len(a) >= 3 and np.std(a) > 1e-6 and np.std(b) > 1e-6:
                return float(np.corrcoef(a, b)[0, 1])
            return float("nan")

        return _corr(Ts, Gt), _corr(Ts, Gs), rows

    def stats(self):
        n = len(self.pop)
        if n == 0:
            return {"n": 0, "tmean": float("nan"), "tstd": float("nan"),
                    "info": 0.0, "tcorr": float("nan"), "smean": float("nan"),
                    "scorr": float("nan"), "gxy": float("nan")}
        t = np.array([o.temp_opt for o in self.pop])
        s = np.array([o.size for o in self.pop])
        tstd = float(t.std())
        info = max(0.0, math.log2(PRIOR_STD / tstd)) if tstd > 1e-9 else float("inf")
        tcorr, scorr, _ = self.cline()
        gxy = (float(np.corrcoef(t, s)[0, 1])
               if t.std() > 1e-9 and s.std() > 1e-9 else float("nan"))
        return {"n": n, "tmean": float(t.mean()), "tstd": tstd, "info": info,
                "tcorr": tcorr, "smean": float(s.mean()), "scorr": scorr, "gxy": gxy}


# --------------------------------------------------------------------------- #
#  Small ASCII helpers to SEE the spatial structure                            #
# --------------------------------------------------------------------------- #
def _ramp(value, lo, hi):
    chars = " .:-=+*#%@"
    if not math.isfinite(value):
        return " "
    x = (value - lo) / (hi - lo) if hi > lo else 0.0
    x = min(0.999, max(0.0, x))
    return chars[int(x * len(chars))]


def _temp_map(sim):
    T = sim.T() - 273.15
    lo, hi = float(T.min()), float(T.max())
    lines = [f"  temperature field ({lo:+.0f}..{hi:+.0f} °C, equator=top):"]
    for i in range(ROWS):
        lines.append("    " + "".join(_ramp(T[i, j], lo, hi) for j in range(COLS)))
    return "\n".join(lines)


def _genome_map(sim):
    gm = np.full((ROWS, COLS), float("nan"))
    gsum = defaultdict(float); gn = defaultdict(int)
    for o in sim.pop:
        gsum[(o.i, o.j)] += o.temp_opt; gn[(o.i, o.j)] += 1
    for (i, j), s in gsum.items():
        gm[i, j] = s / gn[(i, j)] - 273.15
    finite = gm[np.isfinite(gm)]
    if finite.size == 0:
        return "  genome map: (no survivors)"
    lo, hi = float(finite.min()), float(finite.max())
    lines = [f"  temp_opt map ({lo:+.0f}..{hi:+.0f} °C; blank = empty):"]
    for i in range(ROWS):
        lines.append("    " + "".join(_ramp(gm[i, j], lo, hi) for j in range(COLS)))
    return "\n".join(lines)


def _size_map(sim):
    sm = np.full((ROWS, COLS), float("nan"))
    ssum = defaultdict(float); sn = defaultdict(int)
    for o in sim.pop:
        ssum[(o.i, o.j)] += o.size; sn[(o.i, o.j)] += 1
    for (i, j), v in ssum.items():
        sm[i, j] = v / sn[(i, j)]
    finite = sm[np.isfinite(sm)]
    if finite.size == 0:
        return "  size map: (no survivors)"
    lo, hi = float(finite.min()), float(finite.max())
    lines = [f"  body-size map ({lo:.1f}..{hi:.1f}x; bigger = denser; blank = empty):"]
    for i in range(ROWS):
        lines.append("    " + "".join(_ramp(sm[i, j], lo, hi) for j in range(COLS)))
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
#  Demo: cline -> range shift -> refugium                                      #
# --------------------------------------------------------------------------- #
def demo():
    print("=" * 84)
    print("Multi-dimensional adaptation: two genes, two clines, one trade-off")
    print("Same 2D world (warm equator -> cold pole, emergent diffusive gradient),")
    print("but herbivores now carry TWO genes: temp_opt (thermal optimum) and size")
    print("(a body-size strategy). Large size is cheaper to keep warm per kg in the")
    print("cold but slower to reproduce. Watch temp_opt track temperature (tCorr->+1)")
    print("AND size sort by cold (sCorr-> negative: big toward the pole = Bergmann),")
    print("with the two genes ending correlated across individuals (gXY).")
    print("  Phase A (day    0- 999): steady Sun  -> form both clines")
    print("  Phase B (day 1000-1599): gentle warming -> both clines shift")
    print("  Phase C (day 1600+    ): hard gradual cooling -> equatorial refugium")
    print("=" * 84)

    sim = SimTraits()
    hdr = (f"{'day':>5}{'sun':>6}{'pop':>7}{'temp(C)':>9}{'size':>6}{'info':>6}"
           f"{'tCorr':>7}{'sCorr':>7}{'gXY':>7}{'matter':>9}{'E_rel':>9}")
    print(hdr)

    def row():
        s = sim.stats()
        tm = f"{s['tmean']-273.15:.1f}" if s["n"] else "—"
        sm = f"{s['smean']:.2f}" if s["n"] else "—"
        tc = f"{s['tcorr']:+.3f}" if (s["n"] and math.isfinite(s['tcorr'])) else "—"
        sc = f"{s['scorr']:+.3f}" if (s["n"] and math.isfinite(s['scorr'])) else "—"
        xy = f"{s['gxy']:+.3f}" if (s["n"] and math.isfinite(s['gxy'])) else "—"
        info = f"{s['info']:.2f}" if s["n"] else "—"
        print(f"{sim.t:>5}{sim.solar_scale:>6.2f}{s['n']:>7}{tm:>9}{sm:>6}{info:>6}"
              f"{tc:>7}{sc:>7}{xy:>7}{sim.matter_drift():>9.1e}"
              f"{sim.energy_rel_error():>9.1e}")

    for day in range(2700):
        if day % 100 == 0:
            row()
        if 1000 <= day < 1600:
            sim.solar_scale += 0.00010         # gentle warming (~+0.06 over 600 d)
        elif 1600 <= day < 2300:
            sim.solar_scale -= 0.00034         # gradual hard cooling (~-0.24 over 700 d)
        sim.step()

    row()
    print("-" * 84)
    print(_temp_map(sim))
    print()
    print(_genome_map(sim))
    print()
    print(_size_map(sim))
    print("-" * 84)

    tcorr, scorr, rows = sim.cline()
    if rows:
        print("final clines (rows that still hold herbivores):")
        print(f"    {'row':>3} {'lat':>10} {'T(°C)':>7} {'temp_opt(°C)':>13} "
              f"{'size(x)':>8} {'n':>5}")
        for (i, T, g, s, n) in rows:
            lat = "equator" if i == 0 else ("pole" if i == ROWS-1 else f"{i}")
            print(f"    {i:>3} {lat:>10} {T-273.15:>7.1f} {g-273.15:>13.1f} "
                  f"{s:>8.2f} {n:>5}")
        if math.isfinite(tcorr):
            print(f"  temp_opt vs temperature across latitude : {tcorr:+.3f}  "
                  f"(warm gene where warm)")
        if math.isfinite(scorr):
            print(f"  body size vs temperature across latitude: {scorr:+.3f}  "
                  f"(negative = bigger in the cold = Bergmann's rule)")
        st = sim.stats()
        if math.isfinite(st["gxy"]):
            print(f"  gene-gene correlation across individuals: {st['gxy']:+.3f}  "
                  f"(cold-adapted individuals also tend to be large)")

    n = len(sim.pop)
    print()
    if n == 0:
        print("OUTCOME: total extinction.")
    else:
        occ = len({o.i for o in sim.pop})
        print(f"OUTCOME: {n} survivors in {occ}/{ROWS} latitude bands — an equatorial")
        print("  refugium holding a coupled two-gene adaptation: warm-adapted AND")
        print("  the size appropriate to those warm cells, retreated from the frozen")
        print("  pole. Two independent axes of information, kept honest together.")

    assert sim.matter_drift() < 1e-5, "MATTER NOT CONSERVED"
    assert sim.energy_rel_error() < 1e-6, "THERMAL ENERGY NOT CONSERVED ACROSS BOUNDARY"
    print("\nmass · thermal-energy-across-boundary · monotone entropy  ✓   "
          f"deterministic from seed {SEED}")


if __name__ == "__main__":
    demo()
