"""
sim_core.py — Foundational substrate for a thermodynamics + conservation-driven
world simulation (the "body" of a colony-sim, before any cognition layer).

DESIGN AXIOMS
-------------
1. MASS IS CONSERVED. Always. A transformation whose inputs and outputs do not
   balance in mass is rejected at definition time — you cannot even write a
   recipe that violates it. This is the primary guard rail.

2. ENERGY IS CONSERVED. Total energy = thermal energy (kinetic, in the matter)
   + chemical potential energy (stored in the material's bonds), summed over all
   matter in the world. The ONLY ways total energy changes are explicit boundary
   fluxes (sun in, radiation out). Combustion does not "create" heat — it moves
   energy from the chemical bucket to the thermal bucket. Total stays flat.

3. WE SIMULATE PROPERTIES AND FLOWS, NEVER PARTICLES. A material is a handful of
   scalars (density, heat capacity, ignition temperature, ...). Behaviour is
   derived from those scalars everywhere, so a NEW material automatically
   composes with EVERY system — combustion, conduction, metabolism — for free.
   No molecules. No chemistry beyond an energy ledger.

4. THE CANONICAL THERMAL STATE VARIABLE IS INTERNAL ENERGY (joules), NOT
   temperature. Energy adds linearly when matter mixes; temperature does not.
   Temperature and phase (solid/liquid/gas) are DERIVED from energy. This makes
   conservation exact and makes phase transitions (melting, boiling) fall out of
   the same equations for free — including the temperature plateaus.

Units: strict SI throughout. kg, m^3, kelvin (K), joule (J), watt (W), second,
metre. Convert to Celsius only at the display edge. Pure stdlib — runs on a
Raspberry Pi as-is. Hot loops are marked for later numpy/Rust vectorisation.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from enum import Enum


# --------------------------------------------------------------------------- #
#  Materials — defined once, behaviour derived everywhere                      #
# --------------------------------------------------------------------------- #

class Phase(Enum):
    SOLID = "solid"
    LIQUID = "liquid"
    GAS = "gas"


@dataclass(frozen=True)
class Material:
    """Intrinsic, immutable properties of a substance. Add scalars per axis as
    needed (hardness for tools, nutrient_energy for biology, ...). The point is
    that you define a property ONCE here and every system reads it."""

    name: str
    density: float                      # kg/m^3  (links mass <-> volume)

    # --- thermal -----------------------------------------------------------
    c_solid: float                      # J/(kg*K) specific heat. For a material
                                        # with no phase points this is simply
                                        # "its" heat capacity, used in all states.
    c_liquid: float = None              # falls back to c_solid if omitted
    c_gas: float = None
    melting_point: float = None         # K. None => never melts (e.g. wood —
                                        #     it combusts long before)
    boiling_point: float = None         # K. None => never boils
    latent_heat_fusion: float = 0.0     # J/kg absorbed while melting (plateau)
    latent_heat_vaporization: float = 0.0
    default_phase: Phase = Phase.SOLID  # phase for materials w/o phase points
                                        #     (oxygen -> GAS, ash -> SOLID)

    # --- chemical potential energy (J/kg) stored in the material's bonds ----
    chemical_energy: float = 0.0        # released as heat when the material is
                                        #     consumed by an exothermic reaction

    # --- gameplay scalars (one per simulation axis; extend freely) ----------
    hardness: float = 0.0               # mining / tools axis
    nutrient_energy: float = 0.0        # J/kg metabolisable — biology axis

    def __post_init__(self):
        # resolve heat-capacity fallbacks (frozen dataclass => setattr trick)
        if self.c_liquid is None:
            object.__setattr__(self, "c_liquid", self.c_solid)
        if self.c_gas is None:
            object.__setattr__(self, "c_gas", self.c_solid)

    # --- energy <-> temperature, phase-aware (the heart of the model) -------

    def _phase_thresholds(self, mass):
        """Energy (J) thresholds for `mass` kg, measured from U=0 at 0 K."""
        cs = self.c_solid
        if self.melting_point is None:
            return None
        e_melt_start = mass * cs * self.melting_point
        e_melt_end = e_melt_start + mass * self.latent_heat_fusion
        if self.boiling_point is None:
            return (e_melt_start, e_melt_end, None, None)
        e_boil_start = e_melt_end + mass * self.c_liquid * (
            self.boiling_point - self.melting_point)
        e_boil_end = e_boil_start + mass * self.latent_heat_vaporization
        return (e_melt_start, e_melt_end, e_boil_start, e_boil_end)

    def temperature(self, mass, energy):
        """Derive temperature (K) from internal energy. Returns the phase
        plateau temperature during a transition (this is physically correct —
        adding heat to melting ice does not raise its temperature)."""
        if mass <= 0:
            return 0.0
        th = self._phase_thresholds(mass)
        if th is None:                                  # single-phase material
            return energy / (mass * self.c_solid)
        e_ms, e_me, e_bs, e_be = th
        if energy <= e_ms:                              # solid
            return energy / (mass * self.c_solid)
        if energy <= e_me:                              # melting plateau
            return self.melting_point
        if e_bs is None or energy <= e_bs:              # liquid
            return self.melting_point + (energy - e_me) / (mass * self.c_liquid)
        if energy <= e_be:                              # boiling plateau
            return self.boiling_point
        return self.boiling_point + (energy - e_be) / (mass * self.c_gas)  # gas

    def phase(self, mass, energy):
        if mass <= 0:
            return self.default_phase
        th = self._phase_thresholds(mass)
        if th is None:
            return self.default_phase
        e_ms, e_me, e_bs, e_be = th
        if energy <= e_ms:
            return Phase.SOLID
        if energy <= e_me:                              # mushy zone
            return Phase.SOLID if (energy - e_ms) < 0.5 * (e_me - e_ms) else Phase.LIQUID
        if e_bs is None or energy <= e_bs:
            return Phase.LIQUID
        if energy <= e_be:
            return Phase.LIQUID if (energy - e_bs) < 0.5 * (e_be - e_bs) else Phase.GAS
        return Phase.GAS

    def c_for_phase(self, phase):
        if phase is Phase.LIQUID:
            return self.c_liquid
        if phase is Phase.GAS:
            return self.c_gas
        return self.c_solid

    def energy_at_temperature(self, mass, temperature_k):
        """Inverse of `temperature`, for convenient initialisation
        ('I have X kg at temperature T'). At an exact phase point, returns the
        'transition complete' energy (fully liquid / fully gas)."""
        cs = self.c_solid
        if self.melting_point is None or temperature_k < self.melting_point:
            return mass * cs * temperature_k
        e_melt_start = mass * cs * self.melting_point
        e_melt_end = e_melt_start + mass * self.latent_heat_fusion
        if self.boiling_point is None or temperature_k < self.boiling_point:
            return e_melt_end + mass * self.c_liquid * (temperature_k - self.melting_point)
        e_boil_start = e_melt_end + mass * self.c_liquid * (
            self.boiling_point - self.melting_point)
        e_boil_end = e_boil_start + mass * self.latent_heat_vaporization
        return e_boil_end + mass * self.c_gas * (temperature_k - self.boiling_point)


# --------------------------------------------------------------------------- #
#  Parcel — the conserved quantum of matter                                    #
# --------------------------------------------------------------------------- #

@dataclass
class Parcel:
    """A quantity of a SINGLE material. Carries mass (conserved) and thermal
    energy (canonical). Temperature and phase are derived. This is the atom of
    the conservation system — everything that exists is parcels."""

    material: Material
    mass: float                 # kg  — conserved
    thermal_energy: float       # J   — canonical thermal state (>= 0)

    @classmethod
    def at_temperature(cls, material, mass, temperature_k):
        return cls(material, mass, material.energy_at_temperature(mass, temperature_k))

    @property
    def temperature(self):
        return self.material.temperature(self.mass, self.thermal_energy)

    @property
    def phase(self):
        return self.material.phase(self.mass, self.thermal_energy)

    @property
    def volume(self):
        return self.mass / self.material.density

    @property
    def chemical_energy(self):
        return self.mass * self.material.chemical_energy

    @property
    def total_energy(self):
        return self.thermal_energy + self.chemical_energy

    def heat_capacity_rate(self):
        """dU/dT (J/K) at the current state. Approximate on a plateau (uses the
        adjacent-phase capacity) — only ever used to clamp conduction rate, so
        it never affects conservation, only stability."""
        return self.mass * self.material.c_for_phase(self.phase)

    def add_heat(self, joules):
        self.thermal_energy = max(0.0, self.thermal_energy + joules)


# --------------------------------------------------------------------------- #
#  Transformation — a mass-balanced recipe with a derived energy ledger        #
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class Transformation:
    """inputs -> outputs, in kg per 'recipe multiple'. Mass balance is checked
    at construction. The heat released is DERIVED from the chemical-energy
    difference between inputs and outputs, which is exactly what guarantees
    that thermal + chemical energy is conserved when the reaction runs."""

    name: str
    inputs: dict               # Material -> kg consumed per multiple
    outputs: dict              # Material -> kg produced per multiple
    activation_temperature: float = 0.0   # K — minimum temp for it to proceed
    rate: float = 1.0          # recipe-multiples per second at full availability

    def __post_init__(self):
        in_mass = sum(self.inputs.values())
        out_mass = sum(self.outputs.values())
        if not math.isclose(in_mass, out_mass, rel_tol=1e-9, abs_tol=1e-9):
            raise ValueError(
                f"Transformation '{self.name}' violates conservation of mass: "
                f"{in_mass:.6g} kg in, {out_mass:.6g} kg out")

    @property
    def energy_released_per_multiple(self):
        """Exothermic positive (J). chemical energy lost by the system -> heat."""
        in_chem = sum(m.chemical_energy * kg for m, kg in self.inputs.items())
        out_chem = sum(m.chemical_energy * kg for m, kg in self.outputs.items())
        return in_chem - out_chem


# --------------------------------------------------------------------------- #
#  Cell — a well-mixed finite volume holding parcels                           #
# --------------------------------------------------------------------------- #

@dataclass
class Cell:
    id: int
    parcels: list = field(default_factory=list)

    # --- aggregate thermal state (well-mixed assumption) -------------------
    @property
    def capacity(self):
        return sum(p.heat_capacity_rate() for p in self.parcels)

    @property
    def temperature(self):
        cap = self.capacity
        if cap <= 0:
            return 0.0
        return sum(p.temperature * p.heat_capacity_rate() for p in self.parcels) / cap

    @property
    def max_temperature(self):
        return max((p.temperature for p in self.parcels), default=0.0)

    # --- matter bookkeeping ------------------------------------------------
    def mass_of(self, material):
        return sum(p.mass for p in self.parcels if p.material is material)

    def add_parcel(self, parcel):
        """Merge into an existing same-material parcel if present (mass and
        energy both add — exact), else append. Keeps parcel count bounded."""
        for p in self.parcels:
            if p.material is parcel.material:
                p.mass += parcel.mass
                p.thermal_energy += parcel.thermal_energy
                return
        self.parcels.append(parcel)

    def consume(self, material, kg):
        """Remove `kg` of `material`, returning the thermal energy carried away
        with it (so the caller can conserve it). Drops emptied parcels."""
        removed_energy = 0.0
        remaining = kg
        for p in list(self.parcels):
            if p.material is not material or remaining <= 0:
                continue
            take = min(p.mass, remaining)
            frac = take / p.mass if p.mass > 0 else 0.0
            e = p.thermal_energy * frac
            p.mass -= take
            p.thermal_energy -= e
            removed_energy += e
            remaining -= take
            if p.mass <= 1e-12:
                self.parcels.remove(p)
        return removed_energy

    def add_heat(self, joules):
        """Distribute a heat injection across parcels by heat-capacity weight."""
        cap = self.capacity
        if cap <= 0:
            return
        for p in self.parcels:
            p.add_heat(joules * p.heat_capacity_rate() / cap)


# --------------------------------------------------------------------------- #
#  Systems — conduction & reactions (all strictly conservative)                #
# --------------------------------------------------------------------------- #

def _conduct(t_a, t_b, cap_a, cap_b, g, dt, apply_a, apply_b):
    """Move heat from the hotter to the colder side, clamped so it never
    overshoots equilibrium (prevents oscillation). Energy leaving one side
    exactly equals energy entering the other — conservation by construction."""
    if t_a == t_b or g <= 0 or cap_a <= 0 or cap_b <= 0:
        return 0.0
    t_eq = (cap_a * t_a + cap_b * t_b) / (cap_a + cap_b)
    q_req = g * (t_a - t_b) * dt                 # signed: + means a -> b
    if t_a > t_b:
        q = max(0.0, min(q_req, cap_a * (t_a - t_eq)))
    else:
        q = min(0.0, max(q_req, -cap_b * (t_b - t_eq)))
    apply_a(-q)
    apply_b(+q)
    return q


def conduct_parcels(a: Parcel, b: Parcel, g, dt):
    return _conduct(a.temperature, b.temperature,
                    a.heat_capacity_rate(), b.heat_capacity_rate(),
                    g, dt, a.add_heat, b.add_heat)


def conduct_cells(ca: Cell, cb: Cell, g, dt):
    return _conduct(ca.temperature, cb.temperature, ca.capacity, cb.capacity,
                    g, dt, ca.add_heat, cb.add_heat)


def react(cell: Cell, tr: Transformation, dt, events=None, now=0.0):
    """Run a reaction in a cell for one step. Consumes inputs, produces outputs,
    and converts the freed chemical energy (plus the inputs' own thermal energy)
    into the outputs' thermal energy. Mass and total energy both conserved."""
    if cell.max_temperature < tr.activation_temperature:
        return 0.0                                   # not hot enough — no spark

    # extent limited by the scarcest input and by the reaction rate
    avail = math.inf
    for mat, kg in tr.inputs.items():
        avail = min(avail, cell.mass_of(mat) / kg)
    extent = min(tr.rate * dt, avail)
    if extent <= 1e-12:
        return 0.0

    # consume inputs, capturing their thermal energy
    u_consumed = 0.0
    for mat, kg in tr.inputs.items():
        u_consumed += cell.consume(mat, kg * extent)

    # the chemical energy freed by this much reaction
    u_released = tr.energy_released_per_multiple * extent
    u_out = u_consumed + u_released              # all of it becomes thermal

    # create outputs, splitting the thermal energy by heat-capacity weight so
    # they start near a common temperature (any split that sums to u_out would
    # conserve energy; this one just gives sensible temperatures)
    weights = {m: m.c_solid * (kg * extent) for m, kg in tr.outputs.items()}
    total_w = sum(weights.values())
    for mat, kg in tr.outputs.items():
        m = kg * extent
        u = u_out * (weights[mat] / total_w) if total_w > 0 else 0.0
        cell.add_parcel(Parcel(mat, m, u))

    if events is not None:
        events.append({"t": now, "type": "reaction", "cell": cell.id,
                       "name": tr.name, "extent": round(extent, 6),
                       "heat_released_J": round(u_released, 1)})
    return extent


# --------------------------------------------------------------------------- #
#  World — owns cells, links, transformations, the event log, and the tick     #
# --------------------------------------------------------------------------- #

@dataclass
class World:
    cells: list = field(default_factory=list)
    cell_links: list = field(default_factory=list)   # (i, j, conductance W/K)
    transformations: list = field(default_factory=list)
    intra_cell_conductance: float = 5000.0           # well-mixed: fast internal
    time: float = 0.0
    events: list = field(default_factory=list)       # << stage-2 memory feed

    def tick(self, dt):
        """Deterministic system order. Same seed + same inputs => same result.
        (No RNG here yet; when you add it, thread one seeded generator and keep
        this fixed ordering — it is what keeps lockstep multiplayer in sync.)"""
        # 1. reactions
        for cell in self.cells:
            for tr in self.transformations:
                react(cell, tr, dt, self.events, self.time)
        # 2. intra-cell mixing (links rebuilt each tick -> no stale references)
        g_in = self.intra_cell_conductance
        for cell in self.cells:
            ps = cell.parcels
            for i in range(len(ps)):
                for j in range(i + 1, len(ps)):
                    conduct_parcels(ps[i], ps[j], g_in, dt)
        # 3. inter-cell conduction (Fourier, by cell index)
        for i, j, g in self.cell_links:
            conduct_cells(self.cells[i], self.cells[j], g, dt)
        self.time += dt

    # --- the conservation auditor: your debugging & trust backbone ---------
    def totals(self):
        m = e = 0.0
        for cell in self.cells:
            for p in cell.parcels:
                m += p.mass
                e += p.total_energy          # thermal + chemical
        return m, e


# --------------------------------------------------------------------------- #
#  A small material library for the demos                                      #
# --------------------------------------------------------------------------- #

MATERIALS = {
    "water": Material("water", density=1000, c_solid=2090, c_liquid=4186,
                      c_gas=2010, melting_point=273.15, boiling_point=373.15,
                      latent_heat_fusion=334_000, latent_heat_vaporization=2_256_000),
    "stone": Material("stone", density=2500, c_solid=800, melting_point=1500,
                      latent_heat_fusion=200_000, hardness=6.0),
    "wood": Material("wood", density=600, c_solid=1700, chemical_energy=16_000_000,
                     hardness=2.0),                       # ~16 MJ/kg heating value
    "oxygen": Material("oxygen", density=1.4, c_solid=918, default_phase=Phase.GAS),
    "carbon_dioxide": Material("carbon_dioxide", density=1.8, c_solid=849,
                               default_phase=Phase.GAS),
    "ash": Material("ash", density=700, c_solid=840, hardness=1.0),
}

COMBUSTION = Transformation(
    name="wood_combustion",
    inputs={MATERIALS["wood"]: 1.0, MATERIALS["oxygen"]: 1.2},
    outputs={MATERIALS["carbon_dioxide"]: 1.5,
             MATERIALS["water"]: 0.5,
             MATERIALS["ash"]: 0.2},
    activation_temperature=573.0,    # ~300 C ignition
    rate=0.05,                       # burns 0.05 kg wood/s at full availability
)


# --------------------------------------------------------------------------- #
#  Demos                                                                        #
# --------------------------------------------------------------------------- #

def to_c(k):
    return k - 273.15


def demo_phase_change():
    print("=" * 70)
    print("DEMO 1 — phase transitions emerge from the energy model")
    print("Heating 1 kg of ice in fixed 200 kJ steps. Watch the temperature")
    print("PLATEAUS at 0 C (melting) and 100 C (boiling): added energy goes")
    print("into latent heat, not temperature. Nobody coded a plateau.")
    print("=" * 70)
    water = MATERIALS["water"]
    p = Parcel.at_temperature(water, 1.0, 260.0)      # ice at -13 C
    step = 200_000                                    # J per step
    print(f"{'energy(MJ)':>11} {'temp(C)':>9} {'phase':>8}")
    for i in range(26):
        print(f"{p.thermal_energy/1e6:>11.2f} {to_c(p.temperature):>9.1f} "
              f"{p.phase.value:>8}")
        p.add_heat(step)
    print()


def demo_combustion_and_conduction():
    print("=" * 70)
    print("DEMO 2 — combustion + heat conduction in a closed box")
    print("Cell 0 is a fire pit: 100 kg stone + 2 kg wood + 3 kg O2, lit at")
    print("700 K. Wood burns (chemical->thermal), heat conducts down a rod of")
    print("stone cells. The auditor confirms TOTAL MASS and TOTAL ENERGY never")
    print("move — fire creates nothing, it only converts.")
    print("=" * 70)

    # cell 0: the fire pit (ignited at 700 K)
    pit = Cell(0, [
        Parcel.at_temperature(MATERIALS["stone"], 100.0, 700.0),
        Parcel.at_temperature(MATERIALS["wood"], 2.0, 700.0),
        Parcel.at_temperature(MATERIALS["oxygen"], 3.0, 700.0),
    ])
    # cells 1..4: a cold stone rod
    rod = [Cell(i, [Parcel.at_temperature(MATERIALS["stone"], 50.0, 290.0)])
           for i in range(1, 5)]
    cells = [pit] + rod

    links = [(i, i + 1, 2.0) for i in range(len(cells) - 1)]   # 2 W/K per joint
    world = World(cells=cells, cell_links=links, transformations=[COMBUSTION])

    m0, e0 = world.totals()
    header = (f"{'t(s)':>5} | " +
              " ".join(f"cell{c.id}(C)" for c in cells) +
              f" | {'mass(kg)':>9} {'energy(MJ)':>11} {'wood(kg)':>8}")
    print(header)
    print("-" * len(header))

    dt = 1.0
    for t in range(0, 401):
        if t % 40 == 0:
            temps = " ".join(f"{to_c(c.temperature):>8.0f}" for c in cells)
            m, e = world.totals()
            print(f"{t:>5} | {temps} | {m:>9.4f} {e/1e6:>11.4f} "
                  f"{pit.mass_of(MATERIALS['wood']):>8.3f}")
        world.tick(dt)

    m1, e1 = world.totals()
    print("-" * len(header))
    print(f"mass drift   : {abs(m1 - m0):.3e} kg   (expect ~0)")
    print(f"energy drift : {abs(e1 - e0):.3e} J    (expect ~0, float noise only)")
    print(f"reactions logged for the cognition layer: {len(world.events)} events")
    if world.events:
        ev = world.events[0]
        print(f"  e.g. t={ev['t']}s  {ev['name']} in cell {ev['cell']}, "
              f"released {ev['heat_released_J']:.0f} J")
    print()

    # conservation assertions (this is what you'd run in CI)
    assert math.isclose(m0, m1, rel_tol=1e-9, abs_tol=1e-6), "MASS NOT CONSERVED"
    assert math.isclose(e0, e1, rel_tol=1e-7, abs_tol=1e-3), "ENERGY NOT CONSERVED"
    print("CONSERVATION HOLDS ✓  (mass exact, energy within float epsilon)")


if __name__ == "__main__":
    demo_phase_change()
    demo_combustion_and_conduction()
