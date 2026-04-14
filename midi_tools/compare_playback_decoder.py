#!/usr/bin/env python3
"""Compare captured playback data with event decoder output.

Loads a .syx style dump, decodes all events per track using
decode_drum_event(), then compares with captured playback notes.

Usage:
  .venv/bin/python3 midi_tools/compare_playback_decoder.py \
    --syx midi_tools/captured/user_style_live.syx \
    --playback midi_tools/captured/playback_capture_001.json
"""
import sys
import json
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from qymanager.formats.qy70.sysex_parser import SysExParser
from qymanager.utils.yamaha_7bit import decode_7bit


# Style track slot → PATT OUT ch (9~16 mapping)
SLOT_TO_CHANNEL = {
    0: 9,   # RHY1 → D1
    1: 10,  # RHY2 → D2
    2: 12,  # BASS → BA
    3: 13,  # CHD1 → C1
    4: 14,  # CHD2 → C2
    5: 11,  # PAD → PC
    6: 15,  # PHR1 → C3
    7: 16,  # PHR2 → C4
}

SLOT_NAMES = {0: 'RHY1', 1: 'RHY2', 2: 'BASS', 3: 'CHD1',
              4: 'CHD2', 5: 'PAD', 6: 'PHR1', 7: 'PHR2'}

PREAMBLE_TYPES = {
    0x2543: 'drum_primary',
    0x29CB: 'general',
    0x29DC: 'general_29dc',
    0x294B: 'general_294b',
    0x1FA3: 'chord',
    0x2BE3: 'bass',
}

GM_DRUMS = {
    35: 'Kick2', 36: 'Kick1', 38: 'Snare1', 40: 'ElSnare',
    42: 'HHclose', 44: 'HHpedal', 46: 'HHopen', 48: 'HiMidTom',
    49: 'Crash1', 51: 'Ride1', 57: 'Crash2',
}

NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']


def note_name(n):
    return f'{NOTE_NAMES[n % 12]}{n // 12 - 1}'


def rot_right(val, shift, width=56):
    shift = shift % width
    return ((val >> shift) | (val << (width - shift))) & ((1 << width) - 1)


def extract_9bit(val, idx):
    shift = 56 - (idx + 1) * 9
    if shift < 0:
        return (val >> 0) & 0x3  # remainder
    return (val >> shift) & 0x1FF


def decode_event(evt_bytes, event_index):
    """Decode a 7-byte event using the unified decoder.
    Returns dict with type, note, velocity, gate, fields, or None."""
    val = int.from_bytes(evt_bytes, "big")

    # Priority 1: cumulative R=9*(i+1)
    r_cum = 9 * (event_index + 1)
    derot = rot_right(val, r_cum)
    f0 = extract_9bit(derot, 0)
    note = f0 & 0x7F

    rotation_used = f"R={r_cum}"

    if not (13 <= note <= 87):
        # Priority 2: constant R=9
        derot = rot_right(val, 9)
        f0 = extract_9bit(derot, 0)
        note = f0 & 0x7F
        rotation_used = "R=9"

        if not (13 <= note <= 87):
            # Priority 3: control event
            if note > 87:
                fields = [extract_9bit(derot, i) for i in range(6)]
                rem = val & 0x3
                return {"type": "control", "f0": fields[0], "fields": fields,
                        "rem": rem, "rotation": "R=9"}

            # Priority 4: R=47
            derot = rot_right(val, 47)
            f0 = extract_9bit(derot, 0)
            note = f0 & 0x7F
            rotation_used = "R=47"

            if not (13 <= note <= 87):
                return None

    # Decode note event
    fields = [extract_9bit(derot, i) for i in range(6)]
    rem = val & 0x3

    vel_code = ((f0 >> 7) & 0x3) << 2 | (rem & 0x3)
    velocity = max(1, 127 - vel_code * 8)

    f1 = fields[1]
    beat = f1 >> 7
    clock = ((f1 & 0x7F) << 2) | (fields[2] >> 7)
    tick = beat * 480 + clock

    gate = fields[5]

    return {
        "type": "note",
        "note": note,
        "velocity": velocity,
        "gate": gate,
        "tick": tick,
        "beat": beat,
        "clock": clock,
        "fields": fields,
        "rem": rem,
        "rotation": rotation_used,
    }


def extract_tracks(syx_path):
    """Extract and parse all tracks from a .syx file."""
    parser = SysExParser()
    msgs = parser.parse_file(str(syx_path))

    tracks = {}
    for m in msgs:
        if m.is_style_data and m.decoded_data:
            al = m.address_low
            if al not in tracks:
                tracks[al] = b''
            tracks[al] += m.decoded_data

    return tracks


def decode_track_events(track_data, slot):
    """Decode all events from a track's raw data."""
    if len(track_data) < 30:
        return []

    # Preamble is in the first 28 bytes (varies by format)
    preamble_bytes = track_data[:28]
    # Find preamble value - look for known patterns
    preamble = None
    for offset in range(0, min(26, len(preamble_bytes) - 1)):
        val = (preamble_bytes[offset] << 8) | preamble_bytes[offset + 1]
        if val in PREAMBLE_TYPES:
            preamble = val
            break

    events_data = track_data[28:]  # Skip preamble
    if len(events_data) < 13:
        return []

    # Parse segments (delimited by 0xDC or 0x9E)
    all_events = []
    pos = 0

    while pos < len(events_data):
        # Bar header: 13 bytes
        if pos + 13 > len(events_data):
            break
        header = events_data[pos:pos + 13]
        pos += 13

        # Find events until delimiter
        seg_events = []
        while pos < len(events_data):
            if pos < len(events_data) and events_data[pos] in (0xDC, 0x9E):
                pos += 1  # skip delimiter
                break
            if pos + 7 > len(events_data):
                break
            evt = events_data[pos:pos + 7]
            seg_events.append(evt)
            pos += 7

        # Decode events
        for i, evt in enumerate(seg_events):
            decoded = decode_event(evt, i)
            if decoded:
                all_events.append(decoded)

    return all_events


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--syx", required=True, help=".syx file to decode")
    parser.add_argument("--playback", help="JSON playback capture to compare")
    args = parser.parse_args()

    # Decode .syx
    tracks = extract_tracks(args.syx)

    print(f"{'=' * 70}")
    print(f"  DECODER OUTPUT: {args.syx}")
    print(f"{'=' * 70}")

    for al in sorted(tracks):
        if al == 0x7F:
            continue
        name = SLOT_NAMES.get(al, f'AL{al:02X}')
        ch = SLOT_TO_CHANNEL.get(al, '?')
        data = tracks[al]

        events = decode_track_events(data, al)
        note_events = [e for e in events if e["type"] == "note"]
        ctrl_events = [e for e in events if e["type"] == "control"]

        print(f"\n  {name} (AL=0x{al:02X}, PATT_OUT ch{ch}): "
              f"{len(note_events)} notes, {len(ctrl_events)} ctrl")

        if note_events:
            for i, e in enumerate(note_events[:20]):
                n = e["note"]
                if al in (0, 1):  # drum tracks
                    nname = GM_DRUMS.get(n, f"n{n}")
                else:
                    nname = note_name(n)
                print(f"    e{i:2d}: {nname:>10s} n={n:3d} v={e['velocity']:3d} "
                      f"t={e['tick']:4d} g={e['gate']:3d} ({e['rotation']})")
            if len(note_events) > 20:
                print(f"    ... and {len(note_events) - 20} more")

    # Compare with playback if provided
    if args.playback:
        with open(args.playback) as f:
            capture = json.load(f)

        print(f"\n{'=' * 70}")
        print(f"  COMPARISON: decoder vs playback")
        print(f"{'=' * 70}")

        playback_notes = [e for e in capture["events"]
                          if e["type"] == "note_on" and e["velocity"] > 0]

        for al in sorted(tracks):
            if al == 0x7F:
                continue
            name = SLOT_NAMES.get(al, f'AL{al:02X}')
            ch = SLOT_TO_CHANNEL.get(al, 0)

            decoded = [e for e in decode_track_events(tracks[al], al) if e["type"] == "note"]
            captured = [e for e in playback_notes if e["channel"] == ch]

            if not decoded and not captured:
                continue

            print(f"\n  {name} (ch{ch}): {len(decoded)} decoded, {len(captured)} captured")

            # Compare note sets
            dec_notes = sorted(set(e["note"] for e in decoded))
            cap_notes = sorted(set(e["note"] for e in captured))
            common = sorted(set(dec_notes) & set(cap_notes))
            only_dec = sorted(set(dec_notes) - set(cap_notes))
            only_cap = sorted(set(cap_notes) - set(dec_notes))

            print(f"    Decoded notes:  {dec_notes}")
            print(f"    Captured notes: {cap_notes}")
            if common:
                print(f"    MATCH:          {common}")
            if only_dec:
                print(f"    Only decoded:   {only_dec}")
            if only_cap:
                print(f"    Only captured:  {only_cap}")


if __name__ == "__main__":
    main()
