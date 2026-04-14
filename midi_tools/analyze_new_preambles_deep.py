#!/usr/bin/env python3
"""Deep analysis of 2D2B and 303B encodings.

Key observations from initial analysis:
- Preamble encoding type at bytes 24-25 (same structure as all other encodings)
- CHD1 (2D2B): 7 segments, events partially shared across bars (like 1FA3 chord encoding)
- CHD2 (303B): 2 segments, short track

Tests:
1. R_base sweep: find optimal R_base for cumulative R = R_base * (i+1) % 56
2. Bar header decode: do 9-bit fields give valid MIDI chord notes?
3. Event similarity: are events near-identical across bars (shift register pattern)?
4. F3/F4 beat counter / chord mask test
"""
import sys
import os
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qymanager.formats.qy70.sysex_parser import SysExParser
from midi_tools.event_decoder import rot_right, extract_9bit

TRACK_NAMES = {
    0: "RHY1", 1: "RHY2", 2: "BASS", 3: "CHD1",
    4: "CHD2", 5: "PAD", 6: "PHR1", 7: "PHR2",
}

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def note_name(n):
    if 0 <= n <= 127:
        return f"{NOTE_NAMES[n % 12]}{n // 12 - 1}"
    return f"n{n}"


def get_all_tracks(syx_path):
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
            segments.append({"header": header, "events": events, "delim": delim_byte})
        prev = dp + 1
    seg = event_data[prev:]
    if len(seg) >= 13:
        header = seg[:13]
        events = []
        for i in range((len(seg) - 13) // 7):
            evt = seg[13 + i*7:13 + (i+1)*7]
            if len(evt) == 7:
                events.append(evt)
        segments.append({"header": header, "events": events, "delim": None})
    return segments


def decode_at_r(evt_bytes, r_value):
    val = int.from_bytes(evt_bytes, "big")
    derot = rot_right(val, r_value)
    fields = [extract_9bit(derot, i) for i in range(6)]
    rem = derot & 0x3
    return {"fields": fields, "rem": rem}


def decode_header_fields(header_bytes):
    """Decode 13-byte bar header into 9-bit fields (same as event data)."""
    # 13 bytes = 104 bits. Treat as big-endian integer, extract 9-bit fields.
    val = int.from_bytes(header_bytes, "big")
    nbits = len(header_bytes) * 8
    fields = []
    for i in range(nbits // 9):
        shift = nbits - 9 * (i + 1)
        f = (val >> shift) & 0x1FF
        fields.append(f)
    return fields  # 11 fields from 13 bytes (99 bits) + 5 remainder bits


def sweep_r_base(segments, label):
    """Find optimal R_base for cumulative R = R_base * (i+1) % 56."""
    print(f"\n{'=' * 70}")
    print(f"  R_BASE SWEEP — {label}")
    print(f"{'=' * 70}")

    all_events = []
    for si, seg in enumerate(segments):
        for ei, evt in enumerate(seg["events"]):
            all_events.append((si, ei, evt))

    if not all_events:
        print("  No events!")
        return

    # For each R_base, count valid notes (0-127) and common drum/chord range
    results = []
    for r_base in range(1, 56):
        valid_count = 0
        chord_count = 0  # notes in typical chord range (36-84)
        notes = []
        for si, ei, evt in all_events:
            r = (r_base * (ei + 1)) % 56
            d = decode_at_r(evt, r)
            n = d["fields"][0] & 0x7F
            if 0 <= n <= 127:
                valid_count += 1
            if 36 <= n <= 84:
                chord_count += 1
            notes.append(n)

        results.append((chord_count, valid_count, r_base, notes))

    results.sort(key=lambda x: (-x[0], -x[1]))
    print(f"\n  Top 10 by chord-range notes (36-84):")
    print(f"  {'R_base':>5s} {'chord':>5s} {'valid':>5s} {'total':>5s} | sample notes")
    for chord_count, valid_count, r_base, notes in results[:10]:
        sample = [note_name(n) for n in notes[:8]]
        print(f"  {r_base:5d} {chord_count:5d} {valid_count:5d} {len(all_events):5d} | {sample}")

    # Also try constant R (not cumulative)
    print(f"\n  Top 10 CONSTANT R (same R for all events):")
    const_results = []
    for r in range(56):
        chord_count = 0
        notes = []
        for si, ei, evt in all_events:
            d = decode_at_r(evt, r)
            n = d["fields"][0] & 0x7F
            if 36 <= n <= 84:
                chord_count += 1
            notes.append(n)
        const_results.append((chord_count, r, notes))

    const_results.sort(key=lambda x: -x[0])
    for chord_count, r, notes in const_results[:10]:
        sample = [note_name(n) for n in notes[:8]]
        print(f"  R={r:2d}: {chord_count}/{len(all_events)} chord-range | {sample}")


def analyze_event_similarity(segments, label):
    """Check if events are near-identical across bars (like 1FA3)."""
    print(f"\n{'=' * 70}")
    print(f"  EVENT BYTE SIMILARITY — {label}")
    print(f"{'=' * 70}")

    max_events = max((len(s["events"]) for s in segments), default=0)
    for ei in range(min(6, max_events)):
        events_at_pos = []
        for si, seg in enumerate(segments):
            if ei < len(seg["events"]):
                events_at_pos.append((si, seg["events"][ei]))

        if len(events_at_pos) < 2:
            continue

        # Compute byte-wise hamming distance between first and each subsequent
        first_evt = events_at_pos[0][1]
        print(f"\n  Position e{ei} ({len(events_at_pos)} bars):")
        print(f"    Reference (seg{events_at_pos[0][0]}): {first_evt.hex()}")

        for si, evt in events_at_pos[1:]:
            diff_bytes = sum(1 for a, b in zip(first_evt, evt) if a != b)
            diff_bits = sum(bin(a ^ b).count('1') for a, b in zip(first_evt, evt))
            xor = bytes(a ^ b for a, b in zip(first_evt, evt))
            print(f"    seg{si}: {evt.hex()} — {diff_bytes}/7 bytes differ, "
                  f"{diff_bits} bits, XOR={xor.hex()}")


def analyze_header_chords(segments, label):
    """Decode bar headers as 9-bit fields and check for chord notes."""
    print(f"\n{'=' * 70}")
    print(f"  BAR HEADER ANALYSIS — {label}")
    print(f"{'=' * 70}")

    for si, seg in enumerate(segments):
        header = seg["header"]
        fields = decode_header_fields(header)
        delim = f"0x{seg['delim']:02X}" if seg["delim"] is not None else "END"

        # Check if first 5 fields are valid MIDI notes
        valid = sum(1 for f in fields[:5] if 0 <= f <= 127)
        note_str = [f"{f}({note_name(f)})" if f <= 127 else f"{f}" for f in fields[:5]]

        print(f"  Seg {si} [{delim}]: header={header.hex()}")
        print(f"    F0-F4: {note_str}")
        print(f"    F5-F10: {fields[5:]}")
        print(f"    Valid notes (0-127): {valid}/5")


def analyze_f3f4_patterns(segments, label, r_base=9):
    """Check F3 beat counter and F4 chord mask patterns."""
    print(f"\n{'=' * 70}")
    print(f"  F3/F4 PATTERN ANALYSIS — {label} (R_base={r_base})")
    print(f"{'=' * 70}")

    for si, seg in enumerate(segments[:4]):
        if not seg["events"]:
            continue
        print(f"\n  Segment {si} ({len(seg['events'])} events):")

        for ei, evt in enumerate(seg["events"]):
            r = (r_base * (ei + 1)) % 56
            d = decode_at_r(evt, r)
            f0, f1, f2, f3, f4, f5 = d["fields"]
            rem = d["rem"]

            # F0 decomposition
            note = f0 & 0x7F
            bit8 = (f0 >> 8) & 1
            bit7 = (f0 >> 7) & 1

            # F3 decomposition (1FA3 style): hi2 | mid3 | lo4
            f3_hi2 = (f3 >> 7) & 0x3
            f3_mid3 = (f3 >> 4) & 0x7
            f3_lo4 = f3 & 0xF

            # F4 decomposition (1FA3 style): mask5 | param4
            f4_mask5 = (f4 >> 4) & 0x1F
            f4_param4 = f4 & 0xF

            # Beat from lo4
            beat_map = {0: 0, 8: 0, 4: 1, 2: 2, 1: 3}
            beat = beat_map.get(f3_lo4, -1)

            nname = note_name(note)
            print(f"    e{ei} R={r:2d}: {nname:>5s} n={note:3d} "
                  f"F3=[{f3_hi2}|{f3_mid3}|{f3_lo4:04b}]b{beat} "
                  f"F4=[m{f4_mask5:05b}|p{f4_param4}] "
                  f"F5={f5:3d} rem={rem}")


def main():
    user_syx = "midi_tools/captured/user_style_live.syx"
    sgt_syx = "midi_tools/captured/ground_truth_style.syx"

    user_tracks = get_all_tracks(user_syx)
    sgt_tracks = get_all_tracks(sgt_syx)

    # ---- USER-CHD1 (2D2B) ----
    if 3 in user_tracks:
        data = user_tracks[3]
        segments = get_segments(data)
        sweep_r_base(segments, "USER-CHD1 (2D2B)")
        analyze_event_similarity(segments, "USER-CHD1 (2D2B)")
        analyze_header_chords(segments, "USER-CHD1 (2D2B)")
        # Try multiple R_base values for F3/F4
        for rb in [9, 47]:
            analyze_f3f4_patterns(segments, "USER-CHD1 (2D2B)", r_base=rb)

    # ---- USER-CHD2 (303B) ----
    if 4 in user_tracks:
        data = user_tracks[4]
        segments = get_segments(data)
        sweep_r_base(segments, "USER-CHD2 (303B)")
        analyze_event_similarity(segments, "USER-CHD2 (303B)")
        analyze_header_chords(segments, "USER-CHD2 (303B)")
        for rb in [9, 47]:
            analyze_f3f4_patterns(segments, "USER-CHD2 (303B)", r_base=rb)

    # ---- SGT-CHD2 (1FA3) for comparison ----
    if 4 in sgt_tracks:
        data = sgt_tracks[4]
        segments = get_segments(data)
        analyze_event_similarity(segments, "SGT-CHD2 (1FA3)")
        analyze_header_chords(segments, "SGT-CHD2 (1FA3)")
        analyze_f3f4_patterns(segments, "SGT-CHD2 (1FA3)", r_base=9)

    # ---- Also check PAD (303B) and PHR1 (303B) ----
    for al, tname in [(5, "PAD"), (6, "PHR1")]:
        if al in user_tracks:
            data = user_tracks[al]
            preamble = data[24:26].hex()
            segments = get_segments(data)
            print(f"\n\n{'#' * 70}")
            print(f"  USER-{tname} (preamble={preamble})")
            print(f"  {len(data)}B, {len(segments)} segments")
            print(f"{'#' * 70}")
            if segments:
                sweep_r_base(segments, f"USER-{tname} ({preamble})")
                analyze_header_chords(segments, f"USER-{tname} ({preamble})")


if __name__ == "__main__":
    main()
