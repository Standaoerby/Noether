class_name NetClient
extends Node
## Protocol-v1 transport (docs/game-architecture.md). Owns the StreamPeerTCP,
## does the handshake, frames line-delimited JSON, and re-emits typed messages
## as signals. NEVER computes game logic — it only ferries bytes.

signal handshaked(info: Dictionary)
signal snapshot_received(snap: Dictionary)
signal events_received(ev: Dictionary)
signal inspect_received(result: Dictionary)
signal pong(nonce: int)
signal error_received(err: Dictionary)
signal closed()

const PROTOCOL_VERSION := 1
const CLIENT_NAME := "godot"
const CLIENT_VERSION := "0.1.0"

enum { STATE_IDLE, STATE_CONNECTING, STATE_HANDSHAKING, STATE_READY, STATE_CLOSED }

# Godot 4.4+ StreamPeerTCP flickers to STATUS_NONE transiently right after data
# is received (godotengine/godot#62001) even though the link is alive. A single
# NONE must NOT be read as a disconnect — only STATUS_ERROR, or NONE that
# persists for this many consecutive polls with no data arriving, is real.
const NONE_GRACE_POLLS := 120

var _peer := StreamPeerTCP.new()
var _rx := ""                       # inbound UTF-8 text buffer (line framing)
var _state: int = STATE_IDLE
var _none_polls := 0                # consecutive STATUS_NONE polls (no data)


func connect_to_server(host: String, port: int) -> void:
	var err := _peer.connect_to_host(host, port)
	if err != OK:
		push_error("connect_to_host failed: %d" % err)
		_state = STATE_CLOSED
		closed.emit()
		return
	_peer.set_no_delay(true)
	_state = STATE_CONNECTING


func _process(_delta: float) -> void:
	if _state == STATE_IDLE or _state == STATE_CLOSED:
		return
	_peer.poll()                                # refresh status/buffers
	var status := _peer.get_status()

	# A hard error is always fatal, in any state.
	if status == StreamPeerTCP.STATUS_ERROR:
		_fail()
		return

	# Still dialing: wait for CONNECTED; only give up if NONE persists.
	if _state == STATE_CONNECTING:
		if status == StreamPeerTCP.STATUS_CONNECTED:
			_none_polls = 0
			_send({
				"type": "hello",
				"protocol_version": PROTOCOL_VERSION,
				"client": CLIENT_NAME,
				"client_version": CLIENT_VERSION,
			})
			_state = STATE_HANDSHAKING
			return
		if status == StreamPeerTCP.STATUS_NONE:
			_none_polls += 1
			if _none_polls >= NONE_GRACE_POLLS:
				_fail()
		return                                  # CONNECTING: keep waiting

	# HANDSHAKING / READY: the link WAS established. Always try to drain buffered
	# bytes first (data can be readable during a transient NONE), then decide.
	var read_any := _read_incoming()
	if status == StreamPeerTCP.STATUS_CONNECTED or read_any:
		_none_polls = 0                         # healthy (or data still flowing)
	elif status == StreamPeerTCP.STATUS_NONE:
		_none_polls += 1                        # transient flicker — ride it out
		if _none_polls >= NONE_GRACE_POLLS:
			_fail()


## Reads/parses any available lines. Returns true if any bytes were read.
func _read_incoming() -> bool:
	var avail := _peer.get_available_bytes()
	if avail <= 0:
		return false
	var res := _peer.get_partial_data(avail)   # [Error, PackedByteArray]
	if int(res[0]) != OK:
		return false                           # not fatal on its own; let status decide
	var bytes: PackedByteArray = res[1]
	if bytes.is_empty():
		return false
	_rx += bytes.get_string_from_utf8()
	while true:
		var nl := _rx.find("\n")
		if nl == -1:
			break
		var line := _rx.substr(0, nl).strip_edges()
		_rx = _rx.substr(nl + 1)
		if not line.is_empty():
			_dispatch(line)
	return true


func _dispatch(line: String) -> void:
	var msg = JSON.parse_string(line)
	if typeof(msg) != TYPE_DICTIONARY:
		return
	match String(msg.get("type", "")):
		"hello":
			_state = STATE_READY
			handshaked.emit(msg)
		"snapshot":
			snapshot_received.emit(msg)
		"events":
			events_received.emit(msg)
		"inspect_result":
			inspect_received.emit(msg)
		"pong":
			pong.emit(int(msg.get("nonce", 0)))
		"error":
			error_received.emit(msg)
		_:
			pass   # ignore unknown message types (forward-compat)


func send_pace(tps: int) -> void:
	_send({"type": "pace", "tps": tps})


func send_ping(nonce: int) -> void:
	_send({"type": "ping", "nonce": nonce})


func send_commands(batch: Array) -> void:
	_send({"type": "commands", "batch": batch})


func send_inspect(oid: int) -> void:
	_send({"type": "inspect", "oid": oid})


func is_ready_state() -> bool:
	return _state == STATE_READY


func _send(obj: Dictionary) -> void:
	# Send while the link is established. STATUS_NONE can be a transient flicker
	# (see _process), so don't gate strictly on CONNECTED — only refuse once we've
	# truly closed or on a hard error. put_data returns an Error; it won't throw.
	if _state == STATE_CLOSED:
		return
	if _peer.get_status() == StreamPeerTCP.STATUS_ERROR:
		return
	var payload := (JSON.stringify(obj) + "\n").to_utf8_buffer()
	_peer.put_data(payload)


func _fail() -> void:
	if _state != STATE_CLOSED:
		_state = STATE_CLOSED
		closed.emit()
