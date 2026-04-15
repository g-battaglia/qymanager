#!/usr/bin/env python3
"""Raw hex analysis of SGT track data to understand encoding structure.

Dumps the full decoded track data with DC/9E delimiters marked,
and tries multiple decoding hypotheses for each event.
"""

import sys
import os
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from midi_tools.event_decoder import (
    get_track_data, extract_bars, rot_right, extract_9bit,
    SECTION_NAMES, TRACK_NAMES,
)

SYX_PATH = "tests/fixtures/QY70_SGT.syx"

# Ground truth from capture — beat-by-beat for CHD2 MAIN-A
# Capture at 151 BPM ≈ 0.397s per beat
CHD2_BEATS = [
    # (time, notes, velocities)
    (0.027, [69, 72, 76], [45, 62, 48]),
    (0.820, [69, 74, 77], [57, 63, 59]),
    (1.614, [65, 69, 72], [71, 69, 63]),
    (2.408, [67, 71, 74], [65, 0, 0]),  # incomplete from first_10
]


def hex_dump_track(slot, section=0):
    """Hex dump of full decoded track data."""
    data = get_track_data(SYX_PATH, section, slot)
    if not data:
        print(f"No data for slot {slot}")
        return

    print(f"\n{'='*70}")
    print(f"  RAW HEX: Slot {slot} ({TRACK_NAMES[slot]}) Section {SECTION_NAMES[section]}")
    print(f"  Total: {len(data)} bytes")
    print(f"{'='*70}")

    # Mark special bytes
    for i in range(0, len(data), 16):
        line = data[i:i+16]
        hex_parts = []
        for j, b in enumerate(line):
            pos = i + j
            if b == 0xDC:
                hex_parts.append(f"\033[91mDC\033[0m")  # Red for DC delimiter
            elif b == 0x9E:
                hex_parts.append(f"\033[93m9E\033[0m")  # Yellow for 9E
            elif pos < 12:
                hex_parts.append(f"\033[90m{b:02X}\033[0m")  # Grey for fixed header
            elif 12 <= pos < 24:
                hex_parts.append(f"\033[36m{b:02X}\033[0m")  # Cyan for params
            elif 24 <= pos < 28:
                hex_parts.append(f"\033[32m{b:02X}\033[0m")  # Green for preamble
            else:
                hex_parts.append(f"{b:02X}")
        print(f"  0x{i:03X}: {' '.join(hex_parts)}")

    # Find all DC/9E positions
    delimiters = [(i, data[i]) for i in range(28, len(data)) if data[i] in (0xDC, 0x9E)]
    print(f"\n  Delimiters after preamble:")
    for pos, val in delimiters:
        name = "DC(bar)" if val == 0xDC else "9E(sub)"
        print(f"    0x{pos:03X} ({pos}): {name}")


def analyze_chord_events_no_rotation(slot, section=0):
    """Try to decode chord events without rotation — look for note patterns."""
    data = get_track_data(SYX_PATH, section, slot)
    if len(data) < 28:
        return

    preamble, bars = extract_bars(data)

    print(f"\n{'='*70}")
    print(f"  NO-ROTATION ANALYSIS: Slot {slot} Section {SECTION_NAMES[section]}")
    print(f"{'='*70}")

    for bar_idx, (header, events) in enumerate(bars):
        print(f"\n  Bar {bar_idx}: header={header.hex()}")

        for evt_idx, evt in enumerate(events):
            val = int.from_bytes(evt, "big")

            # Try different field widths WITHOUT rotation
            print(f"\n    Event {evt_idx}: {evt.hex()}")

            # Approach 1: 8-bit bytes (no rotation)
            bytes_raw = list(evt)
            bytes_lo7 = [b & 0x7F for b in evt]
            print(f"      Raw bytes:    {[f'{b:02X}' for b in bytes_raw]}")
            print(f"      Bytes & 0x7F: {bytes_lo7}")

            # Approach 2: 7-bit fields from LSB
            fields_7bit_lsb = []
            for fi in range(8):
                shift = fi * 7
                if shift + 7 <= 56:
                    f = (val >> shift) & 0x7F
                    fields_7bit_lsb.append(f)
            print(f"      7-bit (LSB):  {fields_7bit_lsb}")

            # Approach 3: 7-bit fields from MSB
            fields_7bit_msb = []
            for fi in range(8):
                shift = 56 - (fi + 1) * 7
                if shift >= 0:
                    f = (val >> shift) & 0x7F
                    fields_7bit_msb.append(f)
            print(f"      7-bit (MSB):  {fields_7bit_msb}")

            # Approach 4: Nibble pairs → note+velocity?
            nibbles = []
            for b in evt:
                nibbles.append(b >> 4)
                nibbles.append(b & 0xF)
            print(f"      Nibbles:      {nibbles}")

            # Approach 5: XOR with constant(s)
            for xor_val in [0x80, 0xA0, 0xBE, 0x78]:
                xored = [b ^ xor_val for b in evt]
                print(f"      XOR 0x{xor_val:02X}:     {[f'{b:02X}' for b in xored]} "
                      f"= {[b & 0x7F for b in xored]}")


def find_note_encoding(slot, section=0):
    """Brute-force search for how notes are encoded in events."""
    data = get_track_data(SYX_PATH, section, slot)
    if len(data) < 28:
        return

    preamble, bars = extract_bars(data)
    if not bars:
        return

    # For CHD2, target notes per beat from capture
    if slot == 4:
        target_per_event = [
            {69, 72, 76},  # Beat 1
            {69, 74, 77},  # Beat 2
            {65, 69, 72},  # Beat 3
            {67, 71, 74},  # Beat 4
        ]
    elif slot == 0:
        target_per_event = None  # We don't know per-event targets for drums
    else:
        return

    print(f"\n{'='*70}")
    print(f"  NOTE ENCODING SEARCH: Slot {slot} Section {SECTION_NAMES[section]}")
    print(f"{'='*70}")

    if target_per_event and len(bars) > 0:
        header, events = bars[0]
        for evt_idx, evt in enumerate(events[:len(target_per_event)]):
            target = target_per_event[evt_idx]
            val = int.from_bytes(evt, "big")

            print(f"\n  Event {evt_idx}: {evt.hex()} → target notes: {sorted(target)}")

            # Strategy: try ALL rotations and ALL field positions
            found = []
            for r in range(56):
                derot = rot_right(val, r)
                for fi in range(6):
                    f = extract_9bit(derot, fi)
                    lo7 = f & 0x7F
                    if lo7 in target:
                        found.append((r, fi, lo7, f))

            # Group by R value — find R where MULTIPLE target notes appear
            r_notes = {}
            for r, fi, lo7, f in found:
                r_notes.setdefault(r, []).append((fi, lo7, f))

            # Show R values that hit 2+ target notes
            multi_hit = {r: notes for r, notes in r_notes.items() if len(notes) >= 2}
            if multi_hit:
                print(f"    R values hitting 2+ target notes:")
                for r, notes in sorted(multi_hit.items(), key=lambda x: -len(x[1])):
                    note_str = ", ".join(f"F{fi}={lo7}(0x{f:03X})" for fi, lo7, f in notes)
                    print(f"      R={r:2d}: {note_str}")
            else:
                print(f"    No R value hits 2+ target notes in 9-bit fields")

            # Also try 7-bit fields with rotation
            found_7 = []
            for r in range(56):
                derot = rot_right(val, r)
                for fi in range(8):
                    shift = 56 - (fi + 1) * 7
                    if shift >= 0:
                        f = (derot >> shift) & 0x7F
                        if f in target:
                            found_7.append((r, fi, f))

            r_notes_7 = {}
            for r, fi, note in found_7:
                r_notes_7.setdefault(r, []).append((fi, note))

            multi_hit_7 = {r: notes for r, notes in r_notes_7.items()
                          if len(set(n for _, n in notes)) >= 2}
            if multi_hit_7:
                print(f"    7-bit fields hitting 2+ target notes:")
                for r, notes in sorted(multi_hit_7.items(),
                                       key=lambda x: -len(set(n for _, n in x[1]))):
                    unique = set(n for _, n in notes)
                    note_str = ", ".join(f"F{fi}={n}" for fi, n in notes)
                    print(f"      R={r:2d}: {len(unique)} unique — {note_str}")

    # For drums: try to find which R pattern matches across events
    if slot == 0:
        target = {36, 38, 42, 44, 54, 68}
        print(f"\n  Searching for consistent R pattern across drum events...")
        header, events = bars[0]

        # For each event, find all R values that produce a target note
        event_r_sets = []
        for evt_idx, evt in enumerate(events[:12]):
            val = int.from_bytes(evt, "big")
            good_rs = set()
            for r in range(56):
                derot = rot_right(val, r)
                f0 = extract_9bit(derot, 0)
                note = f0 & 0x7F
                if note in target:
                    good_rs.add(r)
            event_r_sets.append(good_rs)
            print(f"    Event {evt_idx}: {evt.hex()} → valid Rs: {sorted(good_rs)}")

        # Check R=9*(i+1) per event — is it in the valid set?
        print(f"\n    Checking R=9*(i+1) cumulative:")
        for i, rs in enumerate(event_r_sets):
            r_cum = (9 * (i + 1)) % 56
            status = "✓" if r_cum in rs else "✗"
            val = int.from_bytes(events[i], "big")
            derot = rot_right(val, r_cum)
            f0 = extract_9bit(derot, 0)
            note = f0 & 0x7F
            print(f"      Event {i}: R={r_cum:2d} {status} (note={note})")


def main():
    # CHD2 deep analysis
    hex_dump_track(4, section=0)
    analyze_chord_events_no_rotation(4, section=0)
    find_note_encoding(4, section=0)

    # RHY1 (drums) — check R consistency
    hex_dump_track(0, section=0)
    find_note_encoding(0, section=0)


if __name__ == "__main__":
    main()
