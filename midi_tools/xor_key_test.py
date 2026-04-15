#!/usr/bin/env python3
"""Test: is the bar header a XOR key for event decoding?

Hypothesis: encoded_event = rotate(plaintext XOR header_key, R)
Decoding: plaintext = rotate_inv(encoded, R) XOR header_key

For known_pattern, the key might have no effect (or cancel out).
For SGT, different bar headers = different keys → explains failure.

Also tests: event-to-event XOR chain (stream cipher hypothesis).

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

def extract_bars_dc_only(data: bytes):
    """DC-only split, returns (preamble, [(header_13, events_list), ...])"""
    if len(data) < 28:
        return b"", []
    preamble = data[24:28]
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
    return preamble, bars


def test_header_xor(syx_path: str, section: int = 0, track: int = 0):
    """XOR each event with its bar header's first 7 bytes, then rotate."""
    data = get_track_data(syx_path, section, track)
    if not data:
        return

    preamble, bars = extract_bars_dc_only(data)
    print(f"=== HEADER XOR TEST ===")
    print(f"File: {os.path.basename(syx_path)}")
    print(f"Bars: {len(bars)}, Preamble: {preamble.hex()}")

    total_events = 0
    total_hits = 0

    for bar_idx, (header, events) in enumerate(bars):
        hdr7 = int.from_bytes(header[:7], "big")
        print(f"\n--- Bar {bar_idx} ({len(events)} events) ---")
        print(f"  Header[0:7]: {header[:7].hex()}")
        print(f"  Header[7:13]: {header[7:13].hex()}")

        for i, evt in enumerate(events):
            val = int.from_bytes(evt, "big")
            r = (9 * (i + 1)) % 56

            # Method 1: rotate THEN XOR with header
            derot = rot_right(val, r)
            xored1 = derot ^ hdr7
            f0_1 = extract_9bit(xored1, 0)
            note1 = f0_1 & 0x7F

            # Method 2: XOR with header THEN rotate
            xored_pre = val ^ hdr7
            derot2 = rot_right(xored_pre, r)
            f0_2 = extract_9bit(derot2, 0)
            note2 = f0_2 & 0x7F

            # Method 3: rotate, then XOR with ROTATED header
            hdr_rot = rot_right(hdr7, r)
            derot3 = rot_right(val, r) ^ hdr_rot
            f0_3 = extract_9bit(derot3, 0)
            note3 = f0_3 & 0x7F

            # Method 4: plain (no XOR, just rotation)
            f0_plain = extract_9bit(derot, 0)
            note_plain = f0_plain & 0x7F

            h1 = "✓" if note1 in TARGET_NOTES else " "
            h2 = "✓" if note2 in TARGET_NOTES else " "
            h3 = "✓" if note3 in TARGET_NOTES else " "
            hp = "✓" if note_plain in TARGET_NOTES else " "

            total_events += 1
            best_hit = any(n in TARGET_NOTES for n in [note1, note2, note3])
            if best_hit:
                total_hits += 1

            print(f"  E{i}: rot→xor={note1:3d}{h1} | xor→rot={note2:3d}{h2} | rot→xor_rot={note3:3d}{h3} | plain={note_plain:3d}{hp}")

    print(f"\n--- SUMMARY ---")
    print(f"Any XOR method hit: {total_hits}/{total_events}")


def test_header_second_half_xor(syx_path: str, section: int = 0, track: int = 0):
    """Try XOR with header bytes 6:13 (the second half of 13-byte header)."""
    data = get_track_data(syx_path, section, track)
    if not data:
        return

    preamble, bars = extract_bars_dc_only(data)
    print(f"\n=== HEADER SECOND-HALF XOR ===")

    total = 0
    hits_m1 = 0
    hits_m2 = 0
    hits_m3 = 0
    hits_plain = 0

    for bar_idx, (header, events) in enumerate(bars):
        # Try different 7-byte slices of the 13-byte header
        for hdr_start in [0, 3, 6]:
            hdr7 = int.from_bytes(header[hdr_start:hdr_start+7], "big") if hdr_start + 7 <= 13 else 0
            if hdr7 == 0:
                continue

            bar_hits = 0
            for i, evt in enumerate(events):
                val = int.from_bytes(evt, "big")
                r = (9 * (i + 1)) % 56

                derot = rot_right(val, r)
                xored = derot ^ hdr7
                note = extract_9bit(xored, 0) & 0x7F
                if note in TARGET_NOTES:
                    bar_hits += 1

            if bar_hits > 0:
                print(f"  Bar {bar_idx} hdr[{hdr_start}:{hdr_start+7}]={header[hdr_start:hdr_start+7].hex()}: {bar_hits}/{len(events)} hits")


def test_preamble_xor(syx_path: str, section: int = 0, track: int = 0):
    """Try XOR with the 4-byte preamble (repeated or padded)."""
    data = get_track_data(syx_path, section, track)
    if not data:
        return

    preamble, bars = extract_bars_dc_only(data)
    preamble_val = int.from_bytes(preamble, "big")
    # Extend 4-byte preamble to 7 bytes by repeating
    preamble_7 = int.from_bytes(preamble + preamble[:3], "big")

    print(f"\n=== PREAMBLE XOR ===")
    print(f"Preamble: {preamble.hex()} → extended: {(preamble + preamble[:3]).hex()}")

    total = 0
    hits = 0
    for bar_idx, (header, events) in enumerate(bars):
        for i, evt in enumerate(events):
            val = int.from_bytes(evt, "big")
            r = (9 * (i + 1)) % 56
            derot = rot_right(val, r)
            xored = derot ^ preamble_7
            note = extract_9bit(xored, 0) & 0x7F
            total += 1
            if note in TARGET_NOTES:
                hits += 1
    print(f"  Hits: {hits}/{total} = {hits*100//max(total,1)}%")


def test_stream_cipher(syx_path: str, section: int = 0, track: int = 0):
    """Test if event N's rotation depends on event N-1's decoded value."""
    data = get_track_data(syx_path, section, track)
    if not data:
        return

    preamble, bars = extract_bars_dc_only(data)
    print(f"\n=== STREAM CIPHER TEST ===")
    print(f"Try: R[n+1] = R[n] + f(decoded[n])")

    for bar_idx, (header, events) in enumerate(bars):
        if bar_idx > 1:
            break

        print(f"\n--- Bar {bar_idx} ---")
        # Start with R=9 for first event
        prev_r = 9
        prev_derot = None

        for i, evt in enumerate(events):
            val = int.from_bytes(evt, "big")

            if i == 0:
                # First event: use R=9
                r = 9
            else:
                # Try different feedback functions
                if prev_derot is not None:
                    candidates = []
                    # Try all rotations, see which give target notes
                    for try_r in range(56):
                        derot = rot_right(val, try_r)
                        note = extract_9bit(derot, 0) & 0x7F
                        if note in TARGET_NOTES:
                            # Compute feedback from previous event
                            delta = (try_r - prev_r) % 56
                            candidates.append((try_r, note, delta))

                    if candidates:
                        print(f"  E{i}: Candidates: ", end="")
                        for tr, tn, td in candidates:
                            print(f"R={tr}→n{tn}(Δ={td}) ", end="")
                        print()
                    else:
                        print(f"  E{i}: No target note at any R (ctrl?)")

                    r = (9 * (i + 1)) % 56  # Fallback

            derot = rot_right(val, r)
            f0 = extract_9bit(derot, 0)
            note = f0 & 0x7F

            # Various feedback components
            prev_r = r
            prev_derot = derot

            hit = "✓" if note in TARGET_NOTES else ""
            print(f"  E{i}: R={r:2d} → n{note:3d} {hit}  [raw fields: F0={f0}, lo7={note}]")


def test_brute_force_xor_key(syx_path: str, section: int = 0, track: int = 0):
    """Brute-force a 7-byte XOR key that makes R=9*(i+1) work for ALL events."""
    data = get_track_data(syx_path, section, track)
    if not data:
        return

    preamble, bars = extract_bars_dc_only(data)
    print(f"\n=== BRUTE FORCE XOR KEY (per bar) ===")
    print("For each bar, find 7-byte key K such that rot_right(event XOR K, R) gives target note")

    for bar_idx, (header, events) in enumerate(bars):
        if len(events) < 2:
            continue

        print(f"\n--- Bar {bar_idx} ({len(events)} events) ---")

        # For the first event (R=9), find all possible F0 values (9 MSBs after rotation)
        # that give a target note. Then compute the XOR key that produces each.
        evt0 = int.from_bytes(events[0], "big")
        derot0 = rot_right(evt0, 9)

        # For each target note, what should the derotated value look like?
        # F0 = note (7 bits) + vel bits (2 bits) → multiple possibilities
        # F0 = note | (vel_high << 7) → vel_high can be 0, 1, 2, 3
        for target_note in sorted(TARGET_NOTES):
            for vel_bits in range(4):
                desired_f0 = target_note | (vel_bits << 7)
                # desired_f0 should be at bits 47-39 of the derotated value
                # Compute what XOR key makes derot0's F0 equal to desired_f0
                actual_f0 = extract_9bit(derot0, 0)
                xor_f0 = actual_f0 ^ desired_f0

                # This XOR only affects 9 bits (positions 47-39).
                # We need to construct a full 56-bit key.
                # For now, just track the F0 xor
                if xor_f0 != 0:
                    # Check if same key works for event 1
                    evt1 = int.from_bytes(events[1], "big")
                    derot1 = rot_right(evt1, 18)
                    actual_f0_1 = extract_9bit(derot1, 0)
                    test_f0_1 = actual_f0_1 ^ xor_f0
                    test_note_1 = test_f0_1 & 0x7F
                    if test_note_1 in TARGET_NOTES:
                        # Check event 2
                        if len(events) >= 3:
                            evt2 = int.from_bytes(events[2], "big")
                            derot2 = rot_right(evt2, 27)
                            test_f0_2 = extract_9bit(derot2, 0) ^ xor_f0
                            test_note_2 = test_f0_2 & 0x7F
                            if test_note_2 in TARGET_NOTES:
                                print(f"  KEY CANDIDATE: XOR_F0=0x{xor_f0:03X} "
                                      f"→ E0:n{target_note} E1:n{test_note_1} E2:n{test_note_2}")


if __name__ == "__main__":
    cap_dir = os.path.join(os.path.dirname(__file__), "captured")

    for name in ["QY70_SGT.syx", "user_style_live.syx", "ground_truth_style.syx"]:
        path = os.path.join(cap_dir, name)
        if os.path.exists(path):
            test_header_xor(path, section=0, track=0)
            test_header_second_half_xor(path, section=0, track=0)
            test_preamble_xor(path, section=0, track=0)
            test_stream_cipher(path, section=0, track=0)
            test_brute_force_xor_key(path, section=0, track=0)
            break
