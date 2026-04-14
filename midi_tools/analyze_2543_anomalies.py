#!/usr/bin/env python3
"""Analyze anomalous 2543 events: notes outside XG drum range (13-87).

Mystery notes found: 1, 32, 98, 99, 100, 109, 120, 127
- n120 appears in 7/10 segments, always vel=127 — possible structural marker
- n109 appears 5x identical in Segment 11 — possible padding/placeholder
- n1, n32 — below GM drum range

This script examines raw bytes, bit patterns, and context of anomalous events
to determine if they're real notes or structural elements.
"""

import sys, os
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from qymanager.formats.qy70.sysex_parser import SysExParser

# XG Standard Kit note range: 13-87 (with some kits extending slightly)
# GM Drums: 35-81
XG_DRUM_MIN = 13
XG_DRUM_MAX = 87

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
    # XG extensions (82-87)
    82: "Shaker", 83: "JnglBell", 84: "BellTree", 85: "Castanets",
    86: "MuSurdo", 87: "OpSurdo",
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
        return [], b""
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
            header = seg[:13]
            for i in range((len(seg) - 13) // 7):
                evt = seg[13 + i * 7: 13 + (i + 1) * 7]
                if len(evt) == 7:
                    events.append((seg_idx, i, evt, header))
    return events, event_data


def decode_event(evt):
    val = int.from_bytes(evt, "big")
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
    gate = f5
    beat = f1 >> 7
    clock_9 = ((f1 & 0x7F) << 2) | (f2 >> 7)
    tick_9 = beat * 480 + clock_9

    return {
        'note': note, 'vel_code': vel_code, 'midi_vel': midi_vel,
        'gate': gate, 'beat': beat, 'clock_9': clock_9, 'tick_9': tick_9,
        'f0': f0, 'f1': f1, 'f2': f2, 'f3': f3, 'f4': f4, 'f5': f5,
        'rem': rem, 'bit8': bit8, 'bit7': bit7,
        'raw_val': int.from_bytes(evt, "big"),
        'derot_val': derot,
    }


def main():
    base = os.path.dirname(os.path.abspath(__file__))
    syx = os.path.join(base, "captured", "ground_truth_style.syx")
    raw_events, event_data = get_events(syx, 0, 0)

    # ============================================================
    # 1. Classify events: normal drum vs anomalous
    # ============================================================
    print(f"{'='*80}")
    print(f"  ANOMALY CLASSIFICATION (XG drum range: {XG_DRUM_MIN}-{XG_DRUM_MAX})")
    print(f"{'='*80}")

    normal = []
    anomalous = []
    for seg_idx, evt_idx, evt, hdr in raw_events:
        d = decode_event(evt)
        d['seg'] = seg_idx
        d['eidx'] = evt_idx
        d['raw_bytes'] = evt
        d['header'] = hdr
        if XG_DRUM_MIN <= d['note'] <= XG_DRUM_MAX:
            normal.append(d)
        else:
            anomalous.append(d)

    print(f"\n  Normal drum events: {len(normal)}")
    print(f"  Anomalous events:  {len(anomalous)}")

    # ============================================================
    # 2. Detail on each anomalous event
    # ============================================================
    print(f"\n{'='*80}")
    print(f"  ANOMALOUS EVENT DETAILS")
    print(f"{'='*80}")

    by_note = defaultdict(list)
    for d in anomalous:
        by_note[d['note']].append(d)

    for note in sorted(by_note.keys()):
        evts = by_note[note]
        print(f"\n  --- Note {note} ({len(evts)} occurrences) ---")
        for d in evts:
            raw_hex = d['raw_bytes'].hex()
            print(f"    Seg {d['seg']:>2} e{d['eidx']}: raw={raw_hex}"
                  f"  F0={d['f0']:>3}(0x{d['f0']:03X})"
                  f"  F1={d['f1']:>3} F2={d['f2']:>3} F3={d['f3']:>3}"
                  f"  F4={d['f4']:>3} F5={d['f5']:>3} rem={d['rem']}")
            print(f"           bit8={d['bit8']} bit7={d['bit7']}"
                  f"  vel_code={d['vel_code']} vel={d['midi_vel']}"
                  f"  gate={d['gate']} beat={d['beat']} tick={d['tick_9']}")

    # ============================================================
    # 3. Binary pattern analysis of anomalous F0 values
    # ============================================================
    print(f"\n{'='*80}")
    print(f"  BINARY PATTERN: Anomalous F0 values")
    print(f"{'='*80}")

    unique_f0 = sorted(set(d['f0'] for d in anomalous))
    print(f"\n  {'F0':>5} {'bin(9bit)':>12} {'note(lo7)':>9} {'b8':>3} {'b7':>3}")
    for f0 in unique_f0:
        note = f0 & 0x7F
        b8 = (f0 >> 8) & 1
        b7 = (f0 >> 7) & 1
        print(f"  {f0:>5} {f0:>09b}     {note:>5}    {b8:>2}  {b7:>2}")

    # Same for normal events
    print(f"\n  Normal F0 range for comparison:")
    unique_f0_normal = sorted(set(d['f0'] for d in normal))
    print(f"  {'F0':>5} {'bin(9bit)':>12} {'note(lo7)':>9} {'b8':>3} {'b7':>3}")
    for f0 in unique_f0_normal:
        note = f0 & 0x7F
        b8 = (f0 >> 8) & 1
        b7 = (f0 >> 7) & 1
        print(f"  {f0:>5} {f0:>09b}     {note:>5}    {b8:>2}  {b7:>2}")

    # ============================================================
    # 4. Alternative interpretations: what if rotation is wrong?
    # ============================================================
    print(f"\n{'='*80}")
    print(f"  ALTERNATIVE ROTATION TEST (anomalous events only)")
    print(f"{'='*80}")

    for d in anomalous[:8]:
        print(f"\n  Seg {d['seg']} e{d['eidx']} raw={d['raw_bytes'].hex()}")
        for r in [0, 1, 5, 7, 9, 11, 15, 17, 23, 34, 47]:
            derot = rot_right(d['raw_val'], r)
            f0 = f9(derot, 0)
            note = f0 & 0x7F
            name = GM_DRUMS.get(note, f"n{note}")
            marker = " <--" if XG_DRUM_MIN <= note <= XG_DRUM_MAX else ""
            print(f"    R={r:>2}: F0={f0:>3} note={note:>3} ({name}){marker}")

    # ============================================================
    # 5. Check if anomalous events could be 6-bit or 8-bit note
    # ============================================================
    print(f"\n{'='*80}")
    print(f"  ALTERNATIVE NOTE FIELD WIDTH")
    print(f"{'='*80}")

    print(f"\n  Event      | 7-bit(lo7) | 8-bit(lo8) | 6-bit(lo6)")
    for d in anomalous[:12]:
        f0 = d['f0']
        lo7 = f0 & 0x7F
        lo8 = f0 & 0xFF
        lo6 = f0 & 0x3F
        n7 = GM_DRUMS.get(lo7, f"n{lo7}")
        n8 = GM_DRUMS.get(lo8, f"n{lo8}")
        n6 = GM_DRUMS.get(lo6, f"n{lo6}")
        in_range_7 = "*" if XG_DRUM_MIN <= lo7 <= XG_DRUM_MAX else " "
        in_range_8 = "*" if XG_DRUM_MIN <= lo8 <= XG_DRUM_MAX else " "
        in_range_6 = "*" if XG_DRUM_MIN <= lo6 <= XG_DRUM_MAX else " "
        print(f"  S{d['seg']:>2}e{d['eidx']} F0={f0:>3}"
              f" | {lo7:>3}{in_range_7} {n7:>10}"
              f" | {lo8:>3}{in_range_8} {n8:>10}"
              f" | {lo6:>3}{in_range_6} {n6:>10}")

    # ============================================================
    # 6. Monotonicity with anomalous removed
    # ============================================================
    print(f"\n{'='*80}")
    print(f"  MONOTONICITY: normal only vs all events")
    print(f"{'='*80}")

    by_seg_all = defaultdict(list)
    by_seg_normal = defaultdict(list)
    for seg_idx, evt_idx, evt, hdr in raw_events:
        d = decode_event(evt)
        d['seg'] = seg_idx
        d['eidx'] = evt_idx
        by_seg_all[seg_idx].append(d)
        if XG_DRUM_MIN <= d['note'] <= XG_DRUM_MAX:
            by_seg_normal[seg_idx].append(d)

    mono_all = 0
    pairs_all = 0
    mono_norm = 0
    pairs_norm = 0

    for seg in sorted(by_seg_all.keys()):
        evts = by_seg_all[seg]
        n = len(evts) - 1
        if n > 0:
            ticks = [d['tick_9'] for d in evts]
            mono_all += sum(1 for i in range(n) if ticks[i+1] >= ticks[i])
            pairs_all += n

    for seg in sorted(by_seg_normal.keys()):
        evts = by_seg_normal[seg]
        n = len(evts) - 1
        if n > 0:
            ticks = [d['tick_9'] for d in evts]
            mono_norm += sum(1 for i in range(n) if ticks[i+1] >= ticks[i])
            pairs_norm += n

    print(f"\n  All events:    {mono_all}/{pairs_all} ({100*mono_all/pairs_all:.0f}%)")
    if pairs_norm > 0:
        print(f"  Normal only:   {mono_norm}/{pairs_norm} ({100*mono_norm/pairs_norm:.0f}%)")
    print(f"  Events removed: {len(anomalous)}/{len(anomalous)+len(normal)}"
          f" ({100*len(anomalous)/(len(anomalous)+len(normal)):.0f}%)")

    # ============================================================
    # 7. Segment 11 deep dive — 5 identical n109 + OpTriang pattern
    # ============================================================
    print(f"\n{'='*80}")
    print(f"  SEGMENT 11 DEEP DIVE (5×n109 + OpTriang)")
    print(f"{'='*80}")

    seg11 = [d for d in anomalous + normal if d['seg'] == 11]
    seg11.sort(key=lambda d: d['eidx'])

    print(f"\n  Raw event order:")
    for d in seg11:
        name = GM_DRUMS.get(d['note'], 'n' + str(d['note']))
        raw = d['raw_bytes'].hex()
        print(f"    e{d['eidx']:>2}: {raw}  note={d['note']:>3}({name:>10})"
              f"  vel={d['midi_vel']:>3}  gate={d['gate']:>3}"
              f"  F1={d['f1']:>3} F2={d['f2']:>3} F3={d['f3']:>3} F4={d['f4']:>3}")

    # Check if odd/even alternation
    print(f"\n  Alternation pattern:")
    for d in seg11:
        name = GM_DRUMS.get(d['note'], 'n' + str(d['note']))
        parity = "EVEN" if d['eidx'] % 2 == 0 else "ODD"
        print(f"    e{d['eidx']:>2} ({parity}): {name} vel={d['midi_vel']}")

    # ============================================================
    # 8. n120 frequency analysis
    # ============================================================
    print(f"\n{'='*80}")
    print(f"  n120 ANALYSIS (appears in many segments)")
    print(f"{'='*80}")

    n120_evts = [d for d in anomalous if d['note'] == 120]
    print(f"\n  Total n120 events: {len(n120_evts)}")
    print(f"  Segments: {sorted(set(d['seg'] for d in n120_evts))}")

    print(f"\n  {'Seg':>4} {'eIdx':>4} | {'F0':>4} {'F1':>4} {'F2':>4} {'F3':>4} {'F4':>4}"
          f" {'F5':>4} | {'beat':>4} {'tick':>5} {'gate':>5}")
    for d in n120_evts:
        print(f"  {d['seg']:>4} {d['eidx']:>4} | {d['f0']:>4} {d['f1']:>4} {d['f2']:>4}"
              f" {d['f3']:>4} {d['f4']:>4} {d['f5']:>4}"
              f" | {d['beat']:>4} {d['tick_9']:>5} {d['gate']:>5}")

    # Check for byte identity among n120 events
    unique_raw = set(d['raw_bytes'].hex() for d in n120_evts)
    print(f"\n  Unique raw byte patterns: {len(unique_raw)}/{len(n120_evts)}")
    for raw in sorted(unique_raw):
        count = sum(1 for d in n120_evts if d['raw_bytes'].hex() == raw)
        if count > 1:
            print(f"    {raw} × {count}")

    # ============================================================
    # 9. Could anomalous events have a different field layout?
    # ============================================================
    print(f"\n{'='*80}")
    print(f"  TEST: 8-BIT NOTE FIELD (F0 = [flag:8bit_note])")
    print(f"{'='*80}")

    # What if the note field is 8 bits instead of 7?
    # Then F0 = [1-bit flag][8-bit note], and the "remainder" is 3 bits
    # Or F0 is split differently
    print(f"\n  If note = F0 lo8 (8 bits), flag = F0 bit8:")
    for d in anomalous[:12]:
        f0 = d['f0']
        note8 = f0 & 0xFF
        flag = (f0 >> 8) & 1
        name = GM_DRUMS.get(note8, 'n' + str(note8))
        in_range = "OK" if XG_DRUM_MIN <= note8 <= XG_DRUM_MAX else "BAD"
        print(f"    S{d['seg']:>2}e{d['eidx']}: F0={f0:>3} → flag={flag} note8={note8:>3}"
              f" ({name}) [{in_range}]")


if __name__ == "__main__":
    main()
