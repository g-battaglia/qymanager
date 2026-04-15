#!/usr/bin/env python3
"""Timing-constrained solver: use capture timing to match events to notes.

The ground truth capture tells us EXACTLY which notes play when.
The SysEx data encodes these notes in some order.
If events are chronological (like known_pattern), we can match them.

Key insight: at 151 BPM, one bar = 1.589s.
First bar notes (from capture):
  t=0.020: n36 v127 (kick)
  t=0.021: n42 v32, n54 v32 (hi-hat + tambourine)
  t=0.022: n68 v32 (agogo)
  t=0.119: n42 v32
  t=0.219: n42 v32, n44 v127, n54 v32
  t=0.319: n42 v32
  t=0.418: n36 v127
  ... (more notes in bar 1)

If bar 1 in the SysEx has N events, those N events should decode to
the first N notes in the capture (assuming chronological order).

For user_style_live.syx bar 0: 4 events → should decode to first 4 notes.
But the capture has simultaneous notes! So 4 events might encode 4
time-positions or 4 individual notes.

Strategy: for each possible assignment of target notes to events,
find the rotation that works, then verify consistency.

Session 20.
"""

import json
import os
import sys
from itertools import product
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from qymanager.formats.qy70.sysex_parser import SysExParser

TARGET_NOTES = {36, 38, 42, 44, 54, 68}

def rot_right(val, shift, width=56):
    shift = shift % width
    return ((val >> shift) | (val << (width - shift))) & ((1 << width) - 1)

def extract_9bit(val, field_idx, width=56):
    shift = width - (field_idx + 1) * 9
    if shift < 0:
        return -1
    return (val >> shift) & 0x1FF

def get_track_data(syx_path, section, track):
    parser = SysExParser()
    messages = parser.parse_file(syx_path)
    al = section * 8 + track
    data = b""
    for m in messages:
        if m.is_style_data and m.address_low == al:
            if m.decoded_data is not None:
                data += m.decoded_data
    return data

def extract_bars(data):
    """DC-only split."""
    if len(data) < 28:
        return []
    event_data = data[28:]
    dc_pos = [i for i, b in enumerate(event_data) if b == 0xDC]
    segments = []
    prev = 0
    for dp in dc_pos:
        segments.append(event_data[prev:dp])
        prev = dp + 1
    segments.append(event_data[prev:])

    bars = []
    for seg in segments:
        if len(seg) >= 20:
            header = seg[:13]
            events = []
            for i in range((len(seg) - 13) // 7):
                evt = seg[13 + i*7 : 13 + (i+1)*7]
                if len(evt) == 7:
                    events.append(evt)
            bars.append((header, events))
    return bars


def load_capture_notes(capture_path, channel=9, bpm=151):
    """Load captured notes and organize by bar."""
    with open(capture_path) as f:
        data = json.load(f)

    ch_key = str(channel)
    if ch_key not in data.get('channels', {}):
        return []

    ch = data['channels'][ch_key]

    # We need ALL notes, not just first_10
    # The capture JSON might have all notes in a different field
    # For now, use first_10 and check if there's a full list
    notes = ch.get('all_notes', ch.get('notes', ch.get('first_10', [])))

    # Organize by bar
    beat_duration = 60.0 / bpm
    bar_duration = beat_duration * 4

    bars = {}
    for n in notes:
        bar_idx = int(n['t'] / bar_duration)
        if bar_idx not in bars:
            bars[bar_idx] = []
        bars[bar_idx].append(n)

    return notes, bars


def solve_bar(bar_events, expected_notes_in_order):
    """For a bar with N events and N expected notes, find R for each event.

    Try all possible note assignments and find consistent R values.
    """
    n = len(bar_events)
    if n == 0 or not expected_notes_in_order:
        return None

    # For each event, compute which R gives which note
    event_r_map = []  # event_idx -> {note: [R_values]}
    for i, evt in enumerate(bar_events):
        val = int.from_bytes(evt, "big")
        r_map = {}
        for r in range(56):
            derot = rot_right(val, r)
            f0 = extract_9bit(derot, 0)
            note = f0 & 0x7F
            if note in TARGET_NOTES:
                if note not in r_map:
                    r_map[note] = []
                r_map[note].append(r)
        event_r_map.append(r_map)

    # Try assigning expected notes to events (in order, with possible gaps)
    # If we have 4 events and 4 expected notes, try all 4! permutations
    # Actually, if events are chronological, notes should also be in order

    # Direct assignment: event i → expected_notes[i]
    if n <= len(expected_notes_in_order):
        assignments = []
        for i in range(n):
            target = expected_notes_in_order[i]
            if target in event_r_map[i]:
                assignments.append((i, target, event_r_map[i][target]))
            else:
                assignments.append((i, target, []))  # No valid R

        return assignments

    return None


def main():
    cap_dir = os.path.join(os.path.dirname(__file__), "captured")
    syx_path = os.path.join(cap_dir, "user_style_live.syx")
    capture_path = os.path.join(cap_dir, "sgt_full_capture.json")

    if not os.path.exists(syx_path) or not os.path.exists(capture_path):
        print("Required files not found")
        return

    data = get_track_data(syx_path, 0, 0)
    bars = extract_bars(data)

    # Load capture
    with open(capture_path) as f:
        capture = json.load(f)

    ch9 = capture['channels']['9']
    bpm = capture['bpm']
    beat_dur = 60.0 / bpm
    bar_dur = beat_dur * 4

    print(f"=== TIMING-CONSTRAINED SOLVER ===")
    print(f"BPM: {bpm}, Bar duration: {bar_dur:.3f}s")
    print(f"SysEx bars: {len(bars)}")
    print(f"Total captured notes: {ch9['note_count']}")
    print(f"Unique notes: {ch9['unique_notes']}")

    # Extract first complete loop of captured notes
    # Pattern has 4 bars = 6.358s at 151 BPM
    # With 6 sections... it's unclear how many bars the style has

    # Get all notes from first_10 (that's all we have in the JSON)
    first_notes = ch9['first_10']

    # Extend with estimated bar structure
    # First bar: t=0 to bar_dur
    bar0_notes = [n for n in first_notes if n['t'] < bar_dur]
    bar1_notes = [n for n in first_notes if bar_dur <= n['t'] < 2*bar_dur]

    print(f"\nFirst bar notes ({len(bar0_notes)}):")
    for n in bar0_notes:
        beat = n['t'] / beat_dur
        print(f"  t={n['t']:.4f} beat={beat:.2f} note={n['note']} vel={n['vel']}")

    print(f"\nSecond bar notes ({len(bar1_notes)}):")
    for n in bar1_notes:
        beat = (n['t'] - bar_dur) / beat_dur
        print(f"  t={n['t']:.4f} beat={beat:.2f} note={n['note']} vel={n['vel']}")

    # SysEx bar 0 has 4 events. First bar has ~10 notes.
    # So 1 event ≠ 1 note. Events might represent "time slots" not individual notes.
    #
    # From known_pattern, each event has:
    # - F0 = note (7 bits) + velocity (2 bits in F0 + 2 in remainder)
    # - F5 = timing
    # So each event IS one note.
    #
    # But bar 0 has only 4 events for ~10 notes. This means:
    # 1. The 4 events might be chord members at beat 1 (36,42,54,68 all play simultaneously)
    # 2. Or the bar has more than 4 events (wrong segmentation)

    # At beat 1, notes 36, 42, 54, 68 all trigger (t≈0.02s).
    # That's EXACTLY 4 notes = 4 events!
    # So bar 0 might encode just beat 1's simultaneous notes.

    beat1_notes = [n for n in bar0_notes if n['t'] < 0.05]
    print(f"\nBeat 1 notes (t<0.05s): {[n['note'] for n in beat1_notes]}")
    print(f"SysEx bar 0 events: {len(bars[0][1])}")

    if len(beat1_notes) == len(bars[0][1]):
        print(f"\n*** MATCH: Beat 1 has {len(beat1_notes)} notes = {len(bars[0][1])} events! ***")
        print(f"Expected notes: {sorted([n['note'] for n in beat1_notes])}")

        # Try to assign notes to events
        expected = sorted([n['note'] for n in beat1_notes])
        result = solve_bar(bars[0][1], expected)

        if result:
            print(f"\nDirect assignment (sorted by note):")
            for i, target, r_values in result:
                evt = bars[0][1][i]
                r_str = ",".join(str(r) for r in r_values[:5])
                print(f"  E{i} [{evt.hex()}] → target n{target}: Rs=[{r_str}]")

        # Also try assignment by capture order (time, then note)
        cap_order = sorted(beat1_notes, key=lambda n: (n['t'], n['note']))
        expected_cap = [n['note'] for n in cap_order]
        print(f"\nCapture order: {expected_cap}")
        result2 = solve_bar(bars[0][1], expected_cap)
        if result2:
            print(f"\nCapture-order assignment:")
            for i, target, r_values in result2:
                evt = bars[0][1][i]
                r_str = ",".join(str(r) for r in r_values[:5])
                print(f"  E{i} [{evt.hex()}] → target n{target}: Rs=[{r_str}]")

        # Try ALL permutations of 4 notes → 4 events
        from itertools import permutations
        note_list = [n['note'] for n in beat1_notes]

        print(f"\n=== ALL PERMUTATIONS ===")
        best_r_pattern = None
        for perm in permutations(note_list):
            # For each permutation, find R for each event→note pair
            r_per_event = []
            valid = True
            for i, target in enumerate(perm):
                evt = bars[0][1][i]
                val = int.from_bytes(evt, "big")
                found_r = []
                for r in range(56):
                    derot = rot_right(val, r)
                    note = extract_9bit(derot, 0) & 0x7F
                    if note == target:
                        found_r.append(r)
                if not found_r:
                    valid = False
                    break
                r_per_event.append(found_r)

            if not valid:
                continue

            # Check if R values follow any pattern
            # For each combination of valid Rs, check if linear
            from itertools import product as iterprod
            for r_combo in iterprod(*r_per_event):
                # Check: R = a*(i+1) + b mod 56
                for a in [9, 7, 11, 13, 3, 5]:
                    for b in range(56):
                        expected_rs = [(a*(i+1) + b) % 56 for i in range(4)]
                        if list(r_combo) == expected_rs:
                            print(f"  FOUND: perm={perm} R=({a}*(i+1)+{b})%56 → Rs={list(r_combo)}")

                # Also check: constant R
                if len(set(r_combo)) == 1:
                    print(f"  CONST R={r_combo[0]}: perm={perm}")

                # Check: R=9*(i+c) for various c
                for c in range(56):
                    expected_rs = [(9*(i+c)) % 56 for i in range(4)]
                    if list(r_combo) == expected_rs:
                        print(f"  FOUND: perm={perm} R=9*(i+{c})%56 → Rs={list(r_combo)}")

    # Also analyze bars 1-5 similarly
    print(f"\n{'='*60}")
    print("BAR-BY-BAR: How many capture notes match event count?")
    print(f"{'='*60}")

    for bar_idx, (header, events) in enumerate(bars):
        print(f"\n  Bar {bar_idx}: {len(events)} events")
        # What time range does this bar cover?
        # We don't know which bar in the pattern this corresponds to
        # But we can check if event count matches any bar's note count


if __name__ == "__main__":
    main()
