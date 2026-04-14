#!/usr/bin/env python3
"""Analyze new preamble values 0x2D2B and 0x303B found in USER style.

USER style (user_style_live.syx) has:
  - CHD1 (AL=3): preamble 0x2D2B (unknown)
  - CHD2 (AL=4), PAD (AL=5), PHR1 (AL=6), PHR2 (AL=7): preamble 0x303B (unknown)

Compare with SGT style (ground_truth_style.syx) which uses known preambles:
  - CHD1: 29DC, CHD2: 1FA3, PHR1: 1FA3, etc.

Goal: determine if 2D2B/303B are variants of known encodings or entirely new.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qymanager.formats.qy70.sysex_parser import SysExParser
from midi_tools.event_decoder import (
    rot_right, extract_9bit, classify_encoding,
    PREAMBLE_CHORD, PREAMBLE_GENERAL, PREAMBLE_BASS_SLOT, PREAMBLE_DRUM_PRIMARY,
)

TRACK_NAMES = {
    0: "RHY1", 1: "RHY2", 2: "BASS", 3: "CHD1",
    4: "CHD2", 5: "PAD", 6: "PHR1", 7: "PHR2",
}


def get_all_tracks(syx_path):
    """Extract all tracks with their preambles from a syx file."""
    parser = SysExParser()
    messages = parser.parse_file(syx_path)
    tracks = {}
    for m in messages:
        if m.is_style_data and m.decoded_data:
            al = m.address_low
            if al not in tracks:
                tracks[al] = b''
            tracks[al] += m.decoded_data
    return tracks


def get_segments(data, skip_preamble=28):
    """Split track data into segments at DC/9E delimiters."""
    event_data = data[skip_preamble:]
    delim_pos = [i for i, b in enumerate(event_data) if b in (0xDC, 0x9E)]
    segments = []
    prev = 0
    for dp in delim_pos:
        seg = event_data[prev:dp]
        delim_byte = event_data[dp]
        if len(seg) >= 13:
            header = seg[:13]
            events = []
            for i in range((len(seg) - 13) // 7):
                evt = seg[13 + i*7:13 + (i+1)*7]
                if len(evt) == 7:
                    events.append(evt)
            trail = seg[13 + ((len(seg) - 13) // 7) * 7:]
            segments.append({
                "header": header,
                "events": events,
                "trail": trail,
                "delim": delim_byte,
                "raw_len": len(seg),
            })
        prev = dp + 1
    # Last segment (no trailing delimiter)
    seg = event_data[prev:]
    if len(seg) >= 13:
        header = seg[:13]
        events = []
        for i in range((len(seg) - 13) // 7):
            evt = seg[13 + i*7:13 + (i+1)*7]
            if len(evt) == 7:
                events.append(evt)
        trail = seg[13 + ((len(seg) - 13) // 7) * 7:]
        segments.append({
            "header": header,
            "events": events,
            "trail": trail,
            "delim": None,
            "raw_len": len(seg),
        })
    return segments


def decode_at_r(evt_bytes, r_value):
    """Decode event at given rotation."""
    val = int.from_bytes(evt_bytes, "big")
    derot = rot_right(val, r_value)
    fields = [extract_9bit(derot, i) for i in range(6)]
    rem = derot & 0x3
    f0 = fields[0]
    note = f0 & 0x7F
    bit8 = (f0 >> 8) & 1
    bit7 = (f0 >> 7) & 1
    vel_code = (bit8 << 3) | (bit7 << 2) | rem
    velocity = max(1, 127 - vel_code * 8)
    f1 = fields[1]
    f2 = fields[2]
    beat = f1 >> 7
    clock = ((f1 & 0x7F) << 2) | (f2 >> 7)
    tick = beat * 480 + clock
    return {
        "note": note, "velocity": velocity, "tick": tick,
        "gate": fields[5], "fields": fields, "rem": rem, "f0": f0,
        "valid_drum": 13 <= note <= 87,
        "valid_note": 0 <= note <= 127,
    }


def r_sweep_event(evt_bytes, valid_range=(0, 127)):
    """Find all R values that give a valid note in range."""
    results = []
    for r in range(56):
        d = decode_at_r(evt_bytes, r)
        if valid_range[0] <= d["note"] <= valid_range[1]:
            results.append((r, d))
    return results


def analyze_preamble_relationship():
    """Check if 2D2B and 303B are bit-rotations or offsets of known preambles."""
    known = {
        "1FA3 (chord)": 0x1FA3,
        "29CB (general)": 0x29CB,
        "2BE3 (bass)": 0x2BE3,
        "2543 (drum)": 0x2543,
        "29DC (CHD1/SGT)": 0x29DC,
        "294B (RHY2)": 0x294B,
    }
    new = {"2D2B": 0x2D2B, "303B": 0x303B}

    print("=" * 70)
    print("  PREAMBLE RELATIONSHIP ANALYSIS")
    print("=" * 70)

    for nname, nval in new.items():
        print(f"\n  {nname} (0x{nval:04X} = {nval:016b}):")
        for kname, kval in known.items():
            diff = nval ^ kval
            dist = bin(diff).count('1')
            offset = (nval - kval) & 0xFFFF
            print(f"    vs {kname}: XOR=0x{diff:04X} hamming={dist} "
                  f"offset={offset:+d} (0x{offset:04X})")

    # Check if they're bit-rotations of known values
    print(f"\n  BIT ROTATION CHECK:")
    for nname, nval in new.items():
        for kname, kval in known.items():
            for rot in range(1, 16):
                rotated = ((kval >> rot) | (kval << (16 - rot))) & 0xFFFF
                if rotated == nval:
                    print(f"    {nname} = ROT_RIGHT({kname}, {rot})")


def analyze_track(data, al, label, preamble_hex):
    """Full analysis of a track with unknown preamble."""
    print(f"\n{'=' * 70}")
    print(f"  {label} (AL={al}) — preamble 0x{preamble_hex}")
    print(f"  {len(data)} bytes total")
    print(f"{'=' * 70}")

    # Show preamble area
    print(f"\n  Preamble (0-27): {data[:28].hex()}")
    print(f"  Preamble bytes 0-1: {data[0]:02X} {data[1]:02X}")
    print(f"  Preamble bytes 2-3: {data[2]:02X} {data[3]:02X}")
    print(f"  Preamble bytes 4-13: {data[4:14].hex()}")
    print(f"  Preamble bytes 14-27: {data[14:28].hex()}")

    # Extended preamble (before first DC)
    event_data = data[28:]
    first_dc = next((i for i, b in enumerate(event_data) if b in (0xDC, 0x9E)), len(event_data))
    ext_preamble = event_data[:first_dc]
    print(f"\n  Extended preamble ({first_dc}B): {ext_preamble.hex()}")

    segments = get_segments(data)
    print(f"\n  Segments: {len(segments)}")

    for si, seg in enumerate(segments):
        nevts = len(seg["events"])
        delim = f"0x{seg['delim']:02X}" if seg["delim"] is not None else "END"
        trail = seg["trail"].hex() if seg["trail"] else ""
        print(f"    Seg {si}: {nevts} events, {seg['raw_len']}B, "
              f"delim={delim}, header={seg['header'][:4].hex()}, trail={trail}")

    # Analyze first few events with multiple R models
    print(f"\n  EVENT ANALYSIS — testing rotation models:")

    models = {
        "R=9 const": lambda i: 9,
        "R=9*(i+1) cum": lambda i: (9 * (i + 1)) % 56,
        "R=47 const": lambda i: 47,
        "R=47*(i+1) cum": lambda i: (47 * (i + 1)) % 56,
    }

    for si, seg in enumerate(segments[:4]):  # First 4 segments
        if not seg["events"]:
            continue
        print(f"\n    --- Segment {si} ({len(seg['events'])} events) ---")

        for ei, evt in enumerate(seg["events"][:6]):  # First 6 events
            print(f"\n    e{ei}: raw={evt.hex()}")
            for mname, rfunc in models.items():
                r = rfunc(ei)
                d = decode_at_r(evt, r)
                n = d["note"]
                v = d["velocity"]
                t = d["tick"]
                g = d["gate"]
                valid = "OK" if d["valid_note"] else "BAD"
                print(f"      {mname:20s} R={r:2d}: n={n:3d} v={v:3d} "
                      f"t={t:5d} g={g:3d} [{valid}]")

    # R sweep per event — find which R values give notes in common MIDI range
    print(f"\n  R SWEEP (find valid-note R per event, first 2 segments):")
    for si, seg in enumerate(segments[:2]):
        for ei, evt in enumerate(seg["events"][:6]):
            valid_rs = r_sweep_event(evt, valid_range=(24, 96))  # piano range
            if valid_rs:
                r_notes = [(r, d["note"]) for r, d in valid_rs]
                print(f"    seg{si}/e{ei}: {len(valid_rs)} valid R → "
                      f"{r_notes[:10]}")

    # Cross-segment consistency (like drum analysis)
    print(f"\n  CROSS-SEGMENT CONSISTENCY:")
    max_events = max((len(s["events"]) for s in segments), default=0)
    for ei in range(min(6, max_events)):
        events_at_pos = []
        for si, seg in enumerate(segments):
            if ei < len(seg["events"]):
                events_at_pos.append((si, seg["events"][ei]))
        if len(events_at_pos) < 2:
            continue

        best_results = []
        for r in range(56):
            note_counts = {}
            for _, evt in events_at_pos:
                d = decode_at_r(evt, r)
                n = d["note"]
                if 0 <= n <= 127:
                    note_counts[n] = note_counts.get(n, 0) + 1
            for n, cnt in note_counts.items():
                if cnt >= 2:
                    best_results.append((cnt, r, n))

        best_results.sort(key=lambda x: (-x[0], x[1]))
        shown = set()
        top3 = []
        for cnt, r, n in best_results:
            if n not in shown:
                shown.add(n)
                top3.append(f"R={r}→n{n}({cnt}/{len(events_at_pos)})")
                if len(top3) >= 3:
                    break
        print(f"    pos e{ei} ({len(events_at_pos)} segs): {', '.join(top3)}")


def main():
    user_syx = "midi_tools/captured/user_style_live.syx"
    sgt_syx = "midi_tools/captured/ground_truth_style.syx"

    # Step 1: Preamble relationship analysis
    analyze_preamble_relationship()

    # Step 2: Survey all tracks in both styles
    print(f"\n{'=' * 70}")
    print(f"  TRACK PREAMBLE SURVEY")
    print(f"{'=' * 70}")

    for syx_path, label in [(user_syx, "USER"), (sgt_syx, "SGT")]:
        tracks = get_all_tracks(syx_path)
        print(f"\n  {label} ({syx_path}):")
        for al in sorted(tracks):
            data = tracks[al]
            if len(data) >= 2:
                preamble = data[:2].hex()
                enc = classify_encoding(data[:2])
                tname = TRACK_NAMES.get(al, f"AL={al}")
                print(f"    AL={al} ({tname:5s}): preamble={preamble}, "
                      f"encoding={enc}, {len(data)}B")

    # Step 3: Analyze the unknown preamble tracks
    user_tracks = get_all_tracks(user_syx)

    # CHD1 with 2D2B
    if 3 in user_tracks:
        analyze_track(user_tracks[3], 3, "USER-CHD1", "2D2B")

    # CHD2 with 303B
    if 4 in user_tracks:
        analyze_track(user_tracks[4], 4, "USER-CHD2", "303B")

    # Compare with SGT-CHD2 (known 1FA3 encoding)
    sgt_tracks = get_all_tracks(sgt_syx)
    if 4 in sgt_tracks:
        print(f"\n\n{'#' * 70}")
        print(f"  COMPARISON: SGT-CHD2 (known 1FA3)")
        print(f"{'#' * 70}")
        sgt_data = sgt_tracks[4]
        print(f"  Preamble: {sgt_data[:2].hex()}")
        print(f"  Preamble area (0-27): {sgt_data[:28].hex()}")
        sgt_segs = get_segments(sgt_data)
        print(f"  Segments: {len(sgt_segs)}")
        for si, seg in enumerate(sgt_segs[:3]):
            print(f"    Seg {si}: {len(seg['events'])} events, "
                  f"header={seg['header'][:4].hex()}")


if __name__ == "__main__":
    main()
