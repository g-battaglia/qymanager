#!/usr/bin/env python3
"""
Systematic solver for chord transposition formula.

We have 4 bars with KNOWN inputs (header 9-bit fields) and KNOWN outputs
(GT chord notes). Find the formula that maps header → GT consistently.

Known data (Summer CHD1):
  Bar 0: GT = G4(67), B4(71), D5(74) = G major
  Bar 1: GT = G4(67), C5(72), E5(76) = C major (2nd inv)
  Bar 2: GT = E4(64), G4(67), B4(71) = E minor
  Bar 3: GT = D4(62), F#4(66), A4(69) = D major

Approach: exhaustive combinatorial search over:
1. Single field + offset
2. Two fields combined (add, subtract, XOR, avg)
3. Root-relative encoding (header = intervals from root, root stored separately)
4. Chord table lookup (header encodes chord type index)
"""

import sys
import os
from itertools import combinations
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qymanager.formats.qy70.sysex_parser import SysExParser
from midi_tools.event_decoder import (
    extract_bars, decode_header_notes, header_to_midi_notes, nn,
    rot_right, extract_9bit,
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

# Chord analysis
# G major: root=G(7), notes=[0,4,7] (major triad)
# C major: root=C(0), notes=[0,4,7] (major triad, voiced as G C E = 2nd inversion)
# E minor: root=E(4), notes=[0,3,7] (minor triad)
# D major: root=D(2), notes=[0,4,7] (major triad)

# Chord types: 0=major, 1=minor
CHORD_TYPES = {0: "major", 1: "major", 2: "minor", 3: "major"}
CHORD_ROOTS_MIDI = {0: 67, 1: 60, 2: 64, 3: 62}  # G4, C4, E4, D4
CHORD_ROOTS_PC = {0: 7, 1: 0, 2: 4, 3: 2}  # pitch class

# Voicings (intervals from bass note, not root):
# Bar 0: G4 B4 D5 = [0, 4, 7] from G4 = root position
# Bar 1: G4 C5 E5 = [0, 5, 9] from G4 = 2nd inversion of C (C E G → G C E)
# Bar 2: E4 G4 B4 = [0, 3, 7] from E4 = root position
# Bar 3: D4 F#4 A4 = [0, 4, 7] from D4 = root position
VOICING_INTERVALS = {
    0: [0, 4, 7],   # root position major
    1: [0, 5, 9],   # 2nd inversion major (from bass=5th)
    2: [0, 3, 7],   # root position minor
    3: [0, 4, 7],   # root position major
}
BASS_NOTES = {0: 67, 1: 67, 2: 64, 3: 62}  # lowest note in voicing


def main():
    syx_path = "data/qy70_sysx/P -  Summer - 20231101.syx"

    # Load CHD1 (track 3) and PHR1 (track 6) bar headers
    for track_idx, track_name in [(3, "CHD1"), (6, "PHR1")]:
        data = load_syx_track(syx_path, section=0, track=track_idx)
        if not data:
            continue

        preamble, bars = extract_bars(data)
        print(f"\n{'='*70}")
        print(f"TRACK {track_name}")
        print(f"{'='*70}")

        all_headers = []
        all_raw_headers = []
        for bar_idx, (header, events) in enumerate(bars):
            if bar_idx >= 4:
                break
            hval = int.from_bytes(header, "big")
            fields_9bit = [(hval >> (104 - (i+1)*9)) & 0x1FF for i in range(11)]
            lo7 = [f & 0x7F for f in fields_9bit]
            bit8 = [(f >> 8) & 1 for f in fields_9bit]

            all_headers.append(fields_9bit)
            all_raw_headers.append(header)

            gt = GT_CHORDS.get(bar_idx, [])
            print(f"\n  Bar {bar_idx}: GT={[f'{nn(n)}({n})' for n in gt]}")
            print(f"    Fields: {fields_9bit}")
            print(f"    Lo7:    {lo7}")
            print(f"    Bit8:   {bit8}")
            print(f"    Notes:  {[nn(n) if 13<=n<=87 else '?' for n in lo7]}")

        if len(all_headers) < 4:
            continue

        # =========================================================
        # APPROACH 1: Single field + constant offset
        # =========================================================
        print(f"\n  --- APPROACH 1: Single field + offset ---")
        for fi in range(11):
            vals = [all_headers[bar][fi] & 0x7F for bar in range(4)]
            for gt_note_idx in range(3):
                gt_vals = [GT_CHORDS[bar][gt_note_idx] for bar in range(4)]
                offsets = [gt_vals[b] - vals[b] for b in range(4)]
                if len(set(offsets)) == 1:
                    print(f"    F{fi} + {offsets[0]} = GT[{gt_note_idx}] *** MATCH ***")

        # =========================================================
        # APPROACH 2: Field pairs → GT note
        # =========================================================
        print(f"\n  --- APPROACH 2: Field pair operations ---")
        ops = {
            "add": lambda a, b: a + b,
            "sub": lambda a, b: a - b,
            "xor": lambda a, b: a ^ b,
            "avg": lambda a, b: (a + b) // 2,
            "add_mod128": lambda a, b: (a + b) % 128,
            "sub_mod128": lambda a, b: (a - b) % 128,
        }
        for fi in range(11):
            for fj in range(11):
                if fi == fj:
                    continue
                for op_name, op in ops.items():
                    for gt_ni in range(3):
                        results = []
                        for bar in range(4):
                            a = all_headers[bar][fi] & 0x7F
                            b = all_headers[bar][fj] & 0x7F
                            r = op(a, b)
                            gt = GT_CHORDS[bar][gt_ni]
                            results.append(r - gt)
                        if len(set(results)) == 1:
                            offset = results[0]
                            print(f"    {op_name}(F{fi}, F{fj}) + {-offset} = GT[{gt_ni}] "
                                  f"*** MATCH ***")

        # =========================================================
        # APPROACH 3: Root + intervals model
        # =========================================================
        print(f"\n  --- APPROACH 3: Root extraction ---")
        # Can any single field give us the chord root?
        for fi in range(11):
            vals = [all_headers[bar][fi] & 0x7F for bar in range(4)]
            # Check if vals encode root pitch class
            pcs = [v % 12 for v in vals]
            target_pcs = [CHORD_ROOTS_PC[bar] for bar in range(4)]
            if pcs == target_pcs:
                print(f"    F{fi} mod 12 = chord root pitch class *** MATCH ***")
            # Check if vals encode root MIDI note
            target_midi = [CHORD_ROOTS_MIDI[bar] for bar in range(4)]
            offsets = [vals[b] - target_midi[b] for b in range(4)]
            if len(set(offsets)) == 1:
                print(f"    F{fi} - {offsets[0]} = root MIDI note *** MATCH ***")
            # Check bass note
            target_bass = [BASS_NOTES[bar] for bar in range(4)]
            offsets = [vals[b] - target_bass[b] for b in range(4)]
            if len(set(offsets)) == 1:
                print(f"    F{fi} - {offsets[0]} = bass MIDI note *** MATCH ***")

        # =========================================================
        # APPROACH 4: Difference between fields = interval
        # =========================================================
        print(f"\n  --- APPROACH 4: Field differences as intervals ---")
        for bar in range(4):
            gt = GT_CHORDS[bar]
            h = all_headers[bar]
            lo7 = [f & 0x7F for f in h]
            # GT intervals
            gt_int = [gt[i] - gt[0] for i in range(3)]
            # Header field differences
            for fi in range(11):
                for fj in range(fi+1, 11):
                    diff = lo7[fi] - lo7[fj]
                    for gi, gint in enumerate(gt_int):
                        if diff == gint:
                            print(f"    Bar {bar}: F{fi}-F{fj}={diff} = GT interval [{gi}]={gint}")

        # =========================================================
        # APPROACH 5: Full header as lookup key
        # =========================================================
        print(f"\n  --- APPROACH 5: Header similarity between bars ---")
        # Which fields CHANGE between bars? (These must encode chord info)
        # Which fields are CONSTANT? (These encode something else)
        for fi in range(11):
            vals = [all_headers[bar][fi] for bar in range(4)]
            if len(set(vals)) == 1:
                print(f"    F{fi}: CONSTANT = {vals[0]} (0x{vals[0]:03X})")
            else:
                lo7_vals = [v & 0x7F for v in vals]
                print(f"    F{fi}: CHANGES = {vals} lo7={lo7_vals}")

        # =========================================================
        # APPROACH 6: Raw header bytes, not 9-bit fields
        # =========================================================
        print(f"\n  --- APPROACH 6: Raw header byte analysis ---")
        for bar in range(4):
            gt = GT_CHORDS[bar]
            h = all_raw_headers[bar]
            print(f"    Bar {bar} header: {' '.join(f'{b:02X}' for b in h)}")
            # Check each byte
            for bi, b in enumerate(h):
                for gn in gt:
                    if b == gn:
                        print(f"      byte[{bi}]=0x{b:02X}={b} matches GT note {nn(gn)}")
                    if b == gn % 12:
                        print(f"      byte[{bi}]={b} = GT pitch class of {nn(gn)}")

        # =========================================================
        # APPROACH 7: Nibble-based extraction
        # =========================================================
        print(f"\n  --- APPROACH 7: Nibble extraction from header ---")
        for bar in range(4):
            gt = GT_CHORDS[bar]
            h = all_raw_headers[bar]
            # Extract all nibbles
            nibbles = []
            for b in h:
                nibbles.append((b >> 4) & 0xF)
                nibbles.append(b & 0xF)
            # Search for GT notes as nibble pairs
            for ni in range(len(nibbles) - 1):
                val = nibbles[ni] * 16 + nibbles[ni+1]
                for gn in gt:
                    if val == gn:
                        print(f"      Bar {bar}: nibbles[{ni}:{ni+2}] = {val} = {nn(gn)}")

        # =========================================================
        # APPROACH 8: Changing fields → chord identity
        # =========================================================
        print(f"\n  --- APPROACH 8: Changing field pattern analysis ---")
        # Extract only the changing fields and see if they form a pattern
        changing_indices = []
        for fi in range(11):
            vals = [all_headers[bar][fi] for bar in range(4)]
            if len(set(vals)) > 1:
                changing_indices.append(fi)

        print(f"    Changing field indices: {changing_indices}")

        for fi in changing_indices:
            lo7_vals = [all_headers[bar][fi] & 0x7F for bar in range(4)]
            # What musical interval do these represent?
            diffs = [lo7_vals[b] - lo7_vals[0] for b in range(4)]
            print(f"    F{fi}: vals={lo7_vals}, diffs_from_bar0={diffs}")

            # GT root diffs
            gt_root_diffs = [CHORD_ROOTS_MIDI[b] - CHORD_ROOTS_MIDI[0] for b in range(4)]
            print(f"      GT root diffs: {gt_root_diffs}")

            # Scale factor search
            for scale in range(1, 13):
                scaled = [d * scale for d in gt_root_diffs]
                if [lo7_vals[b] - lo7_vals[0] for b in range(4)] == scaled:
                    print(f"      *** SCALE MATCH: field diffs = root diffs × {scale} ***")

            # Offset + scale search
            for offset in range(-64, 64):
                adjusted = [(v - offset) for v in lo7_vals]
                # Check if adjusted values have same pitch class as roots
                pcs = [a % 12 for a in adjusted]
                target = [CHORD_ROOTS_PC[b] for b in range(4)]
                if pcs == target:
                    print(f"      *** With offset {offset}: pitch classes match root ***")

        # =========================================================
        # APPROACH 9: The F4 mask selects DIFFERENT fields per bar
        # =========================================================
        print(f"\n  --- APPROACH 9: F4 chord mask with changing fields ---")
        for bar in range(4):
            header = all_raw_headers[bar]
            events = bars[bar][1]
            hfields = all_headers[bar]
            lo7 = [f & 0x7F for f in hfields]

            gt = GT_CHORDS[bar]
            print(f"\n    Bar {bar}: GT={[nn(n) for n in gt]}")
            print(f"      Header lo7: {lo7[:6]}")

            # For each event, extract F4 mask
            for ei, evt in enumerate(events[:4]):
                val = int.from_bytes(evt, "big")
                r = (9 * (ei + 1)) % 56
                derot = rot_right(val, r)
                f4 = extract_9bit(derot, 4)
                mask5 = (f4 >> 4) & 0x1F

                selected = [lo7[i] for i in range(5) if mask5 & (1 << (4-i))]
                print(f"      e{ei}: mask={mask5:05b} → selected={selected}")

                # Can selected + offset = GT?
                for offset in range(-48, 48):
                    shifted = [s + offset for s in selected]
                    if sorted(shifted) == sorted(gt):
                        print(f"        *** offset {offset:+d}: selected+{offset} = GT ***")
                    # Also check if sorted selected + different offsets match
                    if len(selected) == len(gt):
                        ind_offsets = [gt[i] - selected[i] for i in range(len(gt))]
                        if len(set(ind_offsets)) <= 2:
                            print(f"        Per-note offsets: {ind_offsets}")

    print("\nDone.")


if __name__ == "__main__":
    main()
