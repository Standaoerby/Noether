"""trace.py — the soma anchor with DOMAIN SEPARATION (WO §11.5, gate MS-ns).

Two levels, per the review:
  1. Namespace: the anchor STRING is prefixed `soma:` — human-readable, but a prefix can be stripped.
  2. Domain separation: a constant DOMAIN tag is baked into the hash INPUT, so a soma anchor and a
     tower anchor over byte-identical content produce DIFFERENT digests BY CONSTRUCTION. Even with
     the `soma:` prefix removed, a soma digest can never collide with a tower digest — the
     incomparability is enforced, not documented. (This closes the trap: someone a vitok later
     comparing a soma anchor to a tower anchor gets a guaranteed mismatch, not accidental nonsense.)
"""

from __future__ import annotations

import hashlib

DOMAIN = b"soma:v1"   # baked into every hash input; the domain-separation tag (MS-ns)


def _serialize(org) -> bytes:
    """Deterministic bytes of the full organism state. numpy arrays via tobytes() for exactness."""
    s = org.soma
    scalars = repr((s.U_H, s.U_R, s.q, s.h, s.age,
                    org.V_max, org.maturity_leak, org.cum_eggs, org.alive, org.cause)).encode()
    return b"|".join((s.U_E.tobytes(), s.L.tobytes(), scalars))


def raw_digest(org) -> str:
    """Digest WITHOUT the domain tag — for MS-ns to prove the tag actually separates."""
    return hashlib.sha256(_serialize(org)).hexdigest()


def state_digest(org) -> str:
    """The soma anchor: `soma:` namespace prefix + domain-separated sha256."""
    return "soma:" + hashlib.sha256(DOMAIN + b"|" + _serialize(org)).hexdigest()
