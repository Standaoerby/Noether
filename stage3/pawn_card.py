"""
pawn_card.py — E1: the pawn card as PROJECTIONS over the single canonical EventLog.

"Одна великолепная карточка": the journal is ONE, the cards are VIEWS. Nothing here collects
new data and nothing mutates the world — every function is a pure fold/query over an
`EventLog` (+ `viz_export` snapshots where the log has no trail). Canon `Code/sim_*.py` and
`stage3/polis.py` are untouched; the reader lives outside the world classes (the glass
pattern), so a run under this reader keeps its fingerprint (gate E1-VOFF).

SOURCE SPLIT — the cards divide by SOURCE, not by convenience:
  * LOG-derived  — Chronicle, HouseHistory, RelationshipHistory, PropertyHistory. Cheap; the
    log is not lossy for these, so they carry the E1-FAITHFUL guarantee (what the log replays
    == the real thing at every checkpoint).
  * SNAPSHOT-derived — only the co-location half of RelationshipHistory ("who stood beside
    whom"), which no event records.

ВИТОК 2 moved Property to the log. In виток 1 the journal had NO ownership trail at all — no
claim / inherit / lose event existed — so ownership could only be read out of the per-snapshot
`owners` mirror of `_cell_owner`, and the E1-FAITHFUL subgate had to be dropped as vacuous
(a snapshot compared against itself). The faithful-ledger WO fixed the source, not the reader:
`faithful_ledger=True` makes Polis mirror ownership into the log, and Property is now folded
from claim/lose/inherit ALONE. The snapshot path is deleted — one source, no dual path.

Reading the ledger correctly needs one non-obvious thing. A cell handed straight from X to Y
emits `claim actor=Y data{from:X}` and NO `lose` for X — the loss is implicit in `from`. So a
per-oid scan (`events where actor==oid`) would silently keep cells the pawn no longer owns.
Property therefore replays the GLOBAL cell->owner map and filters, which is also what makes
the gate meaningful: the same replay must equal `_cell_owner` tick by tick.

Виток 1: Chronicle · House · Relationship · Property(snapshots).
Виток 2: Property(log) · Reputation · PowerFlow.

Determinism: every projection returns plain sorted/rounded data; `pawn_card()` stamps a
SHA-256 over the canonical dump (sorted keys, compact separators) — same run, same card
(gate E1-DET).
"""
from __future__ import annotations

import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "Code"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from stage3.viz_export import _Houses                      # noqa: E402  (lineage from the log)

CARD_VERSION = 1

# oid-bearing `data` fields (Ф0 forensics; verbatim key names, never renamed)
OID_SCALAR = ("heard_by", "maker", "root")
OID_LIST = ("victims", "takers")

# events that are the pawn's own material/inner acts (Chronicle body)
_ACT_KINDS = (
    "move", "cognition", "forget",
    "artifact_write", "artifact_copy", "artifact_read", "artifact_store",
    "artifact_capital", "artifact_store_draw", "artifact_capital_boost", "artifact_ruin",
)


def _q(x, n=4):
    """Deterministic float rounding (mirrors viz_export._q)."""
    return round(float(x), n) if isinstance(x, (int, float)) else x


def roles_of(e, oid):
    """Every role `oid` plays in event `e`. The full per-oid surface — a scan over
    actor/parent alone under-counts (Ф0: extort carries victims[]/takers[] as LISTS)."""
    r = []
    if e.actor == oid:
        r.append("actor")
    if e.parent == oid:
        r.append("parent")
    d = e.data or {}
    for k in OID_SCALAR:
        if d.get(k) == oid:
            r.append(f"data.{k}")
    for k in OID_LIST:
        v = d.get(k)
        if isinstance(v, (list, tuple)) and oid in v:
            r.append(f"data.{k}")
    return r


# --------------------------------------------------------------------------- #
#  1. PawnChronicle — LOG-derived                                              #
# --------------------------------------------------------------------------- #
def chronicle(log, oid):
    """Origin -> own acts -> death, straight from the journal. `seed` marks a founder (no
    birth event); `birth` marks a child and names the parent."""
    ev = log.events
    origin, death, acts = None, None, []
    for e in ev:
        if e.actor != oid:
            continue
        if e.kind in ("seed", "birth") and origin is None:
            origin = {"kind": e.kind, "t": e.t, "where": list(e.where) if e.where else None,
                      "parent": e.parent, "gene": _q((e.data or {}).get("gene"), 4)}
        elif e.kind == "death":
            death = {"t": e.t, "where": list(e.where) if e.where else None,
                     "age": (e.data or {}).get("age"),
                     "cause": (e.data or {}).get("cause", "starvation"), "dm": _q(e.dm, 4)}
        elif e.kind in _ACT_KINDS:
            acts.append({"t": e.t, "kind": e.kind,
                         "where": list(e.where) if e.where else None})
    counts = {}
    for a in acts:
        counts[a["kind"]] = counts.get(a["kind"], 0) + 1
    span = None
    if origin is not None:
        end = death["t"] if death else (ev[-1].t if ev else origin["t"])
        span = {"born_t": origin["t"], "end_t": end, "ticks": end - origin["t"]}
    return {
        "oid": oid, "origin": origin, "death": death, "lifespan": span,
        "act_counts": dict(sorted(counts.items())),
        "n_acts": len(acts),
        "descendants": sorted(log.descendants(oid)) if hasattr(log, "descendants") else [],
    }


# --------------------------------------------------------------------------- #
#  2. HouseHistory — LOG-derived (lineage reconstructed from birth events)     #
# --------------------------------------------------------------------------- #
def house_history(log, oid, houses=None):
    """Bloodline: which house root, how deep the line runs, who the kin are."""
    ev = log.events
    H = houses or _Houses(ev)
    root = H.house(oid)
    # ancestors: walk parent links up from oid
    parent_of = {e.actor: e.parent for e in ev if e.kind == "birth" and e.actor is not None}
    chain, cur, guard = [], oid, 0
    while cur in parent_of and guard < 10_000:
        cur = parent_of[cur]
        chain.append(cur)
        guard += 1
    children = sorted(e.actor for e in ev if e.kind == "birth" and e.parent == oid)
    kin = sorted({e.actor for e in ev
                  if e.kind in ("birth", "seed") and e.actor is not None and H.house(e.actor) == root})
    return {
        "house_root": root,
        "is_founder": root == oid,
        "ancestors": chain,               # nearest parent first, up to the founder
        "generation_depth": len(chain),   # 0 == founder
        "children": children,
        "n_children": len(children),
        "house_size": len(kin),           # everyone ever born/seeded into this house
    }


# --------------------------------------------------------------------------- #
#  3. RelationshipHistory — LOG (+ snapshot Dunbar edges)                      #
# --------------------------------------------------------------------------- #
def relationship_history(log, snapshots, oid):
    """Who this pawn knew (Dunbar ties over time), who it spoke to / was heard by, whom it
    extorted and who extorted it, and its remittance line."""
    spoke, heard, took, taken_from, remitted, received = [], [], [], [], [], []
    for e in log.events:
        d = e.data or {}
        if e.kind == "communication":
            if e.actor == oid:
                spoke.append({"t": e.t, "to": d.get("heard_by"), "truthful": d.get("truthful")})
            elif d.get("heard_by") == oid:
                heard.append({"t": e.t, "from": e.actor, "truthful": d.get("truthful")})
        elif e.kind == "extort":
            vs, ts = d.get("victims") or [], d.get("takers") or []
            if oid in ts:
                took.append({"t": e.t, "victims": sorted(vs), "amount": _q(d.get("amount"), 4)})
            if oid in vs:
                taken_from.append({"t": e.t, "takers": sorted(ts), "amount": _q(d.get("amount"), 4)})
        elif e.kind == "delegate_remit":
            if e.actor == oid:
                remitted.append({"t": e.t, "root": d.get("root"), "amount": _q(d.get("amount"), 4)})
            if d.get("root") == oid:
                received.append({"t": e.t, "from": e.actor, "amount": _q(d.get("amount"), 4)})
    # Dunbar ties from snapshots: undirected `known` edges touching oid
    ties, tie_ticks = {}, 0
    for s in snapshots:
        partners = [(b if a == oid else a, sal) for (a, b, sal) in s.get("known", ())
                    if a == oid or b == oid]
        if partners:
            tie_ticks += 1
        for p, sal in partners:
            prev = ties.get(p)
            ties[p] = max(sal, prev) if prev is not None else sal
    return {
        "known_partners": [[p, _q(s, 3)] for p, s in sorted(ties.items())],
        "n_known": len(ties),
        "ticks_with_ties": tie_ticks,
        "spoke": spoke, "heard": heard,
        "extorted": took, "extorted_by": taken_from,
        "remitted": remitted, "received_remit": received,
        "totals": {
            "n_spoke": len(spoke), "n_heard": len(heard),
            "n_extorted": len(took), "n_extorted_by": len(taken_from),
            # GROSS, and named so. An extortion pools the take over the cell and splits it
            # among the takers; the event carries only the pool. Summing `amount` therefore
            # measures EVENTS THIS PAWN WAS PART OF, not mass it personally received — for
            # #58 in the showcase scene the gap is 203.63 gross vs 31.25 attributed (×6.5).
            # The personal figure lives in `power.totals.extort_attributed`, which replays
            # the split rule and is checked against real body deltas by gate PF-SHARE.
            "mass_extorted_gross": _q(sum(x["amount"] or 0 for x in took), 4),
            "mass_lost_to_extort_gross": _q(sum(x["amount"] or 0 for x in taken_from), 4),
            "mass_remitted": _q(sum(x["amount"] or 0 for x in remitted), 4),
        },
    }


# --------------------------------------------------------------------------- #
#  4. PropertyHistory — LOG-derived (виток 2: the ledger IS the ownership)     #
# --------------------------------------------------------------------------- #
LEDGER_KINDS = ("claim", "lose", "inherit")


def replay_owners(events, upto=None):
    """The ownership ledger replayed from claim/lose/inherit ALONE -> {cell: owner}.

    This is the whole faithfulness claim in four lines: if the log is a mirror of Polis, this
    dict equals `w._cell_owner` at every tick (gate E1-FAITHFUL-OWN). `claim` and `inherit`
    both SET the owner (a transfer X->Y is one `claim` carrying `from`), `lose` clears the
    cell back to the commons."""
    owner = {}
    for e in events:
        if upto is not None and e.t > upto:
            break
        if e.kind == "claim" or e.kind == "inherit":
            owner[tuple(e.where)] = e.actor
        elif e.kind == "lose":
            owner.pop(tuple(e.where), None)
    return owner


def property_history(log, oid, t_end=None):
    """Ownership over time, folded into tenures — LOG-derived (виток 2).

    Folds the global replay (see `replay_owners`) tick by tick and keeps only the ticks where
    THIS pawn's holding changed; the holding is constant in between, so tenures/ticks/series
    are exact, not sampled. `acts` is the part snapshots could never give: not just that a
    cell changed hands but HOW and WITH WHOM — claim / inherit(from) / lose, and the mirror
    roles `taken` (someone claimed a cell out from under this pawn) and `bequeathed` (a cell
    of this pawn's estate passed to an heir)."""
    ev = [e for e in log.events if e.kind in LEDGER_KINDS]
    if t_end is None:
        t_end = max((e.t for e in log.events), default=0)
    owner, held, acts, changes = {}, set(), [], []
    i, n = 0, len(ev)
    while i < n:
        t = ev[i].t
        j = i
        while j < n and ev[j].t == t:
            e = ev[j]
            cell = tuple(e.where)
            prev = owner.get(cell)
            frm = (e.data or {}).get("from")
            if e.kind == "lose":
                owner.pop(cell, None)
                if prev == oid:
                    acts.append([t, "lose", list(cell), None])
            else:
                owner[cell] = e.actor
                if e.actor == oid:
                    acts.append([t, e.kind, list(cell),
                                 int(frm) if frm is not None else None])
                elif prev == oid:
                    # the cell left this pawn without a `lose`: seized, or passed on at death
                    acts.append([t, "taken" if e.kind == "claim" else "bequeathed",
                                 list(cell), int(e.actor)])
            j += 1
        now = {c for c, o in owner.items() if o == oid}
        if now != held:
            held = now
            changes.append((t, sorted(now)))
        i = j

    # fold the change-points into tenures. A change at t holds until the tick before the next
    # change (or to the end of the run), so the tick count is exact rather than sampled.
    tenures, series, held_ticks, cur = [], [], 0, None
    for idx, (t, cells) in enumerate(changes):
        nxt = changes[idx + 1][0] if idx + 1 < len(changes) else None
        span_end = (nxt - 1) if nxt is not None else t_end
        if not cells:
            if cur is not None:
                cur["cells_seen"] = [list(c) for c in sorted(cur["cells_seen"])]
                tenures.append(cur); cur = None
            continue
        held_ticks += max(0, span_end - t + 1)
        series.append([t, len(cells)])
        if span_end > t:
            series.append([span_end, len(cells)])
        if cur is None:
            cur = {"from_t": t, "to_t": span_end, "peak_cells": len(cells),
                   "cells_seen": set(cells)}
        else:
            cur["to_t"] = max(cur["to_t"], span_end)
            cur["peak_cells"] = max(cur["peak_cells"], len(cells))
            cur["cells_seen"] |= set(cells)
    if cur is not None:
        cur["cells_seen"] = [list(c) for c in sorted(cur["cells_seen"])]
        tenures.append(cur)

    kinds = {}
    for _t, k, _c, _o in acts:
        kinds[k] = kinds.get(k, 0) + 1
    return {
        "source": "log",                      # виток 2: no snapshot touches this projection
        "tenures": tenures,
        "n_tenures": len(tenures),
        "ticks_holding": held_ticks,
        "peak_cells": max((len(c) for _t, c in changes), default=0),
        "final_cells": [list(c) for c in (changes[-1][1] if changes else [])],
        "series": series,                     # step function: [t_in, n], [t_out, n] per span
        "acts": acts,                         # [t, kind, [i,j], other_oid]
        "n_acts": kinds,                      # claim/inherit/lose/taken/bequeathed counts
    }


# --------------------------------------------------------------------------- #
#  5. ReputationHistory — LOG (mark / unmark as a STATE, not a counter)        #
# --------------------------------------------------------------------------- #
def reputation_history(log, oid, t_end=None):
    """Branding over time. Two independent ledgers brand a pawn: `extort` (Фаза 4 — a seized
    owner testifies and every taker is barred from EXTORT henceforth) and `delegate` (the
    REVOKE reputation tooth — a defector who refused to remit is barred from the network).
    Both are membership sets, so the honest projection is SPANS, not a tally: from when to
    when was this pawn branded, and is the brand still on it at the end.

    A brand is sticky by construction — nothing in Polis removes an oid from a mark-ledger
    while it lives (the G2 GC sweeps DEAD oids only, and the emitter diffs over the living
    set precisely so that reclamation cannot masquerade as an un-branding). So `unmark` is
    expected to be rare-to-absent, and an empty projection is a fact about the scene, not a
    hole in the reader."""
    if t_end is None:
        t_end = max((e.t for e in log.events), default=0)
    marks = {}
    for e in log.events:
        if e.kind in ("mark", "unmark") and e.actor == oid:
            marks.setdefault((e.data or {}).get("ledger"), []).append((e.t, e.kind))
    by_ledger, ever, ticks = {}, False, 0
    for led in sorted(marks, key=str):
        spans, open_t = [], None
        for t, kind in marks[led]:
            if kind == "mark" and open_t is None:
                open_t = t
            elif kind == "unmark" and open_t is not None:
                spans.append([open_t, t]); open_t = None
        if open_t is not None:
            spans.append([open_t, None])            # still branded at the end of the run
        held = sum((t_end if b is None else b) - a for a, b in spans)
        ticks += held
        ever = ever or bool(spans)
        by_ledger[led] = {
            "spans": spans,
            "n_marks": sum(1 for _t, k in marks[led] if k == "mark"),
            "n_unmarks": sum(1 for _t, k in marks[led] if k == "unmark"),
            "ticks_branded": held,
            "branded_at_end": bool(spans and spans[-1][1] is None),
            "first_t": spans[0][0] if spans else None,
        }
    return {
        "source": "log",
        "by_ledger": by_ledger,
        "ever_branded": ever,
        "ticks_branded": ticks,
        "branded_at_end": sorted(l for l, v in by_ledger.items() if v["branded_at_end"]),
    }


# --------------------------------------------------------------------------- #
#  6. PowerFlowHistory — LOG (every gram in and out, roles kept APART)         #
# --------------------------------------------------------------------------- #
def extort_share(total, takers, oid):
    """This pawn's share of one extortion — the code's arithmetic replayed, not a guess.

    `Polis._extort` pools the seizure T over the cell and splits it EVENLY among the takers
    (sorted by oid), the last one taking the float remainder so the pool closes exactly:

        share = T / len(takers)
        for tk in takers[:-1]: tk.body += share
        takers[-1].body += (T - given)

    `takers` is emitted in that same order, so the attribution is exact and verifiable —
    gate PF-SHARE checks it against the real body deltas rather than trusting this comment."""
    n = len(takers)
    if n == 0 or oid not in takers:
        return None
    share = total / n
    if oid == takers[-1]:
        return total - share * (n - 1)
    return share


def power_flow(log, oid):
    """Where this pawn's mass came from and where it went — three mechanisms, six roles, kept
    strictly APART. Conflating them is exactly the trap this projection exists to avoid: in
    the showcase scene #58 is an extortion TAKER 174 times and an appropriation PAYER 174
    times, which is the same integer twice for two opposite roles. They are different events
    (disjoint log entries, different `kind`); the counters below prove it by construction and
    `coincidence` reports the real reason the numbers agree.

    ATTRIBUTION HONESTY. A gross event total is not a personal figure. Per role:
      * appropriate payer/receiver — the ledger publishes per-oid amounts. EXACT.
      * extort taker — the pool splits evenly with a documented remainder rule. EXACT
        (see `extort_share`, verified by gate PF-SHARE).
      * extort VICTIM — each victim loses rho*body, i.e. in proportion to its OWN body, and
        the log publishes only the pooled total. NOT resolvable when a cell holds more than
        one victim. Those events are counted in `gross` and in `n_unresolved`, and are NOT
        folded into `attributed`. Two honest numbers beat one invented one.
      * delegate_remit — 1:1, actor to root. EXACT.
    """
    paid, got, took, taken, remit, recv = [], [], [], [], [], []
    # (t, cell) -> the other side of each role, so `coincidence` can be asked SYMMETRICALLY.
    # Both showcase pawns produce an exact integer twice — #58 pays rent 174× and extorts
    # 174×, #42 collects rent 387× and is extorted 387× — and in both cases the answer is the
    # same mechanism seen from opposite ends, not a double count. The projection reports it
    # rather than leaving the reader to wonder.
    took_at, paid_at, got_at, taken_at = {}, {}, {}, {}
    n_actor = 0
    # Rows are rounded for display; TOTALS are accumulated RAW and rounded once at the end.
    # Summing already-rounded rows would drift by ~5e-5 per row — over 10^5 rows that is a
    # visible error, and gate PF-BALANCE (Σ over the whole colony == the canon aggregate)
    # would go red for a reason that has nothing to do with attribution.
    raw = dict.fromkeys(("rent_paid", "rent_received", "extort_gross", "extort_attributed",
                         "extort_solo", "extorted_from_gross", "extorted_from_attributed",
                         "remitted", "received_remit"), 0.0)
    for e in log.events:
        d = e.data or {}
        cell = list(e.where) if e.where else None
        if e.kind == "appropriate":
            rec = [o for o, _v in d.get("receivers", ())]
            pay = [o for o, _v in d.get("payers", ())]
            for o, v in d.get("payers", ()):
                if o == oid:
                    paid.append({"t": e.t, "where": cell, "to": sorted(rec), "mass": _q(v)})
                    paid_at[(e.t, tuple(cell or ()))] = sorted(rec)
                    raw["rent_paid"] += float(v)
            for o, v in d.get("receivers", ()):
                if o == oid:
                    got.append({"t": e.t, "where": cell, "from": sorted(pay), "mass": _q(v)})
                    got_at[(e.t, tuple(cell or ()))] = sorted(pay)
                    raw["rent_received"] += float(v)
        elif e.kind == "extort":
            ts, vs = list(d.get("takers") or []), sorted(d.get("victims") or [])
            total = float(e.dm if e.dm is not None else (d.get("amount") or 0.0))
            if oid in ts:
                n_actor += (e.actor == oid)
                share = extort_share(total, ts, oid)
                took.append({"t": e.t, "where": cell, "victims": vs, "n_takers": len(ts),
                             "gross": _q(total), "share": _q(share)})
                took_at[(e.t, tuple(cell or ()))] = vs
                raw["extort_gross"] += total
                raw["extort_attributed"] += share
                if len(ts) == 1:
                    raw["extort_solo"] += total
            if oid in vs:
                # resolvable only when this pawn is the sole victim: a per-victim seizure is
                # rho*body and the ledger publishes only the pool
                lone = len(vs) == 1
                taken.append({"t": e.t, "where": cell, "takers": sorted(ts),
                              "n_victims": len(vs), "gross": _q(total),
                              "share": _q(total) if lone else None})
                taken_at[(e.t, tuple(cell or ()))] = sorted(ts)
                raw["extorted_from_gross"] += total
                if lone:
                    raw["extorted_from_attributed"] += total
        elif e.kind == "delegate_remit":
            amt = float(d.get("amount") or e.dm or 0.0)
            if e.actor == oid:
                remit.append({"t": e.t, "to_root": d.get("root"), "mass": _q(amt)})
                raw["remitted"] += amt
            if d.get("root") == oid:
                recv.append({"t": e.t, "from": e.actor, "mass": _q(amt)})
                raw["received_remit"] += amt

    both = sorted(set(paid_at) & set(took_at))
    landlord = [k for k in both if took_at[k] == paid_at[k]]
    mirror = sorted(set(got_at) & set(taken_at))            # the rentier's side of the same act
    tenant = [k for k in mirror if set(taken_at[k]) <= set(got_at[k])]
    unres = [r for r in taken if r["share"] is None]
    tot = {k: _q(v, 9) for k, v in raw.items()}     # aggregates: 9 dp, not display rounding
    tot["extorted_from_unresolved"] = len(unres)
    tot["net"] = _q(raw["rent_received"] + raw["extort_attributed"] + raw["received_remit"]
                    - raw["rent_paid"] - raw["extorted_from_attributed"] - raw["remitted"], 9)
    return {
        "source": "log",
        # the roles, explicitly apart — this block IS the 174/174 answer
        "roles": {
            "appropriate": {"payer": len(paid), "receiver": len(got)},
            "extort": {"taker": len(took), "taker_as_actor": n_actor, "victim": len(taken)},
            "delegate_remit": {"remitter": len(remit), "root": len(recv)},
        },
        "coincidence": {
            # tenant's side: paid rent here and robbed the landlord here, same tick
            "paid_and_took_same_tick_cell": len(both),
            "victim_was_the_landlord": len(landlord),
            "of_n_paid": len(paid), "of_n_took": len(took),
            # landlord's side: collected rent here and was robbed here, same tick
            "received_and_was_robbed_same_tick_cell": len(mirror),
            "robbers_were_the_tenants": len(tenant),
            "of_n_received": len(got), "of_n_robbed": len(taken),
        },
        "attribution": {
            "extort_taker": "exact — even split, remainder to the last taker (polis._extort)",
            "extort_victim": ("exact only where this pawn was the sole victim; a per-victim "
                              "seizure is rho*body and the ledger publishes only the pool"),
            "appropriate": "exact — per-oid amounts are in the event",
            "delegate_remit": "exact — one remitter, one root",
        },
        "paid": paid, "received": got,
        "extorted": took, "extorted_by": taken,
        "remitted": remit, "received_remit": recv,
        "totals": tot,
    }


# --------------------------------------------------------------------------- #
#  Assembler                                                                   #
# --------------------------------------------------------------------------- #
def pawn_card(log, snapshots, oid):
    """The six-projection card (виток 1 = four of them), one deterministic object.
    `log` is the canonical EventLog; `snapshots` the viz_export capture."""
    H = _Houses(log.events)
    card = {
        "card_version": CARD_VERSION,
        "oid": oid,
        "chronicle": chronicle(log, oid),
        "house": house_history(log, oid, houses=H),
        "relationships": relationship_history(log, snapshots, oid),
        "property": property_history(log, oid),
        "reputation": reputation_history(log, oid),
        "power": power_flow(log, oid),
        "deferred": [],                       # виток 2 Ф2: all six projections are live
    }
    card["sha"] = card_sha(card)
    return card


def card_sha(card):
    """SHA-256 over the canonical dump (sorted keys, compact) — gate E1-DET."""
    body = {k: v for k, v in card.items() if k != "sha"}
    return hashlib.sha256(_dumps(body).encode()).hexdigest()[:16]


def _dumps(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


# --------------------------------------------------------------------------- #
#  Narrative (Ф2) — prose over the projections, not a table of them            #
# --------------------------------------------------------------------------- #
# The canon `log.narrate` renders one line per event (a chronicle of records). E1 asks for
# the other thing: a connected personal history, the lab->world bridge («потеряла дом ->
# должник дома X -> предала делегировавшего»). So this narrator does not re-emit rows — it
# reads the four projections, classifies the life ARC, and composes conditionally, which is
# what makes it a narrator rather than a template fitted to one pawn.

def _pl(n, one, few, many):
    """Russian plural agreement — the card is prose for the book, not a debug dump."""
    n = abs(int(n))
    if n % 10 == 1 and n % 100 != 11:
        return f"{n} {one}"
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return f"{n} {few}"
    return f"{n} {many}"


def _arc_of(card):
    """Classify the life into an arc from the projections alone.

    Виток 2 refines the top of the ladder. Виток 1 read "extorted often, never extorted from"
    as ВЛАСТЬ — but that stands on event COUNTS, and counts do not know that an extortion is
    a pool shared with co-takers, nor that the same pawn may be paying rent all the while. The
    showcase hero is exactly that case: 174 seizures, 0 seizures against it, and a NEGATIVE
    net across every power flow (−2.07 kg: it clawed back less by force than it paid in rent,
    and its own land yielded nothing). Calling that власть is the same over-attribution the
    gross mass figure made, one level up. So the net decides between force that PAYS and force
    that merely SURVIVES."""
    pr, re_, ch = card["property"], card["relationships"], card["chronicle"]
    P = card["power"]
    t = re_["totals"]
    death_t = (ch["death"] or {}).get("t")
    ten = pr["tenures"]
    lost_alive = bool(ten and death_t is not None and ten[-1]["to_t"] < death_t - 1)
    net = P["totals"]["net"]
    if t["n_extorted"] and not t["n_extorted_by"]:
        if lost_alive:
            return "падение с высоты"
        return "власть" if net > 0 else "сила без прибытка"
    if t["n_extorted_by"] and t["n_extorted_by"] > t["n_extorted"]:
        # The SAME defect one level up. "Extorted from more often than it extorts" is a
        # count, and the contrast pawn of the showcase is preyed on 387 times — because it
        # is the landlord everyone squats on. It still nets +190 kg, outlives the run and
        # leaves 178 heirs. Calling that a victim is the gross-mass error wearing a label.
        return "жертва" if net < 0 else "рантье под данью"
    if lost_alive:
        return "падение"
    if pr["ticks_holding"]:
        return "владение"
    return "тихая жизнь"


def narrate_card(card, title=None):
    """The card as prose. Deterministic (pure function of the card), LLM-ready."""
    ch, ho, re_, pr = card["chronicle"], card["house"], card["relationships"], card["property"]
    rep, P = card["reputation"], card["power"]
    oid, t = card["oid"], re_["totals"]
    org, dth, life = ch["origin"], ch["death"], ch["lifespan"]
    arc = _arc_of(card)
    L = [f"[пешка #{oid} — {arc}]"]

    # I. происхождение
    if org:
        where = f" в клетке {tuple(org['where'])}" if org.get("where") else ""
        g = org.get("gene")
        gtxt = f", ген {g - 273.15:.1f}°C" if isinstance(g, (int, float)) else ""
        if org["kind"] == "seed":
            L.append(f"Основатель: появилась на день {org['t']}{where} из первого посева{gtxt} — "
                     f"у неё нет родителя, её дом начинается с неё самой.")
        else:
            L.append(f"Родилась на день {org['t']}{where}, ребёнок #{org['parent']}{gtxt}; "
                     f"поколение {ho['generation_depth']} в доме {ho['house_root']}.")
    if life:
        L.append(f"Прожила {_pl(life['ticks'],'тик','тика','тиков')} (дни {life['born_t']}–{life['end_t']}), "
                 f"совершив {_pl(ch['n_acts'],'действие','действия','действий')}.")

    # II. земля
    if pr["n_tenures"] == 0:
        L.append("Земли не держала никогда — всю жизнь на чужой или общей.")
    else:
        first = pr["tenures"][0]
        last = pr["tenures"][-1]
        L.append(f"Землю взяла на день {first['from_t']} и держала её {_pl(pr['ticks_holding'],'тик','тика','тиков')} "
                 f"(пик — {_pl(pr['peak_cells'],'клетка','клетки','клеток')}).")
        if pr["final_cells"]:
            L.append("Землю не отдала никому: она была её и в последний день.")
        elif dth and last["to_t"] >= dth["t"] - 1:
            L.append("Держала до самого конца — землю отняла только смерть.")
        else:
            L.append(f"Но на день {last['to_t']} потеряла последнюю клетку и доживала "
                     f"{_pl((dth['t'] - last['to_t']) if dth else 0, 'тик', 'тика', 'тиков')} "
                     f"безземельной.")

    # III. власть и связи
    # Attribution discipline: an extortion is a POOL split among its takers, so "участвовала
    # в N изъятиях" is the only thing the event count licenses. The personal figure is the
    # replayed share (power.totals.extort_attributed), and the gross is named as gross so the
    # two can never again be read as one number.
    if t["n_extorted"]:
        att, gross = P["totals"]["extort_attributed"], P["totals"]["extort_gross"]
        line = f"Участвовала в {_pl(t['n_extorted'],'изъятии','изъятиях','изъятиях')} чужого тела"
        if P["roles"]["extort"]["taker_as_actor"] < t["n_extorted"]:
            line += (f" (заводилой — в {P['roles']['extort']['taker_as_actor']}, "
                     f"в остальных делила добычу с другими)")
        L.append(line + f"; её доля при равном дележе — {att:.4f} кг из {gross:.4f} кг "
                        f"изъятых на этих клетках.")
    if t["n_extorted_by"]:
        lost = P["totals"]["extorted_from_attributed"]
        unres = P["totals"]["extorted_from_unresolved"]
        tail = (f" (ещё {unres} — с другими жертвами на клетке, подушевая доля не выводима)"
                if unres else "")
        L.append(f"И сама была добычей: у неё отняли {_pl(t['n_extorted_by'],'раз','раза','раз')}, "
                 f"{lost:.4f} кг{tail}.")
    elif t["n_extorted"]:
        L.append("При этом её саму не тронул никто — ни одного изъятия против неё.")
    # the rent line: the two roles of appropriation, stated apart
    R, C = P["roles"]["appropriate"], P["coincidence"]
    if R["payer"] or R["receiver"]:
        if R["receiver"] == 0 and R["payer"]:
            L.append(f"С ренты не получила ничего: {_pl(R['payer'],'раз','раза','раз')} платила "
                     f"дань на чужой земле ({P['totals']['rent_paid']:.4f} кг), а со своей — ни грамма.")
        elif R["payer"] == 0:
            L.append(f"Жила рантье: {_pl(R['receiver'],'раз','раза','раз')} получала дань "
                     f"({P['totals']['rent_received']:.4f} кг), не заплатив ни разу.")
        else:
            L.append(f"Рента шла в обе стороны: получила {P['totals']['rent_received']:.4f} кг "
                     f"({R['receiver']}×), отдала {P['totals']['rent_paid']:.4f} кг ({R['payer']}×).")
    if C["victim_was_the_landlord"] and C["of_n_paid"]:
        L.append(f"И это один и тот же жест: в {C['victim_was_the_landlord']} случаях из "
                 f"{C['of_n_paid']} она платила дань владельцу клетки и в тот же день на той же "
                 f"клетке отнимала у него силой.")
    if C["robbers_were_the_tenants"] and C["of_n_received"]:
        L.append(f"С другого конца — тот же жест: в {C['robbers_were_the_tenants']} случаях из "
                 f"{C['of_n_received']} те, кто платил ей дань за клетку, в тот же день на той "
                 f"же клетке обирали её саму. Рента и грабёж здесь — две стороны одного стояния "
                 f"на чужой земле.")
    net = P["totals"]["net"]
    if P["roles"]["extort"]["taker"] or R["payer"] or R["receiver"]:
        verdict = ("вышла в минус" if net < 0 else "вышла в плюс" if net > 0 else "вышла в ноль")
        L.append(f"Итог по всем властным потокам: {net:+.4f} кг — {verdict}.")
    if t["mass_remitted"]:
        L.append(f"Отчисляла наверх: {t['mass_remitted']} кг ушло корню делегирования.")
    # III-bis. клеймо
    if rep["ever_branded"]:
        for led in sorted(rep["by_ledger"]):
            b = rep["by_ledger"][led]
            if not b["spans"]:
                continue
            what = {"extort": "как вымогатель", "delegate": "как отказчик от ремитты"}.get(led, led)
            end = ("и клеймо осталось на ней до конца" if b["branded_at_end"]
                   else f"клеймо сняли на дне {b['spans'][-1][1]}")
            L.append(f"Клеймена {what} на дне {b['first_t']} — {end} "
                     f"({_pl(b['ticks_branded'],'тик','тика','тиков')} под клеймом).")
    elif P["roles"]["extort"]["taker"]:
        L.append("Клейма не носила ни разу: в этой сцене свидетельствовать против вымогателя "
                 "некому — репутационный зуб включён только для делегирования.")
    if re_["n_known"]:
        voice = (f"заговорила {_pl(t['n_spoke'],'раз','раза','раз')}" if t["n_spoke"]
                 else "не заговорила ни разу")
        L.append(f"Знала {_pl(re_['n_known'],'другую пешку','других пешки','других пешек')}, "
                     f"слышала {_pl(t['n_heard'],'чужую заявку','чужие заявки','чужих заявок')} — и {voice}.")

    # IV. кровь
    if ho["n_children"]:
        kids = ", ".join(f"#{k}" for k in ho["children"][:5])
        L.append(f"Оставила потомство: {_pl(ho['n_children'],'наследник','наследника','наследников')} ({kids}); "
                 f"дом {ho['house_root']} насчитывает {_pl(ho['house_size'],'душу','души','душ')} за всю историю.")
    else:
        L.append(f"Потомства не оставила — дом {ho['house_root']} не продлился через неё.")

    # V. конец
    if dth:
        cause = {"senescence": "от старости", "starvation": "от голода"}.get(dth["cause"], dth["cause"])
        L.append(f"Умерла на день {dth['t']} {cause}, в возрасте {dth['age']}, "
                 f"вернув {abs(dth['dm']):.4f} кг в почву.")
    else:
        L.append("К концу прогона была ещё жива.")

    # тезис — дуга одной строкой (мост в мир)
    L.append("")
    L.append(f"Тезис: {_thesis(card, arc)}")
    return "\n".join(L)


def _thesis(card, arc):
    """The arc compressed to one line — the bridge the WO asks for."""
    ho, re_, pr, ch = card["house"], card["relationships"], card["property"], card["chronicle"]
    P = card["power"]
    t, PT = re_["totals"], card["power"]["totals"]
    bits = []
    if ch["origin"] and ch["origin"]["kind"] == "seed":
        bits.append("основатель")
    if pr["ticks_holding"]:
        held = f"держала землю {_pl(pr['ticks_holding'],'тик','тика','тиков')}"
        if P["roles"]["appropriate"]["receiver"] == 0:
            held += ", не собрав с неё ни грамма"
        else:
            held += f" и собрала с неё {PT['rent_received']:.0f} кг дани"
        bits.append(held)
    if t["n_extorted"] and not t["n_extorted_by"]:
        bits.append(f"участвовала в {_pl(t['n_extorted'],'изъятии','изъятиях','изъятиях')} "
                    f"на {PT['extort_attributed']:.2f} кг своей доли")
    elif t["n_extorted_by"]:
        bits.append(f"отдала силой {PT['extorted_from_attributed']:.0f} кг "
                    f"и всё равно осталась в плюсе ({PT['net']:+.0f} кг)"
                    if PT["net"] > 0 else
                    f"отдала силой {PT['extorted_from_attributed']:.4f} кг")
    if PT["net"] < 0 and (t["n_extorted"] or P["roles"]["appropriate"]["payer"]):
        bits.append(f"и всё равно вышла в минус ({PT['net']:+.2f} кг)")
    if not t["n_spoke"] and t["n_heard"]:
        bits.append("не сказав ни слова")
    if ho["n_children"]:
        bits.append(f"оставила {_pl(ho['n_children'],'наследника','наследников','наследников')} и дом, переживший её")
    else:
        bits.append("линия оборвалась на ней")
    return "; ".join(bits) + "."


def build(cfg=None, every=1, oid=None):
    """Convenience: run the E1 scene and return (log, snapshots, card). The scene is
    G2-ON + intent_policy='reflex' — WITHOUT the intent layer the extort seam is skipped and
    the power projections are empty (Ф0 finding, WO §7.4)."""
    from sim_eventlog import EventLog                       # noqa: F401  (import proves path)
    from stage3.viz_export import build_showcase_cfg, run_capture
    if cfg is None:
        cfg = build_showcase_cfg(seed=7, days=400, extort_on=True, delegate_on=True,
                                 revoke_tooth="reputation", extort_enforcers=3,
                                 delegate_enforcers=2, intent_policy="reflex")
    w, snapshots = run_capture(cfg, every)
    card = pawn_card(w.log, snapshots, oid) if oid is not None else None
    return w, snapshots, card
