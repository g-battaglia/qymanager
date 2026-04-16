#!/usr/bin/env python3
"""
Deep analysis of Summer RHY1 segment failures.

Key question: WHY do segs 2 and 3 fail the exhaustive R search?
Are the target notes wrong? Is the event structure different?

Approach:
1. Show EXACT GT notes per bar (at 120 BPM capture clock)
2. For each segment, decode at ALL R values and find which notes appear
3. Compare GT notes vs decodable notes to find mismatches
4. Analyze header differences between working and failing bars
"""

import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qymanager.formats.qy70.sysex_parser import SysExParser
from midi_tools.event_decoder import rot_right, extract_9bit, nn


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


def load_gt_rhy1(json_path, bpm=120.0):
    """Load GT RHY1 notes organized by bar."""
    with open(json_path) as f:
        capture = json.load(f)

    bar_dur = 60.0 / bpm * 4
    rhy1_notes = []
    for evt in capture["events"]:
        d = evt["data"]
        if len(d) == 3:
            ch = d[0] & 0x0F
            msg = d[0] & 0xF0
            if ch == 8 and msg == 0x90 and d[2] > 0:
                rhy1_notes.append({"t": evt["t"], "note": d[1], "vel": d[2]})

    if not rhy1_notes:
        return {}

    t0 = rhy1_notes[0]["t"]
    bars = {}
    for n in rhy1_notes:
        dt = n["t"] - t0
        bar_idx = int(dt / bar_dur)
        beat = (dt - bar_idx * bar_dur) / (60.0 / bpm)
        bars.setdefault(bar_idx, []).append({
            "note": n["note"], "vel": n["vel"], "beat": beat
        })
    return bars


def decode_at_r(evt_bytes, r_val):
    val = int.from_bytes(evt_bytes, "big")
    derot = rot_right(val, r_val)
    f0 = extract_9bit(derot, 0)
    note = f0 & 0x7F
    bit8 = (f0 >> 8) & 1
    bit7 = (f0 >> 7) & 1
    rem = derot & 0x3
    vel_code = (bit8 << 3) | (bit7 << 2) | rem
    velocity = max(1, 127 - vel_code * 8)
    f1 = extract_9bit(derot, 1)
    f5 = extract_9bit(derot, 5)
    return {"note": note, "velocity": velocity, "f0": f0, "f1": f1, "f5": f5}


def extract_segments(data):
    """Extract segments from decoded track data (after preamble)."""
    event_data = data[28:]  # Skip metadata + preamble
    segments = []
    prev = 0
    for i, b in enumerate(event_data):
        if b in (0xDC, 0x9E):
            segments.append(event_data[prev:i])
            prev = i + 1
    if prev < len(event_data):
        segments.append(event_data[prev:])
    return segments


def main():
    syx_path = "data/qy70_sysx/P -  Summer - 20231101.syx"
    gt_path = "midi_tools/captured/summer_playback_s25.json"

    data = load_syx_track(syx_path, section=0, track=0)
    gt_bars = load_gt_rhy1(gt_path, bpm=120.0)
    segments = extract_segments(data)

    # =========================================================
    # PART 1: GT notes per bar
    # =========================================================
    print("=" * 80)
    print("PART 1: GROUND TRUTH — What notes does the QY70 actually play per bar?")
    print("=" * 80)

    gt_notes_per_bar = {}
    for bar_idx in sorted(gt_bars.keys())[:8]:
        notes = gt_bars[bar_idx]
        # Group by note number
        by_note = {}
        for n in sorted(notes, key=lambda x: x["beat"]):
            by_note.setdefault(n["note"], []).append(n)

        gt_notes_per_bar[bar_idx] = set(by_note.keys())

        print(f"\n  Bar {bar_idx}: {len(notes)} hits, {len(by_note)} instruments")
        for note_num in sorted(by_note.keys()):
            hits = by_note[note_num]
            vel_str = ",".join(str(h["vel"]) for h in hits)
            beat_str = ",".join(f"{h['beat']:.1f}" for h in hits)
            print(f"    {nn(note_num):>4s}({note_num:2d}): "
                  f"{len(hits)} hits, vel=[{vel_str}], beat=[{beat_str}]")

    # =========================================================
    # PART 2: All decodable notes per segment event
    # =========================================================
    print("\n" + "=" * 80)
    print("PART 2: DECODABLE NOTES — What notes CAN each event produce?")
    print("=" * 80)

    for seg_idx, seg in enumerate(segments):
        if len(seg) < 20:
            print(f"\n  Seg {seg_idx}: too short ({len(seg)}B), skipping")
            continue

        header = seg[:13]
        event_bytes = seg[13:]
        n_events = len(event_bytes) // 7
        trailing = len(event_bytes) % 7

        # Determine which GT bar this corresponds to
        # Seg 0 is usually init, segs 1-N are musical bars
        gt_bar = seg_idx - 1  # rough mapping
        gt_notes = gt_notes_per_bar.get(gt_bar, set())

        print(f"\n  Seg {seg_idx} (≈GT bar {gt_bar}): "
              f"{len(seg)}B, {n_events} events, {trailing}B trailing")
        print(f"    Header: {header.hex()}")
        if gt_notes:
            print(f"    GT instruments: {sorted(gt_notes)} = "
                  f"{', '.join(nn(n) for n in sorted(gt_notes))}")

        for ei in range(min(n_events, 6)):
            evt = event_bytes[ei*7:(ei+1)*7]
            print(f"\n    e{ei}: {evt.hex()}")

            # Find ALL valid drum notes (13-87) for each R
            note_to_r = {}  # note -> [(R, velocity, f5)]
            for r in range(56):
                d = decode_at_r(evt, r)
                if 13 <= d["note"] <= 87:
                    note_to_r.setdefault(d["note"], []).append(
                        (r, d["velocity"], d["f5"]))

            # Show notes that match GT
            gt_match = sorted(n for n in note_to_r if n in gt_notes)
            other = sorted(n for n in note_to_r if n not in gt_notes)

            if gt_match:
                print(f"      GT MATCH: {', '.join(f'{nn(n)}({n})' for n in gt_match)}")
                for n in gt_match:
                    entries = note_to_r[n]
                    for r, vel, f5 in entries[:3]:
                        print(f"        R={r:2d}: {nn(n):>4s} vel={vel:3d} f5={f5:3d}")
            else:
                print(f"      GT MATCH: NONE!")

            # Show a few other candidate notes
            if other:
                top_others = other[:8]
                print(f"      Other notes ({len(other)} total): "
                      f"{', '.join(f'{nn(n)}({n})' for n in top_others)}")

    # =========================================================
    # PART 3: Header comparison — working vs failing segments
    # =========================================================
    print("\n" + "=" * 80)
    print("PART 3: HEADER ANALYSIS — Working vs Failing segments")
    print("=" * 80)

    # Decode each header as 9-bit fields
    for seg_idx, seg in enumerate(segments):
        if len(seg) < 13:
            continue

        header = seg[:13]
        event_bytes = seg[13:]
        n_events = len(event_bytes) // 7

        # Decode 13 bytes = 104 bits as 11 × 9-bit fields + 5 remaining
        val = int.from_bytes(header, "big")
        fields = []
        for i in range(11):
            shift = 104 - 9 * (i + 1)
            f = (val >> shift) & 0x1FF
            fields.append(f)
        rem = val & 0x1F

        # Determine if this seg works with standard lane R
        gt_bar = seg_idx - 1
        gt_notes = gt_notes_per_bar.get(gt_bar, set())

        # Quick check: can R=[9,22,12,53] decode all GT notes?
        works = "N/A"
        if n_events >= 4 and gt_notes:
            standard_r = [9, 22, 12, 53]
            decoded_notes = set()
            for ei in range(4):
                evt = event_bytes[ei*7:(ei+1)*7]
                d = decode_at_r(evt, standard_r[ei])
                decoded_notes.add(d["note"])
            match = decoded_notes & gt_notes
            works = f"{len(match)}/{len(gt_notes)}" if gt_notes else "?"

        # Can ANY R combo decode all GT notes?
        any_works = "N/A"
        if n_events >= 4 and gt_notes:
            # For each event, which GT notes are reachable?
            reachable = []
            for ei in range(min(4, n_events)):
                evt = event_bytes[ei*7:(ei+1)*7]
                reachable_notes = set()
                for r in range(56):
                    d = decode_at_r(evt, r)
                    if d["note"] in gt_notes:
                        reachable_notes.add(d["note"])
                reachable.append(reachable_notes)

            all_reachable = set()
            for s in reachable:
                all_reachable |= s
            missing = gt_notes - all_reachable
            any_works = f"reachable={sorted(all_reachable)}, missing={sorted(missing)}"

        print(f"\n  Seg {seg_idx}: std_R={works}, {any_works}")
        print(f"    Header hex: {header.hex()}")
        print(f"    9-bit fields: {fields}")
        print(f"    Remaining: {rem:05b} ({rem})")

    # =========================================================
    # PART 4: Byte-level difference between working and failing e0
    # =========================================================
    print("\n" + "=" * 80)
    print("PART 4: EVENT BYTE FORENSICS — Why can't Seg 2/3 produce note 38?")
    print("=" * 80)

    # For each segment, show what R=22 decodes to for e1 (expected snare)
    # and what the closest note to 38 is
    for seg_idx, seg in enumerate(segments):
        if len(seg) < 27:  # Need at least header + 2 events
            continue

        event_bytes = seg[13:]
        if len(event_bytes) < 14:
            continue

        evt_e1 = event_bytes[7:14]  # Second event (e1)

        print(f"\n  Seg {seg_idx} e1: {evt_e1.hex()}")

        # Decode at R=22 (expected snare R)
        d22 = decode_at_r(evt_e1, 22)
        print(f"    R=22: note={d22['note']} ({nn(d22['note'])}) vel={d22['velocity']}")

        # What R gives note closest to 38?
        closest_r = None
        closest_diff = 999
        for r in range(56):
            d = decode_at_r(evt_e1, r)
            diff = abs(d["note"] - 38)
            if diff < closest_diff:
                closest_diff = diff
                closest_r = (r, d["note"], d["velocity"])

        if closest_r:
            r, note, vel = closest_r
            print(f"    Closest to 38: R={r} → note={note} ({nn(note)}) "
                  f"vel={vel}, diff={closest_diff}")

        # Show ALL R values that give notes 35-42 (drum range)
        drum_range = []
        for r in range(56):
            d = decode_at_r(evt_e1, r)
            if 35 <= d["note"] <= 45:
                drum_range.append((r, d["note"], d["velocity"]))
        if drum_range:
            print(f"    Notes in 35-45 range:")
            for r, note, vel in drum_range:
                marker = " ← TARGET" if note == 38 else ""
                print(f"      R={r:2d}: {nn(note):>4s}({note}) vel={vel}{marker}")
        else:
            print(f"    NO notes in 35-45 range at any R!")

    # =========================================================
    # PART 5: Binary pattern analysis — what makes 38 impossible?
    # =========================================================
    print("\n" + "=" * 80)
    print("PART 5: WHY IS NOTE 38 IMPOSSIBLE? — Binary analysis")
    print("=" * 80)

    # Note 38 = 0b0100110, needs F0[6:0] = 0b0100110
    # With vel_code encoding, F0 = (bit8:bit7:note) where note = F0[6:0]
    # So we need the bottom 7 bits of F0 to be 38 = 0b0100110
    # F0 is the top 9 bits of the derotated 56-bit value

    print("\n  Note 38 requires F0[6:0] = 0b0100110 (0x26)")
    print("  This means bits 47-53 of derotated value must be 0100110")
    print()

    for seg_idx, seg in enumerate(segments):
        if len(seg) < 27:
            continue
        event_bytes = seg[13:]
        if len(event_bytes) < 14:
            continue

        for ei in range(min(4, len(event_bytes) // 7)):
            evt = event_bytes[ei*7:(ei+1)*7]
            val = int.from_bytes(evt, "big")

            # For each R, extract the bits that would become F0[6:0]
            can_produce_38 = False
            for r in range(56):
                derot = rot_right(val, r)
                f0_lo7 = (derot >> 47) & 0x7F
                if f0_lo7 == 38:
                    can_produce_38 = True
                    break

            if not can_produce_38:
                print(f"  Seg {seg_idx} e{ei}: CANNOT produce note 38 at ANY R!")
                # Show all possible F0[6:0] values
                f0_lo7_vals = set()
                for r in range(56):
                    derot = rot_right(val, r)
                    f0_lo7_vals.add((derot >> 47) & 0x7F)
                # Which target notes are reachable?
                targets_reachable = {v for v in f0_lo7_vals if v in {36, 38, 42, 46}}
                print(f"    Reachable drum targets: {sorted(targets_reachable)}")
                print(f"    Total unique F0[6:0] values: {len(f0_lo7_vals)}")

    print("\n\nDone.")


if __name__ == "__main__":
    main()
