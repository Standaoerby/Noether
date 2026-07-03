"""
stage3 — the subject layer above the closed tower (modules 1-28).

Stage-3 turns the population substrate into autonomous subjects: a thick Pawn with a
personality vector and a birth->death arc, a Polis (resource-bounded community) as the
unit of play, and Demerzel — the "voice of god": an in-world agent through whom the
observer influences the world WITHOUT breaking its ontology (no hand of god, only voice).

Architecture (see STAGE3_constitution.md):
  GOD (voice) -> directive (logged) -> MIND (LLM, non-det, mod B) -> SUBJECT (det, mod A)
  -> SUBSTRATE (tower 1-28, canon a91480561b6de937, fingerprinted).

mod A (this package, deterministic, NO LLM): prove the whisper propagates and is
attributable, with every OFF-switch (directive=None, t_awaken=inf) reducing the Polis to a
byte-identical tower run. Pure stdlib + numpy; Pi5/Win11/VS Code friendly.
"""
from .personality import Personality, BASELINE, CAUTIOUS, RECKLESS, DEMAGOGUE, seed_personality
from .directive import Directive, PROMOTE, SOW_DISCORD, IMPLANT, GROOM_SUCCESSOR
from .pawn import Pawn, Phase, INFANT, MATURE, ELDER, A_MAT, A_OLD, A_MAX
from .polis import Polis, PolisConfig, run_polis, polis_fingerprint
from .metrics import elite_metrics, directive_attribution, LivingWindow

__all__ = [
    "Personality", "BASELINE", "CAUTIOUS", "RECKLESS", "DEMAGOGUE", "seed_personality",
    "Directive", "PROMOTE", "SOW_DISCORD", "IMPLANT", "GROOM_SUCCESSOR",
    "Pawn", "Phase", "INFANT", "MATURE", "ELDER", "A_MAT", "A_OLD", "A_MAX",
    "Polis", "PolisConfig", "run_polis", "polis_fingerprint",
    "elite_metrics", "directive_attribution", "LivingWindow",
]
