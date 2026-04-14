#!/usr/bin/env python3
"""Analyze raw structure of RHY1 track from user_style_live.syx.

Dumps hex, finds delimiters, checks segment alignment, tries multiple
rotation models to find the best match for known drum notes.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qymanager.formats.qy70.sysex_parser import SysExParser
from midi_tools.event_decoder import rot_right, extract_9bit

GM_DRUMS = {
    35: 'Kick2', 36: 'Kick1', 37: 'SStick', 38: 'Snare1', 39: 'Clap',
    40: 'ElSnare', 42: 'HHclose', 44: 'HHpedal', 46: 'HHopen',
    48: 'HiMidTom', 49: 'Crash1', 51: 'Ride1', 57: 'Crash2',
}
EXPECTED = {36, 38, 42}


def get_track(syx_path, al_target):
    parser = SysExParser()
    messages = parser.parse_file(syx_path)
    data = b''
    for m in messages:
        if m.is_style_data and m.decoded_data and m.address_low == al_target:
            data += m.decoded_data
    return data


def try_decode_note(evt_bytes, event_index, rotation_func):
    """Try to decode a note with a given rotation function."""
    val = int.from_bytes(evt_bytes, "big")
    r = rotation_func(event_index)
    derot = rot_right(val, r)
    f0 = extract_9bit(derot, 0)
    note = f0 & 0x7F
    remainder = derot & 0x3
    bit8 = (f0 >> 8) & 1
    bit7 = (f0 >> 7) & 1
    vel_code = (bit8 << 3) | (bit7 << 2) | remainder
    velocity = max(1, 127 - vel_code * 8)
    return note, velocity, f0


def main():
    data = get_track("midi_tools/captured/user_style_live.syx", 0)
    if not data:
        print("RHY1 not found")
        return

    print(f"RHY1: {len(data)} bytes")

    # Dump preamble area
    print(f"\n=== PREAMBLE (first 28 bytes) ===")
    for i in range(0, min(28, len(data)), 8):
        chunk = data[i:i+8]
        hexs = ' '.join(f'{b:02x}' for b in chunk)
        print(f"  {i:3d}: {hexs}")

    event_data = data[28:]
    print(f"\n=== EVENT DATA ({len(event_data)} bytes) ===")

    # Find all delimiters (DC=0xDC, 9E=0x9E)
    delimiters = []
    for i, b in enumerate(event_data):
        if b in (0xDC, 0x9E):
            delimiters.append((i, b))

    print(f"\nDelimiters found: {len(delimiters)}")
    for pos, val in delimiters:
        print(f"  offset {pos:3d} (0x{pos:03x}): 0x{val:02X} "
              f"({'DC=bar' if val==0xDC else '9E=sub-bar'})")

    # Segment analysis
    print(f"\n=== SEGMENTS ===")
    boundaries = [0] + [pos + 1 for pos, _ in delimiters] + [len(event_data)]
    for si in range(len(boundaries) - 1):
        start = boundaries[si]
        end = boundaries[si + 1]
        seg = event_data[start:end]
        seg_len = len(seg)
        payload = seg_len - 13
        n_events = payload // 7
        trail = payload % 7
        print(f"\n  Segment {si}: offset {start}-{end-1} ({seg_len} bytes)")
        print(f"    Header (13B): {seg[:13].hex()}")
        print(f"    Payload: {payload}B → {n_events} events + {trail} trailing")
        if trail > 0:
            print(f"    TRAILING: {seg[-trail:].hex()}")

        # Dump events with multiple rotation models
        for ei in range(n_events):
            evt = seg[13 + ei*7:13 + (ei+1)*7]
            print(f"\n    e{ei}: {evt.hex()}")

            # Try different R models
            models = [
                ("R=9*(i+1)", lambda i: 9*(i+1)),
                ("R=9",       lambda i: 9),
                ("R=47",      lambda i: 47),
                ("R=0",       lambda i: 0),
            ]
            for name, rfunc in models:
                note, vel, f0 = try_decode_note(evt, ei, rfunc)
                valid = 13 <= note <= 87
                nname = GM_DRUMS.get(note, f"n{note}")
                expected = "***" if note in EXPECTED else ""
                mark = "OK" if valid else "BAD"
                print(f"      {name:12s}: note={note:3d} ({nname:>10s}) "
                      f"vel={vel:3d} f0=0x{f0:03x} [{mark}] {expected}")

    # Brute-force: find R value that maximizes expected note hits
    print(f"\n=== R SWEEP (best rotation for expected notes) ===")
    best_r = -1
    best_score = 0

    # Collect all 7-byte events
    all_events = []
    for si in range(len(boundaries) - 1):
        start = boundaries[si]
        end = boundaries[si + 1]
        seg = event_data[start:end]
        for ei in range((len(seg) - 13) // 7):
            evt = seg[13 + ei*7:13 + (ei+1)*7]
            all_events.append((si, ei, evt))

    for r_test in range(57):
        hits = 0
        valid = 0
        for si, ei, evt in all_events:
            note, vel, f0 = try_decode_note(evt, ei, lambda i, r=r_test: r)
            if 13 <= note <= 87:
                valid += 1
            if note in EXPECTED:
                hits += 1
        if hits > best_score:
            best_score = hits
            best_r = r_test
        if hits >= 3:
            print(f"  R={r_test:2d}: {hits} expected hits, {valid}/{len(all_events)} valid")

    print(f"\n  Best constant R={best_r}: {best_score} expected hits")

    # Also try cumulative with different bases
    print(f"\n=== CUMULATIVE R SWEEP ===")
    for base in range(1, 20):
        hits = 0
        valid = 0
        for si, ei, evt in all_events:
            r_val = base * (ei + 1)
            note, vel, f0 = try_decode_note(evt, ei, lambda i, b=base: b*(i+1))
            if 13 <= note <= 87:
                valid += 1
            if note in EXPECTED:
                hits += 1
        if hits >= 3:
            print(f"  R=base*{base:2d}*(i+1): {hits} expected hits, "
                  f"{valid}/{len(all_events)} valid")


if __name__ == "__main__":
    main()
