#!/usr/bin/env python3
"""Cross-encoding failure analysis: do chord tracks (1FA3, 29CB) also have
events that fail to decode with cumulative rotation?

If yes → the format has non-note event types embedded in the stream.
If no → the issue is 2543-specific (maybe drum-specific control events).

Also tests: what if "note 120" events at R=9 share a common DEROTATED pattern?
"""

import sys, os
from collections import defaultdict, Counter
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from qymanager.formats.qy70.sysex_parser import SysExParser

XG_RANGE = set(range(13, 88))
MIDI_RANGE = set(range(0, 128))

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
    f3 = f9(derot, 3)
    f4 = f9(derot, 4)
    f5 = f9(derot, 5)
    rem = derot & 0x3
    note = f0 & 0x7F
    return note, f0, f1, f2, f3, f4, f5, rem


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


def main():
    base = os.path.dirname(os.path.abspath(__file__))
    syx = os.path.join(base, "captured", "ground_truth_style.syx")
    tracks = get_all_tracks(syx)

    track_names = ["RHY1", "RHY2", "BASS", "CHD1", "CHD2", "PAD", "PHR1", "PHR2"]

    # Encoding per track (from wiki knowledge)
    encoding = {
        0: "2543", 1: "29CB", 2: "2BE3", 3: "29CB",
        4: "1FA3", 5: "29CB", 6: "1FA3", 7: "1FA3"
    }

    # ============================================================
    # 1. Failure rate per track with cumulative R=9*(i+1)
    # ============================================================
    print(f"{'='*80}")
    print(f"  FAILURE RATE PER TRACK (cumulative R=9*(i+1))")
    print(f"{'='*80}")

    all_results = {}

    for track_idx in sorted(tracks.keys()):
        data = tracks[track_idx]
        segments = get_segments(data)

        total = 0
        valid_xg = 0
        valid_midi = 0
        note_120_at_r9 = 0
        failing_positions = []

        for seg_idx, seg in enumerate(segments):
            if len(seg) < 20:
                continue
            nevts = (len(seg) - 13) // 7
            for i in range(nevts):
                evt = seg[13 + i * 7: 13 + (i + 1) * 7]
                if len(evt) != 7:
                    continue
                total += 1

                r_cum = 9 * (i + 1)
                note, f0, *_ = decode(evt, r_cum)

                if note in XG_RANGE:
                    valid_xg += 1
                if note in MIDI_RANGE and note >= 13:
                    valid_midi += 1

                # Check note=120 at R=9
                note9, *_ = decode(evt, 9)
                if note9 == 120:
                    note_120_at_r9 += 1

                if note not in XG_RANGE:
                    failing_positions.append(i)

        enc = encoding.get(track_idx, "?")
        xg_pct = 100 * valid_xg / total if total > 0 else 0
        midi_pct = 100 * valid_midi / total if total > 0 else 0
        print(f"\n  {track_names[track_idx]} ({enc}):"
              f" {valid_xg}/{total} XG valid ({xg_pct:.0f}%)"
              f" | {valid_midi}/{total} MIDI valid ({midi_pct:.0f}%)")
        print(f"    note=120 at R=9: {note_120_at_r9}/{total}")
        if failing_positions:
            pos_counts = Counter(failing_positions)
            print(f"    Failing positions: {dict(pos_counts)}")
            parity = Counter('odd' if p % 2 == 1 else 'even' for p in failing_positions)
            print(f"    Parity distribution: {dict(parity)}")

        all_results[track_idx] = {
            'total': total, 'valid_xg': valid_xg,
            'failing_positions': failing_positions,
            'note_120_at_r9': note_120_at_r9
        }

    # ============================================================
    # 2. Mixed model per track
    # ============================================================
    print(f"\n{'='*80}")
    print(f"  MIXED MODEL PER TRACK (cumulative + constant R=9 fallback)")
    print(f"{'='*80}")

    for track_idx in sorted(tracks.keys()):
        data = tracks[track_idx]
        segments = get_segments(data)

        total = 0
        valid_cum = 0
        valid_const = 0
        valid_mixed = 0

        for seg in segments:
            if len(seg) < 20:
                continue
            nevts = (len(seg) - 13) // 7
            for i in range(nevts):
                evt = seg[13 + i * 7: 13 + (i + 1) * 7]
                if len(evt) != 7:
                    continue
                total += 1

                note_c, *_ = decode(evt, 9 * (i + 1))
                note_k, *_ = decode(evt, 9)

                if note_c in XG_RANGE:
                    valid_cum += 1
                if note_k in XG_RANGE:
                    valid_const += 1
                if note_c in XG_RANGE or note_k in XG_RANGE:
                    valid_mixed += 1

        enc = encoding.get(track_idx, "?")
        print(f"  {track_names[track_idx]} ({enc}): "
              f"cum={valid_cum}/{total} ({100*valid_cum/total:.0f}%) | "
              f"const={valid_const}/{total} ({100*valid_const/total:.0f}%) | "
              f"mixed={valid_mixed}/{total} ({100*valid_mixed/total:.0f}%)")

    # ============================================================
    # 3. Analysis of "note 120" events: common derotated structure?
    # ============================================================
    print(f"\n{'='*80}")
    print(f"  'NOTE 120' EVENTS: DEROTATED BIT PATTERN ANALYSIS")
    print(f"{'='*80}")

    note120_events = []
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

                note9, f0_9, *_ = decode(evt, 9)
                if note9 == 120:
                    note120_events.append((track_idx, seg_idx, i, evt))

    print(f"\n  Found {len(note120_events)} events with note=120 at R=9:")
    for track_idx, seg_idx, pos, evt in note120_events:
        val = int.from_bytes(evt, "big")
        derot9 = rot_right(val, 9)
        # Show the derotated value and its fields
        fields = [f9(derot9, j) for j in range(6)]
        rem = derot9 & 0x3
        print(f"    {track_names[track_idx]} seg{seg_idx} e{pos}: "
              f"{evt.hex()} → derot@9: "
              f"F0={fields[0]:03X} F1={fields[1]:03X} F2={fields[2]:03X} "
              f"F3={fields[3]:03X} F4={fields[4]:03X} F5={fields[5]:03X} "
              f"rem={rem}")

    # Check if F0=0x078 specifically
    f0_values = []
    for _, _, _, evt in note120_events:
        val = int.from_bytes(evt, "big")
        derot9 = rot_right(val, 9)
        f0 = f9(derot9, 0)
        f0_values.append(f0)

    f0_counts = Counter(f0_values)
    print(f"\n  F0 value distribution at R=9: {dict(f0_counts)}")
    print(f"    0x078 (120, flags=00): {f0_counts.get(0x078, 0)}")
    print(f"    0x0F8 (120, flags=01): {f0_counts.get(0x0F8, 0)}")
    print(f"    0x178 (120, flags=10): {f0_counts.get(0x178, 0)}")
    print(f"    0x1F8 (120, flags=11): {f0_counts.get(0x1F8, 0)}")

    # ============================================================
    # 4. What happens with R=0 for ALL chord track events?
    # ============================================================
    print(f"\n{'='*80}")
    print(f"  R=0 TEST: chord events (1FA3) — is event_decoder's formula correct?")
    print(f"{'='*80}")

    # event_decoder.py uses R = event_index × 9, so e0 gets R=0
    # Our formula R = 9*(i+1) gives e0 gets R=9
    # Let's compare both for chord tracks

    for track_idx in [4, 6]:  # CHD2, PHR1
        data = tracks.get(track_idx)
        if not data:
            continue
        segments = get_segments(data)

        total = 0
        valid_r0based = 0  # R = 9*i (e0 at R=0)
        valid_r1based = 0  # R = 9*(i+1) (e0 at R=9)

        for seg in segments:
            if len(seg) < 20:
                continue
            nevts = (len(seg) - 13) // 7
            for i in range(nevts):
                evt = seg[13 + i * 7: 13 + (i + 1) * 7]
                if len(evt) != 7:
                    continue
                total += 1

                note_0, *_ = decode(evt, 9 * i)  # event_decoder formula
                note_1, *_ = decode(evt, 9 * (i + 1))  # our formula

                if note_0 in XG_RANGE:
                    valid_r0based += 1
                if note_1 in XG_RANGE:
                    valid_r1based += 1

        print(f"\n  {track_names[track_idx]}:")
        print(f"    R=9*i (event_decoder):  {valid_r0based}/{total}"
              f" ({100*valid_r0based/total:.0f}%)")
        print(f"    R=9*(i+1) (our):        {valid_r1based}/{total}"
              f" ({100*valid_r1based/total:.0f}%)")

    # ============================================================
    # 5. Per-track: events at MIDI note range (0-127) but outside XG (13-87)
    # ============================================================
    print(f"\n{'='*80}")
    print(f"  EVENTS OUTSIDE XG RANGE BUT INSIDE MIDI RANGE (cumulative)")
    print(f"{'='*80}")

    for track_idx in sorted(tracks.keys()):
        data = tracks[track_idx]
        segments = get_segments(data)

        outside_xg = []
        for seg_idx, seg in enumerate(segments):
            if len(seg) < 20:
                continue
            nevts = (len(seg) - 13) // 7
            for i in range(nevts):
                evt = seg[13 + i * 7: 13 + (i + 1) * 7]
                if len(evt) != 7:
                    continue
                note, f0, *_ = decode(evt, 9 * (i + 1))
                if note not in XG_RANGE:
                    outside_xg.append((seg_idx, i, note, f0))

        if outside_xg:
            enc = encoding.get(track_idx, "?")
            print(f"\n  {track_names[track_idx]} ({enc}):")
            for seg_idx, pos, note, f0 in outside_xg:
                region = ("below" if note < 13 else
                          "above" if note > 87 else "in-range")
                print(f"    seg{seg_idx} e{pos}: note={note:>3} (F0={f0:03X})"
                      f"  [{region}]")


if __name__ == "__main__":
    main()
