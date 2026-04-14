#!/usr/bin/env python3
"""Test whether delimiter bytes (0xDC, 0x9E) could appear INSIDE events,
causing false segmentation and explaining trailing bytes.

Approach:
1. Treat the entire track data (after 28-byte preamble) as a continuous stream
2. DON'T split on delimiters — count total bytes minus headers
3. Check if ignoring delimiters gives better 7-byte alignment
4. Check if merging trail+header across segment boundaries works

Also test: what if header size varies by segment type?
"""

import sys, os
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from qymanager.formats.qy70.sysex_parser import SysExParser

XG_RANGE = set(range(13, 88))
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

def decode(evt, r_val):
    val = int.from_bytes(evt, "big")
    derot = rot_right(val, r_val)
    f0 = f9(derot, 0)
    f1 = f9(derot, 1)
    f2 = f9(derot, 2)
    f5 = f9(derot, 5)
    rem = derot & 0x3
    note = f0 & 0x7F
    bit8 = (f0 >> 8) & 1
    bit7 = (f0 >> 7) & 1
    vel_code = (bit8 << 3) | (bit7 << 2) | rem
    midi_vel = max(1, 127 - vel_code * 8)
    beat = f1 >> 7
    clock = ((f1 & 0x7F) << 2) | (f2 >> 7)
    tick = beat * 480 + clock
    return note, midi_vel, f5, tick, vel_code, f0


def get_track_data(syx_path, section, track):
    """Get raw track data without any segmentation."""
    parser = SysExParser()
    messages = parser.parse_file(syx_path)
    al = section * 8 + track
    data = b""
    for m in messages:
        if m.is_style_data and m.address_low == al:
            if m.decoded_data is not None:
                data += m.decoded_data
    return data


def main():
    base = os.path.dirname(os.path.abspath(__file__))
    syx = os.path.join(base, "captured", "ground_truth_style.syx")
    track_names = ["RHY1", "RHY2", "BASS", "CHD1", "CHD2", "PAD", "PHR1", "PHR2"]

    # ============================================================
    # 1. Raw stream analysis: locate ALL delimiters and check alignment
    # ============================================================
    print(f"{'='*80}")
    print(f"  RAW STREAM ANALYSIS: delimiter positions and alignment")
    print(f"{'='*80}")

    for track in range(8):
        data = get_track_data(syx, 0, track)
        if len(data) < 28:
            continue

        event_data = data[28:]
        total = len(event_data)

        # Find ALL delimiter positions
        delim_positions = []
        for i, b in enumerate(event_data):
            if b in (0xDC, 0x9E):
                delim_positions.append((i, b))

        # Calculate segment sizes
        seg_sizes = []
        prev = 0
        for pos, _ in delim_positions:
            seg_sizes.append(pos - prev)
            prev = pos + 1
        seg_sizes.append(total - prev)  # last segment

        # Total bytes minus delimiters
        total_event_bytes = total - len(delim_positions)

        # If we subtract 13-byte header per segment
        n_segs = len(delim_positions) + 1
        total_minus_headers = total_event_bytes - (n_segs * 13)
        alignment = total_minus_headers % 7

        # What if first segment has different header?
        # Try: first segment 13B, rest 0B (no headers after first)
        total_no_repeat_hdr = total_event_bytes - 13
        alignment_no_repeat = total_no_repeat_hdr % 7

        print(f"\n  {track_names[track]}: {total}B total, "
              f"{len(delim_positions)} delimiters, {n_segs} segments")
        print(f"    Segment sizes: {seg_sizes}")
        print(f"    Per-segment (size-13)%7: "
              f"{[(s-13)%7 if s>=13 else 'SHORT' for s in seg_sizes]}")
        print(f"    Total event bytes (no delims): {total_event_bytes}")
        print(f"    Minus {n_segs}×13B headers: {total_minus_headers} → %7={alignment}")
        print(f"    Minus 1×13B header only: {total_no_repeat_hdr} → %7={alignment_no_repeat}")

        # What if delimiters are NOT separators but part of events?
        # Total stream - 13B header at start, all as 7-byte events
        stream_no_split = total - 13
        align_nosplit = stream_no_split % 7
        print(f"    No split (stream-13): {stream_no_split} → %7={align_nosplit}")

    # ============================================================
    # 2. Test: are delimiter positions at 7-byte-aligned offsets?
    # ============================================================
    print(f"\n{'='*80}")
    print(f"  DELIMITER ALIGNMENT: are delimiters at 7-byte boundaries?")
    print(f"{'='*80}")

    for track in range(8):
        data = get_track_data(syx, 0, track)
        if len(data) < 28:
            continue

        event_data = data[28:]
        delim_positions = [(i, b) for i, b in enumerate(event_data)
                           if b in (0xDC, 0x9E)]

        if not delim_positions:
            continue

        print(f"\n  {track_names[track]}:")
        for pos, val in delim_positions:
            # Distance from start after 13-byte header
            offset_from_events = pos - 13
            align = offset_from_events % 7 if offset_from_events >= 0 else -1
            print(f"    Delim 0x{val:02X} at byte {pos}: "
                  f"offset from events = {offset_from_events}, "
                  f"offset%7 = {align}")

    # ============================================================
    # 3. Cumulative event stream: what if index counts across segments?
    # ============================================================
    print(f"\n{'='*80}")
    print(f"  CROSS-SEGMENT CUMULATIVE INDEX (RHY1)")
    print(f"{'='*80}")

    data = get_track_data(syx, 0, 0)
    if len(data) >= 28:
        event_data = data[28:]
        delim_pos = sorted(i for i, b in enumerate(event_data) if b in (0xDC, 0x9E))
        segments = []
        prev = 0
        for dp in delim_pos:
            segments.append(event_data[prev:dp])
            prev = dp + 1
        segments.append(event_data[prev:])

        # Decode with GLOBAL event index (cumulative across segments)
        global_idx = 0
        total_valid = 0
        total_events = 0

        print(f"\n  Model: R = 9 * (global_index + 1), index continues across segments")
        for seg_idx, seg in enumerate(segments):
            if len(seg) < 20:
                global_idx += max(0, (len(seg) - 13) // 7)
                continue
            nevts = (len(seg) - 13) // 7
            print(f"\n  Seg {seg_idx} (events at global indices {global_idx}-{global_idx+nevts-1}):")

            for i in range(nevts):
                evt = seg[13 + i * 7: 13 + (i + 1) * 7]
                if len(evt) != 7:
                    continue
                total_events += 1

                # Per-segment cumulative (proven best)
                r_seg = 9 * (i + 1)
                note_s, vel_s, gate_s, tick_s, *_ = decode(evt, r_seg)
                ok_s = note_s in XG_RANGE

                # Global cumulative
                r_global = 9 * (global_idx + 1)
                note_g, vel_g, gate_g, tick_g, *_ = decode(evt, r_global)
                ok_g = note_g in XG_RANGE

                if ok_s:
                    total_valid += 1

                name_s = GM_DRUMS.get(note_s, f'n{note_s}')
                name_g = GM_DRUMS.get(note_g, f'n{note_g}')
                seg_mark = "✓" if ok_s else "✗"
                glob_mark = "✓" if ok_g else "✗"

                print(f"    e{i}(g{global_idx}): "
                      f"seg R={r_seg:>3}→{note_s:>3}({name_s:>10}){seg_mark} | "
                      f"glob R={r_global:>3}→{note_g:>3}({name_g:>10}){glob_mark}")

                global_idx += 1

        print(f"\n  Per-segment cumulative valid: {total_valid}/{total_events}")

    # ============================================================
    # 4. Variable header hypothesis
    # ============================================================
    print(f"\n{'='*80}")
    print(f"  VARIABLE HEADER SIZE BY FIRST BYTE")
    print(f"{'='*80}")

    # Hypothesis: header size depends on first byte
    # 0x1A (standard): 13 bytes → (len-13)%7 = trail
    # 0x9B/0xDE/0x98 (init): different size?
    # 0x1E (seg 11): different?

    for track in range(8):
        data = get_track_data(syx, 0, track)
        if len(data) < 28:
            continue

        event_data = data[28:]
        delim_pos = sorted(i for i, b in enumerate(event_data) if b in (0xDC, 0x9E))
        segments = []
        prev = 0
        for dp in delim_pos:
            segments.append(event_data[prev:dp])
            prev = dp + 1
        segments.append(event_data[prev:])

        found = False
        for seg_idx, seg in enumerate(segments):
            if len(seg) < 13:
                continue
            first_byte = seg[0]
            trail_13 = (len(seg) - 13) % 7

            # Try header sizes 6-20 to find zero-trail fit
            best_fits = []
            for hdr_size in range(6, 21):
                if len(seg) >= hdr_size + 7:
                    trail = (len(seg) - hdr_size) % 7
                    if trail == 0:
                        nevts = (len(seg) - hdr_size) // 7
                        best_fits.append((hdr_size, nevts))

            if trail_13 != 0 and best_fits:
                if not found:
                    print(f"\n  {track_names[track]}:")
                    found = True
                fits_str = ", ".join(f"hdr={h}→{n}ev" for h, n in best_fits)
                print(f"    Seg {seg_idx}: first=0x{first_byte:02X} "
                      f"len={len(seg)} trail@13={trail_13} | "
                      f"zero-trail fits: {fits_str}")

    # ============================================================
    # 5. Test: trailing bytes as continuation bits
    # ============================================================
    print(f"\n{'='*80}")
    print(f"  TRAILING BYTE BIT PATTERNS")
    print(f"{'='*80}")

    all_trails = []
    for track in range(8):
        data = get_track_data(syx, 0, track)
        if len(data) < 28:
            continue
        event_data = data[28:]
        delim_pos = sorted(i for i, b in enumerate(event_data) if b in (0xDC, 0x9E))
        segments = []
        prev = 0
        for dp in delim_pos:
            segments.append(event_data[prev:dp])
            prev = dp + 1
        segments.append(event_data[prev:])

        for seg in segments:
            if len(seg) < 20:
                continue
            trail_count = (len(seg) - 13) % 7
            if trail_count > 0:
                trail = seg[-trail_count:]
                all_trails.append((track_names[track], trail))

    print(f"\n  Trail bytes in binary:")
    for tname, trail in all_trails:
        bits = ' '.join(f'{b:08b}' for b in trail)
        # Check for high-bit patterns
        high_bits = all(b & 0x80 for b in trail)
        low_bits = all(not (b & 0x80) for b in trail)
        zero_end = trail[-1] == 0x00 if trail else False
        print(f"    {tname:>5}: {trail.hex():>12} = {bits}"
              f"  {'ALL_HI' if high_bits else ''}"
              f"  {'ALL_LO' if low_bits else ''}"
              f"  {'ZERO_END' if zero_end else ''}")


if __name__ == "__main__":
    main()
