#!/usr/bin/env python3
"""Analyze position encoding in 2543: F1-F4 combined with F5 gate time.

Approach: since F5=gate time and F0=note are confirmed, the only remaining
temporal parameter is the note's START POSITION within the bar.
F1-F4 must encode this position somehow.

Strategy:
1. Group events by their F1-F4 "fingerprint"
2. Track which segments and positions within segments they appear
3. Look for patterns: do certain F1-F4 values always appear as first event?
   As second? etc.
4. Try treating the full 56 bits minus F0(9) minus F5(9) minus rem(2) = 36 bits
   as a single positional value and check ordering.
5. Also try non-9-bit field layouts for the position portion only.
"""

import sys, os
from collections import Counter, defaultdict
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from qymanager.formats.qy70.sysex_parser import SysExParser

GM_DRUMS = {
    35: "Kick2", 36: "Kick1", 37: "SideStk", 38: "Snare1", 39: "Clap",
    40: "Snare2", 41: "LoFlTom", 42: "HHclose", 43: "HiFlTom", 44: "HHpedal",
    45: "LoTom", 46: "HHopen", 47: "MidLoTom", 48: "HiMidTom", 49: "Crash1",
    50: "HiTom", 51: "Ride1", 52: "Chinese", 53: "RideBell", 54: "Tamb",
    55: "Splash", 56: "Cowbell", 57: "Crash2", 58: "Vibslap", 59: "Ride2",
}

R = 9

def rot_right(val, shift, width=56):
    shift = shift % width
    return ((val >> shift) | (val << (width - shift))) & ((1 << width) - 1)

def f9(val, idx, total=56):
    shift = total - (idx + 1) * 9
    return (val >> shift) & 0x1FF if shift >= 0 else -1

def get_segments(syx_path, section=0, track=0):
    """Return list of (header, [(evt_bytes, seg_idx, evt_idx), ...])."""
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

    raw_segs = []
    prev = 0
    for dp in delim_pos:
        raw_segs.append(event_data[prev:dp])
        prev = dp + 1
    raw_segs.append(event_data[prev:])

    segments = []
    for seg_idx, seg in enumerate(raw_segs):
        if len(seg) >= 20:
            header = seg[:13]
            events = []
            for i in range((len(seg) - 13) // 7):
                evt = seg[13 + i * 7: 13 + (i + 1) * 7]
                if len(evt) == 7:
                    events.append((evt, seg_idx, i))
            segments.append((header, events))
    return segments


def main():
    base = os.path.dirname(os.path.abspath(__file__))
    syx = os.path.join(base, "captured", "ground_truth_style.syx")
    segments = get_segments(syx, 0, 0)
    print(f"Segments: {len(segments)}")

    # ============================================================
    # Build a "position catalog" — unique F1-F4 fingerprints
    # ============================================================
    print(f"\n{'='*70}")
    print("  POSITION CATALOG")
    print(f"{'='*70}")

    pos_catalog = defaultdict(list)  # (f1,f2,f3,f4) -> [(seg, evt, f0, f5)]

    for header, events in segments:
        for evt, seg_idx, evt_idx in events:
            val = int.from_bytes(evt, "big")
            derot = rot_right(val, R)
            f0 = f9(derot, 0)
            f1 = f9(derot, 1)
            f2 = f9(derot, 2)
            f3 = f9(derot, 3)
            f4 = f9(derot, 4)
            f5 = f9(derot, 5)
            pos_catalog[(f1, f2, f3, f4)].append((seg_idx, evt_idx, f0, f5))

    print(f"\n  {len(pos_catalog)} unique position fingerprints")
    print(f"\n  {'F1':>4} {'F2':>4} {'F3':>4} {'F4':>4}  {'Count':>5}  Events")

    for (f1, f2, f3, f4), entries in sorted(pos_catalog.items(),
                                             key=lambda x: -len(x[1])):
        notes = []
        for seg, eidx, f0, f5 in entries[:8]:
            lo7 = f0 & 0x7F
            name = GM_DRUMS.get(lo7, f"n{lo7}")
            notes.append(f"s{seg}e{eidx}:{name}(g{f5})")
        print(f"  {f1:>4} {f2:>4} {f3:>4} {f4:>4}  {len(entries):>5}  {', '.join(notes)}")

    # ============================================================
    # Within each segment, try to find the ordering key
    # ============================================================
    print(f"\n{'='*70}")
    print("  ORDERING ANALYSIS — Position within segment")
    print(f"{'='*70}")

    # For segments with many events, see if events are ordered by
    # the 36-bit F1F2F3F4 value, or by any individual field
    for header, events in segments:
        if len(events) < 4:
            continue
        seg_idx = events[0][1]

        decoded = []
        for evt, _, eidx in events:
            val = int.from_bytes(evt, "big")
            derot = rot_right(val, R)
            f0 = f9(derot, 0)
            f1 = f9(derot, 1)
            f2 = f9(derot, 2)
            f3 = f9(derot, 3)
            f4 = f9(derot, 4)
            f5 = f9(derot, 5)
            rem = derot & 0x3
            # 36-bit combined
            combo = (f1 << 27) | (f2 << 18) | (f3 << 9) | f4
            decoded.append((eidx, f0, f1, f2, f3, f4, f5, rem, combo))

        print(f"\n  Segment {seg_idx} ({len(decoded)} events):")
        print(f"  {'#':>2} {'F0':>5} {'note':>6} {'F1':>4} {'F2':>4} {'F3':>4} "
              f"{'F4':>4} {'F5':>4} {'rem':>3} {'combo36':>12}")
        for eidx, f0, f1, f2, f3, f4, f5, rem, combo in decoded:
            lo7 = f0 & 0x7F
            name = GM_DRUMS.get(lo7, f"n{lo7}")[:6]
            print(f"  {eidx:>2} {f0:>5} {name:>6} {f1:>4} {f2:>4} {f3:>4} "
                  f"{f4:>4} {f5:>4} {rem:>3} {combo:>12}")

        # Test all possible sort keys
        combos = [c[-1] for c in decoded]
        f1s = [c[2] for c in decoded]
        f2s = [c[3] for c in decoded]
        f3s = [c[4] for c in decoded]
        f4s = [c[5] for c in decoded]
        f5s = [c[6] for c in decoded]
        rems = [c[7] for c in decoded]

        n = len(decoded) - 1
        if n > 0:
            tests = {
                "combo36": sum(1 for i in range(n) if combos[i+1] >= combos[i]),
                "F1": sum(1 for i in range(n) if f1s[i+1] >= f1s[i]),
                "F2": sum(1 for i in range(n) if f2s[i+1] >= f2s[i]),
                "F3": sum(1 for i in range(n) if f3s[i+1] >= f3s[i]),
                "F4": sum(1 for i in range(n) if f4s[i+1] >= f4s[i]),
                "F5_gate": sum(1 for i in range(n) if f5s[i+1] >= f5s[i]),
                "rem": sum(1 for i in range(n) if rems[i+1] >= rems[i]),
            }
            print(f"  Monotonicity: ", end="")
            print("  ".join(f"{k}={v}/{n}" for k, v in tests.items()))

    # ============================================================
    # Alternative: Try extracting position as different bit fields
    # ============================================================
    print(f"\n{'='*70}")
    print("  ALTERNATIVE BIT LAYOUTS FOR POSITION")
    print(f"{'='*70}")

    # After removing F0(9 bits MSB) and F5+rem(11 bits LSB), we have 36 bits
    # in the middle. These 36 bits encode the position. Let's try:
    # A) 12+12+12 (beat:clock:gate?)
    # B) 16+16+4 (position:gate:flags)
    # C) 11+11+14 (position:gate:other)
    # D) The bits as-is represent: beat(2) + clock(9) + gate_beats(2) + gate_clocks(9) + extra(14)

    for header, events in segments:
        if len(events) < 6:
            continue
        seg_idx = events[0][1]
        print(f"\n  Segment {seg_idx}:")

        for evt, _, eidx in events:
            val = int.from_bytes(evt, "big")
            derot = rot_right(val, R)

            # Full 56-bit breakdown:
            # [F0:9][middle:36][F5:9][rem:2]
            f0 = (derot >> 47) & 0x1FF
            middle36 = (derot >> 11) & 0xFFFFFFFFF  # 36 bits
            f5 = (derot >> 2) & 0x1FF
            rem = derot & 0x3
            lo7 = f0 & 0x7F

            # Layout A: 12+12+12
            a1 = (middle36 >> 24) & 0xFFF
            a2 = (middle36 >> 12) & 0xFFF
            a3 = middle36 & 0xFFF

            # Layout B: beat(2)+clock(10)+beat(2)+clock(10)+extra(12)
            b_beat1 = (middle36 >> 34) & 0x3
            b_clk1 = (middle36 >> 24) & 0x3FF
            b_beat2 = (middle36 >> 22) & 0x3
            b_clk2 = (middle36 >> 12) & 0x3FF
            b_extra = middle36 & 0xFFF

            # Layout C: position_ticks(12)+gate_ticks(12)+flags(12)
            # position = beat*480 + clock
            pos_c = a1  # if this encodes beat:clock
            # Decompose as beat(2) + clock(10)
            c_beat = (a1 >> 10) & 0x3
            c_clock = a1 & 0x3FF

            name = GM_DRUMS.get(lo7, f"n{lo7}")[:8]
            print(f"    e{eidx} {name:>8} |"
                  f" A:{a1:>4},{a2:>4},{a3:>4}"
                  f" | B:b{b_beat1}.{b_clk1:>4},b{b_beat2}.{b_clk2:>4},x{b_extra:>4}"
                  f" | F5(gate)={f5:>3}")

    # ============================================================
    # What if the 36-bit "position" includes NOTE NUMBER somehow?
    # Maybe the actual split is F0(7)+velocity(2)+position(36)+gate(9)+rem(2)
    # ============================================================
    print(f"\n{'='*70}")
    print("  TEST: 7-bit note + 2-bit velocity from F0")
    print(f"{'='*70}")

    # Check if F0 bit8 and bit7 correlate with dynamic markings
    # In a drum pattern, kick/snare are typically louder than ghost notes
    for header, events in segments[:3]:
        seg_idx = events[0][1]
        print(f"\n  Segment {seg_idx}:")
        for evt, _, eidx in events:
            val = int.from_bytes(evt, "big")
            derot = rot_right(val, R)
            f0 = f9(derot, 0)
            f5 = f9(derot, 5)
            rem = derot & 0x3
            bit8 = (f0 >> 8) & 1
            bit7 = (f0 >> 7) & 1
            lo7 = f0 & 0x7F
            vel_bits = (bit8 << 1) | bit7  # 0-3
            name = GM_DRUMS.get(lo7, f"n{lo7}")[:8]
            print(f"    e{eidx} {name:>8} note={lo7:>3} vel_bits={vel_bits} "
                  f"gate={f5:>3} rem={rem}")

    # ============================================================
    # Key insight test: are events within a segment sorted by
    # ANYTHING when we exclude simultaneous events?
    # ============================================================
    print(f"\n{'='*70}")
    print("  UNIQUE POSITIONS ORDERED")
    print(f"{'='*70}")

    for header, events in segments:
        if len(events) < 4:
            continue
        seg_idx = events[0][1]

        # Get unique positions in order of first appearance
        seen_pos = {}
        for evt, _, eidx in events:
            val = int.from_bytes(evt, "big")
            derot = rot_right(val, R)
            f1 = f9(derot, 1)
            f2 = f9(derot, 2)
            f3 = f9(derot, 3)
            f4 = f9(derot, 4)
            key = (f1, f2, f3, f4)
            if key not in seen_pos:
                seen_pos[key] = eidx

        positions = sorted(seen_pos.items(), key=lambda x: x[1])
        combos = [(f1 << 27 | f2 << 18 | f3 << 9 | f4) for (f1, f2, f3, f4), _ in positions]

        print(f"\n  Segment {seg_idx}: {len(positions)} unique positions "
              f"(from {len(events)} events)")
        for i, ((f1, f2, f3, f4), first_evt) in enumerate(positions):
            combo = f1 << 27 | f2 << 18 | f3 << 9 | f4
            mark = "↑" if i > 0 and combo > combos[i-1] else ("↓" if i > 0 else " ")
            print(f"    pos{i}: F1={f1:>3} F2={f2:>3} F3={f3:>3} F4={f4:>3} "
                  f" combo={combo:>12} first@e{first_evt} {mark}")


if __name__ == "__main__":
    main()
