#!/usr/bin/env python3
"""
Test cumulative R model for Summer RHY1 dense drum encoding.

For sparse patterns (known_pattern), R=9*(i+1) mod 56 works with index
resetting per segment. But for dense patterns, what if:
1. The index is GLOBAL (continues across bars, no reset)
2. The multiplier is different
3. There's an offset or different formula

Test ALL these variants systematically.
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


def extract_segments(data):
    event_data = data[28:]
    segments = []
    prev = 0
    for i, b in enumerate(event_data):
        if b in (0xDC, 0x9E):
            segments.append(event_data[prev:i])
            prev = i + 1
    if prev < len(event_data):
        segments.append(event_data[prev:])
    return segments


def decode_at_r(evt_bytes, r_val):
    val = int.from_bytes(evt_bytes, "big")
    derot = rot_right(val, r_val)
    f0 = extract_9bit(derot, 0)
    note = f0 & 0x7F
    return note


def main():
    syx_path = "data/qy70_sysx/P -  Summer - 20231101.syx"
    data = load_syx_track(syx_path, section=0, track=0)
    segments = extract_segments(data)

    # Build list of all events with segment index
    all_events = []
    for seg_idx, seg in enumerate(segments):
        if len(seg) < 20:
            continue
        event_bytes = seg[13:]
        n_events = len(event_bytes) // 7
        for ei in range(n_events):
            evt = event_bytes[ei*7:(ei+1)*7]
            all_events.append((seg_idx, ei, evt))

    # GT target notes per bar (all bars have same instruments)
    TARGET = {36, 38, 42}

    print("=" * 80)
    print(f"Total events across all segments: {len(all_events)}")
    print("=" * 80)

    # =====================================================
    # MODEL 1: R=mult*(i+1) mod 56, global index
    # =====================================================
    print("\n--- MODEL 1: R = mult*(global_i+1) mod 56 ---")

    best_mult = None
    best_score = 0

    for mult in range(1, 56):
        score = 0
        for gi, (seg_idx, ei, evt) in enumerate(all_events):
            if seg_idx > 5:  # Skip fill section
                continue
            r = (mult * (gi + 1)) % 56
            note = decode_at_r(evt, r)
            if note in TARGET:
                score += 1

        if score > best_score:
            best_score = score
            best_mult = mult

    total_main = sum(1 for s, _, _ in all_events if s <= 5)
    print(f"  Best: mult={best_mult}, score={best_score}/{total_main}")

    # Show top 10
    scores = []
    for mult in range(1, 56):
        score = 0
        for gi, (seg_idx, ei, evt) in enumerate(all_events):
            if seg_idx > 5:
                continue
            r = (mult * (gi + 1)) % 56
            note = decode_at_r(evt, r)
            if note in TARGET:
                score += 1
        scores.append((score, mult))

    scores.sort(reverse=True)
    print(f"  Top 10 multipliers:")
    for score, mult in scores[:10]:
        print(f"    mult={mult:2d}: {score}/{total_main} hits")

    # Detail for best multiplier
    print(f"\n  Detail for mult={best_mult}:")
    for gi, (seg_idx, ei, evt) in enumerate(all_events):
        if seg_idx > 5:
            continue
        r = (best_mult * (gi + 1)) % 56
        note = decode_at_r(evt, r)
        marker = "✓" if note in TARGET else "✗"
        print(f"    g{gi:2d} seg{seg_idx}/e{ei} R={r:2d}: "
              f"note={note:3d} ({nn(note):>4s}) {marker}")

    # =====================================================
    # MODEL 2: R=mult*(i+1) mod 56, index resets per bar
    # =====================================================
    print("\n\n--- MODEL 2: R = mult*(bar_i+1) mod 56, reset per bar ---")

    best_mult2 = None
    best_score2 = 0

    for mult in range(1, 56):
        score = 0
        for seg_idx, ei, evt in all_events:
            if seg_idx > 5 or seg_idx < 1:
                continue
            r = (mult * (ei + 1)) % 56
            note = decode_at_r(evt, r)
            if note in TARGET:
                score += 1

        if score > best_score2:
            best_score2 = score
            best_mult2 = mult

    total_bars = sum(1 for s, _, _ in all_events if 1 <= s <= 5)
    print(f"  Best: mult={best_mult2}, score={best_score2}/{total_bars}")

    scores2 = []
    for mult in range(1, 56):
        score = 0
        for seg_idx, ei, evt in all_events:
            if seg_idx > 5 or seg_idx < 1:
                continue
            r = (mult * (ei + 1)) % 56
            note = decode_at_r(evt, r)
            if note in TARGET:
                score += 1
        scores2.append((score, mult))

    scores2.sort(reverse=True)
    print(f"  Top 10 multipliers:")
    for score, mult in scores2[:10]:
        print(f"    mult={mult:2d}: {score}/{total_bars} hits")

    # =====================================================
    # MODEL 3: R=mult*(i+offset) mod 56, find best offset
    # =====================================================
    print("\n\n--- MODEL 3: R = 9*(global_i+offset) mod 56, find best offset ---")

    best_off = None
    best_score3 = 0

    for offset in range(56):
        score = 0
        for gi, (seg_idx, ei, evt) in enumerate(all_events):
            if seg_idx > 5:
                continue
            r = (9 * (gi + offset)) % 56
            note = decode_at_r(evt, r)
            if note in TARGET:
                score += 1

        if score > best_score3:
            best_score3 = score
            best_off = offset

    print(f"  Best: offset={best_off}, score={best_score3}/{total_main}")

    # Show top 5
    off_scores = []
    for offset in range(56):
        score = 0
        for gi, (seg_idx, ei, evt) in enumerate(all_events):
            if seg_idx > 5:
                continue
            r = (9 * (gi + offset)) % 56
            note = decode_at_r(evt, r)
            if note in TARGET:
                score += 1
        off_scores.append((score, offset))

    off_scores.sort(reverse=True)
    for score, off in off_scores[:5]:
        print(f"    offset={off:2d}: {score}/{total_main} hits")

    # =====================================================
    # MODEL 4: Per-bar R derived from HEADER
    # Try: R_base = header_field[k] mod 56
    # =====================================================
    print("\n\n--- MODEL 4: R derived from bar header field ---")

    for seg_idx, seg in enumerate(segments):
        if len(seg) < 20 or seg_idx < 1 or seg_idx > 5:
            continue

        header = seg[:13]
        event_bytes = seg[13:]
        n_events = min(4, len(event_bytes) // 7)

        # Decode header as 9-bit fields
        hval = int.from_bytes(header, "big")
        hfields = []
        for i in range(11):
            shift = 104 - 9 * (i + 1)
            hfields.append((hval >> shift) & 0x1FF)

        # For each header field, try R = field mod 56, field*9 mod 56, etc.
        print(f"\n  Seg {seg_idx} header fields: {hfields[:6]}")

        # Try using each header field as R_base
        for fk in range(11):
            for formula_name, r_func in [
                ("h%56", lambda f, i: f % 56),
                ("h*9%56", lambda f, i: (f * 9) % 56),
                ("(h+i)%56", lambda f, i: (f + i) % 56),
                ("(h+9*i)%56", lambda f, i: (f + 9 * (i + 1)) % 56),
                ("(h*i)%56", lambda f, i: (f * (i + 1)) % 56),
            ]:
                hits = 0
                notes = []
                for ei in range(n_events):
                    evt = event_bytes[ei*7:(ei+1)*7]
                    r = r_func(hfields[fk], ei)
                    note = decode_at_r(evt, r)
                    if note in TARGET:
                        hits += 1
                    notes.append(note)
                if hits == n_events:  # All events decode to target
                    print(f"    PERFECT: field[{fk}]={hfields[fk]} "
                          f"formula={formula_name} → notes={notes}")
                elif hits >= 3:
                    print(f"    good ({hits}/{n_events}): field[{fk}]={hfields[fk]} "
                          f"formula={formula_name} → notes={notes}")

    # =====================================================
    # MODEL 5: Brute-force per-bar R tuple
    # For each bar, what is THE BEST 4-tuple of R values?
    # (Already done in previous analysis but with different perspective)
    # =====================================================
    print("\n\n--- MODEL 5: Per-bar optimal R tuple (any notes in TARGET) ---")

    bar_best_rs = {}
    for seg_idx, seg in enumerate(segments):
        if len(seg) < 20 or seg_idx < 1 or seg_idx > 5:
            continue

        event_bytes = seg[13:]
        n_events = min(4, len(event_bytes) // 7)

        # For each event, find R values that give target notes
        per_event = []
        for ei in range(n_events):
            evt = event_bytes[ei*7:(ei+1)*7]
            valid = {}
            for r in range(56):
                note = decode_at_r(evt, r)
                if note in TARGET:
                    valid.setdefault(note, []).append(r)
            per_event.append(valid)

        print(f"\n  Seg {seg_idx}:")
        for ei, valid in enumerate(per_event):
            for note, rs in sorted(valid.items()):
                print(f"    e{ei}: {nn(note):>4s}({note}) at R={rs}")

    # =====================================================
    # MODEL 6: XOR-based transform instead of rotation
    # Maybe the transform is val XOR key, not rot(val, R)
    # =====================================================
    print("\n\n--- MODEL 6: XOR with per-bar key from header ---")

    # If each segment's events are XORed with a key derived from the header,
    # then XORing two bars' corresponding events should give a key that
    # when applied to the third bar's events, produces correct notes.

    # Use Seg 1 and Seg 4 (both decode to [42,38,42,36] at R=[9,22,12,53])
    seg1_evts = []
    seg4_evts = []
    for seg_idx, seg in enumerate(segments):
        if len(seg) < 20:
            continue
        event_bytes = seg[13:]
        evts = [event_bytes[i*7:(i+1)*7] for i in range(min(4, len(event_bytes)//7))]
        if seg_idx == 1:
            seg1_evts = evts
        elif seg_idx == 4:
            seg4_evts = evts

    if seg1_evts and seg4_evts:
        print("\n  XOR between Seg 1 and Seg 4 per event:")
        for ei in range(4):
            xor = bytes(a ^ b for a, b in zip(seg1_evts[ei], seg4_evts[ei]))
            diff_bits = sum(bin(b).count("1") for b in xor)
            print(f"    e{ei}: {xor.hex()} ({diff_bits} bits)")

    # Test if Seg 1 e1 XOR Seg 4 e1, applied to Seg 2 e1, gives a value
    # where note 38 is extractable
    if seg1_evts and seg4_evts:
        seg2_evts = []
        for seg_idx, seg in enumerate(segments):
            if seg_idx == 2 and len(seg) >= 20:
                event_bytes = seg[13:]
                seg2_evts = [event_bytes[i*7:(i+1)*7] for i in range(min(4, len(event_bytes)//7))]

        if seg2_evts:
            print("\n  Apply Seg1⊕Seg4 key to Seg2:")
            for ei in range(4):
                key = bytes(a ^ b for a, b in zip(seg1_evts[ei], seg4_evts[ei]))
                modified = bytes(a ^ b for a, b in zip(seg2_evts[ei], key))
                # Try all R values on modified
                for r in range(56):
                    note = decode_at_r(modified, r)
                    if note in TARGET:
                        print(f"    e{ei} (XOR corrected) R={r:2d}: {nn(note)}({note})")

    # =====================================================
    # MODEL 7: The "stable core" hypothesis
    # Bytes 1-3 of snare events are stable (ae8d81)
    # Maybe these encode the instrument, and other bytes encode per-bar data
    # =====================================================
    print("\n\n--- MODEL 7: Stable byte core analysis ---")

    print("  e1 (snare position) across bars:")
    for seg_idx, seg in enumerate(segments):
        if len(seg) < 27 or seg_idx < 1:
            continue
        evt = seg[13+7:13+14]
        core = evt[1:4]
        prefix = evt[0:1]
        suffix = evt[4:7]
        print(f"    Seg {seg_idx}: prefix={prefix.hex()} "
              f"core={core.hex()} suffix={suffix.hex()}")

    # Check if the "core" correlates with the instrument
    print("\n  e0 (HH position) across bars:")
    for seg_idx, seg in enumerate(segments):
        if len(seg) < 20 or seg_idx < 1:
            continue
        evt = seg[13:13+7]
        core = evt[1:4]
        print(f"    Seg {seg_idx}: prefix={evt[0]:02x} "
              f"core={core.hex()} suffix={evt[4:].hex()}")

    print("\n  e2 (HH2 position) across bars:")
    for seg_idx, seg in enumerate(segments):
        if len(seg) < 34 or seg_idx < 1:
            continue
        evt = seg[13+14:13+21]
        core = evt[1:4]
        print(f"    Seg {seg_idx}: prefix={evt[0]:02x} "
              f"core={core.hex()} suffix={evt[4:].hex()}")

    print("\n  e3 (kick position) across bars:")
    for seg_idx, seg in enumerate(segments):
        if len(seg) < 41 or seg_idx < 1:
            continue
        evt = seg[13+21:13+28]
        core = evt[1:4]
        print(f"    Seg {seg_idx}: prefix={evt[0]:02x} "
              f"core={core.hex()} suffix={evt[4:].hex()}")

    print("\nDone.")


if __name__ == "__main__":
    main()
