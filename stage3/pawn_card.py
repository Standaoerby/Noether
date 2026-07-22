"""
pawn_card.py — E1: the pawn card as PROJECTIONS over the single canonical EventLog.

"Одна великолепная карточка": the journal is ONE, the cards are VIEWS. Nothing here collects
new data and nothing mutates the world — every function is a pure fold/query over an
`EventLog` (+ `viz_export` snapshots where the log has no trail). Canon `Code/sim_*.py` and
`stage3/polis.py` are untouched; the reader lives outside the world classes (the glass
pattern), so a run under this reader keeps its fingerprint (gate E1-VOFF).

SOURCE SPLIT (Ф0 finding, WO §7 revision) — the cards divide by SOURCE, not by convenience:
  * LOG-derived  — Chronicle, HouseHistory, RelationshipHistory. Cheap; the log is not lossy
    for births/deaths, so these carry the E1-FAITHFUL guarantee (line reconstructed from the
    log == `reconstruct_live` at every checkpoint).
  * SNAPSHOT-derived — PropertyHistory. The log has NO ownership trail at all: there is no
    claim / inherit / appropriate / revert event anywhere, yet cells change hands and mass is
    appropriated. Ownership lives only in `_cell_owner`, surfaced per snapshot as `owners`.
    Its correctness rests on the read-only guarantee (V-OFF), not on a log cross-check —
    comparing a snapshot against itself would be vacuous, so that subgate was dropped.

Виток 1 (this module): Chronicle · House · Relationship · Property.
Виток 2 (deferred, WO §7.3): ReputationHistory (marks-as-state) and full PowerFlowHistory
(the dominant appropriation flow emits no event — blocked on the "faithful ledger" WO).

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
            "mass_extorted": _q(sum(x["amount"] or 0 for x in took), 4),
            "mass_lost_to_extort": _q(sum(x["amount"] or 0 for x in taken_from), 4),
            "mass_remitted": _q(sum(x["amount"] or 0 for x in remitted), 4),
        },
    }


# --------------------------------------------------------------------------- #
#  4. PropertyHistory — SNAPSHOT-derived (the log has no ownership trail)      #
# --------------------------------------------------------------------------- #
def property_history(snapshots, oid):
    """Ownership over time, folded into tenures. Built from the per-snapshot `owners` field
    because NO claim/inherit/revert event exists anywhere in the journal (Ф0)."""
    timeline, held_ticks = [], 0
    for s in snapshots:
        cells = sorted((i, j) for (i, j, o) in s.get("owners", ()) if o == oid)
        if cells:
            held_ticks += 1
        timeline.append((s["t"], cells))
    # fold into tenures: maximal runs of consecutive snapshots with a non-empty holding
    tenures, cur = [], None
    for t, cells in timeline:
        if cells and cur is None:
            cur = {"from_t": t, "to_t": t, "peak_cells": len(cells), "cells_seen": set(cells)}
        elif cells:
            cur["to_t"] = t
            cur["peak_cells"] = max(cur["peak_cells"], len(cells))
            cur["cells_seen"] |= set(cells)
        elif cur is not None:
            cur["cells_seen"] = [list(c) for c in sorted(cur["cells_seen"])]
            tenures.append(cur); cur = None
    if cur is not None:
        cur["cells_seen"] = [list(c) for c in sorted(cur["cells_seen"])]
        tenures.append(cur)
    peak = max((len(c) for _t, c in timeline), default=0)
    return {
        "tenures": tenures,
        "n_tenures": len(tenures),
        "ticks_holding": held_ticks,
        "peak_cells": peak,
        "final_cells": [list(c) for c in (timeline[-1][1] if timeline else [])],
        "series": [[t, len(c)] for t, c in timeline if c],   # sparse: only ticks with land
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
        "property": property_history(snapshots, oid),
        "deferred": ["ReputationHistory", "PowerFlowHistory"],   # виток 2 (WO §7.3)
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
    """Classify the life into an arc from the projections alone."""
    pr, re_, ch = card["property"], card["relationships"], card["chronicle"]
    t = re_["totals"]
    death_t = (ch["death"] or {}).get("t")
    ten = pr["tenures"]
    lost_alive = bool(ten and death_t is not None and ten[-1]["to_t"] < death_t - 1)
    if t["n_extorted"] and not t["n_extorted_by"]:
        return "власть" if not lost_alive else "падение с высоты"
    if t["n_extorted_by"] and t["n_extorted_by"] > t["n_extorted"]:
        return "жертва"
    if lost_alive:
        return "падение"
    if pr["ticks_holding"]:
        return "владение"
    return "тихая жизнь"


def narrate_card(card, title=None):
    """The card as prose. Deterministic (pure function of the card), LLM-ready."""
    ch, ho, re_, pr = card["chronicle"], card["house"], card["relationships"], card["property"]
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
    if t["n_extorted"]:
        L.append(f"Брала силой: {_pl(t['n_extorted'],'изъятие','изъятия','изъятий')} на {t['mass_extorted']} кг чужого тела.")
    if t["n_extorted_by"]:
        L.append(f"И сама была добычей: у неё отняли {_pl(t['n_extorted_by'],'раз','раза','раз')} "
                 f"({t['mass_lost_to_extort']} кг).")
    elif t["n_extorted"]:
        L.append("При этом её саму не тронул никто — ни одного изъятия против неё.")
    if t["mass_remitted"]:
        L.append(f"Отчисляла наверх: {t['mass_remitted']} кг ушло корню делегирования.")
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
    t = re_["totals"]
    bits = []
    if ch["origin"] and ch["origin"]["kind"] == "seed":
        bits.append("основатель")
    if pr["ticks_holding"]:
        bits.append(f"держала землю {_pl(pr['ticks_holding'],'тик','тика','тиков')}")
    if t["n_extorted"] and not t["n_extorted_by"]:
        bits.append(f"брала у других {_pl(t['n_extorted'],'раз','раза','раз')} и не отдала ничего")
    elif t["n_extorted_by"]:
        bits.append(f"отдала силой {t['mass_lost_to_extort']} кг")
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
