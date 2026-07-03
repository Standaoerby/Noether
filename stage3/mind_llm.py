"""
mind_llm.py — the living mind for the Demerzel (Stage-3 mod B): a pluggable decision policy
that can be deterministic (mod A) OR a live LLM (Claude API), with replay-from-log so the
WORLD stays deterministic even when the MIND is not.

Invariant (the spine): the world is deterministic; non-determinism lives only in the mind,
and the mind writes its decision to the log. A live run calls the LLM and logs each decision
(context -> raw reply -> parsed emissions); a replay reads decisions from the log and never
calls the LLM. Byte-identical on replay — exactly the sim_comm_llm pattern
("a stochastic speaker replays from its logged claims").

Action space is IDENTICAL across policies: every policy returns the same
[(listener_oid, cell, amount), ...] salience emissions that mod A's choose_means returns, so
the LLM only changes HOW targets are chosen, not WHAT channel is used. That keeps the delta
("living mind vs mechanical") clean and on one substrate.

Two realistic compaction laws (Stan, 2026-07-03):
  * deliberation_period — the Demerzel holds a plan and re-thinks every N ticks (or on an
    event: target died), not every tick. A strategist doesn't re-plan each second.
  * attention_K context — the LLM sees only the K most salient facts (the SAME personality
    knob that sets a pawn's focus), so a narrow Demerzel deliberates on a smaller world.

Policies:
  DeterministicPolicy — wraps mod A choose_means (default; always available; Pi5-friendly).
  ClaudePolicy        — Anthropic Messages API over stdlib urllib (no new deps). No key /
                        no network -> INERT (0 emissions), so verify_all passes without a
                        live model (the sim_comm_llm "no client inert" pattern).
  MockPolicy          — a deterministic pseudo-LLM (structured output emulated) to prove the
                        replay-from-log machinery in the sandbox with no network.

No secrets in code: the API key is read from ANTHROPIC_API_KEY at call time.
"""
from __future__ import annotations

import json
import os
import urllib.request
import urllib.error

from .directive import choose_means, GROOM_SUCCESSOR

# default model: fast + cheap for an in-loop agent; structured JSON is reliable.
DEFAULT_MODEL = "claude-haiku-4-5"
API_URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2023-06-01"


# --------------------------------------------------------------------------- #
#  context compaction (attention_K law) — what the mind is allowed to see      #
# --------------------------------------------------------------------------- #
def compact_context(world, demerzel_oid, personality, directive):
    """Build a COMPACT structural context, capped at attention_K salient cells. Personality
    is passed as STRUCTURE (knobs), not a role description (ВСТАВКА-27 lesson)."""
    dem = next((a for a in world.pop if a.oid == demerzel_oid), None)
    if dem is None:
        return None
    K = personality.attention_K
    # salient cells: the K cells with the most food in the Demerzel's neighbourhood
    cells = []
    try:
        import numpy as np
        pl = world.plant
        # rank all cells by plant mass, take top-K (deterministic: tie -> (i,j) order)
        idx = sorted(((float(pl[i, j]), i, j)
                      for i in range(pl.shape[0]) for j in range(pl.shape[1])),
                     key=lambda t: (-t[0], t[1], t[2]))[:K]
        cells = [{"cell": [i, j], "food": round(f, 2)} for (f, i, j) in idx]
    except Exception:
        cells = []
    # occupancy of those cells (how many bodies sit there — resonance signal)
    occ = {}
    for a in world.pop:
        occ[(a.i, a.j)] = occ.get((a.i, a.j), 0) + 1
    for c in cells:
        c["occupants"] = occ.get(tuple(c["cell"]), 0)
    return {
        "t": world.t,
        "you": {"oid": demerzel_oid, "cell": [dem.i, dem.j]},
        "personality": {"attention_K": personality.attention_K,
                        "deception_lean": round(personality.deception_lean, 3),
                        "trust_gate": round(personality.trust_gate, 3)},
        "directive": {"goal": directive.goal, "target": directive.target,
                      "covert": bool(directive.constraints.get("covert", False))},
        "salient_cells": cells,                 # capped at attention_K
        "n_living": len(world.pop),
    }


# --------------------------------------------------------------------------- #
#  policies                                                                    #
# --------------------------------------------------------------------------- #
class DeterministicPolicy:
    """mod A behaviour, wrapped as a policy. Always available, no network."""
    name = "deterministic"

    def choose(self, world, demerzel_oid, personality, directive, memory):
        return choose_means(world, demerzel_oid, personality, directive)


class MockPolicy:
    """Deterministic pseudo-LLM: emulates a structured 'reasoned' choice WITHOUT network, to
    prove replay-from-log. It picks the single most-occupied salient cell as the anchor (a
    stand-in for 'the LLM chose a resonant target'), and pushes it to nearest attention_K
    listeners. Deterministic -> a live run and its replay are byte-identical, and the whole
    thing runs in verify_all with no API."""
    name = "mock-llm"

    def choose(self, world, demerzel_oid, personality, directive, memory):
        if directive is None or directive.goal == GROOM_SUCCESSOR:
            return []
        ctx = compact_context(world, demerzel_oid, personality, directive)
        if not ctx or not ctx["salient_cells"]:
            return choose_means(world, demerzel_oid, personality, directive)
        # "reasoned" target: the salient cell with the most occupants (resonant soil)
        anchor = max(ctx["salient_cells"], key=lambda c: (c["occupants"], c["food"]))
        cell = tuple(anchor["cell"])
        dem = next((a for a in world.pop if a.oid == demerzel_oid), None)
        amt = world.inject_amount * (0.5 + personality.deception_lean)
        others = sorted((a for a in world.pop if a.oid != demerzel_oid),
                        key=lambda a: ((a.i - dem.i) ** 2 + (a.j - dem.j) ** 2, a.oid))
        others = others[:personality.attention_K]
        return [(a.oid, cell, amt) for a in others]


class ClaudePolicy:
    """Live LLM policy over the Anthropic Messages API (stdlib urllib; no new deps).

    Realistic compaction: re-deliberates every `deliberation_period` ticks (or when the
    target dies); between deliberations it re-uses the cached plan (the anchor cell). Sees
    only attention_K salient cells. INERT if no ANTHROPIC_API_KEY or network fails -> returns
    [] so verify_all stays green without a live model.

    The world REPLAYS from the log: Polis logs each chosen emission set, and on replay the
    logged decision is used instead of calling this policy. So determinism holds despite the
    LLM's stochasticity."""
    name = "claude"

    def __init__(self, model=DEFAULT_MODEL, deliberation_period=10, max_tokens=512):
        self.model = model
        self.deliberation_period = int(deliberation_period)
        self.max_tokens = int(max_tokens)
        self._plan_cell = None          # cached anchor between deliberations
        self._last_deliberation = None
        self._api_key = os.environ.get("ANTHROPIC_API_KEY", "")

    def _should_deliberate(self, world, directive):
        if self._last_deliberation is None:
            return True
        if (world.t - self._last_deliberation) >= self.deliberation_period:
            return True
        # event trigger: target died
        if directive.target is not None and \
           not any(a.oid == directive.target for a in world.pop):
            return True
        return False

    def _ask_llm(self, ctx):
        """One Anthropic Messages call. Returns an anchor cell [i,j] or None. Inert without
        a key or on any network error."""
        if not self._api_key:
            return None            # INERT — no key
        system = (
            "You are the deliberation core of an in-world agent ('the voice'). You do NOT "
            "roleplay a personality; you receive STRUCTURAL parameters and pick where to "
            "direct attention to best serve the directive, given the salient cells. "
            "The channel is attention only (you cannot move mass). "
            "Reply with STRICT JSON: {\"anchor\": [i, j], \"why\": \"<=12 words\"}. "
            "Choose the anchor cell most likely to make the directive's belief spread — "
            "typically a cell with food AND occupants (resonant soil)."
        )
        body = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": json.dumps(ctx)}],
        }
        data = json.dumps(body).encode()
        req = urllib.request.Request(
            API_URL, data=data, method="POST",
            headers={"content-type": "application/json",
                     "x-api-key": self._api_key,
                     "anthropic-version": API_VERSION})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                resp = json.loads(r.read().decode())
            # concatenate text blocks
            text = "".join(b.get("text", "") for b in resp.get("content", [])
                           if b.get("type") == "text").strip()
            # strip code fences if any
            text = text.replace("```json", "").replace("```", "").strip()
            parsed = json.loads(text)
            a = parsed.get("anchor")
            if isinstance(a, list) and len(a) == 2:
                return (int(a[0]), int(a[1]))
        except (urllib.error.URLError, ValueError, KeyError, TimeoutError, Exception):
            return None            # INERT on any failure — never break the run
        return None

    def choose(self, world, demerzel_oid, personality, directive, memory):
        if directive is None or directive.goal == GROOM_SUCCESSOR:
            return []
        if self._should_deliberate(world, directive):
            ctx = compact_context(world, demerzel_oid, personality, directive)
            if ctx is None:
                return []
            anchor = self._ask_llm(ctx)
            self._last_deliberation = world.t
            if anchor is not None:
                self._plan_cell = anchor
            elif self._plan_cell is None:
                # inert / no reply and no cached plan -> fall back to deterministic means
                return choose_means(world, demerzel_oid, personality, directive)
        if self._plan_cell is None:
            return choose_means(world, demerzel_oid, personality, directive)
        # execute the cached plan: push the anchor cell to nearest attention_K listeners
        dem = next((a for a in world.pop if a.oid == demerzel_oid), None)
        if dem is None:
            return []
        amt = world.inject_amount * (0.5 + personality.deception_lean)
        others = sorted((a for a in world.pop if a.oid != demerzel_oid),
                        key=lambda a: ((a.i - dem.i) ** 2 + (a.j - dem.j) ** 2, a.oid))
        others = others[:personality.attention_K]
        return [(a.oid, self._plan_cell, amt) for a in others]


def make_policy(kind="deterministic", **kw):
    kind = (kind or "deterministic").lower()
    if kind in ("det", "deterministic", "mod-a", "a"):
        return DeterministicPolicy()
    if kind in ("mock", "mock-llm"):
        return MockPolicy()
    if kind in ("claude", "llm", "live"):
        return ClaudePolicy(**kw)
    raise ValueError(f"unknown policy kind: {kind!r}")
