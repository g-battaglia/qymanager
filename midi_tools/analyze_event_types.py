#!/usr/bin/env python3
"""Event type classification and adjusted accuracy computation.

Hypothesis: the event stream contains multiple event types:
  Type N (Note):    F0.lo7 ∈ [13, 87] — normal drum/note events
  Type C (Control): F0 = 0x078 at R=9 — structural/control events
  Type 0 (Null):    F0 = 0x000 — padding/end markers
  Type I (Init):    first segment, first events — setup parameters

This script:
1. Classifies all events by type
2. Computes "true" decode accuracy for note events only
3. Examines control event content (what's in the other fields?)
4. Checks if removing control events changes the rotation model results
"""

import sys, os
from collections import Counter, defaultdict
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from qymanager.formats.qy70.sysex_parser import SysExParser

XG_RANGE = set(range(13, 88))

def rot_right(val, shift, width=56):
    shift = shift % width
    return ((val >> shift) | (val << (width - shift))) & ((1 << width) - 1)

def f9(val, idx, total=56):
    shift = total - (idx + 1) * 9
    return (val >> shift) & 0x1FF if shift >= 0 else -1

def decode(evt, r_val):
    val = int.from_bytes(evt, "big")
    derot = rot_right(val, r_val)
    fields = [f9(derot, j) for j in range(6)]
    rem = derot & 0x3
    note = fields[0] & 0x7F
    bit8 = (fields[0] >> 8) & 1
    bit7 = (fields[0] >> 7) & 1
    vel_code = (bit8 << 3) | (bit7 << 2) | rem
    midi_vel = max(1, 127 - vel_code * 8)
    beat = fields[1] >> 7
    clock = ((fields[1] & 0x7F) << 2) | (fields[2] >> 7)
    tick = beat * 480 + clock
    return note, midi_vel, fields[5], tick, vel_code, fields, rem


def get_all_tracks(syx_path, section=0):
    parser = SysExParser()
    messages = parser.parse_file(syx_path)
    tracks = {}
    for track in range(8):
        al = section * 8 + track
        data = b""
        for m in messages:
            if m.is_style_data and m.address_low == al:
                if m.decoded_data is not None:
                    data += m.decoded_data
        if len(data) >= 28:
            tracks[track] = data
    return tracks


def get_segments(data):
    event_data = data[28:]
    delim_pos = sorted(i for i, b in enumerate(event_data) if b in (0xDC, 0x9E))
    segments = []
    prev = 0
    for dp in delim_pos:
        segments.append(event_data[prev:dp])
        prev = dp + 1
    segments.append(event_data[prev:])
    return segments


def classify_event(evt, pos):
    """Classify event type based on R=9 decode."""
    # Check at R=9 (constant) for type markers
    val = int.from_bytes(evt, "big")
    derot9 = rot_right(val, 9)
    f0_at_9 = f9(derot9, 0)

    # Check at R=cumulative for null
    r_cum = 9 * (pos + 1)
    derot_c = rot_right(val, r_cum)
    f0_cum = f9(derot_c, 0)

    # Type C: control event (F0=0x078 at R=9, note=120)
    if f0_at_9 == 0x078:
        return 'C'  # Control

    # Type C variant: F0=0x0F8 at R=9 (note=120 with bit7)
    if (f0_at_9 & 0x7F) == 120:
        return 'C'

    # Type 0: null event (F0=0x000 at cumulative R)
    if f0_cum == 0x000:
        return '0'  # Null

    # Everything else is a potential note event
    return 'N'  # Note


def main():
    base = os.path.dirname(os.path.abspath(__file__))
    syx = os.path.join(base, "captured", "ground_truth_style.syx")
    tracks = get_all_tracks(syx)

    track_names = ["RHY1", "RHY2", "BASS", "CHD1", "CHD2", "PAD", "PHR1", "PHR2"]
    encoding = {
        0: "2543", 1: "29CB", 2: "2BE3", 3: "29CB",
        4: "1FA3", 5: "29CB", 6: "1FA3", 7: "1FA3"
    }
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
        80: "MuTriang", 81: "OpTriang", 82: "Shaker", 83: "JnglBell", 84: "BellTree",
        85: "Castanets", 86: "MuSurdo", 87: "OpSurdo",
    }

    # ============================================================
    # 1. Classify ALL events
    # ============================================================
    print(f"{'='*80}")
    print(f"  EVENT CLASSIFICATION (all tracks, Section 0)")
    print(f"{'='*80}")

    global_stats = defaultdict(lambda: {'N': 0, 'C': 0, '0': 0, 'total': 0})

    for track_idx in sorted(tracks.keys()):
        data = tracks[track_idx]
        segments = get_segments(data)
        enc = encoding.get(track_idx, "?")

        counts = Counter()
        note_events_valid = 0
        note_events_total = 0

        for seg_idx, seg in enumerate(segments):
            if len(seg) < 20:
                continue
            nevts = (len(seg) - 13) // 7
            for i in range(nevts):
                evt = seg[13 + i * 7: 13 + (i + 1) * 7]
                if len(evt) != 7:
                    continue

                etype = classify_event(evt, i)
                counts[etype] += 1
                global_stats[enc][etype] += 1
                global_stats[enc]['total'] += 1

                if etype == 'N':
                    note_events_total += 1
                    # Cumulative decode for note events
                    note, vel, gate, tick, *_ = decode(evt, 9 * (i + 1))
                    if note in XG_RANGE:
                        note_events_valid += 1

        total = sum(counts.values())
        note_pct = 100 * note_events_valid / note_events_total if note_events_total > 0 else 0
        print(f"\n  {track_names[track_idx]} ({enc}): {total} events")
        print(f"    Types: N={counts.get('N',0)} C={counts.get('C',0)} "
              f"0={counts.get('0',0)}")
        print(f"    Note events: {note_events_valid}/{note_events_total}"
              f" XG valid ({note_pct:.0f}%) ← TRUE accuracy")

    # ============================================================
    # 2. Summary by encoding type
    # ============================================================
    print(f"\n{'='*80}")
    print(f"  SUMMARY BY ENCODING TYPE")
    print(f"{'='*80}")

    for enc in ["2543", "1FA3", "29CB", "2BE3"]:
        s = global_stats[enc]
        if s['total'] == 0:
            continue
        print(f"\n  {enc}: {s['total']} events total")
        print(f"    Note (N): {s['N']} ({100*s['N']/s['total']:.0f}%)")
        print(f"    Control (C): {s['C']} ({100*s['C']/s['total']:.0f}%)")
        print(f"    Null (0): {s['0']} ({100*s['0']/s['total']:.0f}%)")

    # ============================================================
    # 3. RHY1 detailed: note events only, with classification
    # ============================================================
    print(f"\n{'='*80}")
    print(f"  RHY1 DETAILED: note events with cumulative rotation")
    print(f"{'='*80}")

    data = tracks.get(0)
    if data:
        segments = get_segments(data)
        total_note = 0
        valid_note = 0

        for seg_idx, seg in enumerate(segments):
            if len(seg) < 20:
                continue
            nevts = (len(seg) - 13) // 7

            seg_events = []
            for i in range(nevts):
                evt = seg[13 + i * 7: 13 + (i + 1) * 7]
                if len(evt) != 7:
                    continue

                etype = classify_event(evt, i)
                note, vel, gate, tick, vc, fields, rem = decode(evt, 9 * (i + 1))
                name = GM_DRUMS.get(note, f'n{note}')
                valid = note in XG_RANGE

                if etype == 'N':
                    total_note += 1
                    if valid:
                        valid_note += 1
                    status = "✓" if valid else "✗"
                else:
                    status = f"[{etype}]"

                seg_events.append((i, etype, note, name, vel, gate, tick, status, evt))

            if seg_events:
                print(f"\n  Seg {seg_idx}:")
                for i, et, note, name, vel, gate, tick, status, evt in seg_events:
                    print(f"    e{i}: {status:>4} note={note:>3}({name:>10})"
                          f"  vel={vel:>3} gate={gate:>3} tick={tick:>5}"
                          f"  [{et}] {evt.hex()}")

        pct = 100 * valid_note / total_note if total_note > 0 else 0
        print(f"\n  RHY1 TRUE ACCURACY (note events only): "
              f"{valid_note}/{total_note} ({pct:.0f}%)")

    # ============================================================
    # 4. Control event analysis: what do they encode?
    # ============================================================
    print(f"\n{'='*80}")
    print(f"  CONTROL EVENT CONTENT ANALYSIS")
    print(f"{'='*80}")

    ctrl_events = []
    for track_idx in sorted(tracks.keys()):
        data = tracks[track_idx]
        segments = get_segments(data)

        for seg_idx, seg in enumerate(segments):
            if len(seg) < 20:
                continue
            nevts = (len(seg) - 13) // 7
            for i in range(nevts):
                evt = seg[13 + i * 7: 13 + (i + 1) * 7]
                if len(evt) != 7:
                    continue
                if classify_event(evt, i) == 'C':
                    ctrl_events.append((track_idx, seg_idx, i, evt))

    # Group by raw bytes
    by_bytes = defaultdict(list)
    for track_idx, seg_idx, pos, evt in ctrl_events:
        by_bytes[evt.hex()].append(
            f"{track_names[track_idx]}:seg{seg_idx}:e{pos}")

    print(f"\n  Unique control event patterns: {len(by_bytes)}")
    print(f"\n  Shared patterns (appear in >1 location):")
    for hex_str, locations in sorted(by_bytes.items(), key=lambda x: -len(x[1])):
        if len(locations) > 1:
            print(f"    {hex_str}: {', '.join(locations)}")

    # Decode control events at R=9 to see field patterns
    print(f"\n  Control event field distribution at R=9:")
    f1_vals = Counter()
    f5_vals = Counter()
    rem_vals = Counter()
    for _, _, _, evt in ctrl_events:
        val = int.from_bytes(evt, "big")
        derot9 = rot_right(val, 9)
        fields = [f9(derot9, j) for j in range(6)]
        rem = derot9 & 0x3
        f1_vals[fields[1]] += 1
        f5_vals[fields[5]] += 1
        rem_vals[rem] += 1

    print(f"    F1 values: {dict(f1_vals.most_common(10))}")
    print(f"    F5 values: {dict(f5_vals.most_common(10))}")
    print(f"    Remainder: {dict(rem_vals)}")

    # ============================================================
    # 5. Adjusted accuracy: all tracks, note events only
    # ============================================================
    print(f"\n{'='*80}")
    print(f"  ADJUSTED ACCURACY (note events only, cumulative R=9*(i+1))")
    print(f"{'='*80}")

    for track_idx in sorted(tracks.keys()):
        data = tracks[track_idx]
        segments = get_segments(data)
        enc = encoding.get(track_idx, "?")

        total_all = 0
        total_note = 0
        valid_note = 0
        valid_mixed = 0

        for seg in segments:
            if len(seg) < 20:
                continue
            nevts = (len(seg) - 13) // 7
            for i in range(nevts):
                evt = seg[13 + i * 7: 13 + (i + 1) * 7]
                if len(evt) != 7:
                    continue
                total_all += 1
                etype = classify_event(evt, i)
                if etype != 'N':
                    continue
                total_note += 1

                note_c, *_ = decode(evt, 9 * (i + 1))
                note_k, *_ = decode(evt, 9)
                if note_c in XG_RANGE:
                    valid_note += 1
                if note_c in XG_RANGE or note_k in XG_RANGE:
                    valid_mixed += 1

        if total_note > 0:
            pct_c = 100 * valid_note / total_note
            pct_m = 100 * valid_mixed / total_note
            print(f"  {track_names[track_idx]} ({enc}): "
                  f"{total_note}/{total_all} note events | "
                  f"cum={valid_note}/{total_note} ({pct_c:.0f}%) | "
                  f"mixed={valid_mixed}/{total_note} ({pct_m:.0f}%)")


if __name__ == "__main__":
    main()
