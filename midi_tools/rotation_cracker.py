#!/usr/bin/env python3
"""Constraint-satisfaction rotation cracker for QY70 SysEx data.

Uses ground truth MIDI capture (real notes played by QY70 hardware)
to find the correct rotation for each event in the SGT drum track.

Approach:
  1. Load SGT RHY1 track data (decoded SysEx bytes)
  2. Load ground truth capture (6 known drum notes: 36,38,42,44,54,68)
  3. For each 7-byte event, try ALL 56 rotations
  4. Find which rotations produce one of the 6 target notes
  5. Look for a pattern in the working rotations

Also tries alternative decodings: XOR masks, byte permutations, addition.

Session 20 — fresh approach to the complex style encoding problem.
"""

import json
import os
import sys
from collections import Counter, defaultdict
from typing import List, Tuple, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from qymanager.formats.qy70.sysex_parser import SysExParser


# --- Constants ---
TARGET_NOTES = {36, 38, 42, 44, 54, 68}  # From sgt_full_capture.json ch9
TARGET_VELS = {127, 32}  # Observed velocities

def rot_right(val: int, shift: int, width: int = 56) -> int:
    """Barrel rotate right by shift bits within width-bit word."""
    shift = shift % width
    return ((val >> shift) | (val << (width - shift))) & ((1 << width) - 1)

def rot_left(val: int, shift: int, width: int = 56) -> int:
    """Barrel rotate left."""
    shift = shift % width
    return ((val << shift) | (val >> (width - shift))) & ((1 << width) - 1)

def extract_9bit(val: int, field_idx: int, width: int = 56) -> int:
    """Extract 9-bit field at position (0=MSB)."""
    shift = width - (field_idx + 1) * 9
    if shift < 0:
        return -1
    return (val >> shift) & 0x1FF

def get_track_data(syx_path: str, section: int, track: int) -> bytes:
    """Get concatenated decoded data for a specific section/track."""
    parser = SysExParser()
    messages = parser.parse_file(syx_path)
    al = section * 8 + track
    data = b""
    for m in messages:
        if m.is_style_data and m.address_low == al:
            if m.decoded_data is not None:
                data += m.decoded_data
    return data

def extract_events_dc_only(data: bytes) -> Tuple[bytes, List[Tuple[bytes, List[bytes]]]]:
    """Extract bars using ONLY DC delimiters (not 0x9E).

    Session 19 finding: 0x9E appears as data bytes inside events in dense tracks,
    causing mid-event splits. DC-only gives perfect 7-byte alignment.
    """
    if len(data) < 28:
        return b"", []

    preamble = data[24:28]
    event_data = data[28:]

    # Split ONLY by DC (0xDC)
    delim_pos = [i for i, b in enumerate(event_data) if b == 0xDC]

    segments = []
    prev = 0
    for dp in delim_pos:
        segments.append(event_data[prev:dp])
        prev = dp + 1
    segments.append(event_data[prev:])

    bars = []
    for seg in segments:
        if len(seg) >= 20:  # 13-byte header + at least 1 event
            header = seg[:13]
            events = []
            remainder_bytes = (len(seg) - 13) % 7
            for i in range((len(seg) - 13) // 7):
                evt = seg[13 + i * 7: 13 + (i + 1) * 7]
                if len(evt) == 7:
                    events.append(evt)
            bars.append((header, events, remainder_bytes))

    return preamble, bars


def analyze_rotations(syx_path: str, section: int = 0, track: int = 0):
    """For each event, find ALL rotations that produce a target note."""

    data = get_track_data(syx_path, section, track)
    if not data:
        print(f"No data for section {section} track {track}")
        return

    print(f"=== ROTATION CRACKER — Section {section}, Track {track} ===")
    print(f"Total decoded bytes: {len(data)}")
    print(f"Target notes: {sorted(TARGET_NOTES)}")
    print(f"First 28 bytes (header): {data[:28].hex()}")
    print()

    preamble, bars = extract_events_dc_only(data)
    print(f"Preamble: {preamble.hex()}")
    print(f"Bars (DC-only): {len(bars)}")

    total_events = sum(len(evts) for _, evts, _ in bars)
    print(f"Total events: {total_events}")
    print()

    # --- Phase 1: Per-event rotation scan ---
    print("=" * 70)
    print("PHASE 1: Per-event rotation candidates (right-rotate)")
    print("=" * 70)

    global_idx = 0
    all_candidates = []  # (bar_idx, evt_idx, global_idx, [(R, note, vel_code)])

    for bar_idx, (header, events, rem) in enumerate(bars):
        # Header analysis
        hdr_val = int.from_bytes(header[:7], "big") if len(header) >= 7 else 0
        h_fields = [extract_9bit(hdr_val, i) for i in range(6)]
        print(f"\n--- Bar {bar_idx} ({len(events)} events, rem={rem}) ---")
        print(f"  Header[0:7] fields: {h_fields}")
        print(f"  Header hex: {header.hex()}")

        for evt_idx, evt in enumerate(events):
            val = int.from_bytes(evt, "big")
            candidates = []

            for r in range(56):
                derot = rot_right(val, r)
                f0 = extract_9bit(derot, 0)
                note = f0 & 0x7F

                if note in TARGET_NOTES:
                    # Also extract velocity
                    f0_bit8 = (f0 >> 8) & 1
                    f0_bit7 = (f0 >> 7) & 1
                    remainder = derot & 0x3
                    vel_code = (f0_bit8 << 3) | (f0_bit7 << 2) | remainder
                    vel = max(1, 127 - vel_code * 8)

                    # Extract other fields
                    f1 = extract_9bit(derot, 1)
                    f5 = extract_9bit(derot, 5)

                    candidates.append({
                        'R': r,
                        'note': note,
                        'vel': vel,
                        'vel_code': vel_code,
                        'f0': f0,
                        'f1': f1,
                        'f5': f5,
                    })

            all_candidates.append((bar_idx, evt_idx, global_idx, candidates))

            # Print candidates
            if candidates:
                cand_str = ", ".join(
                    f"R={c['R']:2d}→n{c['note']}(v{c['vel']})"
                    for c in candidates
                )
                print(f"  E{global_idx:3d} [{evt.hex()}]: {len(candidates)} hits: {cand_str}")
            else:
                print(f"  E{global_idx:3d} [{evt.hex()}]: NO MATCH (possible ctrl event)")

            global_idx += 1

    # --- Phase 2: Look for R patterns ---
    print("\n" + "=" * 70)
    print("PHASE 2: R pattern analysis")
    print("=" * 70)

    # For events with exactly 1 candidate → R is determined
    determined = []
    ambiguous = []
    no_match = []

    for bar_idx, evt_idx, gidx, cands in all_candidates:
        if len(cands) == 0:
            no_match.append(gidx)
        elif len(cands) == 1:
            determined.append((gidx, cands[0]['R'], cands[0]['note']))
        else:
            ambiguous.append((gidx, [(c['R'], c['note']) for c in cands]))

    print(f"\nDetermined (1 candidate): {len(determined)}")
    print(f"Ambiguous (2+ candidates): {len(ambiguous)}")
    print(f"No match (ctrl/unknown):   {len(no_match)}")

    if determined:
        print("\nDetermined R values:")
        for gidx, r, note in determined:
            expected_r = (9 * (gidx + 1)) % 56
            print(f"  E{gidx:3d}: R={r:2d} → note {note}  (R=9*(i+1)%56 would give {expected_r})")

        # Check if R follows any linear pattern: R = a*(i+1) + b mod 56
        print("\n  Testing linear patterns R = a*(i+c) % 56:")
        for a in range(1, 56):
            for c in range(0, 10):
                matches = sum(1 for gidx, r, _ in determined if (a * (gidx + c)) % 56 == r)
                if matches == len(determined) and len(determined) >= 3:
                    print(f"    PERFECT: R = {a}*(i+{c}) % 56 — matches all {matches}")
                elif matches >= len(determined) * 0.8 and len(determined) >= 3:
                    print(f"    Good ({matches}/{len(determined)}): R = {a}*(i+{c}) % 56")

    # --- Phase 3: Per-bar R analysis ---
    print("\n" + "=" * 70)
    print("PHASE 3: Per-bar R patterns (reset per bar?)")
    print("=" * 70)

    local_idx = 0
    for bar_idx, (header, events, rem) in enumerate(bars):
        print(f"\n--- Bar {bar_idx} ---")
        for evt_idx, evt in enumerate(events):
            val = int.from_bytes(evt, "big")
            matches = []
            for r in range(56):
                derot = rot_right(val, r)
                f0 = extract_9bit(derot, 0)
                note = f0 & 0x7F
                if note in TARGET_NOTES:
                    matches.append(r)

            # Check per-bar R = 9*(evt_idx+1) % 56
            expected_local = (9 * (evt_idx + 1)) % 56
            local_match = expected_local in matches

            match_str = ",".join(str(r) for r in matches[:8])
            if len(matches) > 8:
                match_str += "..."
            marker = " ✓LOCAL" if local_match else ""
            print(f"  e{evt_idx:2d} (G{local_idx:3d}): Rs=[{match_str}] ({len(matches)} hits){marker}")
            local_idx += 1

    # --- Phase 4: Alternative decodings ---
    print("\n" + "=" * 70)
    print("PHASE 4: Alternative decodings")
    print("=" * 70)

    # 4a: Raw byte analysis — is note in a fixed byte position?
    print("\n4a: Note in fixed byte position?")
    for byte_pos in range(7):
        hits = 0
        total = 0
        for bar_idx, (header, events, rem) in enumerate(bars):
            for evt in events:
                total += 1
                if evt[byte_pos] in TARGET_NOTES:
                    hits += 1
        print(f"  Byte[{byte_pos}]: {hits}/{total} events match a target note ({hits*100//max(total,1)}%)")

    # 4b: XOR with constant — try all 256 single-byte XOR keys on each byte position
    print("\n4b: XOR with constant byte key?")
    for byte_pos in range(7):
        best_key = -1
        best_hits = 0
        for key in range(256):
            hits = 0
            total = 0
            for _, (_, events, _) in enumerate(bars):
                for evt in events:
                    total += 1
                    if (evt[byte_pos] ^ key) in TARGET_NOTES:
                        hits += 1
            if hits > best_hits:
                best_hits = hits
                best_key = key
        pct = best_hits * 100 // max(total, 1)
        if pct > 10:  # Only show if better than random
            print(f"  Byte[{byte_pos}] XOR 0x{best_key:02X}: {best_hits}/{total} ({pct}%)")

    # 4c: Simple addition/subtraction on note byte
    print("\n4c: Addition/subtraction per byte position?")
    for byte_pos in range(7):
        best_offset = -1
        best_hits = 0
        for offset in range(128):
            hits = 0
            total = 0
            for _, (_, events, _) in enumerate(bars):
                for evt in events:
                    total += 1
                    if ((evt[byte_pos] + offset) & 0x7F) in TARGET_NOTES:
                        hits += 1
                    if ((evt[byte_pos] - offset) & 0x7F) in TARGET_NOTES:
                        hits += 1  # count both directions
            if hits > best_hits:
                best_hits = hits
                best_offset = offset
        pct = best_hits * 100 // max(total * 2, 1)  # *2 because we try both + and -
        if pct > 10:
            print(f"  Byte[{byte_pos}] ±{best_offset}: {best_hits}/{total*2} ({pct}%)")

    # 4d: Correlations between consecutive events
    print("\n4d: Event-to-event XOR patterns")
    for bar_idx, (header, events, rem) in enumerate(bars):
        if bar_idx > 1:
            break  # Just show first 2 bars
        print(f"  Bar {bar_idx}:")
        for i in range(min(len(events) - 1, 5)):
            v1 = int.from_bytes(events[i], "big")
            v2 = int.from_bytes(events[i + 1], "big")
            xor = v1 ^ v2
            diff = (v2 - v1) % (1 << 56)
            print(f"    E{i}⊕E{i+1} = {xor:014X}  diff = {diff:014X}")

    # 4e: Header-event relationship
    print("\n4e: Header XOR with events")
    for bar_idx, (header, events, rem) in enumerate(bars):
        if bar_idx > 1:
            break
        hdr7 = int.from_bytes(header[:7], "big")
        print(f"  Bar {bar_idx} header = {header[:7].hex()}")
        for i, evt in enumerate(events[:5]):
            val = int.from_bytes(evt, "big")
            xor = val ^ hdr7
            print(f"    H⊕E{i} = {xor:014X}")
            # Try decoding the XOR result
            for r in range(56):
                derot = rot_right(xor, r)
                f0 = extract_9bit(derot, 0)
                note = f0 & 0x7F
                if note in TARGET_NOTES:
                    print(f"      R={r} → note {note}")
                    break

    # --- Phase 5: Full velocity matching ---
    print("\n" + "=" * 70)
    print("PHASE 5: Velocity-constrained search")
    print("=" * 70)
    print("Looking for R values where BOTH note AND velocity match ground truth...")

    # From capture: most events are vel=32 (code=12: 127-12*8=31≈32) or vel=127 (code=0)
    # vel_code = [F0_bit8, F0_bit7, rem_bit1, rem_bit0]
    # vel=127 → code=0 → all bits 0 → F0 < 128, rem=0
    # vel=32  → code=12 → 1100 → F0_bit8=1, F0_bit7=1, rem=0 → F0 >= 384 (bit8+bit7)
    # Wait: vel_code = (f0_bit8 << 3) | (f0_bit7 << 2) | (remainder & 0x3)
    # vel=127: code=0: f0_bit8=0, f0_bit7=0, rem=0 → F0 is just the note (< 128)
    # vel=32: 127-32=95, 95/8≈12: code=12=0b1100: f0_bit8=1, f0_bit7=1, rem=0
    #   → F0 = note | 0x180 (bits 8 and 7 set) → F0 >= 384

    vel127_events = 0
    vel32_events = 0

    for bar_idx, (header, events, rem) in enumerate(bars):
        for evt_idx, evt in enumerate(events):
            val = int.from_bytes(evt, "big")
            for r in range(56):
                derot = rot_right(val, r)
                f0 = extract_9bit(derot, 0)
                note = f0 & 0x7F
                remainder = derot & 0x3

                if note not in TARGET_NOTES:
                    continue

                f0_bit8 = (f0 >> 8) & 1
                f0_bit7 = (f0 >> 7) & 1
                vel_code = (f0_bit8 << 3) | (f0_bit7 << 2) | remainder
                vel = max(1, 127 - vel_code * 8)

                if vel == 127:
                    vel127_events += 1
                elif 25 <= vel <= 39:  # vel≈32
                    vel32_events += 1

    print(f"  Rotation candidates with vel=127: {vel127_events}")
    print(f"  Rotation candidates with vel≈32:  {vel32_events}")

    # --- Phase 6: Known pattern comparison ---
    print("\n" + "=" * 70)
    print("PHASE 6: Known pattern byte comparison")
    print("=" * 70)

    kp_path = os.path.join(os.path.dirname(syx_path), "known_pattern.syx")
    if os.path.exists(kp_path):
        kp_data = get_track_data(kp_path, 0, 0)
        print(f"known_pattern track data: {len(kp_data)} bytes")
        print(f"SGT track data:           {len(data)} bytes")
        print(f"\nknown_pattern header (28 bytes):")
        print(f"  {kp_data[:28].hex()}")
        print(f"SGT header (28 bytes):")
        print(f"  {data[:28].hex()}")

        # Compare preamble area
        print(f"\nPreamble comparison:")
        print(f"  KP bytes 24-27:  {kp_data[24:28].hex()}")
        print(f"  SGT bytes 24-27: {data[24:28].hex()}")

        # Byte-level statistics
        kp_zeros = sum(1 for b in kp_data[28:] if b == 0)
        sgt_zeros = sum(1 for b in data[28:] if b == 0)
        print(f"\nZero byte ratio (after header):")
        print(f"  KP:  {kp_zeros}/{len(kp_data)-28} = {kp_zeros*100//(len(kp_data)-28)}%")
        print(f"  SGT: {sgt_zeros}/{len(data)-28} = {sgt_zeros*100//max(len(data)-28,1)}%")

        # Byte value distribution
        print(f"\nByte distribution (after preamble, event data only):")
        kp_preamble, kp_bars = extract_events_dc_only(kp_data)
        kp_evt_bytes = b""
        for _, evts, _ in kp_bars:
            for e in evts:
                kp_evt_bytes += e

        sgt_evt_bytes = b""
        for _, evts, _ in bars:
            for e in evts:
                sgt_evt_bytes += e

        print(f"  KP event bytes:  {len(kp_evt_bytes)} ({len(kp_evt_bytes)//7} events)")
        print(f"  SGT event bytes: {len(sgt_evt_bytes)} ({len(sgt_evt_bytes)//7} events)")

        # Entropy comparison
        for label, bdata in [("KP", kp_evt_bytes), ("SGT", sgt_evt_bytes)]:
            counts = Counter(bdata)
            total = len(bdata)
            entropy = -sum((c/total) * (c/total).bit_length() for c in counts.values() if c > 0)
            unique = len(counts)
            print(f"  {label}: {unique} unique byte values, most common: {counts.most_common(5)}")
    else:
        print(f"known_pattern.syx not found at {kp_path}")

    return all_candidates


def analyze_left_rotations(syx_path: str, section: int = 0, track: int = 0):
    """Try left rotations too — maybe we have the direction wrong for complex data."""
    data = get_track_data(syx_path, section, track)
    if not data:
        return

    preamble, bars = extract_events_dc_only(data)

    print("\n" + "=" * 70)
    print("PHASE 7: LEFT rotation candidates")
    print("=" * 70)

    global_idx = 0
    for bar_idx, (header, events, rem) in enumerate(bars):
        print(f"\n--- Bar {bar_idx} ---")
        for evt_idx, evt in enumerate(events):
            val = int.from_bytes(evt, "big")
            matches_left = []
            matches_right = []

            for r in range(56):
                # Left rotate
                derot_l = rot_left(val, r)
                f0_l = extract_9bit(derot_l, 0)
                note_l = f0_l & 0x7F
                if note_l in TARGET_NOTES:
                    matches_left.append(r)

                # Right rotate
                derot_r = rot_right(val, r)
                f0_r = extract_9bit(derot_r, 0)
                note_r = f0_r & 0x7F
                if note_r in TARGET_NOTES:
                    matches_right.append(r)

            print(f"  e{evt_idx:2d} (G{global_idx:3d}): Left={len(matches_left)} Right={len(matches_right)}  L:[{','.join(str(r) for r in matches_left[:5])}] R:[{','.join(str(r) for r in matches_right[:5])}]")
            global_idx += 1

            if global_idx > 30:
                print("  ... (truncated)")
                return


def try_different_field_widths(syx_path: str, section: int = 0, track: int = 0):
    """What if events aren't 56-bit / 9-bit fields? Try other decompositions."""
    data = get_track_data(syx_path, section, track)
    if not data:
        return

    preamble, bars = extract_events_dc_only(data)

    print("\n" + "=" * 70)
    print("PHASE 8: Alternative field widths")
    print("=" * 70)

    # What if events are 8-bit fields (plain bytes after some transform)?
    # Or 7-bit fields (like MIDI)?
    # Or the note is at a different bit position?

    for bar_idx, (header, events, rem) in enumerate(bars):
        if bar_idx > 0:
            break

        print(f"\nBar {bar_idx} events (first 10):")
        for evt_idx, evt in enumerate(events[:10]):
            val = int.from_bytes(evt, "big")

            # Try note at various bit positions without rotation
            notes_found = []
            for bit_start in range(0, 49):
                # 7-bit extraction
                note7 = (val >> (56 - bit_start - 7)) & 0x7F
                if note7 in TARGET_NOTES:
                    notes_found.append(f"7b@{bit_start}→{note7}")
                # 8-bit extraction
                if bit_start <= 48:
                    note8 = (val >> (56 - bit_start - 8)) & 0xFF
                    if note8 in TARGET_NOTES:
                        notes_found.append(f"8b@{bit_start}→{note8}")

            found_str = ", ".join(notes_found[:5]) if notes_found else "none"
            print(f"  E{evt_idx}: {evt.hex()} → unrot matches: [{found_str}]")


if __name__ == "__main__":
    sgt_path = os.path.join(os.path.dirname(__file__), "captured", "QY70_SGT.syx")

    if not os.path.exists(sgt_path):
        # Try alternative paths
        for alt in ["captured/user_style_live.syx", "captured/ground_truth_style.syx"]:
            alt_path = os.path.join(os.path.dirname(__file__), alt)
            if os.path.exists(alt_path):
                sgt_path = alt_path
                break

    print(f"Using: {sgt_path}")
    print(f"Exists: {os.path.exists(sgt_path)}")

    if os.path.exists(sgt_path):
        candidates = analyze_rotations(sgt_path, section=0, track=0)
        analyze_left_rotations(sgt_path, section=0, track=0)
        try_different_field_widths(sgt_path, section=0, track=0)
    else:
        print("SGT SysEx file not found. Available .syx files:")
        cap_dir = os.path.join(os.path.dirname(__file__), "captured")
        if os.path.isdir(cap_dir):
            for f in sorted(os.listdir(cap_dir)):
                if f.endswith(".syx"):
                    full = os.path.join(cap_dir, f)
                    print(f"  {f} ({os.path.getsize(full)} bytes)")
