"""soma — layer-0 metabolic core (DEB), the living base class.

ISOLATION CONTRACT (enforced by MS-iso, not by eye)
---------------------------------------------------
This package is a SEALED sandbox. It imports ONLY the standard library and numpy;
it never imports the tower (`Code/`, `stage3/`, `lab/`, `scripts/`) and the tower
never imports it. A metabolic core under the pawn would rewrite every term of every
blob and erase all 31 vertical anchors, so vitok 1 lives with zero seams. Integration
of Soma into the pawn is a separate future vitok with a separate decision by Stan.

This `__init__` deliberately imports nothing (no heavy package side effects): `import
soma` must stay cheap and free of tower reach. Vitok 1 = layer 0 only.
"""

__all__ = ["soma", "run_soma_l0"]
