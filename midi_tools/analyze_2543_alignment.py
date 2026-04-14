#!/usr/bin/env python3
"""Check 2543 segment alignment and padding pattern detection.

Key questions:
1. Is (segment_length - 13) always a multiple of 7? If not, our event parsing is wrong.
2. What raw bytes produce the n125 "padding" events in Pattern mode?
3. What happens if we interpret anomalous events with NO rotation (R=0)?
4. Can we find a byte-level discriminator for real vs non-real events?
"""

import sys, os
from collections import Counter
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from qymanager.formats.qy70.sysex_parser import SysExParser

XG_RANGE = range(13, 88)  # XG drum notes 13-87
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


def get_raw_track_data(syx_path, section, track):
    """Return raw track data and parsed segments."""
    parser = SysExParser()
    messages = parser.parse_file(syx_path)
    al = section * 8 + track
    data = b""
    for m in messages:
        if m.is_style_data and m.address_low == al:
            if m.decoded_data is not None:
                data += m.decoded_data
    if len(data) < 28:
        return None, []
    event_data = data[28:]
    delim_pos = sorted(i for i, b in enumerate(event_data) if b in (0xDC, 0x9E))
    segments = []
    prev = 0
    for dp in delim_pos:
        seg_bytes = event_data[prev:dp]
        segments.append((prev, seg_bytes, event_data[dp]))  # offset, bytes, delimiter
        prev = dp + 1
    segments.append((prev, event_data[prev:], None))  # last segment, no delimiter
    return event_data, segments


def decode_r(evt_bytes, r=9):
    """Decode event with given rotation."""
    val = int.from_bytes(evt_bytes, "big")
    derot = rot_right(val, r)
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
    return note, vel_code, f0, f1, f2, f3, f4, f5, rem


def main():
    base = os.path.dirname(os.path.abspath(__file__))

    # ============================================================
    # 1. SEGMENT SIZE ALIGNMENT CHECK
    # ============================================================
    print(f"{'='*80}")
    print(f"  SEGMENT SIZE ALIGNMENT: (length - 13) mod 7")
    print(f"{'='*80}")

    syx = os.path.join(base, "captured", "ground_truth_style.syx")
    track_names = ["RHY1", "RHY2", "BASS", "CHD1", "CHD2", "PAD", "PHR1", "PHR2"]

    for section in range(4):
        section_names = ["Main A", "Main B", "Fill AA", "Fill BB"]
        for track in range(8):
            event_data, segments = get_raw_track_data(syx, section, track)
            if not event_data:
                continue
            label = f"{section_names[section]} {track_names[track]}"
            bad_segs = []
            for seg_idx, (offset, seg_bytes, delim) in enumerate(segments):
                slen = len(seg_bytes)
                if slen >= 13:
                    remainder = (slen - 13) % 7
                    if remainder != 0:
                        bad_segs.append((seg_idx, slen, remainder))

            if bad_segs:
                print(f"  {label}: *** MISALIGNED ***")
                for si, sl, rem in bad_segs:
                    print(f"    Seg {si}: length={sl}, (len-13)%7={rem}")
            else:
                nseg = len([s for s in segments if len(s[1]) >= 13])
                if nseg > 0:
                    sizes = [len(s[1]) for s in segments if len(s[1]) >= 13]
                    events_per_seg = [(sz - 13) // 7 for sz in sizes]
                    print(f"  {label}: {nseg} segments, aligned OK."
                          f" Events/seg: {events_per_seg}")

    # ============================================================
    # 2. RAW BYTES of padding events (Pattern mode AL=127)
    # ============================================================
    print(f"\n{'='*80}")
    print(f"  PADDING DETECTION: Pattern mode AL=127")
    print(f"{'='*80}")

    pat_syx = os.path.join(base, "captured", "qy70_dump_20260414_114506.syx")
    if os.path.exists(pat_syx):
        parser = SysExParser()
        messages = parser.parse_file(pat_syx)
        for m in messages:
            if m.decoded_data and len(m.decoded_data) >= 28 and m.address_low == 127:
                data = m.decoded_data
                event_data = data[28:]
                print(f"\n  Track data hex dump ({len(event_data)} bytes):")
                for i in range(0, len(event_data), 16):
                    chunk = event_data[i:i+16]
                    hex_str = " ".join(f"{b:02x}" for b in chunk)
                    print(f"    {i:04x}: {hex_str}")

                # Parse segments
                delim_pos = sorted(i for i, b in enumerate(event_data) if b in (0xDC, 0x9E))
                print(f"\n  Delimiter positions: {delim_pos}")

                segments = []
                prev = 0
                for dp in delim_pos:
                    segments.append(event_data[prev:dp])
                    prev = dp + 1
                segments.append(event_data[prev:])

                for seg_idx, seg in enumerate(segments):
                    if len(seg) >= 13:
                        header = seg[:13]
                        print(f"\n  Segment {seg_idx}: {len(seg)} bytes,"
                              f" header={header.hex()}")
                        nevts = (len(seg) - 13) // 7
                        remain = (len(seg) - 13) % 7
                        print(f"    Events: {nevts}, alignment remainder: {remain}")
                        for i in range(nevts):
                            evt = seg[13 + i*7 : 13 + (i+1)*7]
                            note_r9, vc, f0, f1, f2, f3, f4, f5, rem = decode_r(evt, 9)
                            note_r0, vc0, f0_0, *_ = decode_r(evt, 0)
                            print(f"    e{i}: {evt.hex()}"
                                  f"  R9:note={note_r9:>3}(F0={f0:>3})"
                                  f"  R0:note={note_r0:>3}(F0={f0_0:>3})")

    # ============================================================
    # 3. ALL anomalous events at R=0 — are they valid notes?
    # ============================================================
    print(f"\n{'='*80}")
    print(f"  R=0 TEST: do anomalous events decode as valid notes at R=0?")
    print(f"{'='*80}")

    event_data, segments = get_raw_track_data(syx, 0, 0)  # Main A, RHY1
    if segments:
        total_r0_valid = 0
        total_anom = 0
        print(f"\n  {'Seg':>4} {'eIdx':>4} | {'raw':>14} | R=9: {'note':>4} | R=0: {'note':>4} | {'R0 valid?':>9}")
        for seg_idx, (offset, seg_bytes, delim) in enumerate(segments):
            if len(seg_bytes) < 20:
                continue
            nevts = (len(seg_bytes) - 13) // 7
            for i in range(nevts):
                evt = seg_bytes[13 + i*7 : 13 + (i+1)*7]
                if len(evt) == 7:
                    note9, vc9, f0_9, *_ = decode_r(evt, 9)
                    note0, vc0, f0_0, *_ = decode_r(evt, 0)
                    if note9 not in XG_RANGE or note9 < 13:
                        total_anom += 1
                        valid0 = note0 in XG_RANGE
                        if valid0:
                            total_r0_valid += 1
                        name0 = GM_DRUMS.get(note0, 'n' + str(note0))
                        marker = " <-- VALID" if valid0 else ""
                        print(f"  {seg_idx:>4} {i:>4} | {evt.hex()} |"
                              f" n{note9:>3} |"
                              f" n{note0:>3} ({name0:>10}) |{marker}")

        print(f"\n  Anomalous at R=9: {total_anom}")
        print(f"  Valid at R=0:     {total_r0_valid}/{total_anom}"
              f" ({100*total_r0_valid/total_anom:.0f}%)")

    # ============================================================
    # 4. EMPTY PATTERN MARKER: what does BF DF EF F7 FB FD FE look like?
    # ============================================================
    print(f"\n{'='*80}")
    print(f"  EMPTY MARKER TEST: BF DF EF F7 FB FD FE")
    print(f"{'='*80}")

    # The documented empty marker for QY70 is BF DF EF F7 FB FD FE
    empty_marker = bytes([0xBF, 0xDF, 0xEF, 0xF7, 0xFB, 0xFD, 0xFE])
    note_em, vc_em, f0_em, f1_em, f2_em, f3_em, f4_em, f5_em, rem_em = decode_r(empty_marker, 9)
    print(f"  At R=9: note={note_em}, F0={f0_em}, F1={f1_em}, F2={f2_em},"
          f" F3={f3_em}, F4={f4_em}, F5={f5_em}, rem={rem_em}")
    note_em0, vc_em0, f0_em0, *_ = decode_r(empty_marker, 0)
    print(f"  At R=0: note={note_em0}, F0={f0_em0}")
    # Also check if it appears in data
    if event_data:
        positions = []
        for i in range(len(event_data) - 6):
            if event_data[i:i+7] == empty_marker:
                positions.append(i)
        print(f"  Occurrences in RHY1 data: {len(positions)} at positions {positions}")

    # ============================================================
    # 5. BYTE PATTERN ANALYSIS: look for common bytes in anomalous
    # ============================================================
    print(f"\n{'='*80}")
    print(f"  BYTE-LEVEL PATTERNS IN ANOMALOUS vs NORMAL EVENTS")
    print(f"{'='*80}")

    event_data, segments = get_raw_track_data(syx, 0, 0)
    normal_evts = []
    anom_evts = []
    for seg_idx, (offset, seg_bytes, delim) in enumerate(segments):
        if len(seg_bytes) < 20:
            continue
        nevts = (len(seg_bytes) - 13) // 7
        for i in range(nevts):
            evt = seg_bytes[13 + i*7 : 13 + (i+1)*7]
            if len(evt) == 7:
                note, *_ = decode_r(evt, 9)
                if note in XG_RANGE:
                    normal_evts.append(evt)
                else:
                    anom_evts.append(evt)

    # Compare byte distributions per position
    print(f"\n  Byte value ranges per position (min-max):")
    print(f"  {'Pos':>4} | {'Normal':>20} | {'Anomalous':>20}")
    for pos in range(7):
        norm_bytes = [e[pos] for e in normal_evts]
        anom_bytes = [e[pos] for e in anom_evts]
        if norm_bytes and anom_bytes:
            print(f"  {pos:>4} |"
                  f" {min(norm_bytes):>3}-{max(norm_bytes):>3}"
                  f" (mean={sum(norm_bytes)/len(norm_bytes):>5.1f}) |"
                  f" {min(anom_bytes):>3}-{max(anom_bytes):>3}"
                  f" (mean={sum(anom_bytes)/len(anom_bytes):>5.1f})")

    # Check last byte
    print(f"\n  Last byte (byte[6]) distribution:")
    print(f"  Normal:    {Counter(e[6] for e in normal_evts).most_common(10)}")
    print(f"  Anomalous: {Counter(e[6] for e in anom_evts).most_common(10)}")

    # Check if byte[6] & 0x03 correlates with anomaly
    print(f"\n  byte[6] & 0x03 (before rotation = raw remainder):")
    print(f"  Normal:    {Counter(e[6] & 0x03 for e in normal_evts)}")
    print(f"  Anomalous: {Counter(e[6] & 0x03 for e in anom_evts)}")

    # ============================================================
    # 6. SEGMENT HEADER COMPARISON: normal-heavy vs anomaly-heavy
    # ============================================================
    print(f"\n{'='*80}")
    print(f"  SEGMENT HEADERS (are anomaly-heavy segments different?)")
    print(f"{'='*80}")

    for seg_idx, (offset, seg_bytes, delim) in enumerate(segments):
        if len(seg_bytes) >= 13:
            header = seg_bytes[:13]
            nevts = (len(seg_bytes) - 13) // 7
            n_anom = 0
            for i in range(nevts):
                evt = seg_bytes[13 + i*7 : 13 + (i+1)*7]
                if len(evt) == 7:
                    note, *_ = decode_r(evt, 9)
                    if note not in XG_RANGE:
                        n_anom += 1
            print(f"  Seg {seg_idx:>2}: header={header.hex()}"
                  f"  events={nevts} anom={n_anom}")

    # ============================================================
    # 7. CUMULATIVE rotation test for anomalous events
    # ============================================================
    print(f"\n{'='*80}")
    print(f"  CUMULATIVE R TEST: what if anomalous events need R*index?")
    print(f"{'='*80}")

    for seg_idx, (offset, seg_bytes, delim) in enumerate(segments):
        if len(seg_bytes) < 20:
            continue
        nevts = (len(seg_bytes) - 13) // 7
        has_anom = False
        results = []
        for i in range(nevts):
            evt = seg_bytes[13 + i*7 : 13 + (i+1)*7]
            if len(evt) != 7:
                continue
            note_const, *_ = decode_r(evt, 9)          # constant R=9
            note_cum, *_ = decode_r(evt, 9 * (i + 1))   # cumulative R=9*index
            is_anom = note_const not in XG_RANGE
            if is_anom:
                has_anom = True
            results.append((i, note_const, note_cum, is_anom, evt))

        if has_anom:
            print(f"\n  Segment {seg_idx}:")
            for i, nc, ncm, ia, evt in results:
                name_c = GM_DRUMS.get(nc, 'n' + str(nc))
                name_cm = GM_DRUMS.get(ncm, 'n' + str(ncm))
                marker = " ***" if ia else ""
                cm_valid = " VALID!" if ncm in XG_RANGE else ""
                print(f"    e{i}: const_R9={nc:>3}({name_c:>10})"
                      f"  cum_R9×i={ncm:>3}({name_cm:>10}){cm_valid}{marker}")


if __name__ == "__main__":
    main()
