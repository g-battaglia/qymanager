#!/usr/bin/env python3
"""Investigate multi-note hypothesis for RHY1 drum events.

8-beat drum pattern has 12 hits per bar but only 4 events per segment.
Hypothesis: each event encodes multiple notes in different fields.

Also: brute-force find R values that map each event to expected notes.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qymanager.formats.qy70.sysex_parser import SysExParser
from midi_tools.event_decoder import rot_right, extract_9bit

EXPECTED = {36, 38, 42}  # Kick1, Snare1, HHclose


def get_track(syx_path, al_target):
    parser = SysExParser()
    messages = parser.parse_file(syx_path)
    data = b''
    for m in messages:
        if m.is_style_data and m.decoded_data and m.address_low == al_target:
            data += m.decoded_data
    return data


def get_segments(data):
    """Parse segments from track data."""
    event_data = data[28:]
    delim_pos = [i for i, b in enumerate(event_data) if b in (0xDC, 0x9E)]
    boundaries = [0] + [p + 1 for p in delim_pos] + [len(event_data)]

    segments = []
    for si in range(len(boundaries) - 1):
        start = boundaries[si]
        end = boundaries[si + 1]
        seg = event_data[start:end]
        if len(seg) >= 20:  # At least header + 1 event
            header = seg[:13]
            events = []
            for i in range((len(seg) - 13) // 7):
                evt = seg[13 + i*7:13 + (i+1)*7]
                if len(evt) == 7:
                    events.append(evt)
            segments.append((header, events))
    return segments


def full_field_dump(evt_bytes, r_value):
    """Extract all 6 fields and remainder at given R."""
    val = int.from_bytes(evt_bytes, "big")
    derot = rot_right(val, r_value)
    fields = [extract_9bit(derot, i) for i in range(6)]
    rem = derot & 0x3
    return fields, rem


def brute_force_expected(evt_bytes, expected_notes):
    """Find all R values where ANY 9-bit field contains an expected note."""
    val = int.from_bytes(evt_bytes, "big")
    results = {}  # R → list of (field_idx, note)

    for r in range(56):
        derot = rot_right(val, r)
        hits = []
        for fi in range(6):
            f = extract_9bit(derot, fi)
            lo7 = f & 0x7F
            if lo7 in expected_notes:
                hits.append((fi, lo7, f))
        if hits:
            results[r] = hits

    return results


def main():
    data = get_track("midi_tools/captured/user_style_live.syx", 0)
    if not data:
        print("RHY1 not found")
        return

    segments = get_segments(data)
    print(f"Segments: {len(segments)}")

    # Focus on bars 0,1,3,4 (main pattern bars where e0=HH42 at R=9)
    main_bars = [0, 1, 3, 4]  # bars (segment indices after skipping seg0)

    print(f"\n{'='*70}")
    print(f"  FIELD DUMP at R=9 (main bars)")
    print(f"{'='*70}")

    for bi in main_bars:
        if bi >= len(segments):
            continue
        header, events = segments[bi]
        print(f"\n  Bar {bi} ({len(events)} events)")
        for ei, evt in enumerate(events):
            fields, rem = full_field_dump(evt, 9)
            lo7s = [f & 0x7F for f in fields]
            hits = [f"F{i}={lo7s[i]}{'*' if lo7s[i] in EXPECTED else ''}"
                    for i in range(6)]
            print(f"    e{ei}: {evt.hex()} → {' '.join(hits)} rem={rem}")
            print(f"         raw: F0=0x{fields[0]:03x} F1=0x{fields[1]:03x} "
                  f"F2=0x{fields[2]:03x} F3=0x{fields[3]:03x} "
                  f"F4=0x{fields[4]:03x} F5=0x{fields[5]:03x}")

    # Brute force: for each event in main bars, find R values that hit expected notes
    print(f"\n{'='*70}")
    print(f"  BRUTE FORCE: R values that produce expected notes (36,38,42)")
    print(f"{'='*70}")

    for bi in main_bars:
        if bi >= len(segments):
            continue
        header, events = segments[bi]
        print(f"\n  Bar {bi}:")
        for ei, evt in enumerate(events):
            hits = brute_force_expected(evt, EXPECTED)
            if hits:
                best = sorted(hits.items(), key=lambda x: len(x[1]), reverse=True)
                for r, field_hits in best[:5]:
                    desc = ", ".join(f"F{fi}={n}(0x{f:03x})" for fi, n, f in field_hits)
                    print(f"    e{ei}: R={r:2d} → {desc}")
            else:
                print(f"    e{ei}: {evt.hex()} → NO expected notes at any R!")

    # Cross-bar consistency: find R values that work across ALL bars
    print(f"\n{'='*70}")
    print(f"  CROSS-BAR CONSISTENCY: R values per event position")
    print(f"{'='*70}")

    for ei in range(4):  # 4 events per bar
        print(f"\n  Event position {ei}:")
        r_counts = {}
        for bi in main_bars:
            if bi >= len(segments):
                continue
            _, events = segments[bi]
            if ei >= len(events):
                continue
            evt = events[ei]
            hits = brute_force_expected(evt, EXPECTED)
            for r in hits:
                if r not in r_counts:
                    r_counts[r] = []
                r_counts[r].append((bi, hits[r]))

        # Find R values that work for ALL main bars at this position
        for r in sorted(r_counts):
            if len(r_counts[r]) >= 3:  # At least 3/4 bars
                bars_str = ", ".join(
                    f"bar{bi}:{','.join(f'F{fi}={n}' for fi,n,f in fh)}"
                    for bi, fh in r_counts[r]
                )
                print(f"    R={r:2d} ({len(r_counts[r])}/4 bars): {bars_str}")

    # Additional: check if repeated byte patterns exist
    print(f"\n{'='*70}")
    print(f"  REPEATED BYTE PATTERNS")
    print(f"{'='*70}")

    all_events = []
    for bi, (_, events) in enumerate(segments):
        for ei, evt in enumerate(events):
            all_events.append((bi, ei, evt.hex()))

    seen = {}
    for bi, ei, h in all_events:
        if h not in seen:
            seen[h] = []
        seen[h].append((bi, ei))

    for h, positions in sorted(seen.items(), key=lambda x: -len(x[1])):
        if len(positions) > 1:
            pos_str = ", ".join(f"bar{bi}e{ei}" for bi, ei in positions)
            print(f"  {h} at: {pos_str}")


if __name__ == "__main__":
    main()
