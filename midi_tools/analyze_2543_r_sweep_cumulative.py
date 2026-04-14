#!/usr/bin/env python3
"""Sweep all R base values (0-55) with cumulative rotation R_base*(i+1).

Goal: confirm that R_base=9 is the optimal cumulative rotation base,
and test if any other base gives even better results.

Also cross-validate with Pattern mode data and other tracks.
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


def get_segments(syx_path, section, track):
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


def score_cumulative(segments, r_base):
    """Score cumulative rotation R=r_base*(i+1) on RHY1 events."""
    total = 0
    valid = 0
    mono_ok = 0
    mono_total = 0

    for seg in segments:
        if len(seg) < 20:
            continue
        nevts = (len(seg) - 13) // 7
        ticks = []
        for i in range(nevts):
            evt = seg[13 + i * 7: 13 + (i + 1) * 7]
            if len(evt) != 7:
                continue
            r_val = r_base * (i + 1)
            val = int.from_bytes(evt, "big")
            derot = rot_right(val, r_val)
            f0 = f9(derot, 0)
            f1 = f9(derot, 1)
            f2 = f9(derot, 2)
            note = f0 & 0x7F
            total += 1
            if note in XG_RANGE:
                valid += 1
            beat = f1 >> 7
            clock = ((f1 & 0x7F) << 2) | (f2 >> 7)
            ticks.append(beat * 480 + clock)

        for i in range(len(ticks) - 1):
            mono_total += 1
            if ticks[i + 1] >= ticks[i]:
                mono_ok += 1

    valid_pct = 100 * valid / total if total > 0 else 0
    mono_pct = 100 * mono_ok / mono_total if mono_total > 0 else 0
    return valid, total, valid_pct, mono_pct


def main():
    base = os.path.dirname(os.path.abspath(__file__))
    syx = os.path.join(base, "captured", "ground_truth_style.syx")

    # ============================================================
    # 1. R_base sweep for RHY1
    # ============================================================
    print(f"{'='*80}")
    print(f"  CUMULATIVE R_base SWEEP (R = R_base * (i+1))")
    print(f"  RHY1 Section 0, ground_truth_style.syx")
    print(f"{'='*80}")

    segments_rhy1 = get_segments(syx, 0, 0)  # Main A, RHY1

    sweep_results = []
    for r_base in range(56):
        valid, total, vpct, mpct = score_cumulative(segments_rhy1, r_base)
        sweep_results.append((r_base, valid, total, vpct, mpct))

    # Sort by valid count
    sweep_results.sort(key=lambda x: -x[3])

    print(f"\n  Top 15 R_base values (by valid %):")
    print(f"  {'R_base':>6} {'Valid':>5} {'Total':>5} {'Valid%':>6} {'Mono%':>6}")
    for r_base, valid, total, vpct, mpct in sweep_results[:15]:
        marker = " <== BEST" if r_base == sweep_results[0][0] else ""
        marker9 = " *** R=9" if r_base == 9 else ""
        print(f"  {r_base:>6} {valid:>5} {total:>5} {vpct:>5.1f}% {mpct:>5.1f}%{marker}{marker9}")

    # Also show constant rotation for comparison
    print(f"\n  For reference:")
    # Constant = same as R_base*(i+1) where i is always 0
    # Actually no — constant R=9 means EVERY event gets R=9
    # That's R_base=0 with offset 9... let me compute it separately
    total = 0
    valid = 0
    for seg in segments_rhy1:
        if len(seg) < 20:
            continue
        nevts = (len(seg) - 13) // 7
        for i in range(nevts):
            evt = seg[13 + i * 7: 13 + (i + 1) * 7]
            if len(evt) != 7:
                continue
            val = int.from_bytes(evt, "big")
            derot = rot_right(val, 9)
            f0 = f9(derot, 0)
            note = f0 & 0x7F
            total += 1
            if note in XG_RANGE:
                valid += 1
    print(f"  Constant R=9: {valid}/{total} ({100*valid/total:.1f}%)")

    # ============================================================
    # 2. Cross-validate: R_base=9 on OTHER tracks (Section 0 only)
    # ============================================================
    print(f"\n{'='*80}")
    print(f"  CROSS-VALIDATION: R_base=9 cumulative on all tracks")
    print(f"{'='*80}")

    track_names = ["RHY1", "RHY2", "BASS", "CHD1", "CHD2", "PAD", "PHR1", "PHR2"]
    for track in range(8):
        segs = get_segments(syx, 0, track)
        if not segs:
            continue
        valid9, total9, vpct9, mpct9 = score_cumulative(segs, 9)
        # Compare with top R_base for this track
        best_r = 9
        best_vpct = vpct9
        for r in range(56):
            _, _, vp, _ = score_cumulative(segs, r)
            if vp > best_vpct:
                best_vpct = vp
                best_r = r
        print(f"  {track_names[track]:>5}: R=9 cum → {valid9}/{total9} ({vpct9:.0f}%)"
              f"  Best: R={best_r} ({best_vpct:.0f}%)")

    # ============================================================
    # 3. Remaining invalid events in cumulative R=9*(i+1)
    # ============================================================
    print(f"\n{'='*80}")
    print(f"  REMAINING INVALID EVENTS (cumulative R=9*(i+1), RHY1)")
    print(f"{'='*80}")

    for seg_idx, seg in enumerate(segments_rhy1):
        if len(seg) < 20:
            continue
        nevts = (len(seg) - 13) // 7
        for i in range(nevts):
            evt = seg[13 + i * 7: 13 + (i + 1) * 7]
            if len(evt) != 7:
                continue
            r_val = 9 * (i + 1)
            val = int.from_bytes(evt, "big")
            derot = rot_right(val, r_val)
            f0 = f9(derot, 0)
            f1 = f9(derot, 1)
            f5 = f9(derot, 5)
            rem = derot & 0x3
            note = f0 & 0x7F
            bit8 = (f0 >> 8) & 1
            bit7 = (f0 >> 7) & 1
            vel_code = (bit8 << 3) | (bit7 << 2) | rem
            midi_vel = max(1, 127 - vel_code * 8)

            if note not in XG_RANGE:
                # What rotation WOULD give a valid note for this event?
                valid_rotations = []
                for r_test in range(56):
                    derot_test = rot_right(val, r_test)
                    f0_test = f9(derot_test, 0)
                    n_test = f0_test & 0x7F
                    if n_test in XG_RANGE:
                        name_test = GM_DRUMS.get(n_test, 'n' + str(n_test))
                        valid_rotations.append((r_test, n_test, name_test))

                print(f"\n  Seg {seg_idx} e{i}: note={note} (F0={f0})"
                      f" vel={midi_vel} gate={f5}")
                print(f"    R_used = {r_val} = 9*{i+1}")
                print(f"    raw = {evt.hex()}")
                if valid_rotations:
                    # Show rotations that would give valid notes
                    print(f"    Valid at R: ", end="")
                    for r_test, n_test, name in valid_rotations[:8]:
                        cum_idx = r_test / 9 - 1  # What index would this correspond to?
                        print(f"R={r_test}→{name}({n_test})", end=" ")
                    print()

    # ============================================================
    # 4. Check: do trailing segment bytes affect decoding?
    # ============================================================
    print(f"\n{'='*80}")
    print(f"  TRAILING BYTES AND THEIR EFFECT")
    print(f"{'='*80}")

    for seg_idx, seg in enumerate(segments_rhy1):
        slen = len(seg)
        if slen < 20:
            continue
        trail = (slen - 13) % 7
        if trail > 0:
            trail_bytes = seg[slen - trail:]
            nevts_normal = (slen - 13) // 7
            # What if we include trailing bytes as part of last event?
            # Or what if trailing bytes are the START of the event area?
            print(f"\n  Seg {seg_idx}: {slen} bytes, {trail} trailing: {trail_bytes.hex()}")
            print(f"    Normal: {nevts_normal} events (header=13)")

            # What if header is 13+trail?
            adj_hdr = 13 + trail
            nevts_adj = (slen - adj_hdr) // 7
            r_adj = (slen - adj_hdr) % 7
            print(f"    Alt header={adj_hdr}: {nevts_adj} events, remainder={r_adj}")

            # Decode both ways and compare
            if nevts_adj > 0 and r_adj == 0:
                print(f"    Comparison (first 3 events):")
                for j in range(min(3, max(nevts_normal, nevts_adj))):
                    # Normal (header=13)
                    if j < nevts_normal:
                        evt_n = seg[13 + j * 7: 13 + (j + 1) * 7]
                        val_n = int.from_bytes(evt_n, "big")
                        r_n = 9 * (j + 1)
                        derot_n = rot_right(val_n, r_n)
                        note_n = f9(derot_n, 0) & 0x7F
                        name_n = GM_DRUMS.get(note_n, 'n' + str(note_n))
                    else:
                        name_n = "---"
                        note_n = -1

                    # Adjusted (header=13+trail)
                    if j < nevts_adj:
                        evt_a = seg[adj_hdr + j * 7: adj_hdr + (j + 1) * 7]
                        val_a = int.from_bytes(evt_a, "big")
                        r_a = 9 * (j + 1)
                        derot_a = rot_right(val_a, r_a)
                        note_a = f9(derot_a, 0) & 0x7F
                        name_a = GM_DRUMS.get(note_a, 'n' + str(note_a))
                    else:
                        name_a = "---"
                        note_a = -1

                    v_n = "✓" if note_n in XG_RANGE else "✗"
                    v_a = "✓" if note_a in XG_RANGE else "✗"
                    print(f"      e{j}: hdr13={note_n:>3}({name_n:>10}){v_n}"
                          f"  hdr{adj_hdr}={note_a:>3}({name_a:>10}){v_a}")


if __name__ == "__main__":
    main()
