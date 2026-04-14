#!/usr/bin/env python3
"""Deep analysis of 2543 (drum/pattern) encoding.

Builds on Session 12 findings:
- 2543 uses CONSTANT rotation (same R for all events), not cumulative
- R=9 gives best beat validity (~78%)
- F0 appears to contain note number (36=Kick, 44=HH, 46=HHopen, 51=Ride)
- Many F0 values >127 — investigate bit flags
- Events at same timing share F1-F4 but differ in F0, F5

QY70 note event format (Owner's Manual p.196):
- Location: beat:clock (480 clocks/beat)
- Pitch: C-2 (0) to G8 (127)
- Gate time: beat:clock
- Velocity: 001-127
"""

import sys
import os
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import List, Tuple, Dict, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from qymanager.formats.qy70.sysex_parser import SysExParser

# --- Constants ---
R = 9       # Constant rotation amount
GM_DRUM_NAMES = {
    35: "Kick2", 36: "Kick1", 37: "SideStk", 38: "Snare1", 39: "Clap",
    40: "Snare2", 41: "LoFlTom", 42: "HHclose", 43: "HiFlTom", 44: "HHpedal",
    45: "LoTom", 46: "HHopen", 47: "MidLoTom", 48: "HiMidTom", 49: "Crash1",
    50: "HiTom", 51: "Ride1", 52: "Chinese", 53: "RideBell", 54: "Tamb",
    55: "Splash", 56: "Cowbell", 57: "Crash2", 58: "Vibslap", 59: "Ride2",
    60: "HiBongo", 61: "LoBongo", 62: "MuHConga", 63: "OpHConga", 64: "LoConga",
    65: "HiTimbal", 66: "LoTimbal", 67: "HiAgogo", 68: "LoAgogo", 69: "Cabasa",
    70: "Maracas", 71: "ShWhistl", 72: "LgWhistl", 73: "ShGuiro", 74: "LgGuiro",
    75: "Claves", 76: "HiWBlock", 77: "LoWBlock", 78: "MuCuica", 79: "OpCuica",
    80: "MuTriang", 81: "OpTriang",
}


def rot_right(val: int, shift: int, width: int = 56) -> int:
    shift = shift % width
    return ((val >> shift) | (val << (width - shift))) & ((1 << width) - 1)


def extract_9bit(val: int, field_idx: int, total_width: int = 56) -> int:
    shift = total_width - (field_idx + 1) * 9
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


def get_pattern_data(syx_path: str, track: int) -> bytes:
    """Get track data from a Pattern mode capture (AH=02, AM=7E)."""
    parser = SysExParser()
    messages = parser.parse_file(syx_path)
    al = track
    data = b""
    for m in messages:
        if m.is_style_data and m.address_low == al:
            if m.decoded_data is not None:
                data += m.decoded_data
    return data


def extract_segments(data: bytes) -> Tuple[bytes, List[Tuple[bytes, List[bytes]]]]:
    """Extract preamble and segments from decoded track data."""
    if len(data) < 28:
        return b"", []
    preamble = data[24:28]
    event_data = data[28:]

    delim_pos = sorted(i for i, b in enumerate(event_data) if b in (0xDC, 0x9E))

    segments = []
    prev = 0
    for dp in delim_pos:
        segments.append(event_data[prev:dp])
        prev = dp + 1
    segments.append(event_data[prev:])

    bars = []
    for seg in segments:
        if len(seg) >= 20:
            header = seg[:13]
            events = []
            for i in range((len(seg) - 13) // 7):
                evt = seg[13 + i * 7: 13 + (i + 1) * 7]
                if len(evt) == 7:
                    events.append(evt)
            bars.append((header, events))
    return preamble, bars


@dataclass
class DrumEvent:
    seg_idx: int
    evt_idx: int
    raw: bytes
    f0: int
    f1: int
    f2: int
    f3: int
    f4: int
    f5: int
    rem: int
    # F0 decomposition
    f0_bit8: int    # 9th bit
    f0_bit7: int    # 8th bit
    f0_lo7: int     # bits 0-6
    f0_note: int    # proposed note (lo7 if bit8=0, lo7 if bit8=1)


def decode_drum_event(raw: bytes, seg_idx: int, evt_idx: int) -> DrumEvent:
    val = int.from_bytes(raw, "big")
    derot = rot_right(val, R)  # Constant R, NOT R*evt_idx

    f0 = extract_9bit(derot, 0)
    f1 = extract_9bit(derot, 1)
    f2 = extract_9bit(derot, 2)
    f3 = extract_9bit(derot, 3)
    f4 = extract_9bit(derot, 4)
    f5 = extract_9bit(derot, 5)
    rem = derot & 0x3

    f0_bit8 = (f0 >> 8) & 1
    f0_bit7 = (f0 >> 7) & 1
    f0_lo7 = f0 & 0x7F
    f0_note = f0_lo7  # Initial hypothesis

    return DrumEvent(
        seg_idx=seg_idx, evt_idx=evt_idx, raw=raw,
        f0=f0, f1=f1, f2=f2, f3=f3, f4=f4, f5=f5, rem=rem,
        f0_bit8=f0_bit8, f0_bit7=f0_bit7, f0_lo7=f0_lo7, f0_note=f0_note,
    )


def analyze_file(syx_path: str, label: str, section: int = 0, track: int = 0,
                 is_pattern: bool = False):
    """Full analysis of 2543 encoding from a .syx file."""
    print(f"\n{'='*70}")
    print(f"  2543 ANALYSIS: {label}")
    print(f"  File: {os.path.basename(syx_path)}")
    print(f"  Section={section} Track={track} {'(Pattern mode)' if is_pattern else '(Style mode)'}")
    print(f"{'='*70}\n")

    if is_pattern:
        data = get_pattern_data(syx_path, track)
    else:
        data = get_track_data(syx_path, section, track)

    if len(data) < 28:
        print(f"  Insufficient data: {len(data)} bytes")
        return

    preamble, segments = extract_segments(data)
    print(f"  Preamble: {preamble.hex()}")
    print(f"  Data length: {len(data)} bytes")
    print(f"  Segments: {len(segments)}")

    # Decode all events
    all_events: List[DrumEvent] = []
    for seg_idx, (header, events) in enumerate(segments):
        hval = int.from_bytes(header, "big")
        hfields = [(hval >> (104 - (i+1)*9)) & 0x1FF for i in range(11)]

        print(f"\n  --- Segment {seg_idx} ({len(events)} events) ---")
        print(f"  Header hex: {header.hex()}")
        print(f"  Header 9-bit fields: {hfields}")

        for evt_idx, evt in enumerate(events):
            de = decode_drum_event(evt, seg_idx, evt_idx)
            all_events.append(de)

    if not all_events:
        print("  No events decoded")
        return

    print(f"\n{'='*70}")
    print(f"  FIELD ANALYSIS ({len(all_events)} events)")
    print(f"{'='*70}")

    # --- F0 Analysis ---
    print(f"\n  F0 (candidate: note number)")
    print(f"  {'F0':>5} {'bit8':>4} {'bit7':>4} {'lo7':>4} {'GM Drum':>12} {'Count':>5}")
    print(f"  {'-'*40}")
    f0_counter = Counter(e.f0 for e in all_events)
    for f0, cnt in f0_counter.most_common(30):
        bit8 = (f0 >> 8) & 1
        bit7 = (f0 >> 7) & 1
        lo7 = f0 & 0x7F
        name = GM_DRUM_NAMES.get(lo7, f"note{lo7}")
        print(f"  {f0:>5} {bit8:>4} {bit7:>4} {lo7:>4} {name:>12} ×{cnt}")

    # Bit 8 distribution
    bit8_1 = sum(1 for e in all_events if e.f0_bit8)
    bit8_0 = len(all_events) - bit8_1
    print(f"\n  F0 bit8: 0={bit8_0}, 1={bit8_1}")

    # lo7 distribution — are they valid GM drums?
    gm_count = sum(1 for e in all_events if e.f0_lo7 in GM_DRUM_NAMES)
    print(f"  F0 lo7 in GM drums: {gm_count}/{len(all_events)} ({100*gm_count/len(all_events):.0f}%)")

    # --- F1-F4 timing analysis ---
    print(f"\n  F1-F4 (candidate: timing/position)")
    # Group events by (F1,F2,F3,F4) to find simultaneous events
    timing_groups: Dict[Tuple[int,int,int,int], List[DrumEvent]] = defaultdict(list)
    for e in all_events:
        timing_groups[(e.f1, e.f2, e.f3, e.f4)].append(e)

    multi_groups = {k: v for k, v in timing_groups.items() if len(v) > 1}
    print(f"  Unique (F1,F2,F3,F4) tuples: {len(timing_groups)}")
    print(f"  Tuples with >1 event: {len(multi_groups)} (simultaneous notes)")

    if multi_groups:
        print(f"\n  Simultaneous event groups:")
        for key, evts in sorted(multi_groups.items(), key=lambda x: -len(x[1]))[:10]:
            f1, f2, f3, f4 = key
            notes = [f"{e.f0}({GM_DRUM_NAMES.get(e.f0_lo7, e.f0_lo7)})" for e in evts]
            print(f"    F1={f1:3d} F2={f2:3d} F3={f3:3d} F4={f4:3d}  → {', '.join(notes)}")

    # --- F5 analysis (candidate: velocity or gate) ---
    print(f"\n  F5 (candidate: velocity/gate)")
    f5_counter = Counter(e.f5 for e in all_events)
    f5_vals = sorted(f5_counter.keys())
    print(f"  Unique F5 values: {len(f5_vals)}")
    print(f"  Range: {min(f5_vals)} - {max(f5_vals)}")
    print(f"  Distribution:")
    for f5, cnt in f5_counter.most_common(15):
        lo7 = f5 & 0x7F
        print(f"    F5={f5:>4} (lo7={lo7:>3})  ×{cnt}")

    # --- Remainder analysis ---
    print(f"\n  Remainder (2 bits)")
    rem_counter = Counter(e.rem for e in all_events)
    for r, cnt in rem_counter.most_common():
        print(f"    rem={r} ×{cnt}")

    # --- F1 range ---
    f1_vals = sorted(set(e.f1 for e in all_events))
    print(f"\n  F1 range: {min(f1_vals)}-{max(f1_vals)}, {len(f1_vals)} unique values")

    # --- F2 range ---
    f2_vals = sorted(set(e.f2 for e in all_events))
    print(f"\n  F2 range: {min(f2_vals)}-{max(f2_vals)}, {len(f2_vals)} unique values")

    # --- F3 range ---
    f3_vals = sorted(set(e.f3 for e in all_events))
    print(f"\n  F3 range: {min(f3_vals)}-{max(f3_vals)}, {len(f3_vals)} unique values")

    # --- F4 range ---
    f4_vals = sorted(set(e.f4 for e in all_events))
    print(f"\n  F4 range: {min(f4_vals)}-{max(f4_vals)}, {len(f4_vals)} unique values")

    # --- Cross-field correlations ---
    print(f"\n{'='*70}")
    print(f"  CROSS-FIELD ANALYSIS")
    print(f"{'='*70}")

    # F5 by F0 group: does velocity vary with note type?
    print(f"\n  F5 by note (F0 lo7):")
    note_f5: Dict[int, List[int]] = defaultdict(list)
    for e in all_events:
        note_f5[e.f0_lo7].append(e.f5)
    for note in sorted(note_f5.keys()):
        vals = note_f5[note]
        name = GM_DRUM_NAMES.get(note, f"note{note}")
        avg = sum(vals) / len(vals)
        lo7_avg = sum(v & 0x7F for v in vals) / len(vals)
        print(f"    {name:>12} ({note:>3}): F5 avg={avg:.1f} lo7_avg={lo7_avg:.1f} "
              f"range={min(vals)}-{max(vals)} n={len(vals)}")

    # F0 bit8 correlation with other fields
    if bit8_1 > 0 and bit8_0 > 0:
        print(f"\n  F0 bit8=0 vs bit8=1 comparison:")
        for label, events in [("bit8=0", [e for e in all_events if not e.f0_bit8]),
                              ("bit8=1", [e for e in all_events if e.f0_bit8])]:
            if events:
                avg_f5 = sum(e.f5 for e in events) / len(events)
                avg_f1 = sum(e.f1 for e in events) / len(events)
                avg_f3 = sum(e.f3 for e in events) / len(events)
                print(f"    {label}: n={len(events)}, avg F1={avg_f1:.1f}, "
                      f"avg F3={avg_f3:.1f}, avg F5={avg_f5:.1f}")

    # --- Event table (first 30 events) ---
    print(f"\n{'='*70}")
    print(f"  EVENT TABLE (first 30)")
    print(f"{'='*70}")
    print(f"  {'Seg':>3} {'#':>2} {'Raw':>16} {'F0':>5} {'b8':>2} {'lo7':>4}"
          f" {'GM':>10} {'F1':>4} {'F2':>4} {'F3':>4} {'F4':>4} {'F5':>4} {'R':>1}")

    for e in all_events[:30]:
        name = GM_DRUM_NAMES.get(e.f0_lo7, "?")[:10]
        print(f"  {e.seg_idx:>3} {e.evt_idx:>2} {e.raw.hex():>14} {e.f0:>5} {e.f0_bit8:>2}"
              f" {e.f0_lo7:>4} {name:>10} {e.f1:>4} {e.f2:>4} {e.f3:>4} {e.f4:>4}"
              f" {e.f5:>4} {e.rem:>1}")

    # --- Test alternative rotation values ---
    print(f"\n{'='*70}")
    print(f"  ROTATION SCAN (F0 lo7 in GM drums range 35-81)")
    print(f"{'='*70}")

    for test_r in range(0, 56):
        gm_hits = 0
        for e in all_events:
            val = int.from_bytes(e.raw, "big")
            derot = rot_right(val, test_r)
            f0 = extract_9bit(derot, 0)
            lo7 = f0 & 0x7F
            if 35 <= lo7 <= 81:
                gm_hits += 1
        pct = 100 * gm_hits / len(all_events)
        if pct >= 60:
            print(f"  R={test_r:>2}: {gm_hits}/{len(all_events)} ({pct:.0f}%) F0 lo7 in GM drum range")

    # --- Check if F0 bit 8 is note-off flag ---
    # If bit8=1 means note-off, same lo7 should appear with both bit8=0 and bit8=1
    print(f"\n{'='*70}")
    print(f"  BIT8 FLAG TEST: note-on/note-off pairing?")
    print(f"{'='*70}")
    notes_bit8_0 = set(e.f0_lo7 for e in all_events if not e.f0_bit8)
    notes_bit8_1 = set(e.f0_lo7 for e in all_events if e.f0_bit8)
    both = notes_bit8_0 & notes_bit8_1
    only_0 = notes_bit8_0 - notes_bit8_1
    only_1 = notes_bit8_1 - notes_bit8_0
    print(f"  Notes with bit8=0 only: {sorted(only_0)} ({[GM_DRUM_NAMES.get(n,n) for n in sorted(only_0)]})")
    print(f"  Notes with bit8=1 only: {sorted(only_1)} ({[GM_DRUM_NAMES.get(n,n) for n in sorted(only_1)]})")
    print(f"  Notes with both bit8:  {sorted(both)} ({[GM_DRUM_NAMES.get(n,n) for n in sorted(both)]})")

    return all_events


if __name__ == "__main__":
    base = os.path.dirname(os.path.abspath(__file__))

    # Style mode RHY1 (Section 0 = Main A)
    style_syx = os.path.join(base, "captured", "ground_truth_style.syx")
    if os.path.exists(style_syx):
        style_events = analyze_file(style_syx, "Style RHY1 Main-A", section=0, track=0)

    # Pattern mode C1 track
    pattern_syx = os.path.join(base, "captured", "qy70_dump_20260414_114506.syx")
    if os.path.exists(pattern_syx):
        # Pattern mode: track 4 = C1 (from the capture analysis)
        pattern_events = analyze_file(pattern_syx, "Pattern C1", section=0, track=4,
                                      is_pattern=True)
