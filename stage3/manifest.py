"""manifest.py — S6.1 (WO_consolidation-sprint): the artifact-attribution manifest.

A `manifest.json` sits NEXT TO a produced artifact (a viz package, a book figure, a
run output) and answers one question: *what produced this, on what, and when.*

Contrast with `resultjson.py` (S2), on purpose:
  * resultjson is a GATE — deterministic on a commit, NO timestamp, a double run is
    byte-identical (`state_hash` + `event_hash` prove substrate & history).
  * this manifest is ATTRIBUTION — it carries `generated_at` and the environment
    (python / numpy), so it is DELIBERATELY not reproducible byte-for-byte. Never
    gate on it; it labels an artifact, it does not certify a world.

It reuses resultjson's `_commit()` and `event_hash()` (single source of truth) so the
history digest a manifest prints equals the S2 result's exactly.

Usage (next to any produced artifact):
    from stage3.manifest import write_manifest
    write_manifest("viz/pg/manifest.json", "publicgood_showcase",
                   seed=7, config=cfg_dict, world=w)
"""
from __future__ import annotations

import json
import os
import platform
import sys
from datetime import datetime, timezone

import numpy as np

# make `stage3` (and the canon `Code/` it pulls in) importable whether this file is run
# as a script or imported by a runner that has already set the path
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "Code"))
sys.path.insert(0, _ROOT)

from stage3.resultjson import _commit, event_hash

SCHEMA = 1


def _json_safe(obj):
    """Best-effort JSON-safe echo of a config payload (tuples->lists, np scalars->py,
    anything exotic->str). Deterministic; never raises."""
    return json.loads(json.dumps(obj, sort_keys=True, default=str)) if obj is not None else None


def build_manifest(runner, *, seed=None, config=None, world=None, event_count=None):
    """Assemble the attribution payload. `world` (a sim world exposing `.log` and
    `.state_fingerprint()`) is preferred — it fills `event_count`, `event_hash` and
    `state_hash` from the actual run. Fields the WO fixes: commit, seed, config,
    event_count, generated_at, python, numpy."""
    payload = {
        "schema": SCHEMA,
        "runner": runner,
        "commit": _commit(),
        "seed": seed,
        "config": _json_safe(config),
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "python": platform.python_version(),
        "numpy": np.__version__,
    }
    if world is not None:
        payload["event_count"] = len(world.log) if event_count is None else event_count
        payload["event_hash"] = event_hash(world)
        try:
            payload["state_hash"] = world.state_fingerprint()
        except Exception:
            pass
    elif event_count is not None:
        payload["event_count"] = event_count
    return payload


def write_manifest(path, runner, *, seed=None, config=None, world=None, event_count=None):
    """Write `manifest.json` at `path`. Pretty-printed, sorted keys, UTF-8. Returns the
    path. Not deterministic (carries `generated_at`) — attribution, not a gate."""
    payload = build_manifest(runner, seed=seed, config=config, world=world,
                             event_count=event_count)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, sort_keys=True, ensure_ascii=False)
        f.write("\n")
    return path


# --------------------------------------------------------------------------- #
#  self-test (MS6-* gates) — run: py stage3\manifest.py                         #
# --------------------------------------------------------------------------- #
def _selftest():
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "Code"))
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from sim_eventlog import EventLog
    from stage3.polis import Polis, PolisConfig
    from stage3.resultjson import event_hash as _eh

    HDR = "=" * 78
    print(HDR)
    print("manifest.py — S6.1: artifact-attribution manifest (MS6-* gates)")
    print(HDR)

    cfg = PolisConfig(appropriation=0.5, owner_policy="claim", arena_side=6,
                      seed=7, days=40, artifacts=True)
    w = Polis(EventLog(), cfg)
    for _ in range(cfg.days):
        w.step()

    m = build_manifest("selftest", seed=7,
                       config={"appropriation": 0.5, "days": 40, "arena_side": 6},
                       world=w)

    required = {"schema", "runner", "commit", "seed", "config",
                "event_count", "generated_at", "python", "numpy"}
    ok_fields = required.issubset(m)
    print(f"MS6-fields  all 7 WO fields (+schema/runner) present -> {'✓' if ok_fields else '✗'}")
    print(f"            missing: {sorted(required - set(m)) or 'none'}")

    ok_evc = m.get("event_count") == len(w.log)
    print(f"MS6-count   event_count == len(world.log) ({m.get('event_count')}) -> {'✓' if ok_evc else '✗'}")

    ok_eh = m.get("event_hash") == _eh(w)
    print(f"MS6-hash    event_hash reuses resultjson (single source) -> {'✓' if ok_eh else '✗'}")

    # attribution, not a gate: two builds of the SAME world differ ONLY in generated_at.
    m2 = build_manifest("selftest", seed=7,
                        config={"appropriation": 0.5, "days": 40, "arena_side": 6},
                        world=w)
    diff_keys = {k for k in set(m) | set(m2) if m.get(k) != m2.get(k)}
    ok_attr = diff_keys <= {"generated_at"}
    print(f"MS6-attr    two builds differ only in generated_at -> {'✓' if ok_attr else '✗'}")
    print(f"            differing keys: {sorted(diff_keys) or 'none'}")

    all_ok = ok_fields and ok_evc and ok_eh and ok_attr
    print(HDR)
    print("MANIFEST S6.1 OK — attribution manifest carries commit/env/when, reuses S2 digests."
          if all_ok else "MANIFEST S6.1 FAILED — see above.")
    print(HDR)
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(_selftest())
