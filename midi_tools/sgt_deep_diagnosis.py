#!/usr/bin/env python3
"""Deep diagnosis of SGT decoder failures.

Dumps raw bar headers, rotation candidates, and field values
for each track to understand why decoded notes don't match capture.
"""

import sys
import os
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from midi_tools.event_decoder import (
    get_track_data, extract_bars, classify_encoding,
    decode_header_notes, header_to_midi_notes, rot_right, extract_9bit,
    SECTION_NAMES, TRACK_NAMES, R,
)

SYX_PATH = "tests/fixtures/QY70_SGT.syx"

# Ground truth from capture
GROUND_TRUTH = {
    0: {"label": "RHY1/ch9",  "notes": [36, 38, 42, 44, 54, 68]},
    1: {"label": "RHY2/ch10", "notes": [37]},
    2: {"label": "BASS/ch12", "notes": [29, 31, 33, 38]},
    4: {"label": "CHD2/ch14", "notes": [65, 67, 69, 71, 72, 74, 76, 77]},
    5: {"label": "PAD/ch11",  "notes": [34, 37]},
    6: {"label": "PHR1/ch15", "notes": [65, 67, 69, 71, 72, 74, 76, 77]},
}


def try_all_rotations(evt_bytes, target_notes, max_r=56):
    """Try all rotation values and find which ones produce target notes."""
    val = int.from_bytes(evt_bytes, "big")
    matches = []
    for r in range(max_r):
        derot = rot_right(val, r)
        f0 = extract_9bit(derot, 0)
        note = f0 & 0x7F
        if note in target_notes:
            f1 = extract_9bit(derot, 1)
            f2 = extract_9bit(derot, 2)
            f3 = extract_9bit(derot, 3)
            f4 = extract_9bit(derot, 4)
            f5 = extract_9bit(derot, 5)
            matches.append({
                "R": r, "note": note, "f0": f0,
                "f1": f1, "f2": f2, "f3": f3,
                "f4": f4, "f5": f5,
                "rem": derot & 0x3,
            })
    return matches


def analyze_slot(slot, section=0):
    """Deep analysis of one slot in one section."""
    gt = GROUND_TRUTH.get(slot, {})
    label = gt.get("label", TRACK_NAMES[slot])
    target = set(gt.get("notes", []))

    data = get_track_data(SYX_PATH, section, slot)
    if len(data) < 28:
        print(f"\n  No data for slot {slot} section {section}")
        return

    preamble, bars = extract_bars(data)
    encoding = classify_encoding(preamble)

    print(f"\n{'='*70}")
    print(f"  SLOT {slot} ({label}) — Section {SECTION_NAMES[section]}")
    print(f"  Encoding: {encoding}, Preamble: {preamble.hex()}")
    print(f"  Target notes: {sorted(target)}")
    print(f"  Bars: {len(bars)}, Data length: {len(data)}")
    print(f"{'='*70}")

    # Dump first 24 bytes of raw track data for preamble analysis
    print(f"\n  Raw header (first 28 bytes):")
    for i in range(0, min(28, len(data)), 16):
        chunk = data[i:i+16]
        hex_str = ' '.join(f'{b:02X}' for b in chunk)
        print(f"    0x{i:03X}: {hex_str}")

    for bar_idx, (header, events) in enumerate(bars):
        if bar_idx >= 3:  # Limit to first 3 bars
            print(f"\n  ... {len(bars) - 3} more bars")
            break

        header_fields = decode_header_notes(header)
        midi_notes = header_to_midi_notes(header_fields)

        print(f"\n  --- Bar {bar_idx} ---")
        print(f"  Header hex: {header.hex()}")
        print(f"  Header 9-bit fields: {header_fields}")
        print(f"  Header MIDI notes (lo7): {midi_notes}")

        # Check if header notes match target
        header_match = set(midi_notes) & target
        if header_match:
            print(f"  ★ Header notes in target: {sorted(header_match)}")

        for evt_idx, evt in enumerate(events):
            if evt_idx >= 6:  # Limit events per bar
                print(f"    ... {len(events) - 6} more events")
                break

            # Current decoder: R=9*(i+1)
            val = int.from_bytes(evt, "big")
            r_cum = (9 * (evt_idx + 1)) % 56
            derot_cum = rot_right(val, r_cum)
            f0_cum = extract_9bit(derot_cum, 0)
            note_cum = f0_cum & 0x7F

            print(f"\n    Event {evt_idx}: {evt.hex()}")
            print(f"      R={r_cum:2d} (cum): F0=0x{f0_cum:03X} note={note_cum:3d} "
                  f"{'✓' if note_cum in target else '✗'}")

            # Try R=47
            derot_47 = rot_right(val, 47)
            f0_47 = extract_9bit(derot_47, 0)
            note_47 = f0_47 & 0x7F
            print(f"      R=47:     F0=0x{f0_47:03X} note={note_47:3d} "
                  f"{'✓' if note_47 in target else '✗'}")

            # Find which R values produce target notes
            matches = try_all_rotations(evt, target)
            if matches:
                for m in matches[:4]:
                    f_str = f"f1={m['f1']:03X} f2={m['f2']:03X} f3={m['f3']:03X}"
                    print(f"      ★ R={m['R']:2d}: note={m['note']:3d} "
                          f"f0=0x{m['f0']:03X} {f_str}")
            else:
                print(f"      No R produces target notes!")

    # Summary: what R values work across all events?
    print(f"\n  --- R-value analysis (all events, all bars) ---")
    r_hit_count = Counter()
    total_events = 0
    for bar_idx, (header, events) in enumerate(bars):
        for evt_idx, evt in enumerate(events):
            total_events += 1
            matches = try_all_rotations(evt, target)
            for m in matches:
                r_hit_count[m["R"]] += 1

    if r_hit_count:
        print(f"  Total events: {total_events}")
        print(f"  R values producing target notes (top 10):")
        for r_val, count in r_hit_count.most_common(10):
            pct = count / total_events * 100
            print(f"    R={r_val:2d}: {count:3d}/{total_events} events ({pct:.0f}%)")
    else:
        print(f"  ⚠ NO rotation value produces target notes for ANY event!")
        # This means the note encoding is fundamentally different
        # Try looking at different field positions
        print(f"\n  Trying alternative field extraction...")
        for bar_idx, (header, events) in enumerate(bars[:1]):
            for evt_idx, evt in enumerate(events[:4]):
                val = int.from_bytes(evt, "big")
                print(f"\n    Event {evt_idx}: {evt.hex()} (val=0x{val:014X})")
                for r in [0, 9, 18, 27, 36, 45, 47]:
                    derot = rot_right(val, r)
                    fields = [extract_9bit(derot, i) for i in range(6)]
                    lo7s = [f & 0x7F for f in fields]
                    hits = [n for n in lo7s if n in target]
                    rem = derot & 0x3
                    print(f"      R={r:2d}: fields={[f'0x{f:03X}' for f in fields]} "
                          f"lo7={lo7s} rem={rem} "
                          f"{'★ ' + str(hits) if hits else ''}")


def main():
    print("=" * 70)
    print("  SGT DEEP DIAGNOSIS — Why decoder notes don't match capture")
    print("=" * 70)

    # Analyze each slot for MAIN-A
    for slot in [0, 4, 6, 2, 1, 5]:
        analyze_slot(slot, section=0)


if __name__ == "__main__":
    main()
