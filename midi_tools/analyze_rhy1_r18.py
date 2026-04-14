#!/usr/bin/env python3
"""Deep analysis of RHY1 with R=18 and comparison with SGT style.

Findings from analyze_rhy1_structure.py:
  - R=18 constant gives 9 expected note hits (best score)
  - Segment 0 is only 15 bytes (likely extended preamble, not a real segment)
  - Segment 6 has 14 events with repeating patterns

Also compare with ground_truth_style.syx (SGT) RHY1 which uses same 2543 preamble.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qymanager.formats.qy70.sysex_parser import SysExParser
from midi_tools.event_decoder import rot_right, extract_9bit, extract_bars, classify_encoding

GM_DRUMS = {
    35: 'Kick2', 36: 'Kick1', 37: 'SStick', 38: 'Snare1', 39: 'Clap',
    40: 'ElSnare', 41: 'LFlrTom', 42: 'HHclose', 43: 'HFlrTom',
    44: 'HHpedal', 45: 'LowTom', 46: 'HHopen', 47: 'LMidTom',
    48: 'HiMidTom', 49: 'Crash1', 50: 'HiTom', 51: 'Ride1',
    52: 'Chinese', 53: 'RideBell', 54: 'Tamb', 55: 'Splash',
    56: 'Cowbell', 57: 'Crash2',
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


def decode_note(evt_bytes, r_value):
    """Decode a note event with a given constant R."""
    val = int.from_bytes(evt_bytes, "big")
    derot = rot_right(val, r_value)
    f0 = extract_9bit(derot, 0)
    f1 = extract_9bit(derot, 1)
    f2 = extract_9bit(derot, 2)
    f3 = extract_9bit(derot, 3)
    f4 = extract_9bit(derot, 4)
    f5 = extract_9bit(derot, 5)
    remainder = derot & 0x3

    note = f0 & 0x7F
    bit8 = (f0 >> 8) & 1
    bit7 = (f0 >> 7) & 1
    vel_code = (bit8 << 3) | (bit7 << 2) | remainder
    velocity = max(1, 127 - vel_code * 8)

    beat = f1 >> 7
    clock = ((f1 & 0x7F) << 2) | (f2 >> 7)
    tick = beat * 480 + clock

    return {
        "note": note, "velocity": velocity, "tick": tick,
        "gate": f5, "f0": f0, "f1": f1, "f2": f2, "f3": f3, "f4": f4, "f5": f5,
        "remainder": remainder, "bit8": bit8, "bit7": bit7
    }


def analyze_track(syx_path, al, label, r_values):
    """Analyze a track with multiple R values."""
    data = get_track(syx_path, al)
    if not data:
        print(f"  {label}: track not found")
        return

    preamble, bars = extract_bars(data)
    enc = classify_encoding(preamble)
    print(f"\n{'='*70}")
    print(f"  {label}: {len(data)}B, preamble={preamble.hex()}, enc={enc}, {len(bars)} bars")
    print(f"{'='*70}")

    for r_val in r_values:
        print(f"\n  --- R={r_val} ---")
        total_notes = 0
        expected_hits = 0
        valid_notes = 0

        for bi, (header, events) in enumerate(bars):
            for ei, evt in enumerate(events):
                d = decode_note(evt, r_val)
                n = d["note"]
                v = d["velocity"]
                nname = GM_DRUMS.get(n, f"n{n}")
                valid = 13 <= n <= 87
                exp = "*" if n in EXPECTED else " "
                if valid:
                    valid_notes += 1
                if n in EXPECTED:
                    expected_hits += 1
                total_notes += 1
                print(f"    bar{bi} e{ei}: {evt.hex()} → n={n:3d} ({nname:>10s}) "
                      f"v={v:3d} t={d['tick']:4d} g={d['gate']:3d} "
                      f"f0={d['f0']:03x} [{exp}]")

        print(f"    TOTAL: {total_notes} events, {expected_hits} expected hits, "
              f"{valid_notes} valid notes")


def compare_raw_bytes(syx1, al1, label1, syx2, al2, label2):
    """Compare raw bytes structure between two tracks."""
    d1 = get_track(syx1, al1)
    d2 = get_track(syx2, al2)

    print(f"\n{'='*70}")
    print(f"  RAW COMPARISON: {label1} vs {label2}")
    print(f"{'='*70}")
    print(f"  {label1}: {len(d1)} bytes")
    print(f"  {label2}: {len(d2)} bytes")

    # Preamble comparison
    print(f"\n  Preamble area (first 32 bytes):")
    for i in range(0, min(32, min(len(d1), len(d2))), 4):
        h1 = d1[i:i+4].hex() if i+4 <= len(d1) else "----"
        h2 = d2[i:i+4].hex() if i+4 <= len(d2) else "----"
        match = "==" if h1 == h2 else "!="
        print(f"    {i:3d}: {h1}  {match}  {h2}")

    # Delimiter comparison
    for label, d in [(label1, d1), (label2, d2)]:
        event_data = d[28:]
        delims = [(i, b) for i, b in enumerate(event_data) if b in (0xDC, 0x9E)]
        seg_sizes = []
        prev = 0
        for pos, _ in delims:
            seg_sizes.append(pos - prev)
            prev = pos + 1
        seg_sizes.append(len(event_data) - prev)
        print(f"\n  {label} segments: {len(delims)} delimiters")
        print(f"    Segment sizes: {seg_sizes}")
        print(f"    Delimiter offsets: {[p for p, _ in delims]}")


def try_segment0_as_preamble():
    """Test: what if segment 0 (15 bytes before first DC) is extended preamble?"""
    data = get_track("midi_tools/captured/user_style_live.syx", 0)
    event_data = data[28:]

    print(f"\n{'='*70}")
    print(f"  TEST: Segment 0 as extended preamble")
    print(f"{'='*70}")

    # First DC at offset 14 in event_data → first 14 bytes + DC
    first_seg = event_data[:14]
    print(f"  First 14 bytes: {first_seg.hex()}")
    print(f"  Interpretation as extended preamble:")

    # Decode as 9-bit fields
    val = int.from_bytes(first_seg[:13], "big")
    fields = [(val >> (104 - (i+1)*9)) & 0x1FF for i in range(11)]
    print(f"  9-bit fields: {[f'0x{f:03x}' for f in fields]}")
    print(f"  As notes (lo7): {[f & 0x7F for f in fields]}")

    # Also: what if the extended preamble tells us the R value or event count?
    print(f"\n  Raw bytes analysis:")
    for i, b in enumerate(first_seg):
        print(f"    byte {i:2d}: 0x{b:02x} = {b:3d}")


def main():
    user_syx = "midi_tools/captured/user_style_live.syx"
    sgt_syx = "midi_tools/captured/ground_truth_style.syx"

    # 1. Compare structure
    compare_raw_bytes(user_syx, 0, "USER-RHY1", sgt_syx, 0, "SGT-RHY1")

    # 2. Test segment 0 as preamble
    try_segment0_as_preamble()

    # 3. Analyze USER RHY1 with R=18 vs R=9
    analyze_track(user_syx, 0, "USER-RHY1", [18, 9])

    # 4. Analyze SGT RHY1 with R=9 and R=18 for comparison
    analyze_track(sgt_syx, 0, "SGT-RHY1", [9, 18])


if __name__ == "__main__":
    main()
