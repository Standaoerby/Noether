"""
vision.py — mod F (виток 3): «зрение на материю» (store_vision).

THE HOLE (found by the Glass Polis): the canonical agent is NAVIGATIONAL — decide() walks
toward believed food held in cell memory (Code/sim_comm.py: mem[oid] = {(i,j): (food, day)}),
and speakers broadcast claims about good cells. But vitok-2 artifacts are OUTSIDE that
information loop: a cell's memory sees `plant` and is BLIND to a granary standing on it; a
claim cannot say "there is a store at (9,8)". So finding-6 stayed conditional ("a store
nobody knows about does not save"). Vitok 3 closes the blindness→sight axis with the single
most natural injection possible.

ONE injection, ZERO new forces. At the end of Polis.step (after the artifact passes, before
the next canonical decision), for each LIVING pawn standing on a cell (i,j):

    drawable = Σ mass over the STORES on (i,j) that pass THIS pawn's access filter
    if store_vision and drawable > 0:
        mem[oid][(i,j)] = (true_plant(i,j) + drawable, t)   # EXACTLY the visit format

Why this is "maximal naturalness", not a new power:
  * OWN CELL ONLY. Symmetric with plant: the canon learns the truth of a cell by BEING on
    it (_observe). No vision radius is introduced.
  * STORE ONLY. A granary is the same "food is here" modality as a bush. CAPITAL does not
    convert to food honestly (its food-equivalent rate·mass ≈ 0.005–0.05 vs plant food
    8–18 — a ghost signal), and a VESSEL is not food at all; both are out of this vitok.
  * ACCESS FILTER IN THE EYES. A locked foreign granary is invisible AS VALUE (drawable=0
    for a pawn without access) — information about wealth is already stratified by access,
    mirroring who may actually draw (artifact._store_draw uses the same _access_ok).
  * BELIEF, NOT MASS. The injection touches neither plant, soil, body nor art.mass — only
    the belief map `mem`. The four-term invariant is intact by construction.
  * WORD-OF-MOUTH FOR FREE. A speaker whose memory now holds a store-cell as valuable will
    point listeners at it through the ORDINARY claim channel; liars, trust and reputation
    all engage without a single new line in the communication modules. No special
    "gossip-about-stores" channel is added.

The write mirrors CommWorld._observe byte-for-byte in FORMAT: the value tuple is
(float food, world.t) and the cell is dropped from `from_hearsay` (a directly-sensed cell,
not hearsay) — read from the canon and repeated, not invented.
"""
from __future__ import annotations


def apply_store_vision(world) -> int:
    """Inject drawable-store value into each living pawn's OWN-cell memory. Pure belief
    write (world.mem / world.from_hearsay); returns the number of cells written (for the
    MFv3-belief gate / HV instrumentation). No-op when the artifact field is off."""
    af = getattr(world, "_artifacts", None)
    if af is None or not af.on or not af.store_on:
        return 0
    mem = getattr(world, "mem", None)
    if mem is None:                       # cell-memory layer absent from the stack -> STOP
        raise RuntimeError("store_vision: world has no cell memory (mem) — layer disabled")

    # live stores grouped by cell (aid order preserved for determinism, though the sum is
    # order-independent). Only stores with mass are visible as value.
    stores_by_cell: dict[tuple, list] = {}
    for art in af.artifacts:
        if art.kind == "store" and art.mass > 0.0:
            stores_by_cell.setdefault((art.i, art.j), []).append(art)
    if not stores_by_cell:
        return 0

    written = 0
    hearsay = getattr(world, "from_hearsay", None)
    for a in sorted(world.pop, key=lambda x: x.oid):
        cell = (a.i, a.j)
        here = stores_by_cell.get(cell)
        if not here:
            continue
        # access filter IN THE EYES: only stores this pawn could actually draw are seen as
        # value (a locked foreign granary is invisible). Same filter as _store_draw.
        drawable = sum(art.mass for art in here
                       if af._access_ok(world, art, a, af.store_access))
        if drawable <= 0.0:
            continue
        reg = mem.get(a.oid)
        if reg is None:                   # a pawn with no memory record (should not happen)
            continue
        true_plant = float(world.plant[a.i, a.j])
        reg[cell] = (true_plant + drawable, world.t)     # _observe's exact tuple format
        if hearsay is not None and a.oid in hearsay:
            hearsay[a.oid].discard(cell)                 # sensed, not hearsay (mirror _observe)
        written += 1
    return written
