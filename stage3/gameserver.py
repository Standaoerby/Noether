"""gameserver.py — thin protocol-v1 server wrapping the Noether core (Этап 0).

This is a PRESENTATION/INPUT bridge, not a simulation. It drives the canon
Polis one deterministic tick at a time, serialises living-agent state into
snapshots, streams new EventLog events, and applies buffered player commands
ONLY on tick boundaries — so (seed + commands.jsonl) replays bit-for-bit
(gate GAME-DET). The tower never learns the game exists: nothing here touches
`Code/sim_*.py`, and without this server running the башня is byte-identical
(gate GAME-OFF).

Contract: docs/game-architecture.md (protocol v1). Any message-shape change
must edit that file first and bump PROTOCOL_VERSION per its rules.

The server accepts clients in a loop: when one disconnects it returns to
listening on the SAME session (world/tick/commands.jsonl persist), so a client
can reconnect and resume. Ctrl+C exits cleanly. --verbose logs full traffic.

Run:  py stage3/gameserver.py                    (from repo root)
      py stage3/gameserver.py --seed 7 --port 42017 --verbose
"""
from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "Code"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse
import json
import select
import socket
import time
from dataclasses import asdict
from datetime import datetime, timezone

from sim_eventlog import EventLog
from stage3.polis import Polis, PolisConfig
from stage3.resultjson import _commit

# --- protocol constants (mirror docs/game-architecture.md) ----------------- #
PROTOCOL_VERSION = 1                 # single int; a mismatch is a MAJOR break
DEFAULT_PORT = 42017
DEFAULT_HOST = "127.0.0.1"
DEFAULT_SEED = 7
LEGAL_TPS = (0, 2, 10, 40)           # 0 = pause; RimWorld-style tempo control


# --- command registry ------------------------------------------------------ #
# Stage 0 has NO world-mutating commands: `pace` and `ping` are control-plane
# only (see docs/game-architecture.md, WO §1.5). This registry is where Stage 2
# whisper/force intents will hook in — each entry mutates the world at a tick
# boundary and is what replay re-applies from commands.jsonl. Empty by design.
WORLD_COMMANDS: dict = {}


def _json_default(o):
    """Fallback for numpy scalars sneaking into Event.data — protocol
    robustness over byte-identity (events are not part of the state hash)."""
    try:
        return o.item()          # numpy scalar -> python scalar
    except AttributeError:
        return str(o)


def _dumps(obj) -> bytes:
    return (json.dumps(obj, separators=(",", ":"), default=_json_default)
            + "\n").encode("utf-8")


def _event_to_dict(e) -> dict:
    """Same shape as the canon S7 JSONL export (sim_eventlog.to_jsonl)."""
    d = asdict(e)
    if d["where"] is not None:
        d["where"] = list(d["where"])
    return d


class GameSession:
    """Socket-free driver of one deterministic world. The socket server and the
    replay/gate harness both go through this, so what the player sees and what
    replay reproduces are the exact same code path."""

    def __init__(self, seed: int = DEFAULT_SEED, *, session_id: str | None = None,
                 runs_dir: str | None = None, cfg: PolisConfig | None = None):
        self.seed = seed
        # Default session id is derived (not wall-clock) so replay lands in a
        # predictable dir; callers may pass an explicit id for concurrent runs.
        self.session_id = session_id or f"s{seed}"
        self.core_commit = _commit()
        self.cfg = cfg or PolisConfig(seed=seed)
        # Guard the canon: the config's seed is the single source of truth.
        object.__setattr__(self.cfg, "seed", seed)

        self.log = EventLog()
        self.world = Polis(self.log, self.cfg)
        self._event_cursor = 0        # length-cursor into self.log.events

        # REAL arena geometry (Stage-0 bug: the wrapper hardcoded sim_eventlog's
        # 5x5 base grid, but the Polis substrate is CommWorld at 14x14). Pawns
        # roam the FULL substrate — arena_side does NOT clamp position (verified:
        # with arena_side=6 agents still reach index 13 within a few hundred
        # ticks). Report soil.shape so no marker falls off and deme = i*cols+j
        # stays unique across every occupied cell.
        soil = getattr(self.world, "soil", None)
        sub_rows, sub_cols = (soil.shape if soil is not None else (14, 14))
        self.rows = int(sub_rows)
        self.cols = int(sub_cols)

        # session artifacts (manifest + append-only command/hash logs)
        root = runs_dir or os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "runs")
        self.dir = os.path.join(root, self.session_id)
        os.makedirs(self.dir, exist_ok=True)
        self._commands_fp = open(os.path.join(self.dir, "commands.jsonl"),
                                 "w", encoding="utf-8")
        self._hashes_fp = open(os.path.join(self.dir, "hashes.jsonl"),
                               "w", encoding="utf-8")
        self._write_manifest()

    # -- lifecycle ---------------------------------------------------------- #
    def _write_manifest(self) -> None:
        manifest = {
            "schema": 1,
            "session": self.session_id,
            "seed": self.seed,
            "core_commit": self.core_commit,
            "protocol_version": PROTOCOL_VERSION,
            "grid": {"rows": self.rows, "cols": self.cols},
            # attribution only — NOT part of GAME-DET (which hashes core state)
            "generated_at": datetime.now(timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"),
        }
        path = os.path.join(self.dir, "manifest.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, sort_keys=True)

    def close(self) -> None:
        for fp in (self._commands_fp, self._hashes_fp):
            try:
                fp.close()
            except Exception:
                pass

    # -- the tick boundary -------------------------------------------------- #
    def step(self, commands: list | None = None) -> tuple[dict, dict]:
        """Apply all buffered commands at THIS boundary (in receive order,
        logged to commands.jsonl), advance one tick, return (snapshot, events).

        The tick counter reported is the post-step `world.t`."""
        for cmd in (commands or []):
            self._commands_fp.write(json.dumps(
                {"tick": self.world.t, "cmd": cmd},
                separators=(",", ":"), default=_json_default) + "\n")
            self._apply_world_command(cmd)
        self._commands_fp.flush()

        self.world.step()

        snap = self.snapshot()
        self._hashes_fp.write(json.dumps(
            {"tick": snap["tick"], "state_hash": snap["meta"]["state_hash"]}) + "\n")
        self._hashes_fp.flush()
        return snap, self.drain_events()

    def _apply_world_command(self, cmd: dict) -> None:
        handler = WORLD_COMMANDS.get(cmd.get("cmd"))
        if handler is not None:            # Stage 0: never taken
            handler(self.world, cmd)
        # unknown / control-plane commands are logged but do not touch the world

    # -- serialisation ------------------------------------------------------ #
    def _agent_dict(self, a) -> dict:
        w = self.world
        oid = a.oid
        flags = []
        if oid in getattr(w, "speaker", ()):
            flags.append("speaker")
        debt = getattr(w, "_debt", None)
        if debt is not None and debt.is_bonded(oid):
            flags.append("bonded")
        if oid in self._owner_ids:
            flags.append("owner")
        if oid == getattr(w, "_demerzel_oid", None):
            flags.append("demerzel")
        return {
            "oid": oid,
            "x": int(a.j),           # column -> x
            "y": int(a.i),           # row -> y
            "body": round(float(a.body), 6),
            "deme": int(a.i) * self.cols + int(a.j),   # co-located cell = deme
            "flags": flags,
        }

    def snapshot(self) -> dict:
        w = self.world
        try:
            self._owner_ids = set(w.owner_ids())
        except Exception:
            self._owner_ids = set()
        agents = [self._agent_dict(a) for a in w.pop]
        return {
            "type": "snapshot",
            "tick": int(w.t),
            "agents": agents,
            "meta": {
                "rows": self.rows,
                "cols": self.cols,
                "pop": len(agents),
                "state_hash": w.state_fingerprint(),
            },
        }

    def drain_events(self) -> dict:
        new = self.log.events[self._event_cursor:]
        self._event_cursor = len(self.log.events)
        return {
            "type": "events",
            "tick": int(self.world.t),
            "items": [_event_to_dict(e) for e in new],
        }


class GameServer:
    """One-client TCP loopback server: handshake, pace loop, command buffer."""

    def __init__(self, session: GameSession, host: str = DEFAULT_HOST,
                 port: int = DEFAULT_PORT, verbose: bool = False):
        self.session = session
        self.host = host
        self.port = port
        self.verbose = verbose
        self.tps = 0                 # start paused (RimWorld: pause -> act -> release)
        self._buf = b""              # inbound byte buffer (line framing)
        self._cmd_buffer: list = []  # commands awaiting the next tick boundary
        self._first_snapshot_logged = False

    def _log(self, msg: str) -> None:
        print(f"[gameserver] {msg}", flush=True)

    def _vlog(self, msg: str) -> None:
        if self.verbose:
            print(f"[gameserver] {msg}", flush=True)

    def _reset_connection_state(self) -> None:
        """Per-client state, cleared between connections. The SESSION (world,
        tick counter, commands.jsonl) deliberately PERSISTS across reconnects."""
        self.tps = 0                 # paused until the new client sends pace
        self._buf = b""
        self._cmd_buffer = []
        self._first_snapshot_logged = False

    def serve(self) -> None:
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((self.host, self.port))
        srv.listen(1)
        # short accept timeout so Ctrl+C is responsive even on Windows (a bare
        # blocking accept() swallows KeyboardInterrupt until a client arrives).
        srv.settimeout(1.0)
        self._log(f"listening on {self.host}:{self.port} "
                  f"seed={self.session.seed} commit={self.session.core_commit} "
                  f"session={self.session.session_id}"
                  + ("  [verbose]" if self.verbose else ""))
        try:
            while True:                       # accept loop — survive reconnects
                try:
                    conn, addr = srv.accept()
                except socket.timeout:
                    continue                  # idle tick; lets Ctrl+C through
                self._log(f"client {addr} connected "
                          f"(tick={self.session.world.t})")
                try:
                    if self._handshake(conn):
                        self._loop(conn)
                except (ConnectionError, OSError) as e:
                    self._log(f"connection dropped: {e!r}")
                finally:
                    conn.close()
                    self._reset_connection_state()
                self._log("client gone, listening again")
        except KeyboardInterrupt:
            self._log("interrupted (Ctrl+C) — clean shutdown")
        finally:
            srv.close()
            self.session.close()
            self._log("closed")

    # -- handshake ---------------------------------------------------------- #
    def _handshake(self, conn) -> bool:
        msg = self._read_one_blocking(conn, timeout=10.0)
        if msg is None:
            return False
        if msg.get("type") != "hello":
            self._send(conn, {"type": "error", "code": "expected_hello",
                              "message": "first message must be hello"})
            return False
        pv = msg.get("protocol_version")
        if pv != PROTOCOL_VERSION:
            self._send(conn, {"type": "error", "code": "protocol_mismatch",
                              "message": f"server protocol {PROTOCOL_VERSION}, "
                                         f"client sent {pv}; refusing"})
            print(f"[gameserver] handshake rejected: client pv={pv}", flush=True)
            return False
        self._send(conn, {
            "type": "hello",
            "protocol_version": PROTOCOL_VERSION,
            "core_commit": self.session.core_commit,
            "seed": self.session.seed,
            "session": self.session.session_id,
        })
        self._log(f"handshake ok (client={msg.get('client')} "
                  f"{msg.get('client_version')})")
        return True

    # -- main loop ---------------------------------------------------------- #
    def _loop(self, conn) -> None:
        next_tick = time.monotonic()
        while True:
            # wait for inbound data OR until the next tick is due
            if self.tps > 0:
                timeout = max(0.0, next_tick - time.monotonic())
            else:
                timeout = 0.1        # paused: stay responsive to pace/ping
            ready, _, _ = select.select([conn], [], [], timeout)
            if ready:
                if not self._drain_socket(conn):
                    return           # client disconnected

            if self.tps > 0 and time.monotonic() >= next_tick:
                snap, events = self.session.step(self._cmd_buffer)
                self._cmd_buffer = []
                if not self._first_snapshot_logged:
                    self._log(f"first snapshot: tick {snap['tick']} "
                              f"-> {snap['meta']['pop']} agents")
                    self._first_snapshot_logged = True
                self._send(conn, snap)
                if events["items"]:
                    self._send(conn, events)
                dt = 1.0 / self.tps
                next_tick += dt
                # anti-spiral: if we fell more than one tick behind, resync
                if time.monotonic() - next_tick > dt:
                    next_tick = time.monotonic() + dt

    # -- message handling --------------------------------------------------- #
    def _handle(self, conn, msg: dict) -> None:
        mtype = msg.get("type")
        self._vlog(f"<- {mtype} {msg}")
        if mtype == "pace":
            tps = msg.get("tps")
            if tps in LEGAL_TPS:
                self.tps = tps
                self._log(f"pace accepted: tps={tps}"
                          + ("  (pause)" if tps == 0 else ""))
            else:
                self._send(conn, {"type": "error", "code": "bad_pace",
                                  "message": f"tps must be one of {LEGAL_TPS}"})
        elif mtype == "ping":
            self._log(f"ping accepted: nonce={msg.get('nonce')}")
            self._send(conn, {"type": "pong", "nonce": msg.get("nonce")})
        elif mtype == "commands":
            batch = msg.get("batch") or []
            self._vlog(f"commands batch: {len(batch)} item(s)")
            self._cmd_buffer.extend(batch)
        elif mtype == "hello":
            self._send(conn, {"type": "error", "code": "already_hello",
                              "message": "handshake already completed"})
        else:
            self._send(conn, {"type": "error", "code": "unknown_type",
                              "message": f"unknown message type {mtype!r}"})

    # -- transport ---------------------------------------------------------- #
    def _drain_socket(self, conn) -> bool:
        try:
            data = conn.recv(65536)
        except (BlockingIOError, InterruptedError):
            return True
        except (ConnectionResetError, ConnectionAbortedError) as e:
            self._log(f"_drain_socket end: connection reset "
                      f"(errno={getattr(e, 'errno', '?')}) {e!r}")
            return False             # peer vanished (abrupt close) — end cleanly
        except OSError as e:
            self._log(f"_drain_socket end: socket error "
                      f"(errno={getattr(e, 'errno', '?')}) {e!r}")
            return False
        if not data:
            self._log("_drain_socket end: empty read (peer closed cleanly)")
            return False             # peer closed
        self._buf += data
        while b"\n" in self._buf:
            line, self._buf = self._buf.split(b"\n", 1)
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                self._send(conn, {"type": "error", "code": "bad_json",
                                  "message": "line is not valid JSON"})
                continue
            self._handle(conn, msg)
        return True

    def _read_one_blocking(self, conn, timeout: float):
        conn.settimeout(timeout)
        try:
            while b"\n" not in self._buf:
                data = conn.recv(65536)
                if not data:
                    return None
                self._buf += data
            line, self._buf = self._buf.split(b"\n", 1)
            return json.loads(line.strip())
        except (socket.timeout, json.JSONDecodeError, OSError):
            return None
        finally:
            conn.setblocking(False)

    def _send(self, conn, obj) -> None:
        if self.verbose:
            t = obj.get("type")
            if t == "snapshot":
                self._vlog(f"-> snapshot tick={obj['tick']} "
                           f"agents={obj['meta']['pop']}")
            elif t == "events":
                self._vlog(f"-> events tick={obj['tick']} "
                           f"items={len(obj['items'])}")
            else:
                self._vlog(f"-> {t} {obj}")
        try:
            conn.sendall(_dumps(obj))
        except OSError as e:
            self._log(f"send failed ({t if self.verbose else obj.get('type')}): {e!r}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Noether game server (protocol v1)")
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    ap.add_argument("--host", default=DEFAULT_HOST)
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--session", default=None, help="session id (default s<seed>)")
    ap.add_argument("--verbose", action="store_true",
                    help="log full message traffic (per-frame snapshots/events)")
    args = ap.parse_args(argv)

    session = GameSession(seed=args.seed, session_id=args.session)
    server = GameServer(session, host=args.host, port=args.port,
                        verbose=args.verbose)
    server.serve()               # accept loop; Ctrl+C handled inside
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
