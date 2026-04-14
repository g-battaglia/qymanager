#!/usr/bin/env python3
"""Investigate whether 2543 anomalous events represent a second event type.

Key hypothesis: events with note > 87 (XG drum max) are NOT drum notes but
a different event type (control, tie, accent, position marker).

Tests:
1. Pattern mode data — do anomalies exist there too?
2. Paired event analysis (Segment 11 shows ODD/EVEN alternation)
3. Context: what happens BEFORE and AFTER anomalous events?
4. F5 correlation: is gate meaningful for anomalous events?
5. Remainder bit pattern: are anomalous events always rem=0?
"""

import sys, os
from collections import defaultdict, Counter
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from qymanager.formats.qy70.sysex_parser import SysExParser

XG_DRUM_MAX = 87
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


def get_track_events(syx_path, section, track):
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


def get_pattern_events(syx_path):
    """Parse pattern mode data (different address structure)."""
    parser = SysExParser()
    messages = parser.parse_file(syx_path)
    results = {}
    for m in messages:
        if m.decoded_data and len(m.decoded_data) >= 28:
            al = m.address_low
            data = m.decoded_data
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
            if events:
                results[al] = events
    return results


def decode_event(evt):
    val = int.from_bytes(evt, "big")
    derot = rot_right(val, R)
    fields = [f9(derot, i) for i in range(6)]
    rem = derot & 0x3
    f0, f1, f2, f3, f4, f5 = fields
    note = f0 & 0x7F
    bit8 = (f0 >> 8) & 1
    bit7 = (f0 >> 7) & 1
    vel_code = (bit8 << 3) | (bit7 << 2) | rem
    midi_vel = max(1, 127 - vel_code * 8)
    beat = f1 >> 7
    clock_9 = ((f1 & 0x7F) << 2) | (f2 >> 7)
    tick_9 = beat * 480 + clock_9
    return {
        'note': note, 'vel_code': vel_code, 'midi_vel': midi_vel,
        'gate': f5, 'beat': beat, 'clock_9': clock_9, 'tick_9': tick_9,
        'f0': f0, 'f1': f1, 'f2': f2, 'f3': f3, 'f4': f4, 'f5': f5,
        'rem': rem, 'bit8': bit8, 'bit7': bit7,
        'is_anomalous': note > XG_DRUM_MAX,
    }


def main():
    base = os.path.dirname(os.path.abspath(__file__))

    # ============================================================
    # 1. Style mode RHY1 — recap
    # ============================================================
    print(f"{'='*80}")
    print(f"  STYLE MODE: ground_truth_style.syx RHY1")
    print(f"{'='*80}")

    syx = os.path.join(base, "captured", "ground_truth_style.syx")
    style_events = get_track_events(syx, 0, 0)
    style_decoded = [(s, i, e, decode_event(e)) for s, i, e in style_events]

    n_normal = sum(1 for _, _, _, d in style_decoded if not d['is_anomalous'])
    n_anom = sum(1 for _, _, _, d in style_decoded if d['is_anomalous'])
    print(f"  Total: {len(style_decoded)}, Normal: {n_normal}, Anomalous: {n_anom}"
          f" ({100*n_anom/len(style_decoded):.0f}%)")

    # ============================================================
    # 2. Pattern mode — check for anomalies
    # ============================================================
    print(f"\n{'='*80}")
    print(f"  PATTERN MODE: qy70_dump_20260414_114506.syx")
    print(f"{'='*80}")

    pat_syx = os.path.join(base, "captured", "qy70_dump_20260414_114506.syx")
    if os.path.exists(pat_syx):
        pat_tracks = get_pattern_events(pat_syx)
        for al, events in sorted(pat_tracks.items()):
            print(f"\n  Track AL={al} ({len(events)} events):")
            for seg_idx, evt_idx, evt in events:
                d = decode_event(evt)
                name = GM_DRUMS.get(d['note'], 'n' + str(d['note']))
                anom = " *** ANOMALOUS" if d['is_anomalous'] else ""
                print(f"    S{seg_idx} e{evt_idx}: note={d['note']:>3}({name:>10})"
                      f"  vel={d['midi_vel']:>3} gate={d['gate']:>3}"
                      f"  beat={d['beat']} tick={d['tick_9']}"
                      f"  F0={d['f0']:>3} bit8={d['bit8']} bit7={d['bit7']}"
                      f"  rem={d['rem']}{anom}")
    else:
        print("  File not found")

    # ============================================================
    # 3. Style mode: ALL tracks (check other 2543 tracks)
    # ============================================================
    print(f"\n{'='*80}")
    print(f"  STYLE MODE: ALL TRACKS (checking other 2543 tracks)")
    print(f"{'='*80}")

    track_names = ["RHY1", "RHY2", "BASS", "CHD1", "CHD2", "PAD", "PHR1", "PHR2"]
    for section in range(4):
        section_names = ["Main A", "Main B", "Fill AA", "Fill BB"]
        for track in range(8):
            evts = get_track_events(syx, section, track)
            if not evts:
                continue
            decoded = [decode_event(e) for _, _, e in evts]
            n_total = len(decoded)
            n_anom = sum(1 for d in decoded if d['is_anomalous'])
            notes = Counter(d['note'] for d in decoded)
            if n_total > 0:
                anom_notes = {n: c for n, c in notes.items() if n > XG_DRUM_MAX}
                status = f"  {section_names[section]} {track_names[track]:>5}: {n_total:>3} events"
                if n_anom:
                    status += f", {n_anom} anomalous ({100*n_anom/n_total:.0f}%)"
                    status += f"  anom_notes={dict(sorted(anom_notes.items()))}"
                print(status)

    # ============================================================
    # 4. Paired event analysis: adjacent events
    # ============================================================
    print(f"\n{'='*80}")
    print(f"  PAIRED EVENT ANALYSIS (adjacent normal ↔ anomalous)")
    print(f"{'='*80}")

    by_seg = defaultdict(list)
    for seg_idx, evt_idx, evt in style_events:
        d = decode_event(evt)
        d['seg'] = seg_idx
        d['eidx'] = evt_idx
        d['raw'] = evt
        by_seg[seg_idx].append(d)

    for seg_idx in sorted(by_seg.keys()):
        evts = by_seg[seg_idx]
        pairs = []
        for i in range(len(evts)):
            if evts[i]['is_anomalous']:
                prev_note = evts[i-1]['note'] if i > 0 else None
                next_note = evts[i+1]['note'] if i < len(evts)-1 else None
                prev_name = GM_DRUMS.get(prev_note, 'n' + str(prev_note)) if prev_note else "---"
                next_name = GM_DRUMS.get(next_note, 'n' + str(next_note)) if next_note else "---"
                pairs.append((i, evts[i], prev_name, next_name))

        if pairs:
            print(f"\n  Segment {seg_idx}:")
            for i, d, prev, nxt in pairs:
                print(f"    e{d['eidx']}: n{d['note']} vel={d['midi_vel']}"
                      f"  prev={prev}, next={nxt}")

    # ============================================================
    # 5. Remainder bit analysis
    # ============================================================
    print(f"\n{'='*80}")
    print(f"  REMAINDER BIT DISTRIBUTION")
    print(f"{'='*80}")

    rem_normal = Counter(d['rem'] for _, _, _, d in style_decoded if not d['is_anomalous'])
    rem_anom = Counter(d['rem'] for _, _, _, d in style_decoded if d['is_anomalous'])
    print(f"\n  Normal events:    {dict(sorted(rem_normal.items()))}")
    print(f"  Anomalous events: {dict(sorted(rem_anom.items()))}")

    # ============================================================
    # 6. Velocity code distribution
    # ============================================================
    print(f"\n{'='*80}")
    print(f"  VELOCITY CODE DISTRIBUTION")
    print(f"{'='*80}")

    vc_normal = Counter(d['vel_code'] for _, _, _, d in style_decoded if not d['is_anomalous'])
    vc_anom = Counter(d['vel_code'] for _, _, _, d in style_decoded if d['is_anomalous'])
    print(f"\n  Normal:    {dict(sorted(vc_normal.items()))}")
    print(f"  Anomalous: {dict(sorted(vc_anom.items()))}")

    # ============================================================
    # 7. Check if n120 events could be "note repeat" markers
    # ============================================================
    print(f"\n{'='*80}")
    print(f"  n120 CONTEXT: what drums play at same tick?")
    print(f"{'='*80}")

    for seg_idx in sorted(by_seg.keys()):
        evts = by_seg[seg_idx]
        n120_evts = [d for d in evts if d['note'] == 120]
        for d120 in n120_evts:
            same_tick = [d for d in evts
                        if abs(d['tick_9'] - d120['tick_9']) <= 20 and d is not d120]
            nearby = ", ".join(
                GM_DRUMS.get(d['note'], 'n' + str(d['note']))
                + f"(v{d['midi_vel']})"
                for d in same_tick
            )
            if not nearby:
                nearby = "(alone)"
            print(f"  S{seg_idx} e{d120['eidx']}: tick={d120['tick_9']}"
                  f"  gate={d120['gate']}  nearby: {nearby}")

    # ============================================================
    # 8. Gate time comparison
    # ============================================================
    print(f"\n{'='*80}")
    print(f"  GATE TIME COMPARISON")
    print(f"{'='*80}")

    gates_normal = [d['gate'] for _, _, _, d in style_decoded if not d['is_anomalous']]
    gates_anom = [d['gate'] for _, _, _, d in style_decoded if d['is_anomalous']]
    print(f"\n  Normal gates:    min={min(gates_normal)} max={max(gates_normal)}"
          f"  mean={sum(gates_normal)/len(gates_normal):.0f}"
          f"  distinct={len(set(gates_normal))}")
    print(f"  Anomalous gates: min={min(gates_anom)} max={max(gates_anom)}"
          f"  mean={sum(gates_anom)/len(gates_anom):.0f}"
          f"  distinct={len(set(gates_anom))}")

    # ============================================================
    # 9. Are anomalous events at segment boundaries?
    # ============================================================
    print(f"\n{'='*80}")
    print(f"  ANOMALOUS EVENT POSITION WITHIN SEGMENT")
    print(f"{'='*80}")

    for seg_idx in sorted(by_seg.keys()):
        evts = by_seg[seg_idx]
        total = len(evts)
        anom_positions = [d['eidx'] for d in evts if d['is_anomalous']]
        if anom_positions:
            pct_positions = [f"e{p}/{total}" for p in anom_positions]
            print(f"  Seg {seg_idx:>2} ({total} events): anomalous at {', '.join(pct_positions)}")

    # ============================================================
    # 10. Check if anomalous F0 values follow a pattern
    # ============================================================
    print(f"\n{'='*80}")
    print(f"  F0 VALUE ANALYSIS: looking for type discriminator")
    print(f"{'='*80}")

    # What if F0 bits 8:6 encode event type?
    print(f"\n  F0 bits [8:7:6] distribution:")
    for is_anom, label in [(False, "Normal"), (True, "Anomalous")]:
        bits_count = Counter()
        for _, _, _, d in style_decoded:
            if d['is_anomalous'] == is_anom:
                b876 = (d['f0'] >> 6) & 0x7
                bits_count[b876] += 1
        print(f"    {label}: {dict(sorted(bits_count.items()))}")
        for val, cnt in sorted(bits_count.items()):
            print(f"      {val} (0b{val:03b}): {cnt} events")

    # What if note number determines type?
    print(f"\n  Note ranges:")
    for is_anom, label in [(False, "Normal"), (True, "Anomalous")]:
        notes = sorted(set(d['note'] for _, _, _, d in style_decoded
                          if d['is_anomalous'] == is_anom))
        print(f"    {label}: {notes}")


if __name__ == "__main__":
    main()
