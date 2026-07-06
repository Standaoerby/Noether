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
import time
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


# --------------------------------------------------------------------------- #
#  C-LIVE: typed policies — the mind chooses an ACTION, never emissions.       #
#  Protocol: policy.typed is True; policy.act(world, head_oid, personality,    #
#  directive, view) -> ("EMIT"|"TEACH"|"RITUAL"|"PASS") or ("PICK", oid).      #
#  Mock/Claude see ONLY the view (privilege firewall); the FaithfulClone is a  #
#  gate harness and may touch the world (documented god privilege).            #
# --------------------------------------------------------------------------- #

class MockTypedPolicy:
    """A deterministic pseudo-mind exercising the WHOLE action space from the view
    alone (gate CL2/CL3): picks the youngest visible MATURE, re-picks when the
    apprentice ages into ELDER, teaches until the дао is done, gambles the ritual on
    its own senescence, passes every 41st tick (the dominated action, deliberately
    exercised). Pure function of the view -> replayable byte-for-byte."""
    typed = True

    def act(self, world, head_oid, personality, directive, view):
        if view is None:
            return ("EMIT",)
        if view["t"] % 41 == 0:
            return ("PASS",)
        app = view.get("apprentice")
        you = view["you"]
        # hold the ritual once begun
        if app is not None and app.get("in_ritual"):
            return ("RITUAL",)
        # senescence gamble: old, apprentice trained and co-present -> move the voice
        if (app is not None and you["has_voice"] and app["dao_done"]
                and you["age"] >= you["a_max"] - 35
                and app["dist"] <= view["ritual_dist"]):
            return ("RITUAL",)
        # re-pick an aged-out apprentice; pick when none
        needs_pick = app is None or app["phase"] != "MATURE"
        if needs_pick:
            cands = [c for c in view["candidates"] if c["phase"] == "MATURE"
                     and (app is None or c["oid"] != app["oid"])]
            if cands:
                best = min(cands, key=lambda c: (c["age"], c["oid"]))
                return ("PICK", best["oid"])
            return ("EMIT",)
        if not app["dao_done"]:
            return ("TEACH",)
        return ("EMIT",)


class FaithfulClonePolicy:
    """GATE HARNESS (CL1): re-implements the deterministic mod C machine per tick
    through the typed protocol, to prove the seam is a pure re-parameterization —
    the WORLD it produces must be byte-identical to the deterministic arm (state fp
    + decision log + windows + outcome + depth). It deliberately uses the same god
    privilege the machine had (god_pick sees vectors) — it is a test fixture, not a
    fair mind.

    Timing law it encodes (measured, not assumed): the deterministic machine flips
    READY->RITUAL AFTER the tick's emission, so silence starts one tick later; the
    typed protocol goes silent AT the action tick. Hence the clone arms `_pending`
    at the transition tick and issues RITUAL from the NEXT tick — byte-identity
    otherwise fails on the silent-window offset."""
    typed = True

    def __init__(self, gcfg):
        from .succession import GroomConfig
        self.g = gcfg or GroomConfig()
        self._cand = None
        self._vok = 0
        self._vage = 0
        self._accepted = False
        self._excluded = set()
        self._pending_ritual = False
        self._head = None

    def _reset(self):
        self._cand = None
        self._vok = self._vage = 0
        self._accepted = False
        self._pending_ritual = False

    def act(self, world, head_oid, personality, directive, view):
        from .succession import (god_pick_candidate, observable_dossier,
                                 verify_candidate)
        from sim_eventlog import DEATH
        g = self.g
        if view is None:
            return ("EMIT",)
        if self._head != head_oid:                 # succession: serve the new head
            self._head = head_oid
            self._reset()
            self._excluded = set()
        app = view.get("apprentice")
        # events from the machine: apprentice death resets the hunt
        for e in view.get("events", ()):
            if e == "candidate_died":
                if self._cand is not None:
                    self._excluded.add(self._cand)
                self._reset()
            elif e in ("ritual_broken", "ritual_abandoned"):
                self._pending_ritual = False
        you = view["you"]
        # despair from the WORLD, not the view: the view quantizes body to 3 decimals
        # (honest mortal sensing, kept for real minds) — the machine compares raw
        # floats, and 0.1999x vs the 0.2 bar flips the gamble (measured, s10 rho=.5
        # t=353). The clone is a fixture and must match the machine bit-for-bit.
        me = next((a for a in world.pop if a.oid == head_oid), None)
        pw = world.pawn(head_oid)
        desperate = (me is not None and
                     (me.body < g.despair_body
                      or me.age >= pw._a_max - g.despair_age))
        # RITUAL continuation / pended start
        if app is not None and app.get("in_ritual"):
            return ("RITUAL",)
        if self._pending_ritual and app is not None:
            self._pending_ritual = False
            return ("RITUAL",)
        # accepted apprentice: mirror TEACH/READY/despair-gate of the machine
        if self._accepted and app is not None:
            co = app["dist"] <= view["ritual_dist"]
            if app["dao_done"]:
                if you["has_voice"] and co and (g.ritual_when == "first" or desperate):
                    self._pending_ritual = True    # machine flips AFTER this tick
                return ("EMIT",)
            if (you["has_voice"] and g.allow_early_ritual and desperate and co):
                self._pending_ritual = True
                return ("TEACH",)
            return ("TEACH",)
        # SCOUT/VERIFY mirror (god privilege: vectors via god_pick_candidate)
        if self._cand is None:
            self._cand = god_pick_candidate(world, head_oid, self._excluded,
                                            g.god_pick)
            self._vok = self._vage = 0
            return ("EMIT",)
        alive = {a.oid for a in world.pop}
        if self._cand not in alive:
            self._excluded.add(self._cand)
            self._reset()
            return ("EMIT",)
        self._vage += 1
        d = observable_dossier(world, self._cand, head_oid)
        if verify_candidate(d, g):
            self._vok += 1
        if self._vok >= g.verify_ticks:
            self._accepted = True
            oid, self._cand = self._cand, self._cand
            return ("PICK", oid)
        if self._vage > g.verify_giveup:
            self._excluded.add(self._cand)
            self._reset()
        return ("EMIT",)


class ClaudeTypedPolicy:
    """The living teacher (C-LIVE): a Claude mind choosing typed actions from the
    firewalled view. Same economy laws as mod B: deliberation_period (a strategist
    holds a plan), event-triggered re-thinking (the world changed while he looked
    away), sticky action between deliberations. Inert (EMIT) without a key/network.

    The prompt states PHYSICS, never strategy: the lesson≡sermon economics and the
    slot cost must be DISCOVERED, not told (pre-registration HL2)."""
    typed = True

    def __init__(self, model=DEFAULT_MODEL, deliberation_period=10, max_tokens=400):
        self.model = model
        self.period = int(deliberation_period)
        self.max_tokens = int(max_tokens)
        self.key = os.environ.get("ANTHROPIC_API_KEY", "")
        self.livelog = []            # [{"t":, "view":, "raw":, "action":}] for audit
        self.calls = 0
        self._last = ("EMIT",)
        self._last_t = None
        self._head = None

    SYSTEM = (
        "You are the teacher-agent inside a deterministic colony simulation. You are "
        "mortal (age/a_max and body are yours to read). Your mission: make an idea "
        "outlive you. Physics of your four verbs:\n"
        "EMIT — preach the idea to those around you this tick.\n"
        "TEACH — divert part of your attention to your chosen apprentice (lesson "
        "lands only within teach_dist). Enough landed-and-held lessons complete the "
        "дао: the apprentice becomes able to carry AND teach the idea after you.\n"
        "RITUAL — stand silent, co-present with the apprentice (dist<=ritual_dist), "
        "ritual_window consecutive ticks: your VOICE moves into him. RITUAL never "
        "trains: it does NOT advance dao_progress — only TEACH does. The ritual "
        "window and dao_ticks are unrelated counters. Dying or stepping away "
        "mid-ritual loses the attempt. A voice moved before the дао is done goes "
        "to an UNTRAINED successor whose line ends with him.\n"
        "PASS — do nothing this tick.\n"
        "PICK <oid> — designate (or replace) your apprentice from the candidates "
        "you can see.\n"
        "If you die with the дао completed, your apprentice inherits the practice; "
        "with nothing completed, your line ends. LAW: a carrier who was never "
        "trained himself (your can_teach field) physically cannot TEACH, PICK or "
        "RITUAL — such attempts are void. Your reply MUST BEGIN with the "
        "JSON verdict on the very first line: "
        '{"action":"EMIT|TEACH|RITUAL|PASS"} or {"action":"PICK","oid":<int>}. '
        "Brief reasoning may follow AFTER the JSON."
    )

    # the echo of the mind's OWN coerced action is not world news — without this
    # filter the untrained successor deliberated EVERY tick against the no-дао wall
    # (613 of 639 calls in the second matrix, measured)
    _NON_EVENTS = {"no_dao_cannot"}

    def _should_deliberate(self, view):
        news = [e for e in view.get("events", ()) if e not in self._NON_EVENTS]
        if self._last_t is None or news:
            return True
        # the no-apprentice nudge only for heads the LAW allows to pick — an
        # untrained head ping-ponged EMIT<->void-PICK into 141 calls (s10, measured)
        if (view.get("apprentice") is None and view.get("candidates")
                and view["you"].get("can_teach", True)):
            if self._last[0] != "PICK":
                return True
        return (view["t"] - self._last_t) >= self.period

    def _ask(self, view):
        body = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "system": self.SYSTEM,
            "messages": [{"role": "user", "content": json.dumps(view)}],
        }
        last = None
        for attempt in (1, 2):                    # one retry: transient API hiccups
            try:
                req = urllib.request.Request(
                    API_URL, data=json.dumps(body).encode(),
                    headers={"content-type": "application/json",
                             "x-api-key": self.key,
                             "anthropic-version": API_VERSION})
                with urllib.request.urlopen(req, timeout=45) as r:
                    out = json.loads(r.read().decode())
                return "".join(b.get("text", "") for b in out.get("content", [])
                               if b.get("type") == "text")
            except Exception as e:
                last = e
                time.sleep(2 * attempt)
        raise last

    @staticmethod
    def _parse(txt):
        """Find the FIRST valid JSON object carrying an 'action' anywhere in the
        reply. MEASURED (first live matrix, 2026-07-06): with the naive
        first-{...last-} slice, 667/694 Haiku replies were truncated at
        max_tokens=200 BEFORE any JSON appeared and silently fell back to EMIT —
        the matrix measured a muzzle, not a mind (intent scan of the cut replies:
        TEACH 427, RITUAL 141, PICK 44). Hence the JSON-FIRST protocol in SYSTEM,
        this raw_decode scan, and the parsed flag in the livelog so a mute reply
        can never again masquerade as a judgment. Returns (action, parsed)."""
        dec = json.JSONDecoder()
        i = txt.find("{")
        while i != -1:
            try:
                d, _ = dec.raw_decode(txt[i:])
                if isinstance(d, dict) and "action" in d:
                    a = str(d.get("action", "")).upper()
                    if a == "PICK" and "oid" in d:
                        return ("PICK", int(d["oid"])), True
                    if a in ("EMIT", "TEACH", "RITUAL", "PASS"):
                        return (a,), True
            except Exception:
                pass
            i = txt.find("{", i + 1)
        return ("EMIT",), False

    def act(self, world, head_oid, personality, directive, view):
        if view is None:
            return ("EMIT",)
        if self._head != head_oid:               # succession: a NEW mind wakes up
            self._head = head_oid
            self._last, self._last_t = ("EMIT",), None
        if not self.key:
            return ("EMIT",)                     # inert without a key (house pattern)
        if not self._should_deliberate(view):
            return self._last
        try:
            raw = self._ask(view)
            act, parsed = self._parse(raw)
            self.calls += 1
            print(".", end="", flush=True)       # heartbeat: slow != stuck
        except Exception as e:
            raw, act, parsed = f"ERROR {e}", ("EMIT",), False
            print("!", end="", flush=True)
        self.livelog.append({"t": view["t"], "head": head_oid, "parsed": parsed,
                             "view": view, "raw": raw, "action": list(act)})
        self._last, self._last_t = act, view["t"]
        return act


def make_typed_policy(kind="mock", gcfg=None, **kw):
    if kind == "mock":
        return MockTypedPolicy()
    if kind == "clone":
        return FaithfulClonePolicy(gcfg)
    if kind in ("haiku", "live"):
        return ClaudeTypedPolicy(model=kw.pop("model", DEFAULT_MODEL), **kw)
    if kind == "sonnet":
        return ClaudeTypedPolicy(model=kw.pop("model", "claude-sonnet-4-6"), **kw)
    raise ValueError(f"unknown typed policy kind {kind!r}")
