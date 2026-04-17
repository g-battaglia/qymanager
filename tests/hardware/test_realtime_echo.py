"""Hardware-in-the-loop tests for the realtime XG editor.

These tests require a physical QY70 (or QY700) connected via USB-MIDI on a
port whose name contains "UR22C". Enable with ``QY_HARDWARE=1`` and optionally
``QY_PORT=<port name substring>``.

The conftest auto-skips this module unless ``QY_HARDWARE=1`` is set.
"""

from __future__ import annotations

import os
import time

import pytest

from qymanager.editor.realtime import RealtimeSession, list_output_ports

pytestmark = pytest.mark.hardware


def _port_substring() -> str:
    return os.environ.get("QY_PORT", "UR22C")


@pytest.fixture
def out_port_name() -> str:
    substr = _port_substring()
    ports = [p for p in list_output_ports() if substr.lower() in p.name.lower()]
    if not ports:
        pytest.skip(f"no MIDI output port matching {substr!r}")
    return ports[0].name


def test_xg_master_volume_echo(out_port_name: str) -> None:
    """Send an XG master volume change and confirm no exception is raised."""
    with RealtimeSession.open(out_port_name) as session:
        session.send_xg_parameter(0x00, 0x00, 0x04, 100)
        time.sleep(0.05)


def test_xg_transpose_roundtrip(out_port_name: str) -> None:
    """Send a transpose offset and confirm the session handles it cleanly."""
    with RealtimeSession.open(out_port_name) as session:
        session.send_udm_edit("system.transpose", 5)
        time.sleep(0.05)
        session.send_udm_edit("system.transpose", 0)
        time.sleep(0.05)
