"""soma.py — layer-0 STATE and FLUXES (standard DEB, DEB-IBM compound form).

Representation (WO §14/§15, option A): we INTEGRATE the DEB-IBM state variables verbatim —
U_E (scaled reserve), U_H (scaled maturity), U_R (scaled repro buffer), L (volumetric
structural length) — because the canon (Martin 2013) is a REDUCED/compound set (it gives only
[E_G]/[E_m]=kap*g, never the two apart), so the fully-dimensionless form is unreachable without
undoing §14. The §3.1 dimensionless state (e, l, e_H, e_R) is a DERIVED VIEW (below) — what the
trace and cross-config comparison read (the GOAL of §3.1: corn and monkey in one numeric range).

Flux equations are transcribed from Martin et al. (2013) DEB-IBM ODD §7 (Submodels); line refs
below point into that document. Units: ANIMAL length mm (v, U_H, U_Hp, J_XAm); MEDIUM cm^3
(K, X) — the two-length trap (config.py). Vitok 1: single organism, constant/stepped f, T=T_ref.

HONEST SCOPE (WO review):
  * The smoke identity L_inf = f*L_M (and r_B = k_M g/(3(f+g))) is the FIXED POINT of the growth
    ODE — algebra of a correctly-transcribed dL/dt, not a signature of correct DEB. So MS-vb,
    MS-f, HS1 are three NAMES for one transcription check. The real tests are MS-daphnia,
    MS-step-conv, MS-reserve-lag, the infrastructure gates, and HS2.
  * A len-2 reserve vector here is element-wise g*e/(g+e) — TWO independent DEBs, NOT the
    synthesizing-unit co-limitation an autotroph needs (SU is vitok 2). So MS-vector is a SHAPE
    test only ("does not crash on len 2"); autotroph physics is NOT validated until SU.

STARVATION = Martin submodel #1 (structure-burning), an ACCOUNTING RULE (burn exactly enough
structure to cover the somatic-maintenance deficit), death stochastic at `starv_mortality` once
WEIGHT falls below `V_crit` of the max ever reached. Two things are OUR decisions, not canon:
  * SHRINK RATE: we let the growth ODE go negative — it turns negative exactly at the deficit
    (v S_C/(g L^2) < k_M L), the lossless (yield=1) reading. A species-specific equation, if it
    exists, is in the 2013 paper's Appendix A (online enhancement), NOT the generic DEB-IBM ODD
    (companion to Martin 2012) these line refs cite. A yield != 1 would need [E_G] alone, which the
    compound set cannot give (same wall as option B). This affects ONLY HS2 (the low-f sweep) — see
    the arithmetic in the journal: MS-daphnia's four food levels never enter the starvation branch.
  * V_crit uses WEIGHT; we test V/V_max = a ratio of structural VOLUMES. They diverge by the reserve
    contribution, and in starvation reserve is depleted, so V/V_max > weight-ratio and our death
    fires LATER than correct. V/V_max is a TEMPORARY PROXY tied to the same mass PENDING (§11.2).

NOT here: reproduction EVENT (bisection egg cost, ODD 525-557) — stub for MS-daphnia. Mass
reconstruction — PENDING (absent from the ODD; HS3 and the V_crit weight test need it, §11.2).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from random import Random

import numpy as np

from soma.config import RuntimeParams


class Trait(Enum):
    """Evolutionary layers are predicates on `traits`, not subclasses. Vitok 1 ships only layer 0."""

    SOMA = "soma"


@dataclass(slots=True)
class Soma:
    """Integrated DEB-IBM state. U_E, L are VECTORS (WO §3.1 — arrays from day one; len 1 for the
    Daphnia heterotroph, len 2 for the C/N autotroph). U_H, U_R, q, h scalars. e/l/e_H/e_R are
    DERIVED (functions below), not stored."""

    U_E: np.ndarray   # scaled reserve            [d·mm^2]
    L: np.ndarray     # volumetric struct length  [mm]
    U_H: float        # scaled maturity           [d·mm^2]
    U_R: float        # scaled reproduction buffer[d·mm^2]
    q: float          # scaled ageing acceleration (q̈)  [1/d^2]
    h: float          # ageing hazard rate (ḣ)          [1/d]
    age: float        # time alive                [d]


@dataclass(slots=True)
class Organism:
    """Composition, not inheritance. Corn and monkey are one structure, different traits/params."""

    soma: Soma
    params: RuntimeParams
    traits: frozenset = field(default_factory=lambda: frozenset({Trait.SOMA}))
    rng: Random = field(default_factory=Random)
    V_max: float = 0.0            # max structural volume ever reached (for Martin V_crit death)
    maturity_leak: float = 0.0    # cumulative maturity-maintenance dropped by the dU_H>=0 clamp;
                                  # MS-cons must balance WITH this, and it must be 0 when the clamp
                                  # never fires. Makes the clamp's energy hole a number, not a comment.
    cum_eggs: int = 0
    alive: bool = True
    cause: str = ""


@dataclass(slots=True)
class TickContext:
    """Carries per-tick control state through the cognitive phases. Vitok 1 only sets `f`; vitok 2
    lets `regulate` write `kappa` (a controller output). Hooks take and return THIS, not a bare f,
    so their signatures survive vitok 2 (WO review)."""

    f: float
    kappa: float | None = None    # None => use params.kap (vitok 1: kappa fixed)


# --------------------------------------------------------------------------------------------
# Derived views — the §3.1 dimensionless state. Read-only functions of (Soma, RuntimeParams).
# --------------------------------------------------------------------------------------------

def scaled_reserve_density(s: Soma, p: RuntimeParams) -> np.ndarray:
    """e = v̇·U_E / L^3   (ODD 337)."""
    return p.v * s.U_E / s.L ** 3


def scaled_length(s: Soma, p: RuntimeParams) -> np.ndarray:
    """l = L / L_M   (ODD 456)."""
    return s.L / p.L_M


def scaled_maturity(s: Soma, p: RuntimeParams) -> float:
    """e_H = U_H / U_Hp — a 0->1 developmental fraction, comparable across species."""
    return s.U_H / p.U_Hp


def scaled_repro(s: Soma, p: RuntimeParams) -> float:
    return s.U_R / p.U_Hp


def mass(s: Soma, p: RuntimeParams):
    """PENDING: structure L^3 + reserve contribution. The reserve-to-mass term is NOT in the ODD
    (needs [E_m], w_E, d_V — not in the compound set); source = User Manual / Kooijman. HS3 needs
    it pinned (subtrahend (ii), WO §11.2). Do NOT invent (§7а)."""
    raise NotImplementedError("mass reconstruction PENDING — pin the reserve contribution before HS3")


# --------------------------------------------------------------------------------------------
# Cognitive / transport hooks — no-op in vitok 1; order frozen (WO §3.3). Take/return TickContext.
# --------------------------------------------------------------------------------------------
def perceive(org, ctx):  return ctx
def modulate(org, ctx):  return ctx
def regulate(org, ctx):  return ctx     # vitok 2: sets ctx.kappa from a controller
def arbitrate(org, ctx): return ctx
def execute(org, ctx):   return ctx
def transport(org, ctx): return ctx     # vitok 2 (Thornley)


def _fluxes(s: Soma, p: RuntimeParams, f: float, kap: float):
    """(dU_E, dU_H, dU_R, dL, starving) per DEB-IBM §7. dL uses the growth ODE ALWAYS — under
    starvation it is negative (structure burning, Martin #1). Maturity is clamped non-decreasing."""
    e = scaled_reserve_density(s, p)                        # ODD 337
    l = scaled_length(s, p)                                 # ODD 456
    g = p.g

    S_A = (f if s.U_H > p.U_Hb else 0.0) * s.L ** 2         # assimilation; 0 before birth (ODD 319/355)
    S_C = s.L ** 2 * (g * e / (g + e)) * (1.0 + s.L * p.k_M / p.v)   # mobilization (ODD 332)

    dU_E = S_A - S_C                                        # ODD 314
    # growth ODE (ODD 446); negative when v S_C/(g L^2) < k_M L => structure shrinks (Martin #1).
    dL = (1.0 / 3.0) * (p.v * S_C / (g * s.L ** 2) - p.k_M * s.L)
    starving = bool(np.any(e < l))                         # e < l = L/L_M (ODD 455)

    sumSC = float(np.sum(S_C))
    leak_rate = 0.0
    if s.U_H < p.U_Hp:                                      # juvenile: (1-kap) mobilised -> maturity
        raw = (1.0 - kap) * sumSC - p.k_J * s.U_H           # ODD 382
        dU_H = max(raw, 0.0)    # maturity is non-decreasing in standard DEB; the bare ODD eq can go
                                # negative at low food (maturity-maint shortfall). We clamp (plateau,
                                # never reverse). DEVIATION, made MEASURABLE via the leak below.
        leak_rate = -min(raw, 0.0)   # = max(0, k_J U_H - (1-kap)S_C): the dropped maturity-maint
        dU_R = 0.0
    else:                                                  # adult: -> reproduction buffer (ODD 418)
        dU_H = 0.0
        dU_R = (1.0 - kap) * sumSC - p.k_J * p.U_Hp
    return dU_E, dU_H, dU_R, dL, starving, leak_rate


def _ageing(s: Soma, p: RuntimeParams, dL: np.ndarray):
    """Ageing ODEs (ODD 597-600). NB `np.mean(L)` is the organism length only for a single
    structural compartment (Daphnia, len 1) — a placeholder for multi-compartment (root/shoot),
    where organism length is not the mean of compartment lengths. Exact for vitok-1 Daphnia."""
    e = float(np.mean(scaled_reserve_density(s, p)))
    L = float(np.mean(s.L))
    r = (3.0 / L) * float(np.mean(dL))                     # specific growth rate ṙ
    dq = ((s.q * L ** 3 / p.L_M ** 3) * p.s_G + p.h_a) * e * (p.v / L - r) - r * s.q
    dh = s.q - r * s.h
    return dq, dh


def step(org: Organism, f: float, dt: float) -> Organism:
    """One tick: frozen phase order (WO §3.3), Euler. Vitok-1 active phases only; the rest no-op.
    Death: Martin starvation (mass < V_crit·V_max) and ageing hazard, both via 1-exp(-rate·dt) so
    the death probability is EXACT at any step (no dt-dependence to confound MS-step-conv)."""
    if not org.alive:
        return org
    s, p = org.soma, org.params

    ctx = TickContext(f=f)
    for hook in (perceive, modulate, regulate, arbitrate, execute, transport):
        ctx = hook(org, ctx)
    kap = p.kap if ctx.kappa is None else ctx.kappa        # vitok 1: kappa fixed = params

    dU_E, dU_H, dU_R, dL, starving, leak_rate = _fluxes(s, p, ctx.f, kap)
    dq, dh = _ageing(s, p, dL)

    # resolve — Euler
    s.U_E = s.U_E + dt * dU_E
    s.L = s.L + dt * dL
    s.U_H = s.U_H + dt * dU_H
    s.U_R = s.U_R + dt * dU_R
    s.q = s.q + dt * dq
    s.h = s.h + dt * dh
    s.age += dt
    org.maturity_leak += dt * leak_rate                    # measurable clamp hole (MS-cons checks it)

    V = float(np.sum(s.L ** 3))                             # structural volume (sum over compartments)
    org.V_max = max(org.V_max, V)

    # death — exact-per-step probabilities (1 - exp(-rate·dt))
    if V < p.V_crit * org.V_max:                            # Martin #1: below V_crit of max mass
        if org.rng.random() < 1.0 - math.exp(-p.starv_mortality * dt):
            org.alive, org.cause = False, "starvation"
            return org
    if org.rng.random() < 1.0 - math.exp(-s.h * dt):        # ageing hazard
        org.alive, org.cause = False, "ageing"
    # reproduction EVENT (bisection egg cost, ODD 525-557) — STUB for the MS-daphnia stage.
    return org


def birth_state(p: RuntimeParams, f: float, L0: float, U_H0: float | None = None) -> Soma:
    """A physically-consistent post-birth state ON the reserve manifold e = f (so U_E = f·L^3/v̇),
    no bisection, no warm-up (WO answer). U_H0 defaults just past birth (feeding juvenile). Caller
    should assert the maturity flux is non-negative at t=0 (the bug we caught, turned into a guard)."""
    L = np.atleast_1d(np.asarray(L0, dtype=float))
    U_E = f * L ** 3 / p.v                                  # e = v̇·U_E/L^3 = f, exactly on manifold
    U_H = p.U_Hb * 1.05 if U_H0 is None else U_H0           # just past the embryo boundary
    return Soma(U_E=U_E, L=L, U_H=U_H, U_R=0.0, q=0.0, h=0.0, age=0.0)
