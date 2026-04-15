#!/usr/bin/env python3
"""Test: what if DC (0xDC) is NOT a delimiter in dense drum data?

Hypothesis: for dense data, DC bytes are part of regular 7-byte events.
The data structure is simply:
  13-byte bar header + N × 7-byte events (continuous, no delimiters)

Evidence:
  - known_pattern: 62 bytes, no DC at all, 13 + 49 = 7 events ✓
  - SGT: 356 bytes, 6 DC bytes, but 356 - 13 = 343 = 49 × 7 exactly!
  - Previous DC-only split: 36 events (misses 13 events from false headers)

Session 20.
"""

import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from qymanager.formats.qy70.sysex_parser import SysExParser

TARGET_NOTES = {36, 38, 42, 44, 54, 68}

def rot_right(val: int, shift: int, width: int = 56) -> int:
    shift = shift % width
    return ((val >> shift) | (val << (width - shift))) & ((1 << width) - 1)

def extract_9bit(val: int, field_idx: int, width: int = 56) -> int:
    shift = width - (field_idx + 1) * 9
    if shift < 0:
        return -1
    return (val >> shift) & 0x1FF

def get_track_data(syx_path: str, section: int, track: int) -> bytes:
    parser = SysExParser()
    messages = parser.parse_file(syx_path)
    al = section * 8 + track
    data = b""
    for m in messages:
        if m.is_style_data and m.address_low == al:
            if m.decoded_data is not None:
                data += m.decoded_data
    return data


def test_no_delimiters(syx_path: str, section: int = 0, track: int = 0):
    """Treat all data after the initial 13-byte header as continuous 7-byte events."""
    data = get_track_data(syx_path, section, track)
    if not data:
        print("No data")
        return

    event_data = data[28:]  # Skip 28-byte track header
    print(f"=== NO-DELIMITER TEST ===")
    print(f"File: {os.path.basename(syx_path)}, Section {section}, Track {track}")
    print(f"Event data: {len(event_data)} bytes")
    print(f"DC bytes at: {[i for i, b in enumerate(event_data) if b == 0xDC]}")
    print(f"9E bytes at: {[i for i, b in enumerate(event_data) if b == 0x9E]}")

    # Method A: First 13 bytes = header, rest = continuous events
    header_a = event_data[:13]
    raw_events_a = event_data[13:]
    n_events_a = len(raw_events_a) // 7
    remainder_a = len(raw_events_a) % 7
    print(f"\nMethod A: 13-byte header + continuous events")
    print(f"  Header: {header_a.hex()}")
    print(f"  Events: {n_events_a} ({len(raw_events_a)} bytes, rem={remainder_a})")

    # Method B: First 14 bytes = header (13 + 1 trailing), next 13 = bar header, rest = events
    # This matches the structure where byte 14 is a DC "section separator"
    if len(event_data) > 27:
        prefix = event_data[:14]  # 14-byte prefix before first DC
        has_dc_at_14 = (len(event_data) > 14 and event_data[14] == 0xDC)
        after_dc = event_data[15:] if has_dc_at_14 else event_data[14:]
        # After DC, first 13 bytes = bar header
        header_b = after_dc[:13]
        raw_events_b = after_dc[13:]
        n_events_b = len(raw_events_b) // 7
        remainder_b = len(raw_events_b) % 7
        print(f"\nMethod B: 14-byte prefix + DC + 13-byte header + continuous events")
        print(f"  Prefix: {prefix.hex()}")
        print(f"  DC at pos 14: {has_dc_at_14}")
        print(f"  Bar header: {header_b.hex()}")
        print(f"  Events: {n_events_b} ({len(raw_events_b)} bytes, rem={remainder_b})")

    # Method C: Skip ALL DC bytes, then 13 header + events
    no_dc = bytes(b for b in event_data if b != 0xDC)
    header_c = no_dc[:13]
    raw_events_c = no_dc[13:]
    n_events_c = len(raw_events_c) // 7
    remainder_c = len(raw_events_c) % 7
    print(f"\nMethod C: Remove all DC bytes, then 13-header + events")
    print(f"  After removing DC: {len(no_dc)} bytes")
    print(f"  Events: {n_events_c} ({len(raw_events_c)} bytes, rem={remainder_c})")

    # Method D: Skip ALL DC and 9E bytes, then 13 header + events
    no_delim = bytes(b for b in event_data if b not in (0xDC, 0x9E))
    header_d = no_delim[:13]
    raw_events_d = no_delim[13:]
    n_events_d = len(raw_events_d) // 7
    remainder_d = len(raw_events_d) % 7
    print(f"\nMethod D: Remove all DC+9E bytes, then 13-header + events")
    print(f"  After removing DC+9E: {len(no_delim)} bytes")
    print(f"  Events: {n_events_d} ({len(raw_events_d)} bytes, rem={remainder_d})")

    # NOW test each method with R=9*(i+1)
    methods = {
        'A (13-hdr continuous)': (raw_events_a, n_events_a),
        'B (prefix+DC+13-hdr)': (raw_events_b, n_events_b),
        'C (no-DC, 13-hdr)': (raw_events_c, n_events_c),
        'D (no-DC-9E, 13-hdr)': (raw_events_d, n_events_d),
    }

    for method_name, (raw_events, n_events) in methods.items():
        hits = 0
        ctrl_count = 0
        print(f"\n{'='*60}")
        print(f"Method {method_name}: R=9*(i+1) on {n_events} events")
        print(f"{'='*60}")

        note_counts = Counter()
        for i in range(n_events):
            evt = raw_events[i*7:(i+1)*7]
            val = int.from_bytes(evt, "big")

            r = (9 * (i + 1)) % 56
            derot = rot_right(val, r)
            f0 = extract_9bit(derot, 0)
            note = f0 & 0x7F

            # Velocity
            f0_bit8 = (f0 >> 8) & 1
            f0_bit7 = (f0 >> 7) & 1
            remainder = derot & 0x3
            vel_code = (f0_bit8 << 3) | (f0_bit7 << 2) | remainder
            vel = max(1, 127 - vel_code * 8)

            hit = note in TARGET_NOTES
            is_ctrl = note > 87
            if hit:
                hits += 1
                note_counts[note] += 1
            if is_ctrl:
                ctrl_count += 1

            marker = "✓" if hit else ("CTRL" if is_ctrl else "")
            # Show DC positions in the event
            dc_in_evt = [j for j in range(7) if evt[j] == 0xDC]
            dc_str = f" DC@{dc_in_evt}" if dc_in_evt else ""

            if i < 20 or hit or is_ctrl:
                print(f"  E{i:3d} [{evt.hex()}] R={r:2d} → n{note:3d} v{vel:3d} {marker}{dc_str}")
            elif i == 20:
                print(f"  ... (showing only hits and first 20)")

        pct = hits * 100 // max(n_events, 1)
        random_pct = 6 * 100 // 128
        print(f"\n  HITS: {hits}/{n_events} = {pct}% (random: {random_pct}%)")
        print(f"  Ctrl events: {ctrl_count}")
        if note_counts:
            print(f"  Notes found: {dict(note_counts)}")

    # Also compare with the ORIGINAL DC-split approach for reference
    print(f"\n{'='*60}")
    print("ORIGINAL (DC-split, per-segment R): for comparison")
    print(f"{'='*60}")

    dc_pos = [i for i, b in enumerate(event_data) if b == 0xDC]
    segments = []
    prev = 0
    for dp in dc_pos:
        segments.append(event_data[prev:dp])
        prev = dp + 1
    segments.append(event_data[prev:])

    total_hits = 0
    total_events = 0
    for seg_idx, seg in enumerate(segments):
        if len(seg) < 20:
            continue
        header = seg[:13]
        for i in range((len(seg) - 13) // 7):
            evt = seg[13 + i * 7: 13 + (i + 1) * 7]
            if len(evt) != 7:
                continue
            val = int.from_bytes(evt, "big")
            r = (9 * (i + 1)) % 56
            derot = rot_right(val, r)
            note = extract_9bit(derot, 0) & 0x7F
            if note in TARGET_NOTES:
                total_hits += 1
            total_events += 1

    print(f"  DC-split per-segment: {total_hits}/{total_events} = {total_hits*100//max(total_events,1)}%")


def test_known_pattern_no_delimiters(syx_path: str):
    """Verify: known_pattern should work identically with no-delimiter approach."""
    data = get_track_data(syx_path, 0, 0)
    if not data:
        return

    event_data = data[28:]
    print(f"\n{'='*60}")
    print(f"KNOWN_PATTERN VERIFICATION (no delimiters)")
    print(f"{'='*60}")
    print(f"Event data: {len(event_data)} bytes")
    print(f"DC bytes: {[i for i, b in enumerate(event_data) if b == 0xDC]}")

    # 13 header + events
    header = event_data[:13]
    raw = event_data[13:]
    n = len(raw) // 7

    print(f"Header: {header.hex()}")
    print(f"Events: {n} ({len(raw)} bytes, rem={len(raw)%7})")

    hits = 0
    for i in range(n):
        evt = raw[i*7:(i+1)*7]
        val = int.from_bytes(evt, "big")
        r = (9 * (i + 1)) % 56
        derot = rot_right(val, r)
        f0 = extract_9bit(derot, 0)
        note = f0 & 0x7F

        # Known pattern events: check if note is in KNOWN target set
        # Session 14: notes were 36, 44, 38, 44, etc.
        known_targets = {36, 38, 42, 44, 54, 68, 49}  # Include all possible
        hit = note in known_targets
        if hit:
            hits += 1
        print(f"  E{i}: [{evt.hex()}] R={(9*(i+1))%56:2d} → note {note} {'✓' if hit else ''}")

    print(f"  Hits: {hits}/{n}")


if __name__ == "__main__":
    cap_dir = os.path.join(os.path.dirname(__file__), "captured")

    kp_path = os.path.join(cap_dir, "known_pattern.syx")
    if os.path.exists(kp_path):
        test_known_pattern_no_delimiters(kp_path)

    for name in ["QY70_SGT.syx", "user_style_live.syx", "ground_truth_style.syx"]:
        path = os.path.join(cap_dir, name)
        if os.path.exists(path):
            test_no_delimiters(path, section=0, track=0)
            break
