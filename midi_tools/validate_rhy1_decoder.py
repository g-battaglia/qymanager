#!/usr/bin/env python3
"""Validate RHY1 drum decoder against known playback capture.

Session 13 captured playback of user style:
  ch9 (D1/RHY1): Kick36 beats 1,5 / Snare38 beats 3,7 / HHclose42 every 8th
  Velocities: HH=112-122, Kick=111-127, Snare=115-123
  4 bars, 8-beat pattern, 120 BPM

This script decodes the RHY1 track from user_style_live.syx and compares.

Usage:
  .venv/bin/python3 midi_tools/validate_rhy1_decoder.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qymanager.formats.qy70.sysex_parser import SysExParser
from midi_tools.event_decoder import (
    rot_right, extract_9bit, decode_drum_event, extract_bars,
    TRACK_NAMES, classify_encoding,
)

GM_DRUMS = {
    35: 'Kick2', 36: 'Kick1', 37: 'SStick', 38: 'Snare1', 39: 'Clap',
    40: 'ElSnare', 42: 'HHclose', 44: 'HHpedal', 46: 'HHopen',
    48: 'HiMidTom', 49: 'Crash1', 51: 'Ride1', 57: 'Crash2',
}

# Known playback from Session 13 capture (ch9 = D1/RHY1)
# 8-beat pattern: HH every 8th, Kick beats 1/5, Snare beats 3/7
EXPECTED_NOTES = {36, 38, 42}  # Kick1, Snare1, HHclose
EXPECTED_VEL_RANGES = {
    36: (111, 127),  # Kick
    38: (115, 123),  # Snare
    42: (112, 122),  # HH
}


def get_all_tracks(syx_path):
    """Extract all track data from .syx file, grouped by address_low."""
    parser = SysExParser()
    messages = parser.parse_file(syx_path)
    tracks = {}
    for m in messages:
        if m.is_style_data and m.decoded_data:
            al = m.address_low
            if al not in tracks:
                tracks[al] = b''
            tracks[al] += m.decoded_data
    return tracks


def decode_rhy1_full(track_data):
    """Decode RHY1 track with detailed per-bar, per-event output."""
    preamble, bars = extract_bars(track_data)
    enc = classify_encoding(preamble)

    print(f"  Preamble: {preamble.hex()} → {enc}")
    print(f"  Track data: {len(track_data)} bytes")
    print(f"  Bars found: {len(bars)}")

    all_notes = []
    all_ctrl = []

    for bi, (header, events) in enumerate(bars):
        print(f"\n  --- Bar {bi} ({len(events)} events) ---")
        print(f"  Header: {header.hex()}")

        for ei, evt in enumerate(events):
            raw_hex = evt.hex()
            decoded = decode_drum_event(evt, ei)

            if decoded is None:
                print(f"    e{ei}: {raw_hex} → FAILED")
                continue

            if decoded["type"] == "control":
                print(f"    e{ei}: {raw_hex} → CTRL f0={decoded['f0']:03x}")
                all_ctrl.append(decoded)
                continue

            n = decoded["note"]
            v = decoded["velocity"]
            t = decoded["tick"]
            g = decoded["gate"]
            nname = GM_DRUMS.get(n, f"n{n}")
            print(f"    e{ei}: {raw_hex} → {nname:>10s} n={n:3d} v={v:3d} "
                  f"t={t:4d} g={g:3d} f0={decoded['f0']:03x}")
            all_notes.append(decoded)

    return all_notes, all_ctrl


def validate_against_playback(notes):
    """Compare decoded notes with known playback capture data."""
    print(f"\n{'='*60}")
    print(f"  VALIDATION vs PLAYBACK CAPTURE")
    print(f"{'='*60}")

    decoded_note_set = set(e["note"] for e in notes)
    print(f"\n  Decoded notes: {sorted(decoded_note_set)}")
    print(f"  Expected notes: {sorted(EXPECTED_NOTES)}")

    match = decoded_note_set & EXPECTED_NOTES
    only_decoded = decoded_note_set - EXPECTED_NOTES
    only_expected = EXPECTED_NOTES - decoded_note_set

    print(f"  MATCH:        {sorted(match)}")
    if only_decoded:
        print(f"  Only decoded: {sorted(only_decoded)} (extra notes)")
    if only_expected:
        print(f"  MISSING:      {sorted(only_expected)} ← not found in decoder!")

    # Velocity check
    print(f"\n  Velocity validation:")
    for n in sorted(match):
        nname = GM_DRUMS.get(n, f"n{n}")
        vels = [e["velocity"] for e in notes if e["note"] == n]
        vmin, vmax = min(vels), max(vels)
        exp_lo, exp_hi = EXPECTED_VEL_RANGES.get(n, (0, 127))
        in_range = exp_lo - 16 <= vmin and vmax <= exp_hi + 16  # ±16 tolerance
        status = "OK" if in_range else "MISMATCH"
        print(f"    {nname:>10s}: decoded v={vmin}-{vmax}, "
              f"captured v={exp_lo}-{exp_hi} [{status}]")

    # Note count per pitch
    print(f"\n  Note counts per pitch:")
    for n in sorted(decoded_note_set):
        count = sum(1 for e in notes if e["note"] == n)
        nname = GM_DRUMS.get(n, f"n{n}")
        print(f"    {nname:>10s} (n={n}): {count} events")

    accuracy = len(match) / len(EXPECTED_NOTES) * 100 if EXPECTED_NOTES else 0
    print(f"\n  Note set accuracy: {accuracy:.0f}% ({len(match)}/{len(EXPECTED_NOTES)})")


def main():
    syx_path = "midi_tools/captured/user_style_live.syx"

    tracks = get_all_tracks(syx_path)

    print(f"{'='*60}")
    print(f"  RHY1 DECODER VALIDATION")
    print(f"  Source: {syx_path}")
    print(f"{'='*60}")

    # Find RHY1 (AL=0 for section 0)
    # In user style, AL values are the track slot indices (0-7)
    rhy1_data = None
    for al in sorted(tracks):
        name = TRACK_NAMES.get(al, f"AL{al:02X}")
        size = len(tracks[al])
        print(f"  AL={al:02X} ({name}): {size} bytes")
        if al == 0:
            rhy1_data = tracks[al]

    if rhy1_data is None:
        # Try section-based addressing (section*8 + track)
        for al in sorted(tracks):
            if al % 8 == 0 and al != 0x7F:
                rhy1_data = tracks[al]
                print(f"\n  Using AL={al:02X} as RHY1")
                break

    if rhy1_data is None:
        print("\n  ERROR: RHY1 track not found!")
        return

    print(f"\n  RHY1 track size: {len(rhy1_data)} bytes")
    print(f"  First 28 bytes (preamble area): {rhy1_data[:28].hex()}")

    notes, ctrls = decode_rhy1_full(rhy1_data)

    print(f"\n  Total: {len(notes)} note events, {len(ctrls)} control events")

    if notes:
        validate_against_playback(notes)
    else:
        print("\n  WARNING: No note events decoded — trying alternate segment parsing")
        # Try raw 7-byte parsing without bar headers
        print("\n  --- RAW PARSE (skip preamble, 7-byte chunks) ---")
        raw_data = rhy1_data[28:]
        raw_notes = []
        for i in range(len(raw_data) // 7):
            evt = raw_data[i*7:(i+1)*7]
            if all(b == 0 for b in evt):
                continue
            decoded = decode_drum_event(evt, i % 8)
            if decoded and decoded["type"] == "note":
                n = decoded["note"]
                nname = GM_DRUMS.get(n, f"n{n}")
                print(f"  offset {i*7:4d}: {evt.hex()} → {nname} n={n} v={decoded['velocity']}")
                raw_notes.append(decoded)
        if raw_notes:
            validate_against_playback(raw_notes)


if __name__ == "__main__":
    main()
