#!/usr/bin/env python3
"""Analyze message boundaries vs rotation failures.

Hypothesis: rotation resets at SysEx message boundaries (every 128 decoded bytes).
This would explain why R=9*(i+1) works for known_pattern (single message)
but fails for SGT (multiple messages).

Also test: does per-MESSAGE event indexing fix the rotation?

Session 20.
"""

import json
import os
import sys
from typing import List, Tuple

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


def analyze_message_boundaries(syx_path: str, section: int = 0, track: int = 0):
    """Map SysEx message boundaries onto the event structure."""
    parser = SysExParser()
    messages = parser.parse_file(syx_path)
    al = section * 8 + track

    track_msgs = [m for m in messages if m.is_style_data and m.address_low == al]
    print(f"=== MESSAGE BOUNDARY ANALYSIS ===")
    print(f"File: {os.path.basename(syx_path)}")
    print(f"Section {section}, Track {track} (AL={al})")
    print(f"Messages for this track: {len(track_msgs)}")

    # Show per-message data sizes
    total_offset = 0
    msg_boundaries = []
    for i, m in enumerate(track_msgs):
        size = len(m.decoded_data) if m.decoded_data else 0
        msg_boundaries.append((total_offset, total_offset + size))
        print(f"  Msg {i}: {size} bytes (offset {total_offset}-{total_offset+size-1})")
        total_offset += size

    # Concatenate all data
    data = b""
    for m in track_msgs:
        if m.decoded_data:
            data += m.decoded_data

    print(f"\nTotal decoded: {len(data)} bytes")
    print(f"Header (first 28): {data[:28].hex()}")
    print(f"Preamble: {data[24:28].hex()}")

    # Event data starts at byte 28
    event_data = data[28:]
    print(f"Event data: {len(event_data)} bytes")

    # Find DC delimiters
    dc_positions = [i for i, b in enumerate(event_data) if b == 0xDC]
    print(f"DC delimiters at: {dc_positions}")

    # Map message boundaries into event data space
    print(f"\nMessage boundaries in event data space:")
    for i, (start, end) in enumerate(msg_boundaries):
        evt_start = max(0, start - 28)
        evt_end = end - 28
        print(f"  Msg {i}: event_data[{evt_start}:{evt_end}]")
        # Which DC-delimited segments does this cross?
        for dc_idx, dc_pos in enumerate(dc_positions):
            if evt_start <= dc_pos < evt_end:
                print(f"    Contains DC delimiter at event_data[{dc_pos}]")

    # --- Parse events with message awareness ---
    print(f"\n{'='*70}")
    print("PER-MESSAGE EVENT INDEXING")
    print(f"{'='*70}")

    # Build event list with message association
    segments = []
    prev = 0
    for dp in dc_positions:
        segments.append(event_data[prev:dp])
        prev = dp + 1
    segments.append(event_data[prev:])

    events_with_context = []
    global_evt_idx = 0
    byte_offset = 28  # Start after header

    for seg_idx, seg in enumerate(segments):
        if len(seg) < 20:
            byte_offset += len(seg) + 1  # +1 for DC
            continue

        header = seg[:13]
        byte_offset_start = byte_offset + 13

        for i in range((len(seg) - 13) // 7):
            evt_bytes = seg[13 + i * 7: 13 + (i + 1) * 7]
            if len(evt_bytes) != 7:
                continue

            evt_abs_offset = byte_offset + 13 + i * 7

            # Which message does this event belong to?
            msg_idx = -1
            for mi, (ms, me) in enumerate(msg_boundaries):
                if ms <= evt_abs_offset < me:
                    msg_idx = mi
                    break

            # Does this event SPAN a message boundary?
            evt_end_offset = evt_abs_offset + 7
            spans_boundary = False
            for mi, (ms, me) in enumerate(msg_boundaries):
                if evt_abs_offset < me and evt_end_offset > me:
                    spans_boundary = True
                    break

            events_with_context.append({
                'seg': seg_idx,
                'seg_evt': i,
                'global': global_evt_idx,
                'bytes': evt_bytes,
                'abs_offset': evt_abs_offset,
                'msg_idx': msg_idx,
                'spans_boundary': spans_boundary,
            })
            global_evt_idx += 1

        byte_offset += len(seg) + 1

    # Count events per message
    from collections import Counter
    msg_event_counts = Counter(e['msg_idx'] for e in events_with_context)
    print(f"\nEvents per message: {dict(msg_event_counts)}")
    print(f"Events spanning boundaries: {sum(1 for e in events_with_context if e['spans_boundary'])}")

    # --- Try per-message indexing ---
    print(f"\n{'='*70}")
    print("TEST: Per-message event indexing (R resets per message)")
    print(f"{'='*70}")

    msg_local_idx = Counter()  # msg_idx -> next local index
    for e in events_with_context:
        mi = e['msg_idx']
        local_i = msg_local_idx[mi]
        msg_local_idx[mi] += 1

        val = int.from_bytes(e['bytes'], "big")

        # R=9*(local+1) per message
        r_msg = (9 * (local_i + 1)) % 56
        derot = rot_right(val, r_msg)
        f0 = extract_9bit(derot, 0)
        note_msg = f0 & 0x7F

        # R=9*(global+1)
        r_glob = (9 * (e['global'] + 1)) % 56
        derot_g = rot_right(val, r_glob)
        f0_g = extract_9bit(derot_g, 0)
        note_glob = f0_g & 0x7F

        # R=9*(seg_evt+1)
        r_seg = (9 * (e['seg_evt'] + 1)) % 56
        derot_s = rot_right(val, r_seg)
        f0_s = extract_9bit(derot_s, 0)
        note_seg = f0_s & 0x7F

        # Check against target
        glob_hit = "✓" if note_glob in TARGET_NOTES else " "
        msg_hit = "✓" if note_msg in TARGET_NOTES else " "
        seg_hit = "✓" if note_seg in TARGET_NOTES else " "
        span_mark = " SPAN!" if e['spans_boundary'] else ""

        print(f"  G{e['global']:2d} S{e['seg']:d}.{e['seg_evt']:2d} M{mi}[{local_i:2d}] @{e['abs_offset']:3d}: "
              f"Glob R={r_glob:2d}→n{note_glob:3d}{glob_hit} | "
              f"Msg R={r_msg:2d}→n{note_msg:3d}{msg_hit} | "
              f"Seg R={r_seg:2d}→n{note_seg:3d}{seg_hit}{span_mark}")

    # Summary
    glob_hits = sum(1 for e in events_with_context
                    for r in [(9*(e['global']+1))%56]
                    if (extract_9bit(rot_right(int.from_bytes(e['bytes'],"big"), r), 0) & 0x7F) in TARGET_NOTES)

    msg_counters = Counter()
    for e in events_with_context:
        msg_counters[e['msg_idx']] = msg_counters.get(e['msg_idx'], -1) + 1

    # Recompute per-msg hits
    msg_local_idx2 = Counter()
    msg_hits = 0
    for e in events_with_context:
        mi = e['msg_idx']
        local_i = msg_local_idx2[mi]
        msg_local_idx2[mi] += 1
        r = (9 * (local_i + 1)) % 56
        val = int.from_bytes(e['bytes'], "big")
        note = extract_9bit(rot_right(val, r), 0) & 0x7F
        if note in TARGET_NOTES:
            msg_hits += 1

    seg_hits = sum(1 for e in events_with_context
                   for r in [(9*(e['seg_evt']+1))%56]
                   if (extract_9bit(rot_right(int.from_bytes(e['bytes'],"big"), r), 0) & 0x7F) in TARGET_NOTES)

    total = len(events_with_context)
    print(f"\n--- SUMMARY ---")
    print(f"Global index R=9*(g+1): {glob_hits}/{total} = {glob_hits*100//total}%")
    print(f"Per-message R=9*(m+1):  {msg_hits}/{total} = {msg_hits*100//total}%")
    print(f"Per-segment R=9*(s+1):  {seg_hits}/{total} = {seg_hits*100//total}%")
    print(f"Random chance (6/128):  {total*6//128}/{total} = {6*100//128}%")

    # --- Also try: event offset within message as rotation ---
    print(f"\n{'='*70}")
    print("TEST: Byte offset within message as rotation parameter")
    print(f"{'='*70}")

    offset_hits = 0
    for e in events_with_context:
        mi = e['msg_idx']
        msg_start = msg_boundaries[mi][0]
        offset_in_msg = e['abs_offset'] - msg_start

        val = int.from_bytes(e['bytes'], "big")

        # Try R = offset_in_msg mod 56
        r = offset_in_msg % 56
        derot = rot_right(val, r)
        note = extract_9bit(derot, 0) & 0x7F
        hit = "✓" if note in TARGET_NOTES else " "
        if note in TARGET_NOTES:
            offset_hits += 1

        # Try R = (offset_in_msg * 9) mod 56
        r2 = (offset_in_msg * 9) % 56
        derot2 = rot_right(val, r2)
        note2 = extract_9bit(derot2, 0) & 0x7F
        hit2 = "✓" if note2 in TARGET_NOTES else " "

        print(f"  G{e['global']:2d} offset_in_msg={offset_in_msg:3d}: "
              f"R=off%56={r:2d}→n{note:3d}{hit} | "
              f"R=off*9%56={r2:2d}→n{note2:3d}{hit2}")

    print(f"\nOffset-based hits: {offset_hits}/{total}")

    # --- Try: absolute byte position as R ---
    print(f"\n{'='*70}")
    print("TEST: Absolute byte offset as R parameter")
    print(f"{'='*70}")

    abs_hits = 0
    for e in events_with_context:
        val = int.from_bytes(e['bytes'], "big")

        # Offset from start of event_data
        evt_data_offset = e['abs_offset'] - 28

        r = evt_data_offset % 56
        derot = rot_right(val, r)
        note = extract_9bit(derot, 0) & 0x7F
        if note in TARGET_NOTES:
            abs_hits += 1
            print(f"  G{e['global']:2d} abs_off={evt_data_offset:3d} R={r:2d} → note {note} ✓")

    print(f"\nAbsolute offset hits: {abs_hits}/{total}")

    return events_with_context


def test_known_pattern(syx_path: str):
    """Verify message boundary analysis on known_pattern (should show 1 message)."""
    print(f"\n{'='*70}")
    print("KNOWN_PATTERN VERIFICATION")
    print(f"{'='*70}")
    analyze_message_boundaries(syx_path, section=0, track=0)


if __name__ == "__main__":
    cap_dir = os.path.join(os.path.dirname(__file__), "captured")

    # Test known_pattern first
    kp_path = os.path.join(cap_dir, "known_pattern.syx")
    if os.path.exists(kp_path):
        test_known_pattern(kp_path)

    print("\n\n" + "#" * 70)
    print("# SGT / USER STYLE ANALYSIS")
    print("#" * 70 + "\n")

    # Then SGT
    for name in ["QY70_SGT.syx", "user_style_live.syx", "ground_truth_style.syx"]:
        path = os.path.join(cap_dir, name)
        if os.path.exists(path):
            analyze_message_boundaries(path, section=0, track=0)
            break
