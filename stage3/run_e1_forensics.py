"""run_e1_forensics.py — E1 Ф0: per-oid forensics over the canonical EventLog + the
"kind -> card" manifest (gate E1-MAP-COMPLETE).

E1 builds the pawn card as PROJECTIONS over the single existing log — no new collection, no
canon edits. Ф0 answers the prerequisite question: for a focal pawn, WHICH events carry it,
in WHICH role, and is every per-oid-relevant kind assigned to a card (or explicitly ignored)?

FINDINGS THIS HARNESS PINS (run it to reproduce):
  1. oid-bearing `data` fields — not just actor/parent: `heard_by` (communication),
     `maker` (artifact_*), `root` (delegate_remit), and `victims[]`/`takers[]` (extort, LISTS).
  2. `extort` needs BOTH extort_on AND intent_policy != "off": with the showcase default
     (intent off) the seam is skipped and extort NEVER fires (0 events) even with guards.
  3. THE GAP: ownership leaves NO trail in the log. There is no claim / inherit / appropriate /
     tax / revert / reputation / mark event of any kind — yet the run ends with owners holding
     cells and thousands of kg appropriated. PropertyHistory / ReputationHistory (and the tax
     half of PowerFlowHistory) therefore CANNOT be reconstructed from the log; they are
     snapshot-derived. This bounds gate E1-FAITHFUL (see the report).

Run:  py stage3/run_e1_forensics.py
"""
from __future__ import annotations

import os
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "Code"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sim_eventlog import EventLog                                  # noqa: E402
from stage3.polis import Polis                                     # noqa: E402
from stage3.viz_export import build_showcase_cfg, _Houses          # noqa: E402

HDR = "=" * 78
SEED, DAYS = 7, 400

# oid-bearing data fields discovered in Ф0 (scalars and lists), verbatim key names.
OID_SCALAR = ("heard_by", "maker", "root")
OID_LIST = ("victims", "takers")

# ---- the E1 manifest: every per-oid-relevant kind -> its card (or IGNORED) ---------- #
# Names VERBATIM from the code (never renamed), mirroring the viz_export RENDERED/IGNORED
# discipline. A kind may feed more than one card.
CARD_MAP = {
    "seed":                   ("PawnChronicle",),                       # founder origin
    "birth":                  ("PawnChronicle", "HouseHistory"),
    "death":                  ("PawnChronicle",),
    "move":                   ("PawnChronicle",),
    "cognition":              ("PawnChronicle",),
    "forget":                 ("PawnChronicle",),
    "communication":          ("RelationshipHistory",),                 # actor + data.heard_by
    "artifact_write":         ("PawnChronicle",),
    "artifact_copy":          ("PawnChronicle",),
    "artifact_read":          ("PawnChronicle", "RelationshipHistory"), # data.maker = other oid
    "artifact_store":         ("PawnChronicle",),
    "artifact_capital":       ("PawnChronicle",),
    "artifact_store_draw":    ("PawnChronicle", "RelationshipHistory"), # data.maker
    "artifact_capital_boost": ("PawnChronicle",),
    "artifact_ruin":          ("PawnChronicle",),
    "extort":                 ("PowerFlowHistory", "RelationshipHistory"),   # dm; victims/takers
    "delegate_remit":         ("PowerFlowHistory", "RelationshipHistory"),   # dm; data.root
}
IGNORED: set[str] = set()      # nothing per-oid-relevant is dropped in the G2+intent scene

# Cards that have NO event backing at all (Ф0 finding 3) — snapshot-derived, not log-derived.
SNAPSHOT_ONLY = {
    "PropertyHistory": "no claim/inherit/revert event exists; ownership lives in _cell_owner "
                       "and the per-snapshot `owners` field",
    "ReputationHistory": "no mark/brand event exists; _extort_marks/_delegate_marks are state, "
                         "exported per snapshot",
}


def _run(**kw):
    cfg = build_showcase_cfg(seed=SEED, days=DAYS, **kw)
    log = EventLog()
    w = Polis(log, cfg)
    owned_ticks = defaultdict(int)
    for _ in range(cfg.days):
        w.step()
        for o in w.owner_ids():
            owned_ticks[o] += 1
    return w, log, owned_ticks


def roles_of(e, oid):
    """Every role `oid` plays in event `e` — the full per-oid surface (Ф0 finding 1)."""
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
            r.append(f"data.{k}[]")
    return r


def main():
    print(HDR)
    print(f"E1 Ф0 — per-oid forensics over the EventLog (showcase, seed {SEED}, {DAYS}d)")
    print(HDR)

    # --- finding 2: extort needs intent_policy != off --------------------------- #
    print("\n[2] extort требует intent_policy != off (иначе шов пропускается):")
    g2 = dict(extort_on=True, delegate_on=True, revoke_tooth="reputation",
              extort_enforcers=3, delegate_enforcers=2)
    for pol in ("off", "reflex"):
        w, log, _ = _run(intent_policy=pol, **g2)
        k = Counter(e.kind for e in log.events)
        print(f"    intent_policy={pol:<7} extort={k.get('extort', 0):<5} "
              f"delegate_remit={k.get('delegate_remit', 0):<4} "
              f"изъято={getattr(w, '_extorted_total', 0):.1f} кг")

    # the E1 scene: G2 on AND intent on, else PowerFlow/Reputation are empty
    w, log, owned = _run(intent_policy="reflex", **g2)
    kinds = Counter(e.kind for e in log.events)

    # --- gate E1-MAP-COMPLETE --------------------------------------------------- #
    print(f"\n[E1-MAP-COMPLETE] каждый вид отнесён к карточке или IGNORED:")
    unclassified = sorted(k for k in kinds if k not in CARD_MAP and k not in IGNORED)
    for kd in sorted(kinds):
        cards = CARD_MAP.get(kd)
        tag = ", ".join(cards) if cards else ("IGNORED" if kd in IGNORED else "!! UNCLASSIFIED")
        print(f"    {kd:<24} ×{kinds[kd]:<6} -> {tag}")
    ok = not unclassified
    print(f"    E1-MAP-COMPLETE: {'✓ полный словарь' if ok else '✗ не классифицировано: ' + str(unclassified)}")

    # --- finding 3: the ownership gap ------------------------------------------- #
    print("\n[3] ПРОБЕЛ — событий о владении/наследовании/аппроприации в логе НЕТ:")
    for probe in ("claim", "inherit", "appropriate", "tax", "revert", "trade",
                  "exclude", "reputation", "mark", "brand"):
        hit = sorted(k for k in kinds if probe in k)
        print(f"    '{probe}':{'':<12} {hit or 'НЕТ'}")
    print(f"    ...при этом в конце: владельцев={len(w.owner_ids())}, "
          f"клеток={len(w._cell_owner)}, аппроприировано={getattr(w, '_appropriated_total', 0):.1f} кг")
    for card, why in SNAPSHOT_ONLY.items():
        print(f"    ⇒ {card}: НЕТ событийной опоры — {why}")

    # --- focal pawn: full per-oid trace ----------------------------------------- #
    H = _Houses(log.events)
    deaths = {e.actor for e in log.events if e.kind == "death"}
    cand = sorted(((n, o) for o, n in owned.items() if o in deaths), reverse=True)
    print("\n[герой] кандидаты (владел N тиков, затем умер):")
    for n, o in cand[:5]:
        print(f"    oid={o:<4} владел {n:>3}т · дом={H.house(o)}")
    oid = cand[0][1]
    ev = [e for e in log.events if roles_of(e, oid)]
    print(f"\n[трасса] oid={oid}: {len(ev)} событий, все роли:")
    for (kd, r), c in sorted(Counter((e.kind, "/".join(roles_of(e, oid))) for e in ev).items(),
                             key=lambda kv: -kv[1]):
        print(f"    {kd:<24} роль={r:<16} ×{c}")
    print(f"    владел {owned.get(oid, 0)} тиков · дом={H.house(oid)}")
    print(HDR)
    assert ok, "E1-MAP-COMPLETE: unclassified per-oid kinds"
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
