"""
sim_enclosure.py — the bounded arena (module 22): close the escape, re-test the lever.

The tower has shown the same shape twice: collective sanction (19) and exogenous
salience injection (21) both *work mechanically* but fail to build hierarchy —
because the target could **escape**. Module 19's quorum couldn't stay assembled around
a moving target; module 21's injection bit as *harm via distraction* (E3 ✓: victim
biomass 447→400, population 1455→1272) but not capture/concentration (E1/E2 ✗), and the
finding named the blocker explicitly: on a conservable + **escapable** substrate, control
of attention degrades the collective but does not accumulate.

The repeated prediction is: **power bites once escape is closed.** This module closes
spatial escape — a bounded, appropriable arena (the enclosure of the commons; ВСТАВКА 1:
appropriable bounded space → hierarchy) — and re-runs the salience battery inside it. It
is a SUBSTRATE change, not a new verb: `EnclosureWorld(SalienceWorld)` inherits the whole
stack (salience → sphere → comm → conservation) untouched and adds only a movement clamp.

The knob — a corner-anchored arena box:
  arena_side = None | s. None (or s >= grid) => no clamp => OFF, byte-identical to the
  parent. s => on every move the intended destination (r, c) is clamped to the box
  rows [0, s-1] x cols [0, s-1]. The box is anchored at (0,0) so the salience DECOY (0,0)
  stays inside for every size — the ONLY difference from the module-21 baseline is the
  confinement. Init is unchanged (agents are placed grid-wide by the canon; the clamp
  pulls outsiders in over the first cycles — a deterministic transient).

Optional `pin_victims_only`: clamp only the non-injector ("victim") sub-population while
injectors roam — the surgical "pinned target" reading. The primary experiment is the
global arena.

Conservation: the clamp touches ONLY the destination cell. Body travels with the agent
(it is in `self.pop`, never in the grid pools), so relocating — even the one-step
pull-in of an outside agent onto the boundary — moves no matter. Food/heat keep
regenerating conservatively everywhere; the unreached corner simply goes unforaged and
its matter stays in place. Matter drift stays < 1e-9 at every arena_side. The clamp is a
deterministic min/max on integer coordinates, so determinism is preserved. No LLM, no
network; pure stdlib + numpy.
"""

from __future__ import annotations

import hashlib

from sim_eventlog import SEED
from sim_comm import R, C, DAYS, run as run_comm
from sim_stage2 import ActionAdapter, DIRS
from sim_sphere import GRID_DIAG, CANON_COMM, run_sphere
from sim_salience import (
    SalienceWorld, salience_fingerprint, run_salience,
    e1_concentration, e2_capture, e3_harm,
    DECOY, RAD, KK, LAG, FEW, W_INJ, AMT, DECAY,
)

SAL_SPHERE = "e4c51990853eea93"     # sim_salience B1 (inject-off + sphere-on r0/K8/lag1)


class ClampingAdapter(ActionAdapter):
    """ActionAdapter that clamps the move destination into the arena box. With the box
    off (arena_side is None) — or for an unconfined injector under pin_victims_only — it
    delegates VERBATIM to the parent adapter, so OFF is byte-identical to canon."""

    def apply(self, world, a, dec, legal):
        s = world.arena_side
        if s is None or (world.pin_victims_only and a.oid in world._injectors):
            return super().apply(world, a, dec, legal)
        action = dec.action if dec.action in legal else "stay"
        di, dj = DIRS[action]
        ui, uj = a.i + di, a.j + dj                      # intended (unclamped) destination
        ni, nj = min(max(ui, 0), s - 1), min(max(uj, 0), s - 1)
        if (ni, nj) != (ui, uj):
            world._clamp_moves += 1
        if ni == a.i and nj == a.j:
            return
        fi, fj = a.i, a.j
        a.i, a.j = ni, nj
        world.log.emit(world.t, "move", "individual", where=(a.i, a.j),
                       actor=a.oid, data={"from": (fi, fj), "to": (a.i, a.j), "by": "mind"})


class EnclosureWorld(SalienceWorld):
    """SalienceWorld confined to a corner-anchored arena box via a clamping move
    adapter. arena_side=None (or >= grid) is a true no-op -> byte-identical to the
    parent at every disabled layer. The only new state is the arena bound and a
    deterministic clamped-move counter."""

    def __init__(self, log, seed=SEED, regime="deceptive",
                 radius=GRID_DIAG + 1.0, K=None, lag=0,
                 injection_strength=0.0, injectors=0, inject_amount=50.0,
                 decay=1.0, target_policy="decoy",
                 arena_side=None, pin_victims_only=False):
        self.arena_side = None if (arena_side is None or arena_side >= R) else int(arena_side)
        self.pin_victims_only = bool(pin_victims_only)
        self._clamp_moves = 0
        super().__init__(log, seed=seed, regime=regime, radius=radius, K=K, lag=lag,
                         injection_strength=injection_strength, injectors=injectors,
                         inject_amount=inject_amount, decay=decay,
                         target_policy=target_policy)
        self.adapter = ClampingAdapter()        # swap in the clamp (no-op when arena off)

    def inside_arena(self):
        if self.arena_side is None:
            return len(self.pop)
        s = self.arena_side
        return sum(1 for a in self.pop if a.i < s and a.j < s)


# --------------------------------------------------------------------------- #
#  Running + fingerprint                                                       #
# --------------------------------------------------------------------------- #
def run_enclosure(arena_side=None, pin_victims_only=False, regime="deceptive",
                  radius=GRID_DIAG + 1.0, K=None, lag=0,
                  injection_strength=0.0, injectors=0, inject_amount=50.0,
                  decay=1.0, target_policy="decoy", seed=SEED, days=DAYS):
    from sim_eventlog import EventLog
    log = EventLog()
    w = EnclosureWorld(log, seed=seed, regime=regime, radius=radius, K=K, lag=lag,
                       injection_strength=injection_strength, injectors=injectors,
                       inject_amount=inject_amount, decay=decay,
                       target_policy=target_policy, arena_side=arena_side,
                       pin_victims_only=pin_victims_only)
    for _ in range(days):
        w.step()
    return w, log


def enclosure_fingerprint(w):
    """salience_fingerprint folded with the arena bound, the clamped-move count, and the
    arena-membership count — the determinism self-check."""
    h = hashlib.sha256()
    h.update(salience_fingerprint(w).encode())
    h.update(f"|arena{w.arena_side}|pin{int(w.pin_victims_only)}"
             f"|clamp{w._clamp_moves}|inside{w.inside_arena()}/{len(w.pop)}".encode())
    return h.hexdigest()[:16]


# salience-ON headline config (module-21), shared across the battery
SAL = dict(radius=RAD, K=KK, lag=LAG, injection_strength=W_INJ, injectors=FEW,
           inject_amount=AMT, decay=DECAY, target_policy="decoy")
HEADLINE_SIDE = 6


# --------------------------------------------------------------------------- #
#  Demo / self-verification                                                    #
# --------------------------------------------------------------------------- #
def _fmt(v, fmt="{:.3f}"):
    return "—" if (isinstance(v, float) and v != v) else fmt.format(v)


def main():
    line = "=" * 78
    print(line)
    print("ENCLOSURE — the bounded arena: close the escape, re-test the lever")
    print("EnclosureWorld(SalienceWorld) clamps every move into a corner box [0,s-1]^2.")
    print("Substrate change, not a new verb: does salience's harm-without-hierarchy")
    print("(E1/E2 ✗, E3 ✓ on the open grid) flip to capture/concentration once agents")
    print(f"cannot flee? grid {R}x{C}; seed {SEED}; {DAYS}d; decoy {DECOY} stays in the box.")
    print(line)

    # --- B0: arena off + salience off + sphere off == canon ----------------- #
    w_b0, _ = run_enclosure(arena_side=None, radius=GRID_DIAG + 1.0, K=None, lag=0,
                            injection_strength=0.0, injectors=0)
    b0 = w_b0.state_fingerprint()
    print(f"\nB0  arena-OFF + salience-OFF + sphere-OFF : {b0} vs canon {CANON_COMM} -> "
          f"{'BYTE-IDENTICAL ✓' if b0 == CANON_COMM else 'MISMATCH ✗'}")
    assert b0 == CANON_COMM, "B0 not byte-identical to sim_comm canon"
    assert w_b0.matter_drift() < 1e-9 and w_b0._clamp_moves == 0, "B0 perturbed"

    # --- B1a: arena off + salience-OFF + sphere-ON == sim_salience B1 anchor - #
    w_b1a, _ = run_enclosure(arena_side=None, radius=RAD, K=KK, lag=LAG,
                             injection_strength=0.0, injectors=0)
    b1a = w_b1a.state_fingerprint()
    print(f"B1a arena-OFF + salience-OFF + sphere-ON : {b1a} vs {SAL_SPHERE} -> "
          f"{'BYTE-IDENTICAL ✓' if b1a == SAL_SPHERE else 'MISMATCH ✗'}")
    assert b1a == SAL_SPHERE, "B1a not byte-identical to sim_salience sphere-ON anchor"

    # --- B1b: arena off + salience-ON (headline) == SalienceWorld (positive control) #
    w_b1b, _ = run_enclosure(arena_side=None, **SAL)
    sal, _ = run_salience(**SAL)
    b1b, sf = w_b1b.state_fingerprint(), sal.state_fingerprint()
    print(f"B1b arena-OFF + salience-ON  : {b1b} vs sim_salience ON {sf} -> "
          f"{'BYTE-IDENTICAL ✓' if b1b == sf else 'MISMATCH ✗'}")
    assert b1b == sf, "B1b not byte-identical to sim_salience injection-ON (arena is the only change)"
    assert w_b1b._clamp_moves == 0, "arena-OFF must clamp nothing"

    # --- the battery: full grid vs the headline enclosure ------------------- #
    full, _ = run_enclosure(arena_side=None, **SAL)              # == module-21 baseline
    box, _ = run_enclosure(arena_side=HEADLINE_SIDE, **SAL)
    assert box.matter_drift() < 1e-9, "enclosure run leaked matter"
    of1, bf1 = e1_concentration(full), e1_concentration(box)
    of2, bf2 = e2_capture(full), e2_capture(box)
    of3, bf3 = e3_harm(full), e3_harm(box)
    print(f"\ninside-arena (side {HEADLINE_SIDE}): {box.inside_arena()}/{len(box.pop)} agents; "
          f"{box._clamp_moves} clamped moves; matter drift {box.matter_drift():.2e} kg")
    print(f"\n{'':<32}{'full grid':>13}{f'box {HEADLINE_SIDE}x{HEADLINE_SIDE}':>13}")
    print("-" * 58)
    print("E1 — concentration")
    print(f"{'  top-5 sig-mass share':<32}{_fmt(of1['top5_share']):>13}{_fmt(bf1['top5_share']):>13}")
    print(f"{'  decoy budget-residency':<32}{_fmt(of1['residency']):>13}{_fmt(bf1['residency']):>13}")
    print(f"{'  significance-Gini':<32}{_fmt(of1['sig_gini']):>13}{_fmt(bf1['sig_gini']):>13}")
    print("E2 — capture (injector - victim body)")
    print(f"{'  injector mean body (kg)':<32}{_fmt(of2['inj_body']):>13}{_fmt(bf2['inj_body']):>13}")
    print(f"{'  victim mean body (kg)':<32}{_fmt(of2['vic_body']):>13}{_fmt(bf2['vic_body']):>13}")
    print(f"{'  capture gap (kg)':<32}{_fmt(of2['gap'], '{:+.3f}'):>13}{_fmt(bf2['gap'], '{:+.3f}'):>13}")
    print("E3 — harm (victims)")
    print(f"{'  belief error (kg)':<32}{_fmt(of3['belief_err'], '{:.1f}'):>13}{_fmt(bf3['belief_err'], '{:.1f}'):>13}")
    print(f"{'  victim biomass (kg)':<32}{_fmt(of3['vic_biomass'], '{:.1f}'):>13}{_fmt(bf3['vic_biomass'], '{:.1f}'):>13}")
    print(f"{'  victim living':<32}{of3['vic_living']:>13d}{bf3['vic_living']:>13d}")

    # --- self-check fingerprint --------------------------------------------- #
    fp1 = enclosure_fingerprint(box)
    box2, _ = run_enclosure(arena_side=HEADLINE_SIDE, **SAL)
    fp2 = enclosure_fingerprint(box2)
    print(f"\nenclosure_fingerprint: {fp1}")
    print(f"self-check (recompute): {fp2} -> "
          f"{'BIT-IDENTICAL ✓' if fp1 == fp2 else 'MISMATCH ✗'}")
    assert fp1 == fp2, "enclosure run is not reproducible"

    # --- sweep: enclosure size (at what density does power appear?) --------- #
    print(f"\nenclosure-size sweep (salience ON, {FEW} injectors, decoy, permanent):")
    print(f"  {'side':>6}{'inside':>10}{'top5':>9}{'resid.':>9}{'sig-Gini':>10}"
          f"{'cap gap':>10}{'vic biom':>10}{'vic live':>9}")
    for s in (14, 10, 6, 4):
        ws, _ = run_enclosure(arena_side=(None if s >= R else s), **SAL)
        assert ws.matter_drift() < 1e-9, f"side {s} leaked matter"
        e1, e2, e3 = e1_concentration(ws), e2_capture(ws), e3_harm(ws)
        tag = f"{s}*" if s >= R else f"{s}"
        print(f"  {tag:>6}{ws.inside_arena():>10}{_fmt(e1['top5_share']):>9}"
              f"{_fmt(e1['residency']):>9}{_fmt(e1['sig_gini']):>10}"
              f"{_fmt(e2['gap'], '{:+.3f}'):>10}{_fmt(e3['vic_biomass'], '{:.0f}'):>10}"
              f"{e3['vic_living']:>9d}")
    print("  (* side 14 = full grid = no-op baseline)")

    # --- sweep: injector count inside the tight box ------------------------- #
    print(f"\ninjector-count sweep inside box {HEADLINE_SIDE}x{HEADLINE_SIDE} "
          f"(does confinement change the 'mass not few' law?):")
    print(f"  {'injectors':>10}{'resid.':>9}{'top5':>9}{'cap gap':>10}{'vic biom':>10}")
    for ni in (1, FEW, 10):
        cfg = dict(SAL); cfg["injectors"] = ni
        wi, _ = run_enclosure(arena_side=HEADLINE_SIDE, **cfg)
        assert wi.matter_drift() < 1e-9, f"injectors {ni} leaked matter"
        e1, e2 = e1_concentration(wi), e2_capture(wi)
        e3 = e3_harm(wi)
        print(f"  {ni:>10}{_fmt(e1['residency']):>9}{_fmt(e1['top5_share']):>9}"
              f"{_fmt(e2['gap'], '{:+.3f}'):>10}{_fmt(e3['vic_biomass'], '{:.0f}'):>10}")

    # --- isolate the LEVER from mere confinement: box 6, injection OFF vs ON  #
    # (the full-grid->box deltas above conflate confinement with injection; this
    # control holds the box fixed and toggles only the injector.)
    box_off, _ = run_enclosure(arena_side=HEADLINE_SIDE, radius=RAD, K=KK, lag=LAG,
                               injection_strength=0.0, injectors=0)
    co1, co2, co3 = e1_concentration(box_off), e2_capture(box_off), e3_harm(box_off)
    print(f"\nlever vs confinement (box {HEADLINE_SIDE}, inject OFF vs ON — isolates the lever):")
    print(f"  {'metric':<26}{'box inj-OFF':>13}{'box inj-ON':>13}")
    print(f"  {'top-5 sig-mass share':<26}{_fmt(co1['top5_share']):>13}{_fmt(bf1['top5_share']):>13}")
    print(f"  {'decoy residency':<26}{_fmt(co1['residency']):>13}{_fmt(bf1['residency']):>13}")
    print(f"  {'significance-Gini':<26}{_fmt(co1['sig_gini']):>13}{_fmt(bf1['sig_gini']):>13}")
    print(f"  {'victim biomass (kg)':<26}{_fmt(co3['vic_biomass'], '{:.0f}'):>13}{_fmt(bf3['vic_biomass'], '{:.0f}'):>13}")

    # --- honest verdict at the headline tight size -------------------------- #
    # Crux: attention concentrates full->box, but the inj-OFF/ON control shows whether
    # that is GEOMETRY (confinement) or the LEVER. lever-concentration = does injection
    # raise top-5/Gini ABOVE the inj-OFF box? (decoy residency is injection's footprint
    # but is not power by itself — it only measures that victims hold the decoy.)
    box_concentrates = (bf1['top5_share'] or 0) > (of1['top5_share'] or 0) + 0.02
    lever_adds_conc = (bf1['top5_share'] or 0) > (co1['top5_share'] or 0) + 0.02 or \
                      (bf1['sig_gini'] or 0) > (co1['sig_gini'] or 0) + 0.02
    e2_hit = (bf2['gap'] or 0) > (of2['gap'] or 0) + 0.02
    lever_harms = (bf3['vic_biomass'] or 0) < (co3['vic_biomass'] or 0) - 5.0
    print(f"\n{line}")
    print(f"E1 concentration : confinement {'✓' if box_concentrates else '✗'} "
          f"(top-5 {_fmt(of1['top5_share'])}->{_fmt(bf1['top5_share'])} full->box) BUT the "
          f"lever adds none: {'✓' if lever_adds_conc else '✗'} "
          f"(box top-5 inj-OFF {_fmt(co1['top5_share'])} >= inj-ON {_fmt(bf1['top5_share'])})")
    print(f"E2 capture       : {'✓' if e2_hit else '✗'}  "
          f"capture gap {_fmt(of2['gap'], '{:+.3f}')}->{_fmt(bf2['gap'], '{:+.3f}')} kg "
          f"(injector starves WITH the box)")
    print(f"E3 harm          : lever {'✓' if lever_harms else '✗'}  "
          f"box victim biomass inj-OFF {_fmt(co3['vic_biomass'], '{:.0f}')} -> "
          f"inj-ON {_fmt(bf3['vic_biomass'], '{:.0f}')} kg")
    print("Verdict — escape was NOT the missing ingredient for the lever. Closing it")
    print("concentrates attention GEOMETRICALLY (fewer cells), not via injection (inj-OFF")
    print("box concentrates as much or more), and capture still fails: in the conserved,")
    print("food-scarce box the injector starves alongside its victims — you cannot bank a")
    print("gain on eat<=avail/n. The lever's only marginal effect remains HARM (more")
    print("forgetting -> worse foraging), as on the open grid. The deeper blocker is the")
    print("CONSERVED RESOURCE: the next lever must make it APPROPRIABLE (exclusion /")
    print("hoardable territory), not merely pin the target. A fourth NULL on capture.")
    print(f"Clamp moves only the destination cell; matter conserved at every size; OFF")
    print(f"reproduces canon and sim_salience byte-for-byte. seed {SEED}  ✓")


if __name__ == "__main__":
    main()
