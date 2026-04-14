#!/usr/bin/env python3
"""Test velocity hypothesis: F0 bit8 + bit7 + remainder = 4-bit inverted velocity.

Hypothesis: velocity is encoded as [F0_bit8 : F0_bit7 : rem_bit1 : rem_bit0]
where 0000 = LOUDEST (127) and 1111 = SOFTEST (1).

Evidence:
- Same note (lo7) appears with different F0 values (80 vs 336 = same note 80, different bit8)
- Kick/Crash/Ride (typically loud) have vel_code=0
- OpTriang/Cabasa (typically soft) have vel_code=12/15
- Musically consistent velocity ordering
"""

import sys, os
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from qymanager.formats.qy70.sysex_parser import SysExParser

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
}

R = 9

def rot_right(val, shift, width=56):
    shift = shift % width
    return ((val >> shift) | (val << (width - shift))) & ((1 << width) - 1)

def f9(val, idx, total=56):
    shift = total - (idx + 1) * 9
    return (val >> shift) & 0x1FF if shift >= 0 else -1

def get_events(syx_path, section=0, track=0):
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

    events = []
    for seg_idx, seg in enumerate(segments):
        if len(seg) >= 20:
            for i in range((len(seg) - 13) // 7):
                evt = seg[13 + i * 7: 13 + (i + 1) * 7]
                if len(evt) == 7:
                    events.append((seg_idx, i, evt))
    return events


def vel_code(bit8, bit7, rem):
    """4-bit velocity code: [bit8:bit7:rem1:rem0], 0=loudest, 15=softest."""
    return (bit8 << 3) | (bit7 << 2) | (rem & 0x3)


def vel_to_midi(vcode):
    """Convert 4-bit velocity code to approximate MIDI velocity.
    0 → 127, 15 → 1. Linear mapping."""
    return max(1, 127 - vcode * 8)


def main():
    base = os.path.dirname(os.path.abspath(__file__))
    syx = os.path.join(base, "captured", "ground_truth_style.syx")
    events = get_events(syx, 0, 0)
    print(f"Events: {len(events)}")

    # ============================================================
    # Decode all events with velocity hypothesis
    # ============================================================
    print(f"\n{'='*70}")
    print("  VELOCITY HYPOTHESIS: [bit8 : bit7 : rem] inverted")
    print(f"{'='*70}")

    print(f"\n  {'Seg':>3} {'#':>2} {'note':>4} {'Drum':>10} {'bit8':>4} {'bit7':>4}"
          f" {'rem':>3} {'vcode':>5} {'MIDI_v':>6} {'gate':>4} {'F1':>4} {'F2':>4}")

    all_decoded = []
    for seg_idx, evt_idx, evt in events:
        val = int.from_bytes(evt, "big")
        derot = rot_right(val, R)
        f0 = f9(derot, 0)
        f1 = f9(derot, 1)
        f2 = f9(derot, 2)
        f3 = f9(derot, 3)
        f4 = f9(derot, 4)
        f5 = f9(derot, 5)
        rem = derot & 0x3

        bit8 = (f0 >> 8) & 1
        bit7 = (f0 >> 7) & 1
        lo7 = f0 & 0x7F
        vc = vel_code(bit8, bit7, rem)
        midi_v = vel_to_midi(vc)
        name = GM_DRUMS.get(lo7, f"n{lo7}")[:10]

        all_decoded.append({
            'seg': seg_idx, 'evt': evt_idx, 'lo7': lo7, 'name': name,
            'bit8': bit8, 'bit7': bit7, 'rem': rem, 'vc': vc,
            'midi_v': midi_v, 'gate': f5, 'f1': f1, 'f2': f2,
            'f3': f3, 'f4': f4,
        })

        print(f"  {seg_idx:>3} {evt_idx:>2} {lo7:>4} {name:>10} {bit8:>4} {bit7:>4}"
              f" {rem:>3} {vc:>5} {midi_v:>6} {f5:>4} {f1:>4} {f2:>4}")

    # ============================================================
    # Velocity distribution
    # ============================================================
    print(f"\n{'='*70}")
    print("  VELOCITY DISTRIBUTION")
    print(f"{'='*70}")

    vc_counter = defaultdict(int)
    for d in all_decoded:
        vc_counter[d['vc']] += 1

    print(f"\n  {'VCode':>5} {'MIDI_v':>6} {'Count':>5} {'Dynamic':>8} {'Example Notes'}")
    dynamics = {0: "fff", 1: "ff+", 2: "ff", 3: "f+",
                4: "f", 5: "mf+", 6: "mf", 7: "mp",
                8: "mp-", 9: "p+", 10: "p", 11: "p-",
                12: "pp", 13: "pp-", 14: "ppp", 15: "pppp"}

    for vc in range(16):
        cnt = vc_counter.get(vc, 0)
        if cnt > 0:
            notes = set(d['name'] for d in all_decoded if d['vc'] == vc)
            dyn = dynamics.get(vc, "?")
            midi_v = vel_to_midi(vc)
            print(f"  {vc:>5} {midi_v:>6} {cnt:>5} {dyn:>8}  {', '.join(sorted(notes))}")

    # ============================================================
    # Same note, different velocities
    # ============================================================
    print(f"\n{'='*70}")
    print("  SAME NOTE, DIFFERENT VELOCITIES")
    print(f"{'='*70}")

    note_vels = defaultdict(set)
    for d in all_decoded:
        note_vels[d['lo7']].add(d['vc'])

    multi = {k: v for k, v in note_vels.items() if len(v) > 1}
    if multi:
        print(f"\n  Notes appearing at multiple velocity levels:")
        for lo7 in sorted(multi.keys()):
            name = GM_DRUMS.get(lo7, f"n{lo7}")
            vcs = sorted(multi[lo7])
            vc_str = ", ".join(f"v{vc}({vel_to_midi(vc)})" for vc in vcs)
            print(f"    {name:>12} ({lo7:>3}): {vc_str}")
    else:
        print("  No notes with multiple velocity levels (each note has fixed velocity)")

    # ============================================================
    # Position encoding: F1-F4 as [beat(2):clock(10):...] from the
    # top 12 bits of F1-F2 concatenation
    # ============================================================
    print(f"\n{'='*70}")
    print("  POSITION TEST: top 12 bits of F1-F2 = beat:clock?")
    print(f"{'='*70}")

    # F1(9 bits) + F2(9 bits) = 18 bits. Top 12 = [F1_full(9) : F2_top3(3)]
    # Or: [F1_top2(2) : F1_lo7+F2_top3(10)]
    # = pos_beat = F1 >> 7, pos_clock = ((F1 & 0x7F) << 3) | (F2 >> 6)

    pos_data = []
    for d in all_decoded:
        pos_beat = d['f1'] >> 7
        pos_clock = ((d['f1'] & 0x7F) << 3) | (d['f2'] >> 6)
        pos_ticks = pos_beat * 480 + (pos_clock if pos_clock < 480 else pos_clock % 480)
        pos_data.append({**d, 'pos_beat': pos_beat, 'pos_clock': pos_clock, 'pos_ticks': pos_ticks})

    # Group by segment and check chronological order
    by_seg = defaultdict(list)
    for pd in pos_data:
        by_seg[pd['seg']].append(pd)

    print(f"\n  Events by segment with position:")
    for seg_idx in sorted(by_seg.keys()):
        evts = by_seg[seg_idx]
        print(f"\n  Segment {seg_idx}:")
        print(f"  {'#':>2} {'Note':>10} {'v':>3} {'Beat':>4} {'Clock':>5} {'Ticks':>5} {'Gate':>4}")
        prev_ticks = -1
        for pd in evts:
            mark = "↑" if pd['pos_ticks'] > prev_ticks and prev_ticks >= 0 else \
                   ("=" if pd['pos_ticks'] == prev_ticks and prev_ticks >= 0 else " ")
            print(f"  {pd['evt']:>2} {pd['name']:>10} {pd['vc']:>3}"
                  f" {pd['pos_beat']:>4} {pd['pos_clock']:>5} {pd['pos_ticks']:>5}"
                  f" {pd['gate']:>4} {mark}")
            prev_ticks = pd['pos_ticks']

        # Monotonicity check
        ticks = [pd['pos_ticks'] for pd in evts]
        n = len(ticks) - 1
        if n > 0:
            mono = sum(1 for i in range(n) if ticks[i+1] >= ticks[i])
            print(f"  Position monotonic: {mono}/{n}")

    # ============================================================
    # Musical summary: complete event decode
    # ============================================================
    print(f"\n{'='*70}")
    print("  MUSICAL SUMMARY (first 5 segments)")
    print(f"{'='*70}")

    for seg_idx in sorted(by_seg.keys())[:5]:
        evts = sorted(by_seg[seg_idx], key=lambda x: x['pos_ticks'])
        print(f"\n  Segment {seg_idx} — Events in time order:")
        for pd in evts:
            beat_str = f"b{pd['pos_beat']}.{pd['pos_clock']:03d}"
            print(f"    {beat_str}  {pd['name']:>10}  vel={pd['midi_v']:>3}"
                  f"  gate={pd['gate']:>3} ticks")


if __name__ == "__main__":
    main()
