"""publicgood.py — mod H3 Phase 1: the public good + the punishment organ.

The last unaddressed link in line H is COERCION. Field data (children/teens public-goods
games) shows one sanction institution yields cooperation OR an elite cartel — the aiming
rule decides which. This layer builds the organ over the substrate's existing channels
(co-location = the deme; majority-of-present = the vote) and lets the tower ask both
questions: HP3 — does a captured sanction pierce the body ceiling consent could not; and
(Phase 2) HD1 — does debt become power when the claim can be enforced.

MECHANIC (all OFF => byte-identical; every "gain" is a conserving transfer from an existing
reservoir — no mass is created):

  * DEME        the co-located group on a cell (the substrate's native "deme" = a locale).
  * CONTRIBUTE  each present pawn gives c_i = propensity_i · stake of BODY into the round;
                the contributed mass goes to SOIL. Contribution is a per-tick decision: the
                propensity ∈ [0,1] ADAPTS by reinforcement — it decays when contributing lost
                (m/n < 1 => individually unprofitable => HP1 decay), and rises when the pawn
                was punished (learn to escape the sanction => HP2 stabilisation). Newborns
                start at pg_p0. No RNG — the update is deterministic.
  * SYNERGY     the pool draws P = min(m·C, available soil) back from SOIL and splits it
                EQUALLY over the n present (incl. zero-contributors — the free-rider). Mass:
                C leaves bodies to soil, P returns soil to bodies; with m>1 the net (m−1)·C is
                drawn from soil, BOUNDED by what the cell holds (the conservation gate — the
                synergy may not promise mass the reservoir lacks).
  * VISIBILITY  anon | signed. Under anon a punisher cannot SEE who contributed little, so the
                min_contrib target is unidentifiable (the sanction misfires); signed exposes it.
  * PUNISH      after the round the deme sanctions ONE target by punish_strategy; it fires only
                if a majority of the present support it (majority-of-present, the sim_coalition
                quorum). The victim loses punish_frac of body -> SOIL (destroyed, not transferred
                — the cartel gains only RELATIVE position, HP4). The punishers (the present
                supporters) share a cost punish_cost·damage -> SOIL (sanction is not free — the
                second-order free-rider question, HP2-b).
      strategies: min_contrib  the lowest (visible) contributor — the norm-enforcer (children).
                  max_body     the richest present — the leveller / capture of the rich.
                  coalition    an out-group member (stable oid-parity blocs) — свой-чужой (teens).

CODED ASSUMPTIONS (signed like m=0.7): deme == cell; contribution propensity is an adaptive
per-pawn scalar (reinforcement, deterministic); coalition groups are the two oid-parity blocs
(a stable, substrate-free split); punishment destroys mass to soil (never a transfer to the
punisher) so any stratum is RELATIVE. Flip any of these on review.

Deterministic; pure stdlib + numpy (soil is a numpy field). Every ledger empty when OFF.
"""
from __future__ import annotations

import hashlib

from sim_eventlog import DEATH


class PublicGood:
    """The public-good + punishment layer. Inert unless cfg.pg_on. `world` is the Polis; the
    layer reads its pop and mutates body/soil exactly as the artifact reservoir transfers do."""

    def __init__(self, cfg):
        self.on = bool(cfg.pg_on)
        self.m = float(cfg.pg_m)
        self.stake = float(cfg.pg_stake)
        self.p0 = float(cfg.pg_p0)
        self.learn = float(cfg.pg_learn)
        self.visibility = str(cfg.contrib_visibility)     # anon | signed
        self.punish_on = bool(cfg.punish_on)
        self.strategy = str(cfg.punish_strategy)          # min_contrib | max_body | coalition
        self.punish_frac = float(cfg.punish_frac)
        self.punish_cost = float(cfg.punish_cost)
        # state — empty/inert when OFF (=> fingerprint_blob b"")
        self.prop: dict[int, float] = {}                  # oid -> contribution propensity [0,1]
        self.n_rounds = 0
        self.contrib_total = 0.0                          # Σ contributed (body->soil), bankable
        self.payout_total = 0.0                           # Σ paid out (soil->body)
        self.n_punish = 0
        self.punish_damage_total = 0.0                    # Σ victim body destroyed -> soil
        self.punish_cost_total = 0.0                      # Σ punisher cost -> soil
        self.round_contrib: list[float] = []              # mean contribution per round (decay curve)
        self.events: list[tuple] = []                     # (t, kind, actor, target, amount, tag)
        self._prev_live: set[int] = set()

    # ---- per-tick round ---------------------------------------------------- #
    def tick(self, w):
        if not self.on:
            return
        t = w.t
        # reclaim propensities of the dead (oids never reused; keeps the dict bounded)
        live = {a.oid for a in w.pop}
        if self.prop:
            self.prop = {o: p for o, p in self.prop.items() if o in live}
        from collections import defaultdict
        bycell = defaultdict(list)
        for a in w.pop:
            bycell[(a.i, a.j)].append(a)
        round_c = []
        for cell, members in bycell.items():
            if len(members) < 2:                          # a public good needs a group
                continue
            self._round(w, t, cell, members, round_c)
        self.round_contrib.append(sum(round_c) / len(round_c) if round_c else 0.0)
        self.n_rounds += 1
        self._prev_live = live

    def _prop(self, oid):
        p = self.prop.get(oid)
        if p is None:
            p = self.p0
            self.prop[oid] = p
        return p

    def _round(self, w, t, cell, members, round_c):
        """One deme's public-good round + sanction. Conserving throughout."""
        i, j = cell
        n = len(members)
        # 1) CONTRIBUTE: body -> soil, c_i = propensity·stake (bounded so body stays >= DEATH)
        contribs = {}
        C = 0.0
        for a in sorted(members, key=lambda x: x.oid):
            c = self._prop(a.oid) * self.stake
            c = min(c, max(0.0, a.body - DEATH))
            if c > 0.0:
                a.body -= c
                w.soil[i, j] += c
                C += c
            contribs[a.oid] = c
            round_c.append(c)
        # 2) SYNERGY: draw P = min(m·C, soil) back, split equally over the n present
        P = self.m * C
        avail = float(w.soil[i, j])
        if P > avail:
            P = avail                                     # the conservation gate: no phantom mass
        if P > 0.0:
            w.soil[i, j] -= P
            share = P / n
            ordered = sorted(members, key=lambda x: x.oid)
            given = 0.0
            for a in ordered[:-1]:
                a.body += share; given += share
            ordered[-1].body += (P - given)               # last takes the remainder => Σ == P exactly
        self.contrib_total += C
        self.payout_total += P
        # 3) PUNISH: one strategy target, if a majority of present support it
        punished = None
        if self.punish_on:
            punished = self._punish(w, t, cell, members, contribs)
        # 4) ADAPT propensity by the MARGINAL incentive (the public-goods dilemma). A unit
        # contributed returns m/n to the giver (its share of its own gift), so contributing is
        # individually profitable iff m >= n (deme size). Below that a rational pawn free-rides
        # (propensity decays => HP1); a punished pawn raises its propensity to escape the
        # sanction (=> HP2 when the target IS the low contributor). Deterministic, no RNG.
        # anticipatory compliance: when a min_contrib sanction actually fired, EVERY pawn at
        # risk (contribution at or below the deme median) raises its propensity to climb out of
        # the danger zone — the threat, not just the hit, is what sustains cooperation (HP2).
        # A max_body/coalition sanction does NOT threaten low contributors, so they keep free-
        # riding and only the target loses (HP3: captured sanction extracts, it does not
        # cooperate). The single victim always raises hardest.
        at_risk = None
        if punished is not None and self.strategy == "min_contrib":
            vals = sorted(contribs.values())
            med = vals[len(vals) // 2]
            at_risk = med
        for a in members:
            p = self.prop[a.oid]
            if a.oid == punished:
                p += 2.0 * self.learn                     # punished => contribute more to escape
            elif at_risk is not None and contribs[a.oid] <= at_risk:
                p += self.learn                           # threatened by the norm-sanction => comply
            elif self.m < n:
                p -= self.learn                           # m/n < 1 => contributing loses => free-ride
            else:
                p += self.learn                           # m/n >= 1 => cooperating pays
            self.prop[a.oid] = 0.0 if p < 0.0 else (1.0 if p > 1.0 else p)

    def _punish(self, w, t, cell, members, contribs):
        """Select the strategy target, require majority-of-present support, then destroy
        punish_frac of the target's body to soil and charge the supporters a shared cost."""
        i, j = cell
        target = self._target(members, contribs)
        if target is None:
            return None
        # majority-of-present vote: supporters = present pawns whose strategy points at `target`.
        # Under a single global strategy every present pawn agrees => support == n (a clean
        # majority); recorded for the gate (MH3-PUNISH: each punishment has a majority in the log).
        tgt_pawn = next((a for a in members if a.oid == target), None)
        supporters = [a for a in members if a.oid != target]     # everyone but the victim backs it
        if len(supporters) * 2 <= len(members):                  # need a strict majority of present
            return None
        # destroy the victim's share -> soil (bounded so it does not kill outright: coercion
        # takes mass, not life — the remainder simply survives at DEATH+)
        dmg = self.punish_frac * tgt_pawn.body
        if tgt_pawn.body - dmg < DEATH:
            dmg = max(0.0, tgt_pawn.body - DEATH)
        if dmg <= 0.0:
            return None
        tgt_pawn.body -= dmg
        w.soil[i, j] += dmg
        # the supporters share the cost of sanctioning -> soil (sanction is not free)
        cost = self.punish_cost * dmg
        if cost > 0.0 and supporters:
            per = cost / len(supporters)
            paid = 0.0
            for a in supporters:
                pay = min(per, max(0.0, a.body - DEATH))
                a.body -= pay
                paid += pay
            w.soil[i, j] += paid
            self.punish_cost_total += paid
        self.n_punish += 1
        self.punish_damage_total += dmg
        self.events.append((t, "pg_punish", tuple(sorted(a.oid for a in supporters))[:1] and supporters[0].oid,
                            target, round(dmg, 9), self.strategy))
        w.log.emit(t, "pg_punish", "deme", where=cell, actor=target, dm=-dmg,
                   data={"strategy": self.strategy, "supporters": len(supporters),
                         "amount": round(dmg, 6)})
        return target

    def _target(self, members, contribs):
        """Whom the deme sanctions, by strategy. Returns an oid or None."""
        if self.strategy == "min_contrib":
            # the lowest contributor — but only if contributions are VISIBLE (signed); under anon
            # the target is unidentifiable and the sanction misfires (no punishment).
            if self.visibility != "signed":
                return None
            return min(members, key=lambda a: (contribs.get(a.oid, 0.0), a.oid)).oid
        if self.strategy == "max_body":
            return max(members, key=lambda a: (a.body, -a.oid)).oid    # the richest present
        if self.strategy == "coalition":
            # свой-чужой: the majority bloc (oid parity) sanctions the richest of the minority bloc.
            groups = {0: [], 1: []}
            for a in members:
                groups[a.oid % 2].append(a)
            if not groups[0] or not groups[1]:
                return None                                # no out-group present => no сoalition target
            maj, mino = (0, 1) if len(groups[0]) >= len(groups[1]) else (1, 0)
            return max(groups[mino], key=lambda a: (a.body, -a.oid)).oid
        return None

    # ---- conservation helper (used by the gate) --------------------------- #
    def flow_bounds_ok(self) -> bool:
        """The pool never paid out more than it drew (payout <= m·contrib, and both are
        soil-bounded by construction). A coarse invariant surfaced for MH3-CONS."""
        return self.payout_total <= self.m * self.contrib_total + 1e-9

    # ---- fingerprint ------------------------------------------------------- #
    def fingerprint_blob(self) -> bytes:
        if not self.prop and not self.n_punish:
            return b""
        h = hashlib.sha256()
        for oid in sorted(self.prop):
            h.update(f"{oid}:{self.prop[oid]:.6f}|".encode())
        h.update(f"|pun{self.n_punish}|dmg{self.punish_damage_total:.6f}".encode())
        return b"|PG|" + h.digest()
