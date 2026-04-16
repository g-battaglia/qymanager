#!/usr/bin/env python3
"""
Analyze chord transposition layer using Summer GT.

We know:
- GT bar 0: G4(67), B4(71), D5(74) = G major
- GT bar 1: G4(67), C5(72), E5(76) = C major (2nd inversion)
- GT bar 2: E4(64), G4(67), B4(71) = E minor
- GT bar 3: D4(62), F#4(66), A4(69) = D major

And the header 9-bit fields for each bar.

Question: what transformation maps header fields → GT chord notes?
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qymanager.formats.qy70.sysex_parser import SysExParser
from midi_tools.event_decoder import (
    extract_bars, decode_header_notes, header_to_midi_notes, nn, rot_right, extract_9bit
)


def load_syx_track(syx_path, section=0, track=0):
    parser = SysExParser()
    messages = parser.parse_file(syx_path)
    al = section * 8 + track
    data = b""
    for m in messages:
        if m.is_style_data and m.address_low == al:
            if m.decoded_data is not None:
                data += m.decoded_data
    return data


# GT chord notes per bar (from capture)
GT_CHORDS = {
    0: [67, 71, 74],  # G4 B4 D5 = G major
    1: [67, 72, 76],  # G4 C5 E5 = C major (2nd inv)
    2: [64, 67, 71],  # E4 G4 B4 = E minor
    3: [62, 66, 69],  # D4 F#4 A4 = D major
}

# Chord names for display
GT_NAMES = {0: "G major", 1: "C major", 2: "E minor", 3: "D major"}


def main():
    syx_path = "data/qy70_sysx/P -  Summer - 20231101.syx"

    # Analyze CHD1 (track 3) — the main chord track
    for track_idx, track_name in [(3, "CHD1"), (6, "PHR1")]:
        data = load_syx_track(syx_path, section=0, track=track_idx)
        if not data:
            continue

        preamble, bars = extract_bars(data)
        print(f"\n{'='*70}")
        print(f"{track_name} — Preamble: {preamble.hex()}")
        print(f"{'='*70}")

        for bar_idx, (header, events) in enumerate(bars):
            if bar_idx >= 5:  # Skip bar 5 (empty/ending)
                continue

            # Header 9-bit fields
            hval = int.from_bytes(header, "big")
            fields_9bit = [(hval >> (104 - (i+1)*9)) & 0x1FF for i in range(11)]
            midi_notes = header_to_midi_notes(fields_9bit)

            # GT chord for this bar
            gt = GT_CHORDS.get(bar_idx % 4, [])
            gt_name = GT_NAMES.get(bar_idx % 4, "?")

            print(f"\n  Bar {bar_idx} — GT: {gt_name} = {[f'{nn(n)}({n})' for n in gt]}")
            print(f"  Header 11×9-bit: {fields_9bit}")
            print(f"  Header lo7 notes: {[f'{nn(n)}({n})' for n in midi_notes]}")
            print(f"  Header hex: {header.hex()}")

            # Try various transformations from header to GT
            print(f"\n  Transformation search:")

            # 1. Direct difference
            for i, gt_note in enumerate(gt):
                if i < len(midi_notes):
                    diff = gt_note - midi_notes[i]
                    print(f"    GT[{i}]={gt_note} - header[{i}]={midi_notes[i]} = {diff:+d}")

            # 2. Search: which header field(s) + offset = each GT note?
            for gn in gt:
                matches = []
                for fi, fv in enumerate(fields_9bit):
                    lo7 = fv & 0x7F
                    offset = gn - lo7
                    if -24 <= offset <= 24:
                        matches.append((fi, lo7, offset))
                if matches:
                    print(f"    GT note {nn(gn)}({gn}): "
                          + ", ".join(f"F{fi}={lo7}+{off:+d}" for fi, lo7, off in matches))

            # 3. Check if GT notes can be formed as combinations of header fields
            for gn in gt:
                # gn = field_a + field_b (mod something)?
                for fi in range(11):
                    for fj in range(fi, 11):
                        a = fields_9bit[fi] & 0x7F
                        b = fields_9bit[fj] & 0x7F
                        if (a + b) % 128 == gn or (a + b) == gn:
                            if fi != fj:
                                print(f"    GT {gn} = F{fi}({a}) + F{fj}({b})")
                        if abs(a - b) == gn:
                            print(f"    GT {gn} = |F{fi}({a}) - F{fj}({b})|")

            # 4. What do the F4 masks select?
            print(f"\n  Event F4 masks and selected notes:")
            for ei, evt in enumerate(events[:4]):
                val = int.from_bytes(evt, "big")
                r = (9 * (ei + 1)) % 56
                derot = rot_right(val, r)
                f4 = extract_9bit(derot, 4)
                mask5 = (f4 >> 4) & 0x1F
                selected = [midi_notes[i] for i in range(5)
                            if mask5 & (1 << (4-i))]
                print(f"    e{ei}: mask={mask5:05b} → header notes {selected}")

    # Cross-bar comparison: which header fields CHANGE between bars?
    print(f"\n{'='*70}")
    print(f"HEADER FIELD CHANGES BETWEEN BARS")
    print(f"{'='*70}")

    for track_idx, track_name in [(3, "CHD1"), (6, "PHR1")]:
        data = load_syx_track(syx_path, section=0, track=track_idx)
        if not data:
            continue
        preamble, bars = extract_bars(data)
        print(f"\n  {track_name}:")

        all_fields = []
        for bar_idx, (header, _) in enumerate(bars[:5]):
            hval = int.from_bytes(header, "big")
            fields = [(hval >> (104 - (i+1)*9)) & 0x1FF for i in range(11)]
            all_fields.append(fields)

        for fi in range(11):
            vals = [f[fi] for f in all_fields]
            unique = len(set(vals))
            if unique == 1:
                print(f"    F{fi:2d}: CONSTANT = {vals[0]}")
            else:
                print(f"    F{fi:2d}: CHANGES  = {vals}")
                # Show as lo7
                lo7s = [v & 0x7F for v in vals]
                bit8s = [(v >> 8) & 1 for v in vals]
                print(f"          lo7={lo7s}  bit8={bit8s}")

    # Musical analysis: GT chord intervals
    print(f"\n{'='*70}")
    print(f"GT CHORD INTERVALS")
    print(f"{'='*70}")

    for bar_idx, (name, notes) in enumerate(
            zip(GT_NAMES.values(), GT_CHORDS.values())):
        root = notes[0]
        intervals = [n - root for n in notes]
        root_name = nn(root)
        print(f"  Bar {bar_idx} ({name}): root={root_name}({root}), "
              f"intervals={intervals}")

        # Also show relative to C4(60)
        rel_c4 = [n - 60 for n in notes]
        print(f"    Relative to C4: {rel_c4}")

        # And as scale degrees relative to G
        rel_g = [(n - 55) % 12 for n in notes]  # G3=55
        print(f"    Relative to G: {rel_g} (semitones mod 12)")

    print("\nDone.")


if __name__ == "__main__":
    main()
