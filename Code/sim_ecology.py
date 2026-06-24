"""
sim_ecology.py — Level-1 entropy + ecology, built on sim_core.py.

Put this file NEXT TO sim_core.py and run it.

WHAT THIS ADDS ON TOP OF THE CONSERVATION KERNEL
------------------------------------------------
1. BOUNDARY FLUX — the thing the second law forces on you. A closed box runs
   down to heat death (uniform temperature, no gradients, no work possible). So
   the world needs a low-entropy SOURCE (the Sun: concentrated energy at a very
   high effective temperature) and a high-entropy SINK (cold space: where
   low-grade waste heat is radiated away). The conservation law is now:
        E_total(t) - E_total(0) == energy_in - energy_out   (cumulative)
   i.e. energy is still conserved, but only when you count the boundary.

2. ENTROPY, LEVEL 1 — "gradient as resource", not an explicit S number on every
   parcel. Two parts:
     (a) irreversibility is already in the kernel (heat only flows hot->cold,
         combustion is one-way). Here we MEASURE it at the boundary: entropy
         imported = Q_sun / T_sun, entropy exported = Q_radiated / T_surface.
         Because T_surface << T_sun, the world exports far more entropy than it
         imports. That surplus IS the entropy the system produces — and it is
         exactly what lets it keep internal order (Schrodinger: life exports
         entropy to maintain itself).
     (b) the exergy / Carnot gate: useful work can only be drawn from a
         temperature gradient, and drawing it shrinks the gradient. Max work
         from heat Q taken at T_hot, rejected at T_cold, is Q*(1 - T_cold/T_hot).
         See `extract_work`. Energy is conserved (W + waste = drawn); entropy is
         produced.

3. ECOLOGY AS A DISSIPATIVE STRUCTURE — photosynthesis converts a small fraction
   of the solar throughput into low-entropy chemical order (biomass); herbivory
   moves energy up the trophic chain at low efficiency; metabolism and decay
   dissipate the rest as heat, which is radiated to space. Biomass — the "order"
   — persists ONLY while the throughput continues. Cut the Sun and it decays
   back to cold equilibrium. The demo shows exactly this.

Units: SI, kelvin. Pure stdlib. Mass/energy conservation reuses the kernel's
parcels, so everything here is automatically mass- and energy-balanced.
"""

from __future__ import annotations

import math

from sim_core import Material, Parcel, Cell, Phase, MATERIALS, to_c, conduct_parcels

# --------------------------------------------------------------------------- #
#  Physical constants                                                          #
# --------------------------------------------------------------------------- #

STEFAN_BOLTZMANN = 5.670374e-8     # W/(m^2 K^4)
T_SUN_EFFECTIVE = 5800.0           # K — solar photosphere; sets solar exergy
T_SPACE = 2.725                    # K — cosmic background; the cold sink
EMISSIVITY = 0.90                  # surface emissivity for radiation to space


# --------------------------------------------------------------------------- #
#  Ecology materials — biomass is just a high-chemical-energy material         #
# --------------------------------------------------------------------------- #

# biomass modelled as CH2O (M=30). Photosynthesis:  CO2 + H2O -> CH2O + O2
#   per kg of biomass (CH2O): CO2 = 44/30, H2O = 18/30, O2 out = 32/30
CO2_PER_BIOMASS = 44.0 / 30.0      # 1.4667 kg CO2 per kg biomass
H2O_PER_BIOMASS = 18.0 / 30.0      # 0.6000 kg H2O per kg biomass
O2_PER_BIOMASS = 32.0 / 30.0       # 1.0667 kg O2 produced per kg biomass
# (mass balances: 1.4667 + 0.6 == 1.0 + 1.0667)

BIOMASS_CHEM_ENERGY = 16.0e6       # J/kg stored in bonds (~real dry biomass)

MATERIALS.update({
    "biomass_plant": Material("biomass_plant", density=800, c_solid=3000,
                              chemical_energy=BIOMASS_CHEM_ENERGY),
    "biomass_animal": Material("biomass_animal", density=1000, c_solid=3500,
                               chemical_energy=BIOMASS_CHEM_ENERGY),
    "soil": Material("soil", density=1500, c_solid=900),   # inert thermal mass
})

PLANT = MATERIALS["biomass_plant"]
ANIMAL = MATERIALS["biomass_animal"]
CO2 = MATERIALS["carbon_dioxide"]
O2 = MATERIALS["oxygen"]
WATER = MATERIALS["water"]


# --------------------------------------------------------------------------- #
#  The exergy / Carnot gate  (Level-1 entropy, part b)                         #
# --------------------------------------------------------------------------- #

def extract_work(hot: Parcel, cold: Parcel, requested_work, dt, rate=1.0):
    """Run a heat engine between a hot and a cold parcel. Returns (work, waste,
    entropy_produced). Useful work can only come from the gradient; pulling it
    rejects waste heat to the cold side and shrinks the gradient. Energy is
    conserved; entropy is produced. With no gradient, no work — the second law."""
    t_h, t_c = hot.temperature, cold.temperature
    if t_h <= t_c:
        return 0.0, 0.0, 0.0                     # no gradient -> no work
    eta = 1.0 - t_c / t_h                          # Carnot ceiling
    # heat we must draw from hot to deliver the requested work
    q_h = requested_work / eta if eta > 0 else math.inf
    # clamp: don't draw so much that we'd over-cool the hot reservoir past
    # equilibrium, and respect a per-tick rate limit
    cap_h = hot.heat_capacity_rate()
    cap_c = cold.heat_capacity_rate()
    t_eq = (cap_h * t_h + cap_c * t_c) / (cap_h + cap_c)
    q_h_max = min(cap_h * (t_h - t_eq), rate * cap_h * t_h * dt)
    q_h = min(q_h, max(0.0, q_h_max))
    work = eta * q_h
    waste = q_h - work                             # rejected to cold side
    hot.add_heat(-q_h)
    cold.add_heat(+waste)
    # entropy produced = S gained by cold - S lost by hot (work carries none)
    entropy = waste / t_c - q_h / t_h
    return work, waste, max(0.0, entropy)


# --------------------------------------------------------------------------- #
#  Metabolism helpers — all reuse the kernel's conservation guarantees         #
# --------------------------------------------------------------------------- #

def _respire(cell: Cell, biomass_material: Material, kg):
    """Oxidise `kg` of biomass: biomass + O2 -> CO2 + H2O + heat. The stored
    chemical energy is released as thermal energy in the cell. Mass-balanced;
    limited by available O2. Returns kg actually respired."""
    have = cell.mass_of(biomass_material)
    kg = min(kg, have)
    if kg <= 0:
        return 0.0
    o2_needed = kg * O2_PER_BIOMASS
    o2_have = cell.mass_of(O2)
    if o2_have < o2_needed:                        # oxygen-limited
        kg *= o2_have / o2_needed if o2_needed > 0 else 0.0
        o2_needed = kg * O2_PER_BIOMASS
    if kg <= 1e-15:
        return 0.0
    # consume biomass + O2, capturing their thermal energy
    u = cell.consume(biomass_material, kg)
    u += cell.consume(O2, o2_needed)
    # chemical energy released as heat
    u += kg * biomass_material.chemical_energy
    # products (mass balanced): CO2 + H2O, carrying the thermal energy
    co2 = kg * CO2_PER_BIOMASS
    h2o = kg * H2O_PER_BIOMASS
    w_co2 = CO2.c_solid * co2
    w_h2o = WATER.c_solid * h2o
    tot = w_co2 + w_h2o
    cell.add_parcel(Parcel(CO2, co2, u * w_co2 / tot))
    cell.add_parcel(Parcel(WATER, h2o, u * w_h2o / tot))
    return kg


def _photosynthesize(cell: Cell, incident_energy, efficiency, k_leaf):
    """Build plant biomass from CO2 + H2O using a fraction of the incident solar
    energy. Returns the energy stored as chemical bonds (the local order built).
    The caller turns the rest of the incident energy into heat. Mass-balanced
    (CO2 + H2O -> biomass + O2); limited by CO2/H2O availability."""
    plant = cell.mass_of(PLANT)
    intercept_frac = 1.0 - math.exp(-k_leaf * plant)   # saturates with canopy
    intercepted = incident_energy * intercept_frac
    chem = efficiency * intercepted                    # energy stored as bonds
    biomass = chem / BIOMASS_CHEM_ENERGY               # kg of new biomass
    # limit by reactant availability
    need_co2 = biomass * CO2_PER_BIOMASS
    need_h2o = biomass * H2O_PER_BIOMASS
    f = 1.0
    if need_co2 > 0:
        f = min(f, cell.mass_of(CO2) / need_co2)
    if need_h2o > 0:
        f = min(f, cell.mass_of(WATER) / need_h2o)
    f = max(0.0, min(1.0, f))
    biomass *= f
    if biomass <= 1e-15:
        return 0.0
    chem = biomass * BIOMASS_CHEM_ENERGY
    # consume reactants (capture their thermal energy -> preserve it)
    u = cell.consume(CO2, biomass * CO2_PER_BIOMASS)
    u += cell.consume(WATER, biomass * H2O_PER_BIOMASS)
    # produce biomass (carries chemical energy intrinsically) + O2, splitting the
    # reactants' thermal energy so nothing is lost
    o2 = biomass * O2_PER_BIOMASS
    w_b = PLANT.c_solid * biomass
    w_o = O2.c_solid * o2
    tot = w_b + w_o
    cell.add_parcel(Parcel(PLANT, biomass, u * w_b / tot))
    cell.add_parcel(Parcel(O2, o2, u * w_o / tot))
    return chem


def _graze(cell: Cell, eaten_kg, assimilation):
    """Animals eat plant biomass. A fraction is assimilated into animal biomass
    (relabelled — same chemical energy per kg, so energy is conserved); the rest
    is respired (dissipated as heat). Mass-balanced."""
    eaten = min(eaten_kg, cell.mass_of(PLANT))
    if eaten <= 0:
        return 0.0
    assimilated = assimilation * eaten
    # relabel assimilated plant biomass -> animal biomass, carrying its heat
    u = cell.consume(PLANT, assimilated)
    cell.add_parcel(Parcel(ANIMAL, assimilated, u))
    # respire the unassimilated remainder
    _respire(cell, PLANT, eaten - assimilated)
    return eaten


# --------------------------------------------------------------------------- #
#  The ecosystem: one well-mixed patch with sun in and space out               #
# --------------------------------------------------------------------------- #

class Ecosystem:
    # --- biological rates (per second). Tuned for visible dynamics, not realism.
    PHOTO_EFFICIENCY = 0.10        # fraction of intercepted light stored as bonds
    K_LEAF = 0.04                  # canopy light-interception saturation
    PLANT_MAINTENANCE = 1.5e-8     # /s respired for upkeep
    ANIMAL_MAINTENANCE = 4.0e-8    # /s respired for upkeep (animals cost more)
    GRAZE_COEF = 5.0e-9            # /s mass-action grazing coefficient
    ASSIMILATION = 0.35            # fraction of eaten biomass -> animal biomass

    def __init__(self, area_m2=1.0, sun_flux=361.0):
        self.area = area_m2
        self.sun_flux = sun_flux           # W/m^2 (361 ~ equilibrium near 290 K)
        self.sun_on = True
        # one patch: inert soil thermal mass + atmosphere + starting life
        self.cell = Cell(0, [
            Parcel.at_temperature(MATERIALS["soil"], 2000.0, 290.0),
            Parcel.at_temperature(CO2, 60.0, 290.0),
            Parcel.at_temperature(O2, 60.0, 290.0),
            Parcel.at_temperature(WATER, 80.0, 290.0),
            Parcel.at_temperature(PLANT, 10.0, 290.0),
            Parcel.at_temperature(ANIMAL, 1.0, 290.0),
        ])
        self.time = 0.0
        # boundary ledgers
        self.energy_in = 0.0
        self.energy_out = 0.0
        self.entropy_in = 0.0
        self.entropy_out = 0.0
        self.E0 = self.total_energy()

    # --- aggregate state ---------------------------------------------------
    def total_energy(self):
        return sum(p.total_energy for p in self.cell.parcels)

    def total_mass(self):
        return sum(p.mass for p in self.cell.parcels)

    def biomass(self, material):
        return self.cell.mass_of(material)

    # --- the tick ----------------------------------------------------------
    def tick(self, dt):
        c = self.cell

        # 1. SOLAR INPUT (low-entropy energy enters the system)
        if self.sun_on:
            incident = self.sun_flux * self.area * dt
            self.energy_in += incident
            self.entropy_in += incident / T_SUN_EFFECTIVE
            # photosynthesis stores a little as chemical order; rest -> heat
            chem = _photosynthesize(c, incident, self.PHOTO_EFFICIENCY, self.K_LEAF)
            c.add_heat(incident - chem)

        # 2. TROPHIC FLOW + METABOLISM (energy moves up, mostly dissipates)
        plant = c.mass_of(PLANT)
        animal = c.mass_of(ANIMAL)
        self._eaten = _graze(c, self.GRAZE_COEF * plant * animal * dt,
                             self.ASSIMILATION)
        _respire(c, PLANT, self.PLANT_MAINTENANCE * plant * dt)
        _respire(c, ANIMAL, self.ANIMAL_MAINTENANCE * animal * dt)

        # 2b. WELL-MIXED: equalise parcel temperatures. Respiration dumps heat
        # into its product parcels locally; without this, temperatures diverge,
        # cold parcels hit the zero-energy floor under radiation, and the clamp
        # silently creates energy. A couple of Gauss-Seidel sweeps at very high
        # conductance drives the patch to a single temperature, conserving energy
        # exactly (pairwise transfer never overshoots equilibrium).
        ps = c.parcels
        for _ in range(2):
            for i in range(len(ps)):
                for j in range(i + 1, len(ps)):
                    conduct_parcels(ps[i], ps[j], 1.0e12, dt)

        # 3. RADIATION TO SPACE (high-entropy waste heat leaves the system)
        t = c.temperature
        if t > T_SPACE:
            p_rad = EMISSIVITY * STEFAN_BOLTZMANN * self.area * (t**4 - T_SPACE**4)
            q_out = min(max(0.0, p_rad * dt),
                        0.25 * sum(pc.thermal_energy for pc in c.parcels))
            c.add_heat(-q_out)
            self.energy_out += q_out
            self.entropy_out += q_out / t           # entropy carried away at T

        self.time += dt

    # --- auditors ----------------------------------------------------------
    def energy_balance_error(self):
        """Should stay ~0: conservation holds once you count the boundary."""
        return (self.total_energy() - self.E0) - (self.energy_in - self.energy_out)

    def entropy_surplus(self):
        """S exported - S imported. Positive and growing => the system is a net
        entropy producer, which is what pays for its internal order."""
        return self.entropy_out - self.entropy_in


# --------------------------------------------------------------------------- #
#  Demos                                                                        #
# --------------------------------------------------------------------------- #

def demo_carnot_gate():
    print("=" * 74)
    print("DEMO 1 — exergy / Carnot gate: work needs a gradient")
    print("A heat engine between a 1200 K source and a 300 K sink. Each step we")
    print("ask for work. Watch the gradient shrink, efficiency fall, and work")
    print("dry up as the two sides equalise. Energy is conserved every step;")
    print("entropy is produced every step.")
    print("=" * 74)
    hot = Parcel.at_temperature(MATERIALS["stone"], 50.0, 1200.0)
    cold = Parcel.at_temperature(MATERIALS["stone"], 50.0, 300.0)
    banked_work = 0.0
    total_entropy = 0.0
    e0 = hot.thermal_energy + cold.thermal_energy
    print(f"{'step':>4} {'T_hot(K)':>9} {'T_cold(K)':>10} {'Carnot_eff':>11} "
          f"{'work(MJ)':>9} {'S_made(kJ/K)':>13}")
    for i in range(16):
        t_h, t_c = hot.temperature, cold.temperature
        eta = max(0.0, 1 - t_c / t_h)
        w, waste, s = extract_work(hot, cold, requested_work=5.0e6, dt=1.0, rate=0.05)
        banked_work += w
        total_entropy += s
        if i % 2 == 0:
            print(f"{i:>4} {t_h:>9.0f} {t_c:>10.0f} {eta:>11.3f} "
                  f"{banked_work/1e6:>9.2f} {total_entropy/1e3:>13.2f}")
    e1 = hot.thermal_energy + cold.thermal_energy
    print("-" * 74)
    print(f"energy check: heat drawn from system = banked work + waste in cold")
    print(f"  thermal energy now {e1/1e6:.3f} MJ vs {e0/1e6:.3f} MJ start; "
          f"the {(e0-e1)/1e6:.3f} MJ difference is the {banked_work/1e6:.3f} MJ "
          f"of work we pulled out.")
    print(f"  (the rest stayed as heat, just redistributed.) entropy only ever "
          f"grew.\n")


def demo_ecosystem():
    print("=" * 74)
    print("DEMO 2 — ecology as a dissipative structure")
    print("One sunlit patch. Solar energy flows IN (low entropy), some is stored")
    print("as biomass (local ORDER), the rest dissipates and radiates to space")
    print("(high entropy). Phase A: Sun ON — order builds and sustains on the")
    print("throughput. Phase B: Sun OFF at day 1000 — no throughput, the order")
    print("decays back toward cold equilibrium. The second law, made visible.")
    print("=" * 74)
    eco = Ecosystem()
    dt = 86400.0      # 1 day per step
    print(f"{'day':>5} {'sun':>4} {'T(C)':>6} {'plant(kg)':>10} {'animal(kg)':>11} "
          f"{'E_err(J)':>10} {'S_surplus(MJ/K)':>16}")

    def row(day):
        print(f"{day:>5} {'on' if eco.sun_on else 'OFF':>4} "
              f"{to_c(eco.cell.temperature):>6.1f} "
              f"{eco.biomass(PLANT):>10.2f} {eco.biomass(ANIMAL):>11.2f} "
              f"{eco.energy_balance_error():>10.2e} "
              f"{eco.entropy_surplus()/1e6:>16.1f}")

    m0 = eco.total_mass()
    for day in range(1601):
        if day == 1000:
            eco.sun_on = False        # cut the throughput
        if day % 100 == 0:
            row(day)
        eco.tick(dt)

    print("-" * 74)
    print(f"mass drift over whole run : {abs(eco.total_mass()-m0):.3e} kg "
          f"(closed to matter — only energy crosses the boundary)")
    print(f"energy balance error      : {eco.energy_balance_error():.3e} J "
          f"(E(t)-E0 == solar_in - radiated_out)")
    print(f"cumulative solar in       : {eco.energy_in/1e6:.1f} MJ")
    print(f"cumulative radiated out   : {eco.energy_out/1e6:.1f} MJ")
    print(f"entropy imported (sun)    : {eco.entropy_in/1e6:.2f} MJ/K")
    print(f"entropy exported (space)  : {eco.entropy_out/1e6:.2f} MJ/K")
    print(f"=> net entropy produced   : {eco.entropy_surplus()/1e6:.2f} MJ/K "
          f"(>0: the patch pays for its order by dumping entropy)\n")

    assert math.isclose(eco.total_mass(), m0, rel_tol=1e-9, abs_tol=1e-6), \
        "MASS NOT CONSERVED"
    assert abs(eco.energy_balance_error()) < 1.0, \
        "ENERGY NOT CONSERVED ACROSS THE BOUNDARY"
    assert eco.entropy_surplus() > 0, "SECOND LAW VIOLATED"
    print("CHECKS PASS ✓  mass conserved · energy conserved across the boundary "
          "· entropy strictly produced")


if __name__ == "__main__":
    demo_carnot_gate()
    demo_ecosystem()
