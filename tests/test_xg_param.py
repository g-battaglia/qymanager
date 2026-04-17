"""Regression tests for midi_tools/xg_param.py — XG Parameter Change tool."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from midi_tools.xg_param import (
    AH_DRUM_SETUP_2,
    AH_EFFECT,
    AH_MULTI_PART,
    AH_SYSTEM,
    build_xg,
    parse_channel_event,
    parse_file,
    parse_xg,
    split_stream,
    split_sysex,
)


def test_build_and_parse_roundtrip():
    # XG System On
    raw = build_xg(0x00, 0x00, 0x7E, [0x00])
    assert raw == bytes.fromhex("F0 43 10 4C 00 00 7E 00 F7".replace(" ", ""))
    m = parse_xg(raw)
    assert m is not None
    assert m.ah == 0x00 and m.am == 0x00 and m.al == 0x7E
    assert m.data == b"\x00"
    assert "XG System On" in m.decode()


def test_parse_multi_part_part_mode():
    raw = build_xg(0x08, 0x01, 0x07, [0x01])
    m = parse_xg(raw)
    assert m.ah == AH_MULTI_PART
    assert m.am == 0x01  # Part 1
    assert m.al == 0x07
    dec = m.decode()
    assert "Part 01" in dec
    assert "Part Mode" in dec
    assert "Drum" in dec  # mode 1 = Drum


def test_parse_effect_variation_type_2byte():
    # Variation Type MSB/LSB = 08 00 (Cross Delay)
    raw = build_xg(0x02, 0x01, 0x40, [0x08, 0x00])
    m = parse_xg(raw)
    assert m.ah == AH_EFFECT
    assert m.data == b"\x08\x00"
    assert "Variation Type MSB" in m.decode()


def test_parse_drum_setup():
    # DS2 note 2C (Pedal HH) Level = 0x61
    raw = build_xg(0x31, 0x2C, 0x02, [0x61])
    m = parse_xg(raw)
    assert m.ah == AH_DRUM_SETUP_2
    assert m.am == 0x2C
    assert m.al == 0x02
    assert "DS2 note=2C" in m.decode()
    assert "Level" in m.decode()


def test_parse_rejects_non_xg():
    # Sequencer Param Change (Model 5F) → should not parse as XG
    seq = bytes.fromhex("F0 43 10 5F 00 00 00 01 F7".replace(" ", ""))
    assert parse_xg(seq) is None
    # Roland SysEx
    ro = bytes.fromhex("F0 41 10 42 12 40 00 7F 00 41 F7".replace(" ", ""))
    assert parse_xg(ro) is None
    # Malformed
    assert parse_xg(b"\xF0\xF7") is None


def test_split_sysex_multiple():
    a = build_xg(0x00, 0x00, 0x7E, [0x00])
    b = build_xg(0x08, 0x00, 0x07, [0x03])
    blob = a + b
    msgs = split_sysex(blob)
    assert len(msgs) == 2
    assert msgs[0] == a
    assert msgs[1] == b


def test_parse_file_ground_truth_preset():
    """ground_truth_preset.syx is a real QY70 XG PARM OUT capture."""
    path = ROOT / "midi_tools/captured/ground_truth_preset.syx"
    if not path.exists():
        import pytest
        pytest.skip("capture fixture not available")
    msgs = parse_file(path)
    assert len(msgs) > 500  # 812 messages confirmed in session 30e
    # Expect at least one of each type
    assert any(m.ah == AH_SYSTEM for m in msgs)
    assert any(m.ah == AH_EFFECT for m in msgs)
    assert any(m.ah == AH_MULTI_PART for m in msgs)
    assert any(m.ah == AH_DRUM_SETUP_2 for m in msgs)
    # First message must be XG System On
    assert msgs[0].ah == AH_SYSTEM and msgs[0].al == 0x7E


def test_pattern_dump_contains_no_xg():
    """Sequencer pattern dump (Model 5F) must have zero XG Param Change messages."""
    path = ROOT / "midi_tools/captured/ground_truth_C_kick.syx"
    if not path.exists():
        import pytest
        pytest.skip("capture fixture not available")
    msgs = parse_file(path)
    assert msgs == []  # pattern dump is Model 5F, not 4C


def test_split_stream_mixed_sysex_and_channel_events():
    """split_stream must handle a mix of XG SysEx and channel MIDI events —
    the realistic XG PARM OUT capture shape when --all is used."""
    xg = build_xg(0x08, 0x00, 0x07, [0x03])           # 9 bytes SysEx
    note_on = bytes([0x91, 0x3C, 0x64])                # NoteOn ch2 note 60
    pgm_change = bytes([0xC2, 0x20])                   # PC ch3 prog 32
    cc_bank_msb = bytes([0xB0, 0x00, 0x7F])            # CC ch1 Bank MSB=127
    # Realtime clock (0xF8) and active sense (0xFE) should be skipped.
    blob = xg + b"\xF8" + note_on + b"\xFE" + pgm_change + cc_bank_msb

    parts = split_stream(blob)
    assert len(parts) == 4, [p.hex() for p in parts]
    assert parts[0] == xg
    assert parts[1] == note_on
    assert parts[2] == pgm_change
    assert parts[3] == cc_bank_msb


def test_parse_channel_event_program_change():
    ev = parse_channel_event(bytes([0xC5, 0x21]))
    assert ev is not None
    assert ev.kind == 0xC0
    assert ev.channel == 5
    assert ev.data == b"\x21"
    assert "PgmChg" in ev.decode()


def test_parse_channel_event_rejects_sysex_and_realtime():
    assert parse_channel_event(bytes([0xF0, 0x43, 0xF7])) is None
    assert parse_channel_event(bytes([0xF8])) is None
    assert parse_channel_event(b"") is None


def test_segment_snapshots_on_ground_truth_preset():
    """33 snapshots confirmed in session 30f analysis."""
    from midi_tools.xg_param import segment_snapshots
    path = ROOT / "midi_tools/captured/ground_truth_preset.syx"
    if not path.exists():
        import pytest
        pytest.skip("capture fixture not available")
    msgs = parse_file(path)
    snaps = segment_snapshots(msgs)
    assert len(snaps) == 33
    # First snapshot must start with XG System On
    assert snaps[0].boundary == "XG_ON"
    # All subsequent snapshots start with Drum Setup Reset
    assert all(s.boundary == "DS_RESET" for s in snaps[1:])
    # Sum of messages across snapshots must equal parsed total
    assert sum(len(s.messages) for s in snaps) == len(msgs)


def test_segment_snapshots_extracts_var_type():
    """Build a synthetic stream with a Variation Type message and check extraction."""
    from midi_tools.xg_param import segment_snapshots
    raw = (
        build_xg(0x00, 0x00, 0x7E, [0x00])              # XG System On → new snap
        + build_xg(0x02, 0x01, 0x40, [0x08, 0x00])      # Variation Type = 0800
        + build_xg(0x00, 0x00, 0x7D, [0x01])            # Drum Setup Reset → new snap
        + build_xg(0x31, 0x24, 0x02, [0x7F])            # DS2 note 36 Level
    )
    msgs = [parse_xg(m) for m in split_sysex(raw)]
    snaps = segment_snapshots([m for m in msgs if m is not None])
    assert len(snaps) == 2
    assert snaps[0].var_type == "0800"
    assert snaps[1].ds2_notes == [0x24]
