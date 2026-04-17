"""Regression tests for midi_tools/syx_edit.py — byte-level QY70 SysEx editor."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from midi_tools.syx_edit import (
    compute_tempo_encoding,
    edit_syx,
    parse_sysex,
    is_bulk_header,
)
from qymanager.utils.yamaha_7bit import decode_7bit, encode_7bit
from qymanager.utils.checksum import verify_sysex_checksum

SGT = ROOT / "tests/fixtures/QY70_SGT.syx"


def _first_header_tempo(syx_bytes: bytes):
    msgs = parse_sysex(syx_bytes)
    for m in msgs:
        if is_bulk_header(m):
            payload = bytes(m[9:-2])
            decoded = decode_7bit(payload)
            enc = encode_7bit(decoded[:7])
            range_byte = enc[0]
            offset_byte = decoded[0]
            return range_byte * 95 - 133 + offset_byte
    return None


def test_compute_tempo_encoding_covers_common_range():
    for bpm in (80, 100, 120, 140, 160, 180):
        r, off = compute_tempo_encoding(bpm)
        assert 0 <= off <= 127
        assert r * 95 - 133 + off == bpm


def test_compute_tempo_encoding_out_of_range():
    import pytest

    with pytest.raises(ValueError):
        compute_tempo_encoding(500)


def test_sgt_original_tempo_is_151():
    data = SGT.read_bytes()
    assert _first_header_tempo(data) == 151


def test_edit_tempo_to_120_preserves_length():
    data = SGT.read_bytes()
    edited = edit_syx(data, bpm=120)
    assert len(edited) == len(data)


def test_edit_tempo_to_120_applies():
    data = SGT.read_bytes()
    edited = edit_syx(data, bpm=120)
    assert _first_header_tempo(edited) == 120


def test_edit_multiple_tempos():
    data = SGT.read_bytes()
    for target in (100, 130, 160, 180):
        edited = edit_syx(data, bpm=target)
        assert _first_header_tempo(edited) == target


def test_edited_checksums_remain_valid():
    data = SGT.read_bytes()
    edited = edit_syx(data, bpm=120)
    for msg in parse_sysex(edited):
        if len(msg) >= 11 and msg[1] == 0x43 and (msg[2] & 0xF0) == 0x00:
            assert verify_sysex_checksum(msg), \
                f"Bad checksum on edited msg: {msg[:12].hex(' ')}..."


def test_edit_syx_no_op_without_bpm_returns_unchanged_content():
    data = SGT.read_bytes()
    edited = edit_syx(data)
    assert edited == data
