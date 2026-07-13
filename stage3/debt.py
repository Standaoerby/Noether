"""debt.py — mod H (виток 1): DEBT. Power from consent.

DELEGATE (mod G2 Фаза 2) is coercion from above; EXTORT (Фаза 1) is violence in the
shadow. Debt is the deal from below: a hungry pawn accepts a creditor's terms and a
stratum is born WITHOUT title, WITHOUT violence, WITHOUT presence — the candidate third
conductivity, and the only mechanism able to pierce both ceilings vitok 2 found (the
presence ceiling and the body ceiling).

The mechanic, on the conserving substrate:
  * LOAN     a creditor's free `store` mass -> a hungry debtor's BODY (a reservoir->body
             transfer, lossless like a hunger draw; mass-neutral by construction). The
             obligation `debt[(creditor,debtor)] += amount·k` is a LEDGER entry, not mass.
  * RATE k   endogenous, k = k_min + (k_max-k_min)·sat(D/S), sat(x)=x/(1+x); D = total
             outstanding (demand), S = total free store (supply). FIXED at the contract
             (vintage) — a debt glut makes new credit dear, which makes more defaults,
             which makes more bondage: the feedback that grows the stratum.
  * PAYMENT  a share r of the debtor's per-tick INCOME (body gain this tick) flows body ->
             the creditor's store, every tick until the obligation clears. Mass-neutral.
  * EXITS    (1) repay — income cleared it; (2) default — deterministic trigger r·income >
             metabolism (paying = dying) => the pawn chooses life at the price of rights =>
             BONDAGE; (3) death — the remainder passes to a _house heir, or (no heir) the
             creditor eats the loss (the obligation is written off — no mass moves).
  * LADDER   0 free · 1 debtor (pays r) · 2 overdue (no new loans, claim frozen) · 3
             bondage (all income above metabolism to the creditor, no claim, no voice, and
             its victim-testimony no longer marks an extortioner). Stage 4 (slave) is H3.

CODED ASSUMPTIONS (signed like m=0.7 — properties of the SYSTEM, not pawn knowledge):
  * k_t is a system rate read off aggregate D/S; the hungry does not haggle, it accepts.
  * income this tick = the body gain across the canonical step (grazing + appropriation −
    metabolism), snapshotted by Polis before super().step() and handed in here.
  * metabolism this tick = the canon upkeep (BASE + PEN·mism²)·body (sim_eventlog constants).
  * OVERDUE (stage 2) := a debtor's live outstanding exceeds the principal ever handed to it
    (Σ debt[(·,d)] > principal[d]) — i.e. interest has outrun repayment (Stan 2026-07-13,
    "долг вырос > выданного"). Because k>1 a fresh single loan starts overdue and a debtor
    climbs to stage 1 only once it has paid the interest down (outstanding <= principal):
    stage 1 is the recovering debtor, stage 2 the underwater one. Deterministic, substrate-
    grounded; flip the comparison if the mirror was meant.

Deterministic; pure stdlib. Every ledger empty when debt_on=False => fingerprint_blob b""
=> the layer is byte-identical to mod G2 (gate MH-OFF).
"""
from __future__ import annotations

import hashlib

from sim_eventlog import BASE, PEN, REPRO


def _sat(x: float) -> float:
    return x / (1.0 + x)


class DebtLedger:
    """The debt layer. Inert (all no-ops) unless cfg.debt_on. `world` is the Polis: the
    ledger reads its pawns, temperature grid and artifact stores, and moves mass between a
    store and a body exactly as the canon store-draw does (lossless reservoir transfer)."""

    def __init__(self, cfg):
        self.on = bool(cfg.debt_on)
        self.r = float(cfg.debt_r)
        self.k_min = float(cfg.debt_k_min)
        self.k_max = float(cfg.debt_k_max)
        self.hunger_at = (float(cfg.store_draw_at) if cfg.debt_hunger_at is None
                          else float(cfg.debt_hunger_at))
        self.income_drop = float(cfg.debt_income_drop)
        self.invest_at = (2.0 * REPRO if cfg.debt_invest_at is None
                          else float(cfg.debt_invest_at))
        # ledgers — ALL empty when OFF (=> fingerprint_blob() == b"" => MH-OFF)
        self.debt: dict[tuple[int, int], float] = {}   # (creditor, debtor) -> outstanding (kg)
        self.principal: dict[int, float] = {}          # debtor -> Σ mass handed over (pre-k)
        self.stage: dict[int, int] = {}                # debtor -> 1|2|3   (0 free = absent)
        self._bonded: set[int] = set()                 # debtors that have defaulted (stage-3 sticky)
        self.issued_k_total = 0.0                      # Σ(amount·k)      — MH-ledger identity
        self.repaid_total = 0.0                        # Σ repaid          — MH-ledger identity
        self.written_off_total = 0.0                   # Σ burned on heirless death
        self.n_loans = 0
        self.n_defaults = 0
        self.reason_counts = {"hunger": 0, "income_drop": 0, "investment": 0}
        self.events: list[tuple] = []                  # (t, kind, creditor, debtor, amount, tag)
        self._income: dict[int, float] = {}            # oid -> income THIS tick (set by Polis)
        self._income_mean: dict[int, float] = {}       # oid -> trailing mean income (income_drop)
        self._prev_live: set[int] = set()              # last tick's living oids (death detection)

    # ---- income handoff from Polis ---------------------------------------- #
    def set_income(self, income: dict):
        """Polis hands in {oid: body gain across super().step()} (clamped >= 0)."""
        self._income = income

    # ---- rate ------------------------------------------------------------- #
    def _rate(self) -> float:
        D = sum(self.debt.values())
        S = self._free_store_total_cache
        if S <= 0.0:
            return self.k_max                    # no supply => credit at the ceiling
        return self.k_min + (self.k_max - self.k_min) * _sat(D / S)

    # ---- store helpers (a store == an Artifact(kind='store'), maker-owned) - #
    def _stores_by_maker(self, w):
        out: dict[int, list] = {}
        af = getattr(w, "_artifacts", None)
        if af is None:
            return out
        for art in af.artifacts:
            if art.kind == "store" and art.mass > 1e-15:
                out.setdefault(art.maker_oid, []).append(art)
        return out

    def _free_store_total(self, stores_by_maker) -> float:
        return sum(a.mass for lst in stores_by_maker.values() for a in lst)

    # ---- the per-tick pass ------------------------------------------------ #
    def tick(self, w):
        if not self.on:
            return
        t = w.t
        living = {a.oid: a for a in w.pop}
        # death: obligations of the dead pass to a _house heir, else write off
        self._resolve_deaths(w, t, living)
        stores = self._stores_by_maker(w)
        self._free_store_total_cache = self._free_store_total(stores)
        # 1) payment out of income (services existing debt)
        self._pay(w, t, living, stores)
        # 2) default + stage ladder (deterministic; reads income + metabolism)
        self._update_stages(w, t, living)
        # 3) new loans (triggered debtors matched to a co-present creditor with free store)
        self._lend(w, t, living, stores)
        # 4) rights enforcement AT EXECUTION (claim revoke + voice strip for stage>=2/3)
        self._enforce_rights(w, t, living)
        # 5) roll trailing income for the income_drop trigger
        for oid, inc in self._income.items():
            m = self._income_mean.get(oid)
            self._income_mean[oid] = inc if m is None else 0.7 * m + 0.3 * inc
        self._prev_live = set(living)

    # ---- metabolism (canon upkeep, recomputed exactly) -------------------- #
    @staticmethod
    def _metabolism(w, a) -> float:
        mism = a.gene - float(w.T[a.i, a.j])
        up = (BASE + PEN * mism * mism) * a.body
        return up if up < a.body else a.body

    # ---- outstanding-per-debtor helper ------------------------------------ #
    def _owed_by(self, debtor: int) -> float:
        return sum(v for (c, d), v in self.debt.items() if d == debtor)

    # ---- (1) PAYMENT ------------------------------------------------------ #
    def _pay(self, w, t, living, stores):
        """Each debtor with income routes a share to its creditors (body -> creditor store).
        stage 1/2 pay r·income; stage 3 (bondage) pays ALL income above metabolism. Mass is
        conserved: it leaves the debtor's body and enters the creditor's store."""
        debtors = sorted({d for (_c, d) in self.debt})
        for d in debtors:
            a = living.get(d)
            if a is None:
                continue
            inc = max(0.0, self._income.get(d, 0.0))
            if inc <= 0.0:
                continue
            if d in self._bonded:
                met = self._metabolism(w, a)
                budget = max(0.0, inc - met)                 # all surplus above metabolism
            else:
                budget = self.r * inc
            budget = min(budget, max(0.0, a.body - 1e-12))   # cannot pay more body than one has
            if budget <= 0.0:
                continue
            # pay creditors in oid order until the budget is spent
            for c in sorted(cc for (cc, dd) in self.debt if dd == d):
                owed = self.debt.get((c, d), 0.0)
                if owed <= 0.0:
                    continue
                creditor = living.get(c)
                if creditor is None:
                    continue                                # creditor gone (resolved already) — no mass moves
                pay = min(budget, owed)
                if pay <= 0.0:
                    continue
                a.body -= pay                                # MASS leaves the debtor's body...
                self._deposit_to_store(w, creditor, pay)     # ...and enters the creditor's store/body
                self.debt[(c, d)] = owed - pay
                if self.debt[(c, d)] <= 1e-12:
                    del self.debt[(c, d)]
                self.repaid_total += pay
                budget -= pay
                self.events.append((t, "debt_pay", c, d, round(pay, 9), None))
                w.log.emit(t, "debt_pay", "individual", where=(a.i, a.j), actor=d,
                           dm=pay, data={"creditor": c, "amount": round(pay, 6)})
                if budget <= 1e-12:
                    break

    def _deposit_to_store(self, w, creditor, amount):
        """body -> the (living) creditor's store. Top up the creditor's oldest live store; if
        it has none, the mass returns to the creditor's body (the store was fully lent out —
        the repayment rebuilds the body). Conserving by construction — `creditor` is a live
        Animal (checked in _pay), so the mass always lands."""
        af = getattr(w, "_artifacts", None)
        best = None
        if af is not None:
            for art in af.artifacts:
                if art.kind == "store" and art.maker_oid == creditor.oid and art.mass > 1e-15:
                    if best is None or art.aid < best.aid:
                        best = art
        if best is not None:
            best.mass += amount
        else:
            creditor.body += amount

    # ---- (2) STAGES + DEFAULT --------------------------------------------- #
    def _update_stages(self, w, t, living):
        debtors = sorted({d for (_c, d) in self.debt})
        for d in debtors:
            a = living.get(d)
            owed = self._owed_by(d)
            if owed <= 1e-12:
                self.stage.pop(d, None)
                continue
            if a is not None and d not in self._bonded:
                inc = max(0.0, self._income.get(d, 0.0))
                met = self._metabolism(w, a)
                if self.r * inc > met:                       # paying = dying => choose life
                    self._bonded.add(d)
                    self.n_defaults += 1
                    self.events.append((t, "debt_default", None, d, 0.0, "bondage"))
                    w.log.emit(t, "debt_default", "individual",
                               where=(a.i, a.j), actor=d, dm=0.0, data={"reason": "bondage"})
            if d in self._bonded:
                self.stage[d] = 3
            elif owed > self.principal.get(d, 0.0):          # overdue: interest outran repayment
                self.stage[d] = 2
            else:
                self.stage[d] = 1

    # ---- (3) LOANS -------------------------------------------------------- #
    def _lend(self, w, t, living, stores):
        if not stores:
            return
        k = self._rate()                                     # one system rate per tick (vintage)
        owners = set(w.owner_ids()) if hasattr(w, "owner_ids") else set()
        # co-location map (presence == same cell on this substrate)
        bycell: dict[tuple, list] = {}
        for a in w.pop:
            bycell.setdefault((a.i, a.j), []).append(a)
        # deterministic debtor order
        for a in sorted(w.pop, key=lambda x: x.oid):
            d = a.oid
            st = self.stage.get(d, 0)
            if st >= 2:                                       # overdue/bonded: no new loans
                continue
            reason = self._loan_reason(a, owners)
            if reason is None:
                continue
            # creditor: co-present maker of a free store, nearest (== same cell) then lowest oid
            cand = None
            for other in sorted(bycell.get((a.i, a.j), ()), key=lambda x: x.oid):
                if other.oid == d:
                    continue
                lst = stores.get(other.oid)
                if lst and any(s.mass > 1e-15 for s in lst):
                    cand = other.oid
                    break
            if cand is None:
                continue
            amount = self._loan_amount(a, reason, stores[cand])
            if amount <= 1e-12:
                continue
            self._issue(w, t, cand, d, amount, k, stores, reason, a)

    def _loan_reason(self, a, owners):
        """Return the trigger reason, or None. Priority: hunger > income_drop > investment."""
        if a.body < self.hunger_at:
            return "hunger"
        inc = self._income.get(a.oid, 0.0)
        mean = self._income_mean.get(a.oid)
        if mean is not None and mean > 1e-9 and inc < self.income_drop * mean:
            return "income_drop"
        if a.oid not in owners and a.body >= self.invest_at:
            return "investment"
        return None

    def _loan_amount(self, a, reason, creditor_stores):
        free = sum(s.mass for s in creditor_stores if s.mass > 1e-15)
        if reason == "hunger":
            target = max(0.0, self.hunger_at - a.body)        # lift the body to the hunger line
        else:
            target = REPRO * 0.5                              # a fixed quantum (shock / claim seed)
        return min(free, target)

    def _issue(self, w, t, creditor, debtor, amount, k, stores, reason, a):
        # draw `amount` from the creditor's stores (oldest first), add to the debtor's body
        need = amount
        for s in sorted(stores[creditor], key=lambda x: x.aid):
            if need <= 1e-12:
                break
            take = min(s.mass, need)
            s.mass -= take                                    # MASS leaves the store...
            need -= take
        moved = amount - need
        if moved <= 1e-12:
            return
        a.body += moved                                       # ...and enters the debtor's body
        obligation = moved * k
        self.debt[(creditor, debtor)] = self.debt.get((creditor, debtor), 0.0) + obligation
        self.principal[debtor] = self.principal.get(debtor, 0.0) + moved
        self.issued_k_total += obligation
        self.stage[debtor] = max(self.stage.get(debtor, 0), 1)
        self.n_loans += 1
        self.reason_counts[reason] += 1
        self.events.append((t, "debt_loan", creditor, debtor, round(moved, 9), reason))
        w.log.emit(t, "debt_loan", "individual", where=(a.i, a.j), actor=debtor, dm=moved,
                   data={"creditor": creditor, "amount": round(moved, 6),
                         "k": round(k, 6), "reason": reason})

    # ---- (4) RIGHTS ENFORCEMENT (at execution, not affordance) ------------ #
    def _enforce_rights(self, w, t, living):
        """Stage 2/3 freeze the claim; stage 3 also strips the voice. Enforced HERE, on the
        settled tick, by mutating world state — NOT only on an affordance — so a reflex policy
        cannot make the deprivation a silent no-op (the Фаза-4 lesson; gate MH-BANKRUPT). The
        testimony strip (a bonded victim no longer marks an extortioner) lives in Polis._extort,
        which reads is_bonded()."""
        owner_map = getattr(w, "_cell_owner", None)
        for d, st in self.stage.items():
            if st < 2:
                continue
            a = living.get(d)
            if a is None:
                continue
            # claim frozen: revoke any territorial ownership the frozen/bonded pawn holds
            if owner_map is not None:
                for cell, oid in list(owner_map.items()):
                    if oid == d:
                        del owner_map[cell]
                        self.events.append((t, "debt_claim_revoke", None, d, 0.0, cell))
            if st >= 3:
                # bondage: no voice — struck from the speaker set (canon set, mutable state)
                spk = getattr(w, "speaker", None)
                if spk is not None and d in spk:
                    spk.discard(d)
                    self.events.append((t, "debt_voice_strip", None, d, 0.0, None))

    def is_bonded(self, oid) -> bool:
        return oid in self._bonded

    # ---- DEATH: inheritance by _house, else write-off --------------------- #
    def _resolve_deaths(self, w, t, living):
        dead = self._prev_live - set(living)
        if not dead:
            return
        house = getattr(w, "_house", None)                    # oid -> line id (mod 25), if present
        for (c, d) in list(self.debt.keys()):
            amt = self.debt[(c, d)]
            heir = None
            if d in dead:
                heir = self._find_heir(w, d, house, living)
                del self.debt[(c, d)]
                if heir is not None and heir != c:
                    self.debt[(c, heir)] = self.debt.get((c, heir), 0.0) + amt
                    self.principal[heir] = self.principal.get(heir, 0.0) + self.principal.get(d, 0.0)
                    if d in self._bonded:
                        self._bonded.add(heir)                # bondage is inherited with the debt
                    self.events.append((t, "debt_inherit", c, heir, round(amt, 9), d))
                else:
                    self.written_off_total += amt             # no heir => the creditor eats it
                    self.events.append((t, "debt_writeoff", c, d, round(amt, 9), None))
            if c in dead and (c, d) in self.debt:
                # creditor died: the claim on a live debtor lapses (obligation written off)
                self.written_off_total += self.debt[(c, d)]
                self.events.append((t, "debt_writeoff", c, d, round(self.debt[(c, d)], 9), "creditor"))
                del self.debt[(c, d)]
        for d in dead:
            self.stage.pop(d, None)
            self.principal.pop(d, None)
            self._bonded.discard(d)

    @staticmethod
    def _find_heir(w, dead_oid, house, living):
        """The lowest-oid living pawn sharing the dead's _house line (mod 25). None if the
        world has no _house map or no living kin."""
        if not house:
            return None
        line = house.get(dead_oid)
        if line is None:
            return None
        kin = sorted(o for o in living if house.get(o) == line and o != dead_oid)
        return kin[0] if kin else None

    # ---- identity + fingerprint ------------------------------------------- #
    def outstanding_sum(self) -> float:
        return sum(self.debt.values())

    def ledger_identity_residual(self) -> float:
        """MH-ledger: Σ outstanding ≡ Σ(issued·k) − Σ repaid − Σ written_off. Returns the
        residual, which must be ~0 every tick (float print tolerance)."""
        return self.outstanding_sum() - (self.issued_k_total - self.repaid_total
                                         - self.written_off_total)

    def fingerprint_blob(self) -> bytes:
        """Empty when OFF (no loan ever issued) => the substrate hash is byte-identical to
        mod G2 (MH-OFF). When ON, the debt state enters the fingerprint: outstanding per
        (creditor,debtor) in a fixed order + the stage ladder + the bonded set."""
        if not self.debt and not self.stage and not self._bonded:
            return b""
        h = hashlib.sha256()
        for (c, d) in sorted(self.debt):
            h.update(f"{c}>{d}:{self.debt[(c, d)]:.9f}|".encode())
        for d in sorted(self.stage):
            h.update(f"s{d}={self.stage[d]}|".encode())
        for d in sorted(self._bonded):
            h.update(f"b{d}|".encode())
        return b"|DEBT|" + h.digest()
