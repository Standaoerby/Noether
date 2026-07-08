"""
vision.py — mod F (виток 3): «зрение на материю» (store_vision).

THE HOLE (found by the Glass Polis): the canonical agent is NAVIGATIONAL — decide() walks
toward believed food held in cell memory (Code/sim_comm.py: mem[oid] = {(i,j): (food, day)}),
and speakers broadcast claims about good cells. But vitok-2 artifacts are OUTSIDE that
information loop: a cell's memory sees `plant` and is BLIND to a granary standing on it; a
claim cannot say "there is a store at (9,8)". So finding-6 stayed conditional ("a store
nobody knows about does not save"). Vitok 3 closes the blindness→sight axis with the single
most natural injection possible.

V1 (kept in history as a reference) wrote the vision at the END of Polis.step and was
behaviourally INERT: the canonical think-cycle is observe→decide, and _observe overwrites
mem[own_cell] with the bare true-plant value the tick BEFORE decide reads it — so the
post-hoc write never survived to a decision. V2 puts the vision where it belongs: INSIDE
perception. Polis overrides _observe to call the canonical super()._observe first (true
plant, freshness stamp, hearsay drop) and THEN fold in the standing store, so the order is
correct by construction (our observe → decide → move).

ONE organ, ZERO new forces. `observe_stores(world, a)` runs for the pawn being sensed:

    drawable = Σ mass over the LIVE STORES on a's cell that pass a's access filter
    if store_vision and drawable > 0:
        mem[a.oid][(a.i,a.j)] = (true_plant(a.i,a.j) + drawable, world.t)   # visit format

Why this is "maximal naturalness", not a new power:
  * OWN CELL ONLY. Symmetric with plant: the canon learns a cell's truth by BEING on it.
    No vision radius is introduced.
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
    all engage without a single new line in the communication modules.

The value tuple format is exactly CommWorld._observe's, (float food, world.t). The hearsay
discard for this cell was already done by the canonical super()._observe that ran first, so
we do not touch from_hearsay here (its semantics are left intact).
"""
from __future__ import annotations


def observe_stores(world, a) -> bool:
    """Fold the drawable standing store on pawn `a`'s own cell into its cell-memory.
    Called from Polis._observe AFTER the canonical super()._observe(a). Pure belief write;
    returns True iff it wrote (for gate/instrumentation). No-op when the store layer is off
    or nothing accessible stands here."""
    af = getattr(world, "_artifacts", None)
    if af is None or not af.on or not af.store_on:
        return False
    mem = getattr(world, "mem", None)
    if mem is None:                       # cell-memory layer absent from the stack -> STOP
        raise RuntimeError("store_vision: world has no cell memory (mem) — layer disabled")
    reg = mem.get(a.oid)
    if reg is None:
        return False

    ai, aj = a.i, a.j
    # access filter IN THE EYES: only stores this pawn could actually draw are seen as
    # value (a locked foreign granary is invisible). Same _access_ok as _store_draw.
    drawable = 0.0
    for art in af.artifacts:
        if (art.kind == "store" and art.mass > 0.0 and art.i == ai and art.j == aj
                and af._access_ok(world, art, a, af.store_access)):
            drawable += art.mass
    if drawable <= 0.0:
        return False

    true_plant = float(world.plant[ai, aj])
    reg[(ai, aj)] = (true_plant + drawable, world.t)     # _observe's exact tuple format
    return True
