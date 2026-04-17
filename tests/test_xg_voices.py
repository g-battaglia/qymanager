"""Tests for midi_tools/xg_voices.py — voice name lookup."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from midi_tools.xg_voices import (
    GM_DRUM_NOTES,
    GM_VOICES,
    XG_DRUM_KITS,
    drum_note_name,
    voice_name,
)


def test_gm_voices_count():
    assert len(GM_VOICES) == 128


def test_gm_piano_program_0():
    assert voice_name(0, 0, 0) == "GrandPno"


def test_gm_nylon_guitar_program_24():
    # Program 24 in GM = NylonGtr on QY70
    assert voice_name(0, 0, 24) == "NylonGtr"


def test_gm_standard_program_out_of_range():
    # Defensive path — out-of-spec programs must not crash and must be labeled.
    out = voice_name(0, 0, 200)
    assert "GM" in out and "200" in out


def test_drum_kit_msb_127_standard():
    assert "Standard Kit" in voice_name(127, 0, 0)
    assert "(drum)" in voice_name(127, 0, 0)


def test_drum_kit_unknown_program():
    # An unmapped drum program should still produce a useful label.
    out = voice_name(127, 0, 99)
    assert "Drum Kit" in out
    assert "99" in out


def test_xg_variation_bank_fallback():
    # Bank != 0/127 should hit the generic fallback.
    out = voice_name(0, 1, 0)
    assert "MSB=0" in out and "LSB=1" in out


def test_drum_kit_list_is_subset_of_128():
    for prog in XG_DRUM_KITS:
        assert 0 <= prog < 128


def test_drum_note_name_kick():
    # Note 36 = Kick in every Standard Kit layout
    assert drum_note_name(36) == "Kick"
    assert drum_note_name(38) == "Snare"
    assert drum_note_name(42) == "Hi-Hat Closed"
    assert drum_note_name(44) == "Hi-Hat Pedal"
    assert drum_note_name(46) == "Hi-Hat Open"


def test_drum_note_name_fallback():
    # Outside documented range → graceful fallback
    assert "note 5" in drum_note_name(5)
    assert "note 120" in drum_note_name(120)


def test_drum_notes_cover_captured_range():
    # All DS2 notes actually seen in ground_truth_preset.syx (session 30f)
    # must map to a real Standard Kit name.
    seen = {31, 33, 35, 36, 37, 38, 39, 40, 42, 44, 46, 51}
    for n in seen:
        assert n in GM_DRUM_NOTES, f"Note 0x{n:02X} missing from GM_DRUM_NOTES"
