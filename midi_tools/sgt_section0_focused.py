#!/usr/bin/env python3
"""Focused analysis: decode ONLY MAIN-A (section 0) and compare.

Key question: does R=9*(i+1) work per-segment (9E-delimited),
or is the event counter continuous across segments?
Also: check what sections the capture actually played.
"""

import json
import sys
import os
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from midi_tools.event_decoder import (
    get_track_data, rot_right, extract_9bit,
    SECTION_NAMES, TRACK_NAMES,
)

SYX_PATH = "tests/fixtures/QY70_SGT.syx"
CAPTURE_PATH = "midi_tools/captured/sgt_full_capture.json"

# Target from capture
DRUM_TARGETS = {36, 38, 42, 44, 54, 68}


def analyze_section_0_rhy1():
    """Exhaustive analysis of RHY1 MAIN-A decoding."""
    data = get_track_data(SYX_PATH, 0, 0)
    print(f"RHY1 MAIN-A: {len(data)} bytes")

    # Parse segments manually (same as extract_bars but with more detail)
    event_data = data[28:]
    delim_pos = sorted(
        (i, event_data[i]) for i in range(len(event_data))
        if event_data[i] in (0xDC, 0x9E)
    )

    print(f"\nDelimiters in event_data:")
    for pos, val in delim_pos:
        name = "DC" if val == 0xDC else "9E"
        abs_pos = pos + 28
        print(f"  offset {pos} (abs 0x{abs_pos:03X}): {name}")

    # Split into segments
    segments = []
    prev = 0
    for dp, delim in delim_pos:
        seg = event_data[prev:dp]
        segments.append((seg, prev, prev + 28))
        prev = dp + 1
    seg = event_data[prev:]
    if seg:
        segments.append((seg, prev, prev + 28))

    print(f"\nSegments: {len(segments)}")

    # Try multiple R strategies across all events
    global_idx = 0  # Global event counter (never resets)
    note_idx = 0    # Note event counter (never resets)

    all_decoded = []

    for si, (seg, rel_off, abs_off) in enumerate(segments):
        if len(seg) < 20:
            # Count any 7-byte events anyway for global counter
            n_events = max(0, (len(seg) - 13) // 7) if len(seg) >= 13 else 0
            # Check: maybe this is NOT [header + events] but just padding/extra
            print(f"\n  Seg {si}: {len(seg)} bytes (skip, too short) "
                  f"hex={seg.hex()[:40]}")
            global_idx += n_events
            continue

        header = seg[:13]
        events = []
        for i in range((len(seg) - 13) // 7):
            evt = seg[13 + i * 7: 13 + (i + 1) * 7]
            if len(evt) == 7:
                events.append(evt)

        extra_bytes = (len(seg) - 13) % 7
        print(f"\n  Seg {si}: {len(seg)} bytes, header={header[:4].hex()}..., "
              f"{len(events)} events, {extra_bytes} extra bytes")

        local_idx = 0  # Resets per segment

        for ei, evt in enumerate(events):
            val = int.from_bytes(evt, "big")

            # Strategy 1: R=9*(local+1) — per-segment reset
            r_local = (9 * (local_idx + 1)) % 56
            d_local = rot_right(val, r_local)
            f0_local = extract_9bit(d_local, 0)
            note_local = f0_local & 0x7F

            # Strategy 2: R=9*(global+1) — never resets
            r_global = (9 * (global_idx + 1)) % 56
            d_global = rot_right(val, r_global)
            f0_global = extract_9bit(d_global, 0)
            note_global = f0_global & 0x7F

            # Strategy 3: brute force — find which R gives target note
            best_r = None
            best_note = None
            for r in range(56):
                d = rot_right(val, r)
                f0 = extract_9bit(d, 0)
                n = f0 & 0x7F
                if n in DRUM_TARGETS:
                    best_r = r
                    best_note = n
                    break  # Take first match

            # Velocity extraction from best R
            vel_str = ""
            if best_r is not None:
                d = rot_right(val, best_r)
                f0 = extract_9bit(d, 0)
                rem = d & 0x3
                bit8 = (f0 >> 8) & 1
                bit7 = (f0 >> 7) & 1
                vel_code = (bit8 << 3) | (bit7 << 2) | rem
                vel = max(1, 127 - vel_code * 8)
                vel_str = f"v={vel:3d}"

            local_ok = "✓" if note_local in DRUM_TARGETS else "✗"
            global_ok = "✓" if note_global in DRUM_TARGETS else "✗"
            brute_str = f"R={best_r:2d}→{best_note}" if best_r is not None else "NONE"

            if ei < 15 or (best_r is not None and best_note in DRUM_TARGETS):
                print(f"    e{ei} g{global_idx}: {evt.hex()} | "
                      f"local R={r_local:2d}→{note_local:3d}{local_ok} | "
                      f"global R={r_global:2d}→{note_global:3d}{global_ok} | "
                      f"brute: {brute_str} {vel_str}")

            if best_r is not None:
                all_decoded.append({
                    "seg": si, "local": local_idx, "global": global_idx,
                    "note": best_note, "r": best_r,
                    "r_local": r_local, "r_global": r_global,
                })

            local_idx += 1
            global_idx += 1

    # Analysis of R patterns
    print(f"\n{'='*70}")
    print(f"  R-PATTERN ANALYSIS")
    print(f"{'='*70}")

    # Check: what's the relationship between brute-force R and indices?
    for d in all_decoded[:30]:
        r = d["r"]
        gl = d["global"]
        loc = d["local"]

        # Check if R = 9*(k+1) for some k
        for k in range(56):
            if (9 * (k + 1)) % 56 == r:
                r_match = f"9*({k}+1)"
                break
        else:
            r_match = "no 9k+1 match"

        # Check offset from local and global
        delta_local = (r - (9 * (loc + 1)) % 56) % 56
        delta_global = (r - (9 * (gl + 1)) % 56) % 56

        print(f"  seg{d['seg']} e{loc:2d} g{gl:3d}: "
              f"note={d['note']:2d} R={r:2d} "
              f"Δlocal={delta_local:2d} Δglobal={delta_global:2d} "
              f"{r_match}")


def analyze_capture_timing():
    """Check what sections the capture actually played."""
    with open(CAPTURE_PATH) as f:
        cap = json.load(f)

    ch9 = cap["channels"]["9"]
    bpm = cap["bpm"]
    beat_dur = 60.0 / bpm  # seconds per beat
    bar_dur = beat_dur * 4  # 4/4 time

    print(f"\n{'='*70}")
    print(f"  CAPTURE TIMING ANALYSIS")
    print(f"{'='*70}")
    print(f"  BPM: {bpm}, beat: {beat_dur:.3f}s, bar: {bar_dur:.3f}s")
    print(f"  Total ch9 notes: {ch9['note_count']}")
    print(f"  Duration: {cap['duration']}s = {cap['duration']/bar_dur:.1f} bars")

    # Count notes per bar period
    first_10 = ch9["first_10"]
    print(f"\n  First 10 drum events:")
    for evt in first_10:
        bar = int(evt["t"] / bar_dur)
        beat = (evt["t"] % bar_dur) / beat_dur
        print(f"    t={evt['t']:6.3f}s bar={bar} beat={beat:.2f} "
              f"note={evt['note']:3d} vel={evt['vel']:3d}")


if __name__ == "__main__":
    analyze_section_0_rhy1()
    analyze_capture_timing()
