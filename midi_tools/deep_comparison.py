#!/usr/bin/env python3
"""Deep byte-level comparison: known_pattern vs ground_truth_style.

Both files have IDENTICAL 13-byte bar headers: 9b8447c641582c288f8d818c58
known_pattern: 7 events, R=9*(i+1) works 100%
ground_truth_style: 84 events, R=9*(i+1) fails (4%, random)

Why? This script compares them byte-by-byte to find structural differences.

Session 20.
"""

import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from qymanager.formats.qy70.sysex_parser import SysExParser

TARGET_NOTES = {36, 38, 42, 44, 54, 68}
KNOWN_PATTERN_NOTES = [36, 49, 44, 44, 38, 44, 44]  # From Session 14 ground truth

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

def get_per_message_data(syx_path, section, track):
    """Return list of decoded_data per message (not concatenated)."""
    parser = SysExParser()
    messages = parser.parse_file(syx_path)
    al = section * 8 + track
    result = []
    for m in messages:
        if m.is_style_data and m.address_low == al:
            if m.decoded_data is not None:
                result.append(m.decoded_data)
    return result


def compare_files():
    cap_dir = os.path.join(os.path.dirname(__file__), "captured")
    kp_path = os.path.join(cap_dir, "known_pattern.syx")
    gt_path = os.path.join(cap_dir, "ground_truth_style.syx")

    kp_data = get_track_data(kp_path, 0, 0)
    gt_data = get_track_data(gt_path, 0, 0)

    print("=" * 70)
    print("DEEP COMPARISON: known_pattern vs ground_truth_style")
    print("=" * 70)

    print(f"\nTrack data sizes: KP={len(kp_data)}, GT={len(gt_data)}")
    print(f"28-byte header identical: {kp_data[:28] == gt_data[:28]}")
    print(f"Header: {kp_data[:28].hex()}")

    kp_evtdata = kp_data[28:]
    gt_evtdata = gt_data[28:]

    print(f"\nEvent data: KP={len(kp_evtdata)}, GT={len(gt_evtdata)}")
    print(f"13-byte bar header identical: {kp_evtdata[:13] == gt_evtdata[:13]}")
    print(f"Bar header: {kp_evtdata[:13].hex()}")

    # PER-MESSAGE analysis
    print("\n" + "=" * 70)
    print("PER-MESSAGE RAW DATA")
    print("=" * 70)

    kp_msgs = get_per_message_data(kp_path, 0, 0)
    gt_msgs = get_per_message_data(gt_path, 0, 0)

    print(f"\nKP messages: {len(kp_msgs)}")
    for i, msg in enumerate(kp_msgs):
        print(f"  Msg {i}: {len(msg)} bytes")
        # Show first 32 bytes
        print(f"    {msg[:32].hex()}")

    print(f"\nGT messages: {len(gt_msgs)}")
    for i, msg in enumerate(gt_msgs):
        print(f"  Msg {i}: {len(msg)} bytes")
        print(f"    {msg[:32].hex()}")
        if i == 0 and len(kp_msgs) > 0:
            # Compare with KP msg 0
            same = sum(1 for a, b in zip(msg, kp_msgs[0]) if a == b)
            print(f"    Same bytes as KP msg 0: {same}/{min(len(msg), len(kp_msgs[0]))}")

    # Byte-by-byte comparison of shared portion
    shared_len = min(len(kp_evtdata), len(gt_evtdata))
    print(f"\n" + "=" * 70)
    print(f"BYTE-BY-BYTE: first {shared_len} bytes of event data")
    print("=" * 70)

    diffs = []
    for i in range(shared_len):
        if kp_evtdata[i] != gt_evtdata[i]:
            diffs.append(i)

    print(f"Identical bytes: {shared_len - len(diffs)}/{shared_len}")
    print(f"Different bytes: {len(diffs)}")
    if diffs:
        print(f"First 20 differences:")
        for d in diffs[:20]:
            print(f"  Byte {d:3d}: KP=0x{kp_evtdata[d]:02X} GT=0x{gt_evtdata[d]:02X}  XOR=0x{kp_evtdata[d]^gt_evtdata[d]:02X}")

    # KP events decoded correctly
    print("\n" + "=" * 70)
    print("KNOWN_PATTERN EVENTS (verified correct)")
    print("=" * 70)

    kp_events_raw = kp_evtdata[13:]
    for i in range(7):
        evt = kp_events_raw[i*7:(i+1)*7]
        val = int.from_bytes(evt, "big")
        r = (9 * (i + 1)) % 56
        derot = rot_right(val, r)
        f0 = extract_9bit(derot, 0)
        note = f0 & 0x7F
        f1 = extract_9bit(derot, 1)
        f2 = extract_9bit(derot, 2)
        f3 = extract_9bit(derot, 3)
        f4 = extract_9bit(derot, 4)
        f5 = extract_9bit(derot, 5)
        rem = derot & 0x3

        print(f"  E{i} [{evt.hex()}] R={r:2d} → "
              f"F0={f0:3d}(n{note}) F1={f1:3d} F2={f2:3d} F3={f3:3d} F4={f4:3d} F5={f5:3d} rem={rem}")

    # GT events at same positions
    print("\n" + "=" * 70)
    print("GROUND_TRUTH events at SAME byte positions")
    print("=" * 70)

    gt_events_raw = gt_evtdata[13:]
    for i in range(min(7, len(gt_events_raw) // 7)):
        evt = gt_events_raw[i*7:(i+1)*7]
        val = int.from_bytes(evt, "big")
        r = (9 * (i + 1)) % 56
        derot = rot_right(val, r)
        f0 = extract_9bit(derot, 0)
        note = f0 & 0x7F

        # Also show what ALL rotations give
        hit_rotations = []
        for tr in range(56):
            td = rot_right(val, tr)
            tf0 = extract_9bit(td, 0)
            tn = tf0 & 0x7F
            if tn in TARGET_NOTES:
                hit_rotations.append((tr, tn))

        hit_str = ", ".join(f"R={tr}→{tn}" for tr, tn in hit_rotations[:5])
        target_hit = "✓" if note in TARGET_NOTES else ""
        print(f"  E{i} [{evt.hex()}] R={r:2d} → n{note:3d} {target_hit}  | targets at: [{hit_str}]")

    # What about treating GT as having 9E-delimited sub-segments?
    print("\n" + "=" * 70)
    print("GT: 9E-delimited structure analysis")
    print("=" * 70)

    nine_pos = [i for i, b in enumerate(gt_evtdata) if b == 0x9E]
    print(f"9E positions: {nine_pos}")

    # Split on 9E
    parts = []
    prev = 0
    for np in nine_pos:
        parts.append(gt_evtdata[prev:np])
        prev = np + 1
    parts.append(gt_evtdata[prev:])

    for pi, part in enumerate(parts):
        print(f"\n  Segment {pi}: {len(part)} bytes")
        if len(part) >= 13:
            hdr = part[:13]
            print(f"    Header: {hdr.hex()}")
            print(f"    Starts with 0x1A: {hdr[0] == 0x1A}")
            print(f"    Header == KP header: {hdr == kp_evtdata[:13]}")

            # Events in this segment
            evt_bytes = part[13:]
            n = len(evt_bytes) // 7
            rem = len(evt_bytes) % 7
            print(f"    Events: {n}, remainder: {rem}")

            hits = 0
            for i in range(min(n, 8)):  # Show up to 8 events
                evt = evt_bytes[i*7:(i+1)*7]
                val = int.from_bytes(evt, "big")
                r = (9 * (i + 1)) % 56
                derot = rot_right(val, r)
                f0 = extract_9bit(derot, 0)
                note = f0 & 0x7F
                hit = "✓" if note in TARGET_NOTES else ""
                if note in TARGET_NOTES:
                    hits += 1

                # Check all rotations for target hits
                best = []
                for tr in range(56):
                    td = rot_right(val, tr)
                    tn = extract_9bit(td, 0) & 0x7F
                    if tn in TARGET_NOTES:
                        best.append(f"R{tr}→{tn}")

                print(f"      E{i} R={r:2d} → n{note:3d} {hit}  candidates: [{', '.join(best[:4])}]")

            if n > 8:
                # Count total hits
                for i in range(8, n):
                    evt = evt_bytes[i*7:(i+1)*7]
                    val = int.from_bytes(evt, "big")
                    r = (9 * (i + 1)) % 56
                    note = extract_9bit(rot_right(val, r), 0) & 0x7F
                    if note in TARGET_NOTES:
                        hits += 1
                print(f"      ... ({n-8} more events)")

            print(f"      Segment hits: {hits}/{n}")
        else:
            print(f"    Content: {part.hex()}")

    # Check if KP events appear anywhere in GT data
    print("\n" + "=" * 70)
    print("Do known_pattern events appear in ground_truth data?")
    print("=" * 70)

    for i in range(7):
        kp_evt = kp_events_raw[i*7:(i+1)*7]
        # Search in GT event data
        pos = -1
        for j in range(len(gt_events_raw) - 6):
            if gt_events_raw[j:j+7] == kp_evt:
                pos = j
                break
        found = f"at byte {pos}" if pos >= 0 else "NOT FOUND"
        print(f"  KP E{i} [{kp_evt.hex()}]: {found}")


if __name__ == "__main__":
    compare_files()
