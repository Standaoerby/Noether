"""config.py — the canon parameter table. THE single home of numbers (gate MS-lit).

CANON = Martin, Jager, Nisbet, Preuss & Grimm (2013), Am. Nat. 181(4):506-519, Table 1
(Daphnia magna). WO §10.3 was INVERTED: canon is the PRINTED source, not the AmP entry —
a printed table never moves between versions; the AmP full set + version proved not cleanly
retrievable; and AmP lacks Martin's starvation submodel + molt, so an "AmP canon" would be an
unrun AmP-core + Martin-submodel HYBRID. AmP is DIAGNOSTIC only (run it, print R^2 beside
ours, never gate). NB: Martin's v̇ (18.1 mm/d) is ~10x AmP's (0.1858 cm/d) — the two
parameterisations are NOT interchangeable, which is exactly why canon is pinned to one.

!! THE TWO-LENGTH TRAP (Table 1 legend). There are TWO different lengths and confusing them is
   a 1000x error in volume. Keep them as SEPARATE types, never one "length":
     * ANIMAL length  L : millimetres (mm)  -> v̇, U_H^b, U_H^p, {J̇_XAm} live in mm
     * MEDIUM  length  l : centimetres (cm)  -> K and food density X live in cm^3
   The only bridge is the DIMENSIONLESS f = X/(X+K), with X and K both in cells·cm^-3.
   {J̇_XAm} (per mm^2 of animal surface) must NEVER be combined with a cm-volume, and the
   arena/medium volume must NEVER be derived from the animal length. Contract for soma.py:
   the two lengths stay distinct; a future MS-units gate can assert it.

NOTATION: DEB-IBM SCALED convention as printed (U_H = scaled maturity, {J̇_XAm}, g). The §3.1
state is dimensionless-unscaled (e_H); the U_H -> e_H conversion is ONE explicit function in
the loader (deferred) — config holds the source values VERBATIM. Silent conversion at source
would be §7а through the back door. Field names are Martin's verbatim symbols (U_Hb, not E_Hb).

SOURCE: full Table 1 (values, 95% CI, dimensions) read from the PDF by Stan. FROZEN except two
non-blocking PENDINGs: T_A (absent — single-T study) and the Euler step (in ODD Appendix A,
not the main text). Neither blocks vitok-1 f-work.

MS-daphnia on these params is a RE-IMPLEMENTATION test (WO §13): same params -> any deviation
is unambiguously OURS. It licenses NOTHING about DEB being right, reserve working, or
validation against reality.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# Explicit sentinel: a value that must come from a named source. Never a silent default.
PENDING = None


@dataclass(frozen=True, slots=True)
class DebParams:
    """One DEB parameter set in Martin 2013 / DEB-IBM SCALED notation. Units are EXACT per
    Table 1; the two lengths (animal mm, medium cm) are called out per field."""

    # --- core std-DEB primaries (Martin 2013 Table 1); animal length is mm ---
    kap: float        # κ      [-]                 0.678     CI 0.657-0.700
    kap_R: float      # κ_R    [-]  (fixed)        0.95
    k_M: float        # k̇_M    [1/d]               0.3314    CI 0.327-0.336
    k_J: float        # k̇_J    [1/d]               0.1921    CI 0.150-0.236
    U_Hb: float       # U_H^b  [d·mm^2]            0.1108    CI 0.0989-0.123
    U_Hp: float       # U_H^p  [d·mm^2]            2.555     CI 2.36-2.844
    v: float          # v̇      [mm/d]  (ANIMAL mm) 18.1      CI 17.89-18.3
    g: float          # g      [-]  (fixed)        10
    h_a: float        # ḧ_a    [1/d^2]             3.04e-6   CI 1.70e-6-4.60e-6
    s_G: float        # s_G    [-]                 0.019     CI 0.00911-0.0273
    J_XAm: float      # {J̇_XAm}[cells·mm^-2·d^-1]  3.80e-5   CI 3.7e-5-4.0e-5   (ANIMAL mm^2)
    K: float          # K      [cells·cm^-3]       1585      CI 1571-1600       (MEDIUM cm^3)

    # --- Daphnia-specific + STARVATION SUBMODEL #1 only (Martin 2013; WO §12.2) ---
    # Submodel #1 (structure-burning, V_crit, this mortality) produced the individual-level
    # R^2 0.986/0.967. Submodel #2 M(1-e) is POPULATION-level ("M Varied") and is NOT vitok 1.
    molt: float             # molt interval        [d]        2.8
    V_crit: float           # struct-burn threshold[fraction] 0.4
    starv_mortality: float  # starvation mortality [1/d]      0.35   (submodel #1)

    # --- required downstream, still PENDING (non-blocking for vitok-1 f-work) ---
    T_A: float | None    # Arrhenius temp. ABSENT from Table 1 (single-T 20°C study). Inert at
                         #   fixed T=20°C (factor 1). Blocks the T-AXIS of HS2's sweep; the
                         #   f-axis runs without it. Pin from a named source before the T-sweep.
    T_ref: float         # reference temperature [K]  (20°C = 293.15; a convention)


# Canon entry — Daphnia magna. Heterotroph => 1 reserve compartment (WO §3.1). The 2-reserve
# autotroph config for MS-vector is a SEPARATE entry, added when its source is pinned.
DAPHNIA_MAGNA = DebParams(
    kap=0.678,
    kap_R=0.95,
    k_M=0.3314,
    k_J=0.1921,
    U_Hb=0.1108,
    U_Hp=2.555,
    v=18.1,
    g=10.0,
    h_a=3.04e-6,
    s_G=0.019,
    J_XAm=3.80e-5,
    K=1585.0,
    molt=2.8,
    V_crit=0.4,
    starv_mortality=0.35,
    T_A=PENDING,      # !! pin from a named source before the HS2 T-sweep
    T_ref=293.15,
)

DAPHNIA_COMPARTMENTS = 1  # reserves; the autotroph config carries 2 (C, N)


# --------------------------------------------------------------------------------------------
# Run-mode switches (vitok 1) — explicit, because each silences a "green with broken mechanism".
# --------------------------------------------------------------------------------------------

# Inter-individual scatter: Martin's individuals carry a lognormal multiplier on
# {U_Hb, U_Hp, J_XAm, K, g} for POPULATION runs. Vitok 1 is a single organism under MS-replay
# (byte-for-byte), so it is OFF, explicitly — a multiplier would break bit-identical replay.
SCATTER = "off"

# Integrator: the reference is discretised with EULER. A different integrator gives a different
# R^2 even with correct code, so vitok 1 MUST use Euler (not RK), and the MS-daphnia tolerance
# is declared WITH the caveat "step not matched" until the step is pinned.
INTEGRATOR = "euler"
EULER_STEP = PENDING   # !! in Martin 2013 ODD Appendix A, not the main text — pin before
                       #    claiming an exact MS-daphnia tolerance.


# --------------------------------------------------------------------------------------------
# Gate targets (numbers live here, not in gate code — MS-lit).
# --------------------------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class MSDaphniaTarget:
    """MS-daphnia acceptance. INDIVIDUAL level, Martin 2013 Fig. 2 (four food levels
    100000/25000/5000/1000 cells·mL^-1). NOT the Table 2 population R^2 (0.878/0.2013/0.318),
    which has nothing to do with vitok 1. Tolerance carries a 'Euler step not matched' caveat
    until EULER_STEP is pinned."""

    r2_growth: float       # >= this
    r2_reproduction: float # >= this
    level: str
    step_caveat: bool      # True while EULER_STEP is PENDING


MS_DAPHNIA_TARGET = MSDaphniaTarget(
    r2_growth=0.986,
    r2_reproduction=0.967,
    level="individual (Fig. 2)",
    step_caveat=True,      # flip to False once EULER_STEP is pinned and matched
)


# --------------------------------------------------------------------------------------------
# Loader — the printed canon (DebParams) -> runtime params. THE one place scaled-U meets a run.
# --------------------------------------------------------------------------------------------
# Martin's set is REDUCED (compound): it gives only [E_G]/[E_m] = kap*g = 6.78, never [E_G] and
# [E_m] apart. That is why fully-dimensionless integration is unreachable from THIS canon — it
# would mean undoing §14 (taking [E_G]/[E_m] separately => AmP => reversing the canon choice).
# The cost §14 did not name: choosing Martin for completeness+availability locks us into the
# compound form. Consequence we carry forward: g is NOT independent — g = ([E_G]/[E_m]) / kap.
# We store the INVARIANT and DERIVE g from kap, so that in vitok 2, when kap becomes a controller
# output, g (and hence L_M) follow it physically, with NO two-number retrofit.


@dataclass(frozen=True, slots=True)
class RuntimeParams:
    """Runtime view of a DebParams. `g` and `L_M` are DERIVED from kappa via the [E_G]/[E_m]
    invariant — never stored independently. Vitok 1 keeps kappa fixed (= config) so g == config.g
    exactly; the derivation only starts to matter in vitok 2 (kappa as controller output)."""

    kap: float
    k_M: float
    k_J: float
    v: float
    U_Hb: float
    U_Hp: float
    J_XAm: float
    K: float
    h_a: float
    s_G: float
    V_crit: float
    starv_mortality: float
    E_G_over_E_m: float   # INVARIANT (= kap*g); the ONLY separable combo Martin's set gives
    T_A: float | None
    T_ref: float

    @property
    def g(self) -> float:
        return self.E_G_over_E_m / self.kap            # derived from kappa, not stored

    @property
    def L_M(self) -> float:
        return self.v / (self.k_M * self.g)            # max structural length [mm] (ODD: L_M=v/(k_M g))

    def arrhenius(self, T_K: float) -> float:
        """Vitok 1 runs at T_ref (T_A PENDING). At T_ref the factor is exactly 1. Variable T is
        blocked until T_A is pinned (the T-axis of HS2)."""
        if self.T_A is None:
            if T_K != self.T_ref:
                raise ValueError("T_A is PENDING — variable-T is blocked (HS2 T-axis); vitok-1 is f-work only.")
            return 1.0
        return math.exp(self.T_A / self.T_ref - self.T_A / T_K)


def load(entry: DebParams) -> RuntimeParams:
    """The loader. Computes [E_G]/[E_m] from the printed (kap, g) so kappa is free and g follows.
    Reference for the flux equations these params feed: Martin et al. (2013) DEB-IBM ODD model
    description, §7 (Submodels) — assimilation/mobilization/maturity/repro/growth/starvation/ageing."""
    return RuntimeParams(
        kap=entry.kap, k_M=entry.k_M, k_J=entry.k_J, v=entry.v,
        U_Hb=entry.U_Hb, U_Hp=entry.U_Hp, J_XAm=entry.J_XAm, K=entry.K,
        h_a=entry.h_a, s_G=entry.s_G, V_crit=entry.V_crit,
        starv_mortality=entry.starv_mortality,
        E_G_over_E_m=entry.kap * entry.g,              # 6.78 — the invariant
        T_A=entry.T_A, T_ref=entry.T_ref,
    )
