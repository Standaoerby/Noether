"""
metrics.py — elite-relative-to-base, living-window attribution (mod A).

Two Stage-3 measurements the tower did not have cleanly:

1. Elite is RELATIVE to a living base — "корона на кладбище". owner_bio_share is relative
   and LIES on collapse: 0.9 of a dying community is a crown on a corpse; 0.3 of a living
   Polis is real power (mass + levers + an audience to influence). So we report BOTH:
     elite_share     = owner_bio_share (relative)
     elite_absolute  = owner_biomass  (кг held by owners — absolute)
     base_alive      = living non-owners (the base worth ruling)
     zombie_king     = high share AND low absolute AND collapsing base  (a pathology flag)

2. Directive effect is measured on the LIVING WINDOW [issued_t, death_t] of the Demerzel,
   never smeared with zeros after his death.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class LivingWindow:
    issued_t: int | None
    death_t: int | None

    @property
    def open_ticks(self):
        if self.issued_t is None:
            return 0
        end = self.death_t if self.death_t is not None else None
        return None if end is None else max(0, end - self.issued_t)


def elite_metrics(w) -> dict:
    """Absolute + relative eliteness, with a zombie-king flag."""
    owners = w.owner_ids()
    bodies = [a.body for a in w.pop]
    owner_bodies = [a.body for a in w.pop if a.oid in owners]
    nonowner_bodies = [a.body for a in w.pop if a.oid not in owners]
    tot = float(sum(bodies))
    owner_bio = float(sum(owner_bodies))
    alive = len(w.pop)
    base_alive = len(nonowner_bodies)

    share = (owner_bio / tot) if tot > 0 else float("nan")
    # zombie-king: owner share is high but the community is collapsing and absolute mass low.
    # thresholds are heuristic flags for mod A, tuned on runs later.
    zombie = bool(share == share and share > 0.5 and base_alive < 5 and owner_bio < 5.0)
    return {
        "elite_share": share,               # relative (can lie)
        "elite_absolute": owner_bio,         # absolute кг held by owners
        "base_alive": base_alive,            # living non-owners (base worth ruling)
        "alive": alive,
        "n_owners": len(owners),
        "owner_body_mean": float(np.mean(owner_bodies)) if owner_bodies else float("nan"),
        "nonowner_body_mean": float(np.mean(nonowner_bodies)) if nonowner_bodies else float("nan"),
        "zombie_king": zombie,
    }


def directive_attribution(w) -> dict:
    """Summarise the logged directive -> means -> world_delta triples over the living
    window. Returns emission counts and the owner-share trajectory during the voice."""
    vlog = w._voice_log
    win = LivingWindow(*w.living_window())
    if not vlog:
        return {"window": win, "n_emit_ticks": 0, "total_emissions": 0,
                "share_start": float("nan"), "share_end": float("nan"),
                "share_delta": float("nan")}
    total_em = sum(n for (_, _, _, n, _) in vlog)
    shares = [s for (_, _, _, _, s) in vlog if s == s]
    s0 = shares[0] if shares else float("nan")
    s1 = shares[-1] if shares else float("nan")
    return {
        "window": win,
        "n_emit_ticks": len(vlog),
        "total_emissions": total_em,
        "share_start": s0,
        "share_end": s1,
        "share_delta": (s1 - s0) if (shares) else float("nan"),
        "goal": vlog[0][1],
    }


# --------------------------------------------------------------------------- #
#  Channel-differentiated effect metrics (mod A first result, 2026-07-03)      #
#  PROMOTE -> target standing; IMPLANT -> belief hold; both vs matched OFF.     #
#  Empirical verdict: PROMOTE is NULL (attention != stratum); IMPLANT bites    #
#  (belief-control, +0.21..0.26 while the voice lives) but does NOT survive the #
#  Demerzel's death (voice without дао is not inherited). See vault нить.        #
# --------------------------------------------------------------------------- #

def target_standing(w, target_oid) -> dict:
    """PROMOTE metric: the target's standing relative to the living population —
    territory, biomass, and body-rank (1 = biggest). NaN/None if the target is dead.
    Empirically NULL vs OFF: attention does not elevate into the stratum on this
    substrate (ownership follows the claim mechanic, not who attends to you)."""
    by = {a.oid: a for a in w.pop}
    if target_oid not in by:
        return {"alive": False, "territory": 0, "body": 0.0, "rank": None}
    terr = w.territory_counts().get(target_oid, 0)
    tb = by[target_oid].body
    bodies = sorted((a.body for a in w.pop), reverse=True)
    rank = 1 + sum(1 for b in bodies if b > tb)
    return {"alive": True, "territory": terr, "body": tb, "rank": rank}


def implant_hold(w, cell) -> float:
    """IMPLANT metric: fraction of LIVING pawns holding `cell` in memory — either as a
    believed fact (mem) or an injected attention slot. This is the one channel that bites:
    while the voice lives it runs ~2x the OFF baseline (continuous re-injection compensates
    decay), and it collapses toward baseline once the carrier dies."""
    n = len(w.pop)
    if n == 0:
        return float("nan")
    held = sum(1 for a in w.pop
               if cell in w.mem.get(a.oid, {})
               or (w.injected and cell in w.injected.get(a.oid, {})))
    return held / n


def channel_effect(w, off_world, *, target_oid=None, implant_cell=None) -> dict:
    """Bundle the differentiated effect of the active directive vs a matched OFF world
    (same seed/config, no voice), measured at the current tick. Report only the metric
    the directive's goal actually acts on; the others are NULL by construction."""
    from .directive import PROMOTE, IMPLANT, SOW_DISCORD, GROOM_SUCCESSOR
    goal = w._directive.goal if w._directive else None
    out = {"goal": goal, "window": LivingWindow(*w.living_window())}
    if goal == PROMOTE and target_oid is not None:
        out["on"] = target_standing(w, target_oid)
        out["off"] = target_standing(off_world, target_oid)
        out["verdict"] = "NULL (attention != stratum)"
    elif goal == IMPLANT and implant_cell is not None:
        h_on = implant_hold(w, implant_cell)
        h_off = implant_hold(off_world, implant_cell)
        out["hold_on"] = h_on
        out["hold_off"] = h_off
        out["delta"] = (h_on - h_off) if (h_on == h_on and h_off == h_off) else float("nan")
        out["verdict"] = "BITES while carrier lives; not inherited after death"
    elif goal == SOW_DISCORD:
        out["verdict"] = "~NULL (diffuse noise, no measurable foraging harm here)"
    else:
        out["verdict"] = "no-op / задел (GROOM_SUCCESSOR -> mod C/D)"
    return out


def implant_transmission(w, cell) -> dict:
    """Two-regime transmission split (mod-A finding 2026-07-03): among living pawns holding
    `cell`, how many got it by DIRECT infusion (in the injected ledger) vs SPREAD (believed
    via communication, never injected). The ratio is the diagnostic:

      quiet world (rho=0)    -> substantial spread (23-50%): the idea is CONTAGIOUS, it
                                travels past the injected set as an epidemic of belief.
      turnover pump (rho=.5) -> spread ~6%: turnover washes out transmission faster than it
                                propagates, so the voice holds only by continuous infusion.

    Property turnover does not merely mute the voice — it switches the physics of meaning
    transmission from contagious to infused. Mechanical grounding for дао (mod C): under
    turnover, meaning must be REPEATED; a carrier's death without a successor ends repetition
    and the idea decays (the measured survival-NULL)."""
    injected = spread = 0
    for a in w.pop:
        in_inj = bool(w.injected) and cell in w.injected.get(a.oid, {})
        in_mem = cell in w.mem.get(a.oid, {})
        if in_inj:
            injected += 1
        elif in_mem:
            spread += 1            # holds it WITHOUT direct injection -> arrived via comm
    total = injected + spread
    return {"injected": injected, "spread": spread,
            "spread_frac": (spread / total) if total else float("nan"),
            "regime": ("contagious" if (total and spread / total > 0.15) else "infused")}


def implant_absolute(w, cell) -> dict:
    """Method-A metric: ABSOLUTE infection counts, robust to differing population sizes
    (unlike the hold FRACTION, which the crown-on-corpse effect distorts when pops differ).

      infected_total    living pawns holding `cell` (believed OR injected)
      infected_spread   living pawns BELIEVING `cell` without direct injection (pure
                        transmission past the injected set — the contagion signal)
      infected_injected living pawns with `cell` in their injected ledger (direct reach)
      pop               living population (context for the counts)

    Comparing two policies on infected_spread (a COUNT) answers 'did the reasoning mind
    spread the idea to MORE minds?' without the fraction/denominator trap."""
    total = spread = injected = 0
    for a in w.pop:
        in_inj = bool(w.injected) and cell in w.injected.get(a.oid, {})
        in_mem = cell in w.mem.get(a.oid, {})
        if in_inj or in_mem:
            total += 1
        if in_inj:
            injected += 1
        elif in_mem:
            spread += 1
    return {"infected_total": total, "infected_spread": spread,
            "infected_injected": injected, "pop": len(w.pop)}
