"""
sim_world.py — the full synthesis.

Everything from the arc, woven into one system:
  - sim_core      : mass + energy conservation, phase-aware thermodynamics
  - sim_ecology   : boundary flux (Sun in / space out), entropy, photosynthesis
                    as a dissipative structure
  - sim_genetics  : a heritable genome, copied with error, filtered by selection,
                    information accumulated about the environment

The new thing here, and the whole point: SELECTION NOW RUNS ON REAL
THERMODYNAMICS, not an abstract penalty.

  * Herbivores are real `biomass_animal` matter (mass + chemical energy). The
    invariant  sum(animal bodies) == animal-biomass parcel mass  is asserted.
  * They eat real plant biomass; the unassimilated part is respired (its bond
    energy becomes heat in the patch, which radiates to space).
  * Their metabolic upkeep is real biomass burned per step. Its RATE rises with
    the mismatch between the animal's genome (its temperature optimum) and the
    ACTUAL patch temperature — and that temperature is not scripted: it emerges
    from the solar/radiation energy balance. A maladapted genome literally burns
    more of its body as heat, loses mass, and starves. Fitness IS an energy
    budget.
  * So the gene distribution comes to encode the physically-emergent temperature
    of the world. Change the Sun, the real temperature shifts, and the genome
    must re-learn it — on the conserved energy/entropy substrate the whole time.

Matter cycles in a closed loop (CO2+H2O -photosynthesis-> plant -grazing->
animal -respiration/decay-> CO2+H2O); only energy crosses the boundary. Seeded
RNG => the entire eco-evolutionary history is deterministic and replayable.

Put this next to sim_core.py and sim_ecology.py. Pure stdlib.
"""

from __future__ import annotations

import math
import random
from statistics import mean, pstdev

from sim_core import Parcel, Cell, Material, MATERIALS, to_c, conduct_parcels
from sim_ecology import (
    STEFAN_BOLTZMANN, T_SUN_EFFECTIVE, T_SPACE, EMISSIVITY,
    PLANT, ANIMAL, CO2, O2, WATER,
    BIOMASS_CHEM_ENERGY, O2_PER_BIOMASS,
    _respire, _photosynthesize,
)

SEED = 7
PRIOR_STD = 40.0 / math.sqrt(12.0)     # initial genome spread (uniform 260-300)

# dead biomass: same stoichiometry as living biomass, decomposes back to CO2+H2O
MATERIALS.setdefault("detritus", Material("detritus", density=700, c_solid=2500,
                                          chemical_energy=BIOMASS_CHEM_ENERGY))
DETRITUS = MATERIALS["detritus"]


class Animal:
    __slots__ = ("temp_opt", "body", "age")

    def __init__(self, temp_opt, body):
        self.temp_opt = temp_opt       # heritable gene under thermodynamic selection
        self.body = body               # kg of biomass_animal (a slice of the parcel)
        self.age = 0


class LivingWorld:
    # --- environment -------------------------------------------------------
    AREA = 1000.0                  # m^2 — a real meadow; throughput feeds a herd
    BASE_SUN_FLUX = 361.0          # W/m^2 -> radiative equilibrium near ~290 K

    # --- plants (aggregate biomass on solar throughput) --------------------
    PHOTO_EFFICIENCY = 0.03        # small, so the patch temperature is a stable
    K_LEAF = 0.004                 #   function of the Sun, not of the biota
    PLANT_MAINTENANCE = 1.5e-8     # /s

    # --- herbivores (individuals with genomes) -----------------------------
    GRAZE = 1.0e-6                 # /s grazing coefficient (per kg body)
    GRAZE_HALFSAT = 300.0          # kg plant biomass at half grazing rate
    ASSIMILATION = 0.45            # fraction of eaten biomass kept as body
    BASE_MAINT = 2.0e-7            # /s upkeep at perfect adaptation
    TEMP_PENALTY = 6.0e-9          # /s extra upkeep per (K mismatch)^2  <-- selection
    CROWD = 1.5e-9                 # /s upkeep per individual -> logistic self-limit
    REPRO_THRESHOLD = 6.0          # kg body to split
    DEATH_THRESHOLD = 1.0          # kg body -> death
    MUTATION_STD = 0.8             # K gene copy error

    # --- decay -------------------------------------------------------------
    DECOMP = 2.0e-7                # /s detritus -> CO2 + H2O + heat

    def __init__(self, n_herbivores=60):
        self.rng = random.Random(SEED)
        self.sun_flux = self.BASE_SUN_FLUX
        self.time = 0.0
        self.cell = Cell(0, [
            Parcel.at_temperature(MATERIALS["soil"], 2.0e6, 290.0),
            Parcel.at_temperature(CO2, 12000.0, 290.0),
            Parcel.at_temperature(O2, 12000.0, 290.0),
            Parcel.at_temperature(WATER, 15000.0, 290.0),
            Parcel.at_temperature(PLANT, 1000.0, 290.0),
        ])
        # seed herbivores with a broad, uninformed genome distribution that
        # brackets the (unknown to them) emergent patch temperature
        self.pop = []
        body0 = 4.0
        for _ in range(n_herbivores):
            self.pop.append(Animal(self.rng.uniform(260.0, 300.0), body0))
        # their bodies are real biomass in the patch
        self.cell.add_parcel(Parcel.at_temperature(ANIMAL,
                                                    n_herbivores * body0, 290.0))
        # boundary ledgers
        self.energy_in = self.energy_out = 0.0
        self.entropy_in = self.entropy_out = 0.0
        self.E0 = self._total_energy()

    # --- aggregate state ---------------------------------------------------
    def _total_energy(self):
        return sum(p.total_energy for p in self.cell.parcels)

    def total_mass(self):
        return sum(p.mass for p in self.cell.parcels)

    @property
    def T(self):
        return self.cell.temperature

    # --- the tick ----------------------------------------------------------
    def tick(self, dt):
        c = self.cell
        rng = self.rng
        t_ref = c.temperature              # start-of-step (daily-balanced) temp

        # 1. BOUNDARY FLUXES as ONE net step. Dumping a day of sunlight and only
        #    then radiating would spike the temperature within the tick and the
        #    herbivores would sample the spike, not the daily mean. So we apply
        #    (solar in - radiation out) together, with radiation evaluated at the
        #    start-of-step temperature. At steady state the two nearly cancel and
        #    the temperature the organisms feel is stable.
        incident = self.sun_flux * self.AREA * dt
        self.energy_in += incident
        self.entropy_in += incident / T_SUN_EFFECTIVE
        chem = _photosynthesize(c, incident, self.PHOTO_EFFICIENCY, self.K_LEAF)
        q_rad = 0.0
        if t_ref > T_SPACE:
            p_rad = EMISSIVITY * STEFAN_BOLTZMANN * self.AREA * (t_ref**4 - T_SPACE**4)
            q_rad = min(max(0.0, p_rad * dt),
                        0.25 * sum(pc.thermal_energy for pc in c.parcels))
            self.energy_out += q_rad
            self.entropy_out += q_rad / t_ref
        c.add_heat((incident - chem) - q_rad)     # single net heat application

        # 2. HERBIVORES — feed, pay real metabolic cost, die, reproduce.
        #    Selection happens here, in joules: upkeep rises with the mismatch
        #    between genome and the ACTUAL emergent temperature, and is paid in
        #    burned biomass.
        t_patch = c.temperature
        n_now = len(self.pop)                  # for density-dependent crowding
        rng.shuffle(self.pop)                  # deterministic, fair feeding order
        survivors, newborns = [], []
        for a in self.pop:
            plant_avail = c.mass_of(PLANT)
            # grazing (Holling type-II), limited by the shared plant pool
            eaten = (self.GRAZE * a.body * plant_avail
                     / (plant_avail + self.GRAZE_HALFSAT) * dt)
            eaten = min(eaten, plant_avail)
            if eaten > 0:
                assimilated = self.ASSIMILATION * eaten
                u = c.consume(PLANT, assimilated)       # plant -> animal (relabel)
                c.add_parcel(Parcel(ANIMAL, assimilated, u))
                a.body += assimilated
                _respire(c, PLANT, eaten - assimilated)  # rest dissipated as heat

            # metabolic upkeep = base + thermodynamic mismatch penalty + crowding
            mismatch = a.temp_opt - t_patch
            upkeep = (self.BASE_MAINT + self.TEMP_PENALTY * mismatch * mismatch
                      + self.CROWD * n_now) * a.body * dt
            burned = _respire(c, ANIMAL, min(upkeep, a.body))   # body -> heat
            a.body -= burned
            a.age += 1

            # death: remaining body becomes detritus (still conserved)
            if a.body < self.DEATH_THRESHOLD:
                u = c.consume(ANIMAL, a.body)
                c.add_parcel(Parcel(DETRITUS, a.body, u))
                continue

            # reproduction: split body, child inherits genome + copy error
            if a.body >= self.REPRO_THRESHOLD:
                half = a.body / 2.0
                a.body = half
                newborns.append(Animal(a.temp_opt + rng.gauss(0.0, self.MUTATION_STD),
                                       half))
            survivors.append(a)
        self.pop = survivors + newborns

        # 3. plant upkeep + decomposition of detritus (close the matter loop)
        _respire(c, PLANT, self.PLANT_MAINTENANCE * c.mass_of(PLANT) * dt)
        _respire(c, DETRITUS, self.DECOMP * c.mass_of(DETRITUS) * dt)

        # 4. well-mixed: equalise parcel temperatures (conservative)
        ps = c.parcels
        for _ in range(2):
            for i in range(len(ps)):
                for j in range(i + 1, len(ps)):
                    conduct_parcels(ps[i], ps[j], 1.0e12, dt)

        self.time += dt

    # --- auditors ----------------------------------------------------------
    def energy_balance_error(self):
        return (self._total_energy() - self.E0) - (self.energy_in - self.energy_out)

    def entropy_surplus(self):
        return self.entropy_out - self.entropy_in

    def body_parcel_mismatch(self):
        """Invariant: sum of individual bodies == the animal-biomass parcel."""
        return abs(sum(a.body for a in self.pop) - self.cell.mass_of(ANIMAL))

    def gene_stats(self):
        n = len(self.pop)
        if n == 0:
            return {"n": 0, "mean": float("nan"), "std": float("nan"),
                    "info_bits": 0.0}
        g = [a.temp_opt for a in self.pop]
        m = mean(g)
        s = pstdev(g) if n > 1 else 0.0
        info = max(0.0, math.log2(PRIOR_STD / s)) if s > 1e-9 else float("inf")
        return {"n": n, "mean": m, "std": s, "info_bits": info}


# --------------------------------------------------------------------------- #
#  Demo: the genome tracks the world's emergent temperature                    #
# --------------------------------------------------------------------------- #

def demo():
    print("=" * 80)
    print("FULL SYNTHESIS — selection on real thermodynamics")
    print("Herbivores (real biomass, individual genomes) graze a sunlit patch.")
    print("Their metabolic cost rises with the mismatch between genome and the")
    print("PATCH'S OWN emergent temperature (set by the solar/radiation balance).")
    print("Watch the gene_mean chase T_patch — the population encoding the real")
    print("physical environment in its genes — while mass, energy-across-the-")
    print("boundary, and entropy all stay honest.")
    print("  Phase A (day    0- 999): steady Sun  -> establish + learn T_patch")
    print("  Phase B (day 1000-1999): Sun brightens slowly -> T_patch rises, genes track")
    print("  Phase C (day 2000+    ): Sun drops hard -> T_patch plunges, can they keep up?")
    print("=" * 80)

    w = LivingWorld(n_herbivores=150)
    dt = 86400.0
    m0 = w.total_mass()

    print(f"{'day':>5} {'flux':>5} {'T_patch':>8} {'plant':>7} {'herb':>5} "
          f"{'gene(C)':>8} {'std':>6} {'info':>5} {'err':>5} {'E_err':>9} {'Ssurp':>7}")

    def row(day):
        g = w.gene_stats()
        gm = f"{to_c(g['mean']):.1f}" if g["n"] else "—"
        gs = f"{g['std']:.2f}" if g["n"] else "—"
        err = f"{abs(g['mean'] - w.T):.1f}" if g["n"] else "—"
        print(f"{day:>5} {w.sun_flux:>5.0f} {to_c(w.T):>7.1f}C {w.cell.mass_of(PLANT):>7.1f} "
              f"{g['n']:>5} {gm:>8} {gs:>6} {g['info_bits']:>5.2f} {err:>5} "
              f"{w.energy_balance_error():>9.1e} {w.entropy_surplus()/1e6:>7.1f}")

    for day in range(2701):
        if 1000 <= day < 2000:
            w.sun_flux += 0.04            # gentle warming the genome can track
        if day == 2000:
            w.sun_flux = 230.0            # sudden dimming -> cold shock
        if day % 100 == 0:
            row(day)
        w.tick(dt)

    print("-" * 80)
    print(f"mass drift over run        : {abs(w.total_mass() - m0):.3e} kg")
    print(f"energy balance error       : {w.energy_balance_error():.3e} J "
          f"(conserved across the boundary)")
    print(f"body<->parcel invariant    : {w.body_parcel_mismatch():.3e} kg "
          f"(sum of bodies == animal biomass parcel)")
    print(f"net entropy produced       : {w.entropy_surplus()/1e6:.1f} MJ/K")
    g = w.gene_stats()
    if g["n"] == 0:
        print("OUTCOME: herbivores EXTINCT. The cold shock outran selection; every")
        print("  bit the lineage had learned about its world is gone for good.")
    else:
        print(f"OUTCOME: {g['n']} herbivores; genome mean {to_c(g['mean']):.1f} C "
              f"tracking the patch at {to_c(w.T):.1f} C — the gene pool literally "
              f"encodes the world's physical temperature.")

    assert math.isclose(w.total_mass(), m0, rel_tol=1e-9, abs_tol=1e-5), "MASS"
    assert abs(w.energy_balance_error()) < 10.0, "ENERGY ACROSS BOUNDARY"
    assert w.body_parcel_mismatch() < 1e-4, "BODY/PARCEL INVARIANT"
    assert w.entropy_surplus() > 0, "SECOND LAW"
    print("\nALL INVARIANTS HOLD ✓  mass · energy-across-boundary · body/parcel · "
          "entropy  —  deterministic from seed", SEED)


if __name__ == "__main__":
    demo()
