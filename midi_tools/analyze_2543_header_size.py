#!/usr/bin/env python3
"""Test variable header sizes for 2543 segments.

CRITICAL FINDING: (segment_length - 13) % 7 != 0 for many segments.
This means either:
  A) Headers are variable-length (not always 13 bytes)
  B) There are trailing bytes after events
  C) Some events are not 7 bytes

For each misaligned segment, try header sizes 13-20 and count valid drum notes.
The correct header size should maximize valid notes and minimize anomalies.
"""

import sys, os
from collections import Counter
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from qymanager.formats.qy70.sysex_parser import SysExParser

XG_RANGE = set(range(13, 88))
R = 9

GM_DRUMS = {
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
    82: "Shaker", 83: "JnglBell", 84: "BellTree", 85: "Castanets",
    86: "MuSurdo", 87: "OpSurdo",
}


def rot_right(val, shift, width=56):
    shift = shift % width
    return ((val >> shift) | (val << (width - shift))) & ((1 << width) - 1)

def f9(val, idx, total=56):
    shift = total - (idx + 1) * 9
    return (val >> shift) & 0x1FF if shift >= 0 else -1


def decode_event(evt_bytes):
    """Decode 7-byte event at constant R=9."""
    val = int.from_bytes(evt_bytes, "big")
    derot = rot_right(val, R)
    f0 = f9(derot, 0)
    f1 = f9(derot, 1)
    f2 = f9(derot, 2)
    f3 = f9(derot, 3)
    f4 = f9(derot, 4)
    f5 = f9(derot, 5)
    rem = derot & 0x3
    note = f0 & 0x7F
    bit8 = (f0 >> 8) & 1
    bit7 = (f0 >> 7) & 1
    vel_code = (bit8 << 3) | (bit7 << 2) | rem
    midi_vel = max(1, 127 - vel_code * 8)
    beat = f1 >> 7
    clock_9 = ((f1 & 0x7F) << 2) | (f2 >> 7)
    tick_9 = beat * 480 + clock_9
    return note, midi_vel, f5, tick_9, vel_code, f0, f1, f2, f3, f4, f5, rem


def get_segments(syx_path, section, track):
    """Get raw segment bytes."""
    parser = SysExParser()
    messages = parser.parse_file(syx_path)
    al = section * 8 + track
    data = b""
    for m in messages:
        if m.is_style_data and m.address_low == al:
            if m.decoded_data is not None:
                data += m.decoded_data
    if len(data) < 28:
        return []
    event_data = data[28:]
    delim_pos = sorted(i for i, b in enumerate(event_data) if b in (0xDC, 0x9E))
    segments = []
    prev = 0
    for dp in delim_pos:
        segments.append(event_data[prev:dp])
        prev = dp + 1
    segments.append(event_data[prev:])
    return segments


def score_header_size(seg_bytes, header_size):
    """Try parsing events with given header size, return quality metrics."""
    if len(seg_bytes) < header_size:
        return None
    event_area = seg_bytes[header_size:]
    nevts = len(event_area) // 7
    remainder = len(event_area) % 7
    if nevts == 0:
        return None

    notes_valid = 0
    notes_total = 0
    ticks = []
    events = []

    for i in range(nevts):
        evt = event_area[i * 7: (i + 1) * 7]
        note, vel, gate, tick, vc, f0, f1, f2, f3, f4, f5, rem = decode_event(evt)
        notes_total += 1
        if note in XG_RANGE:
            notes_valid += 1
        ticks.append(tick)
        events.append((note, vel, gate, tick, vc, f0))

    # Monotonicity
    mono = 0
    for i in range(len(ticks) - 1):
        if ticks[i + 1] >= ticks[i]:
            mono += 1
    mono_pct = mono / (len(ticks) - 1) * 100 if len(ticks) > 1 else 100

    return {
        'header_size': header_size,
        'nevts': nevts,
        'remainder': remainder,
        'valid': notes_valid,
        'valid_pct': notes_valid / notes_total * 100 if notes_total > 0 else 0,
        'mono_pct': mono_pct,
        'events': events,
    }


def main():
    base = os.path.dirname(os.path.abspath(__file__))
    syx = os.path.join(base, "captured", "ground_truth_style.syx")
    segments = get_segments(syx, 0, 0)

    # ============================================================
    # 1. Try all header sizes for each segment
    # ============================================================
    print(f"{'='*80}")
    print(f"  HEADER SIZE OPTIMIZATION PER SEGMENT")
    print(f"{'='*80}")

    for seg_idx, seg in enumerate(segments):
        if len(seg) < 20:
            print(f"\n  Seg {seg_idx}: too short ({len(seg)} bytes)")
            continue

        print(f"\n  Seg {seg_idx} ({len(seg)} bytes):")
        print(f"  {'HdrSz':>5} {'Events':>6} {'Trail':>5} {'Valid':>5}"
              f" {'Valid%':>6} {'Mono%':>6} | Notes")

        best_score = -1
        best_hdr = 13

        for hdr_size in range(11, 21):
            result = score_header_size(seg, hdr_size)
            if result and result['nevts'] > 0:
                notes_str = ", ".join(
                    GM_DRUMS.get(n, 'n' + str(n))
                    for n, v, g, t, vc, f0 in result['events']
                )
                aligned = " *" if result['remainder'] == 0 else ""
                score = result['valid_pct'] + (10 if result['remainder'] == 0 else 0)

                print(f"  {hdr_size:>5} {result['nevts']:>6} {result['remainder']:>5}"
                      f" {result['valid']:>5}"
                      f" {result['valid_pct']:>5.0f}%"
                      f" {result['mono_pct']:>5.0f}%"
                      f" | {notes_str[:60]}{aligned}")

                if score > best_score:
                    best_score = score
                    best_hdr = hdr_size

        print(f"  → Best header: {best_hdr} bytes")

    # ============================================================
    # 2. For misaligned segments, compare 13-byte vs optimal header
    # ============================================================
    print(f"\n{'='*80}")
    print(f"  DETAILED COMPARISON: 13-byte vs aligned header (misaligned segs)")
    print(f"{'='*80}")

    misaligned = []
    for seg_idx, seg in enumerate(segments):
        if len(seg) >= 20 and (len(seg) - 13) % 7 != 0:
            misaligned.append((seg_idx, seg))

    for seg_idx, seg in misaligned:
        # Find aligned header size
        for hdr in range(13, 21):
            if (len(seg) - hdr) % 7 == 0 and (len(seg) - hdr) >= 7:
                aligned_hdr = hdr
                break
        else:
            aligned_hdr = 13

        print(f"\n  Segment {seg_idx} ({len(seg)} bytes),"
              f" aligned header = {aligned_hdr}:")

        # Parse with standard 13
        r13 = score_header_size(seg, 13)
        ra = score_header_size(seg, aligned_hdr)

        print(f"\n    Header=13 ({r13['nevts']} events, {r13['remainder']} trailing):")
        for i, (n, v, g, t, vc, f0) in enumerate(r13['events']):
            name = GM_DRUMS.get(n, 'n' + str(n))
            valid = "OK" if n in XG_RANGE else "BAD"
            print(f"      e{i}: note={n:>3} ({name:>10})"
                  f"  vel={v:>3} gate={g:>3} tick={t:>5}  [{valid}]")

        print(f"\n    Header={aligned_hdr} ({ra['nevts']} events, {ra['remainder']} trailing):")
        for i, (n, v, g, t, vc, f0) in enumerate(ra['events']):
            name = GM_DRUMS.get(n, 'n' + str(n))
            valid = "OK" if n in XG_RANGE else "BAD"
            print(f"      e{i}: note={n:>3} ({name:>10})"
                  f"  vel={v:>3} gate={g:>3} tick={t:>5}  [{valid}]")

        # Score comparison
        print(f"\n    13-byte: {r13['valid']}/{r13['nevts']} valid ({r13['valid_pct']:.0f}%),"
              f" mono={r13['mono_pct']:.0f}%")
        print(f"    {aligned_hdr}-byte: {ra['valid']}/{ra['nevts']} valid ({ra['valid_pct']:.0f}%),"
              f" mono={ra['mono_pct']:.0f}%")

    # ============================================================
    # 3. What are the "extra" bytes in the header?
    # ============================================================
    print(f"\n{'='*80}")
    print(f"  EXTRA HEADER BYTES ANALYSIS")
    print(f"{'='*80}")

    for seg_idx, seg in enumerate(segments):
        if len(seg) < 20:
            continue
        remainder = (len(seg) - 13) % 7
        if remainder != 0:
            # Find the aligned header size
            for hdr in range(13, 21):
                if (len(seg) - hdr) % 7 == 0:
                    break
            extra = seg[13:hdr]
            print(f"  Seg {seg_idx}: extra bytes at 13..{hdr}: {extra.hex()}"
                  f" (values: {list(extra)})")

    # ============================================================
    # 4. Global stats with aligned vs 13-byte headers
    # ============================================================
    print(f"\n{'='*80}")
    print(f"  GLOBAL STATISTICS")
    print(f"{'='*80}")

    total_events_13 = 0
    valid_events_13 = 0
    total_events_a = 0
    valid_events_a = 0
    mono_pairs_13 = 0
    mono_ok_13 = 0
    mono_pairs_a = 0
    mono_ok_a = 0

    for seg_idx, seg in enumerate(segments):
        if len(seg) < 20:
            continue

        # 13-byte header
        r13 = score_header_size(seg, 13)
        if r13:
            total_events_13 += r13['nevts']
            valid_events_13 += r13['valid']
            if r13['nevts'] > 1:
                ticks = [e[3] for e in r13['events']]
                for i in range(len(ticks)-1):
                    mono_pairs_13 += 1
                    if ticks[i+1] >= ticks[i]:
                        mono_ok_13 += 1

        # Aligned header
        for hdr in range(13, 21):
            if (len(seg) - hdr) % 7 == 0 and (len(seg) - hdr) >= 7:
                break
        else:
            hdr = 13
        ra = score_header_size(seg, hdr)
        if ra:
            total_events_a += ra['nevts']
            valid_events_a += ra['valid']
            if ra['nevts'] > 1:
                ticks = [e[3] for e in ra['events']]
                for i in range(len(ticks)-1):
                    mono_pairs_a += 1
                    if ticks[i+1] >= ticks[i]:
                        mono_ok_a += 1

    print(f"\n  13-byte header:")
    print(f"    Events: {total_events_13}, Valid: {valid_events_13}"
          f" ({100*valid_events_13/total_events_13:.0f}%)")
    print(f"    Monotonicity: {mono_ok_13}/{mono_pairs_13}"
          f" ({100*mono_ok_13/mono_pairs_13:.0f}%)" if mono_pairs_13 > 0 else "")

    print(f"\n  Aligned header (variable):")
    print(f"    Events: {total_events_a}, Valid: {valid_events_a}"
          f" ({100*valid_events_a/total_events_a:.0f}%)")
    print(f"    Monotonicity: {mono_ok_a}/{mono_pairs_a}"
          f" ({100*mono_ok_a/mono_pairs_a:.0f}%)" if mono_pairs_a > 0 else "")

    # ============================================================
    # 5. Could the extra bytes be a SECOND delimiter or sub-header?
    # ============================================================
    print(f"\n{'='*80}")
    print(f"  RAW BYTE STREAM AROUND SEGMENT BOUNDARIES")
    print(f"{'='*80}")

    parser = SysExParser()
    messages = parser.parse_file(syx)
    data = b""
    for m in messages:
        if m.is_style_data and m.address_low == 0:
            if m.decoded_data is not None:
                data += m.decoded_data
    if len(data) >= 28:
        event_data = data[28:]
        delim_pos = sorted(i for i, b in enumerate(event_data) if b in (0xDC, 0x9E))

        print(f"\n  Total event data: {len(event_data)} bytes")
        print(f"  Delimiters at: {delim_pos}")

        # Show bytes around each delimiter
        for dp in delim_pos:
            start = max(0, dp - 10)
            end = min(len(event_data), dp + 15)
            chunk = event_data[start:end]
            hex_parts = []
            for i, b in enumerate(chunk):
                pos = start + i
                if pos == dp:
                    hex_parts.append(f"[{b:02x}]")
                else:
                    hex_parts.append(f"{b:02x}")
            print(f"  pos {dp}: ...{' '.join(hex_parts)}...")


if __name__ == "__main__":
    main()
