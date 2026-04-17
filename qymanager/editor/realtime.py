"""Realtime XG Parameter Change I/O via python-rtmidi.

Bridges `qymanager.editor.ops.make_xg_messages` to live MIDI hardware.

Why rtmidi directly (not mido): on macOS, mido silently drops SysEx
messages larger than ~15 bytes. Using rtmidi.MidiOut avoids that bug.
(See memory/feedback_mido_sysex_bug.md.)

Typical usage:

    with RealtimeSession(port="UR22C Port 1") as rt:
        rt.send_udm_edit("system.master_volume", 77)
        rt.send_udm_edits({"effects.reverb.type_code": 5})

Watch mode for reverse-engineering:

    rt = RealtimeSession.open_input(port="UR22C Port 1")
    for path, value in rt.watch_xg():
        print(path, value)
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Iterator, Optional

from qymanager.editor.address_map import build_xg_parameter_change
from qymanager.editor.ops import make_xg_messages
from qymanager.model import Device


@dataclass(frozen=True)
class PortInfo:
    index: int
    name: str


def _import_rtmidi() -> Any:
    try:
        import rtmidi  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError(
            "python-rtmidi is required for realtime MIDI I/O; "
            "install with 'uv add python-rtmidi' or similar."
        ) from exc
    return rtmidi


def list_output_ports() -> list[PortInfo]:
    rtmidi = _import_rtmidi()
    m = rtmidi.MidiOut()
    return [PortInfo(i, n) for i, n in enumerate(m.get_ports())]


def list_input_ports() -> list[PortInfo]:
    rtmidi = _import_rtmidi()
    m = rtmidi.MidiIn()
    return [PortInfo(i, n) for i, n in enumerate(m.get_ports())]


def _find_port_index(name_pattern: str, ports: list[PortInfo]) -> int:
    for p in ports:
        if name_pattern.lower() in p.name.lower():
            return p.index
    available = ", ".join(p.name for p in ports) or "<none>"
    raise ValueError(
        f"no MIDI port matching {name_pattern!r} (available: {available})"
    )


class RealtimeSession:
    """Manages an open rtmidi output (+ optional input) port for XG I/O."""

    def __init__(self, midi_out: Any, midi_in: Optional[Any] = None) -> None:
        self._out = midi_out
        self._in = midi_in

    @classmethod
    def open(cls, port: str) -> "RealtimeSession":
        rtmidi = _import_rtmidi()
        m = rtmidi.MidiOut()
        idx = _find_port_index(port, list_output_ports())
        m.open_port(idx)
        return cls(m)

    @classmethod
    def open_input(cls, port: str) -> "RealtimeSession":
        rtmidi = _import_rtmidi()
        mi = rtmidi.MidiIn()
        idx = _find_port_index(port, list_input_ports())
        mi.open_port(idx)
        return cls(midi_out=None, midi_in=mi)

    @classmethod
    def open_bidirectional(cls, out_port: str, in_port: str) -> "RealtimeSession":
        rtmidi = _import_rtmidi()
        out = rtmidi.MidiOut()
        out_idx = _find_port_index(out_port, list_output_ports())
        out.open_port(out_idx)
        mi = rtmidi.MidiIn()
        in_idx = _find_port_index(in_port, list_input_ports())
        mi.open_port(in_idx)
        return cls(midi_out=out, midi_in=mi)

    def __enter__(self) -> "RealtimeSession":
        return self

    def __exit__(self, *_exc: Any) -> None:
        self.close()

    def close(self) -> None:
        if self._out is not None:
            self._out.close_port()
            self._out = None
        if self._in is not None:
            self._in.close_port()
            self._in = None

    # -- Output -----------------------------------------------------------

    def send_raw_sysex(self, data: bytes) -> None:
        if self._out is None:
            raise RuntimeError("session has no output port open")
        self._out.send_message(list(data))

    def send_xg_parameter(
        self,
        ah: int,
        am: int,
        al: int,
        value: int,
        *,
        device: int = 0,
    ) -> bytes:
        msg = build_xg_parameter_change(ah, am, al, value, device=device)
        self.send_raw_sysex(msg)
        return msg

    def send_udm_edit(
        self,
        path: str,
        value: Any,
        *,
        device_number: int = 0,
    ) -> bytes:
        return self.send_udm_edits({path: value}, device_number=device_number)

    def send_udm_edits(
        self,
        edits: dict[str, Any],
        *,
        device_number: int = 0,
    ) -> bytes:
        dummy = Device()
        messages = make_xg_messages(dummy, edits, device_number=device_number)
        blob = b""
        for _path, msg in messages:
            self.send_raw_sysex(msg)
            blob += msg
        return blob

    # -- Input (watch mode) ----------------------------------------------

    def watch_xg(
        self,
        *,
        timeout_s: Optional[float] = None,
    ) -> Iterator[tuple[int, int, int, int]]:
        """Yield (AH, AM, AL, value) tuples for every XG Parameter Change
        received on the input port. If `timeout_s` is set, stop after
        that many seconds of silence; otherwise run until the port closes.
        """
        if self._in is None:
            raise RuntimeError("session has no input port open")
        start = time.monotonic()
        while True:
            msg = self._in.get_message()
            if msg is None:
                if timeout_s is not None and time.monotonic() - start > timeout_s:
                    return
                time.sleep(0.005)
                continue
            data, _delta = msg
            start = time.monotonic()
            # Expect F0 43 1n 4C ah am al dd F7
            if (
                len(data) == 9
                and data[0] == 0xF0
                and data[1] == 0x43
                and (data[2] & 0xF0) == 0x10
                and data[3] == 0x4C
                and data[-1] == 0xF7
            ):
                yield (data[4], data[5], data[6], data[7])
