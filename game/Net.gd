class_name NetClient
extends Node
## Protocol-v1 transport (docs/game-architecture.md). Owns the StreamPeerTCP,
## does the handshake, frames line-delimited JSON, and re-emits typed messages
## as signals. NEVER computes game logic — it only ferries bytes.

signal handshaked(info: Dictionary)
signal snapshot_received(snap: Dictionary)
signal events_received(ev: Dictionary)
signal pong(nonce: int)
signal error_received(err: Dictionary)
signal closed()

const PROTOCOL_VERSION := 1
const CLIENT_NAME := "godot"
const CLIENT_VERSION := "0.1.0"

enum { STATE_IDLE, STATE_CONNECTING, STATE_HANDSHAKING, STATE_READY, STATE_CLOSED }

var _peer := StreamPeerTCP.new()
var _rx := ""                       # inbound UTF-8 text buffer (line framing)
var _state: int = STATE_IDLE


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
	_peer.poll()
	var status := _peer.get_status()
	if status == StreamPeerTCP.STATUS_ERROR or status == StreamPeerTCP.STATUS_NONE:
		_fail()
		return
	if _state == STATE_CONNECTING and status == StreamPeerTCP.STATUS_CONNECTED:
		_send({
			"type": "hello",
			"protocol_version": PROTOCOL_VERSION,
			"client": CLIENT_NAME,
			"client_version": CLIENT_VERSION,
		})
		_state = STATE_HANDSHAKING
	if status == StreamPeerTCP.STATUS_CONNECTED:
		_read_incoming()


func _read_incoming() -> void:
	var avail := _peer.get_available_bytes()
	if avail > 0:
		var res := _peer.get_partial_data(avail)   # [Error, PackedByteArray]
		if int(res[0]) != OK:
			_fail()
			return
		var bytes: PackedByteArray = res[1]
		_rx += bytes.get_string_from_utf8()
	while true:
		var nl := _rx.find("\n")
		if nl == -1:
			break
		var line := _rx.substr(0, nl).strip_edges()
		_rx = _rx.substr(nl + 1)
		if not line.is_empty():
			_dispatch(line)


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


func is_ready_state() -> bool:
	return _state == STATE_READY


func _send(obj: Dictionary) -> void:
	if _peer.get_status() != StreamPeerTCP.STATUS_CONNECTED:
		return
	var payload := (JSON.stringify(obj) + "\n").to_utf8_buffer()
	_peer.put_data(payload)


func _fail() -> void:
	if _state != STATE_CLOSED:
		_state = STATE_CLOSED
		closed.emit()
