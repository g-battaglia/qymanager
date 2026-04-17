"""Tests for realtime editor wrapper (F5) — no hardware, rtmidi mocked."""

from __future__ import annotations

from typing import Any, Optional

import pytest

from qymanager.editor.realtime import RealtimeSession


class FakeMidiOut:
    def __init__(self) -> None:
        self.sent: list[list[int]] = []
        self.closed = False

    def send_message(self, data: list[int]) -> None:
        self.sent.append(list(data))

    def close_port(self) -> None:
        self.closed = True


class FakeMidiIn:
    def __init__(self, queue: Optional[list[tuple[list[int], float]]] = None) -> None:
        self._queue = list(queue or [])
        self.closed = False

    def get_message(self) -> Optional[tuple[list[int], float]]:
        if not self._queue:
            return None
        return self._queue.pop(0)

    def close_port(self) -> None:
        self.closed = True


class TestSendUdmEdits:
    def test_system_master_volume(self):
        out = FakeMidiOut()
        rt = RealtimeSession(out)
        rt.send_udm_edit("system.master_volume", 77)
        assert len(out.sent) == 1
        msg = out.sent[0]
        assert msg[0] == 0xF0 and msg[-1] == 0xF7
        assert msg[3] == 0x4C and msg[4] == 0x00 and msg[6] == 0x04
        assert msg[7] == 77

    def test_batch_send(self):
        out = FakeMidiOut()
        rt = RealtimeSession(out)
        rt.send_udm_edits(
            {
                "effects.reverb.type_code": 5,
                "multi_part[0].volume": 110,
            }
        )
        assert len(out.sent) == 2

    def test_unmapped_path_skipped(self):
        out = FakeMidiOut()
        rt = RealtimeSession(out)
        rt.send_udm_edits({"nonsense.foo": 1})
        assert out.sent == []

    def test_context_manager_closes(self):
        out = FakeMidiOut()
        with RealtimeSession(out) as rt:
            rt.send_udm_edit("system.master_volume", 50)
        assert out.closed


class TestWatchXg:
    def test_yields_xg_messages(self):
        queue = [
            (
                [0xF0, 0x43, 0x10, 0x4C, 0x00, 0x00, 0x04, 77, 0xF7],
                0.0,
            ),
            (
                [0xF0, 0x43, 0x10, 0x4C, 0x08, 0x00, 0x0B, 110, 0xF7],
                0.01,
            ),
        ]
        rt = RealtimeSession(midi_out=None, midi_in=FakeMidiIn(queue))
        got = list(rt.watch_xg(timeout_s=0.05))
        assert got == [(0x00, 0x00, 0x04, 77), (0x08, 0x00, 0x0B, 110)]

    def test_filters_non_xg(self):
        queue = [
            (
                [0xF0, 0x43, 0x10, 0x5F, 0x00, 0x00, 0x00, 0x01, 0xF7],  # QY70 init
                0.0,
            )
        ]
        rt = RealtimeSession(midi_out=None, midi_in=FakeMidiIn(queue))
        got = list(rt.watch_xg(timeout_s=0.05))
        assert got == []

    def test_timeout_returns(self):
        rt = RealtimeSession(midi_out=None, midi_in=FakeMidiIn([]))
        got = list(rt.watch_xg(timeout_s=0.02))
        assert got == []


class TestSessionGuards:
    def test_send_without_output_raises(self):
        rt = RealtimeSession(midi_out=None)
        with pytest.raises(RuntimeError, match="no output"):
            rt.send_xg_parameter(0x00, 0x00, 0x04, 77)

    def test_watch_without_input_raises(self):
        rt = RealtimeSession(midi_out=FakeMidiOut())
        with pytest.raises(RuntimeError, match="no input"):
            next(rt.watch_xg(timeout_s=0.01))
