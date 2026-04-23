#!/usr/bin/env python3
"""
Summer GT bit attribution analyzer.

For each of 20 events, decompose the 56-bit value using multiple schemes
and correlate against known strike data.

Schemes tested:
  A) Raw byte invariants per beat-position
  B) XOR across bars at same beat (reveals content bits)
  C) 56-bit → 6×9bit + 2bit cumulative rotation (R=9×(i+1))
  D) Per-beat rotation (R=0/2/1/0 per Session 29b)
  E) 44-bit "pattern ID" invariant + 12-bit variable
  F) Strike delta correlation: velocity delta vs byte delta

The aim is to identify a bit layout where each bit has a deterministic
function, compatible with all 20 events + 61 strikes.
"""

import json
from collections import defaultdict
from itertools import combinations
from pathlib import Path

GT_PATH = Path(__file__).parent / "captured" / "summer_ground_truth.json"


def load_events():
    """Return list of dicts with bar, beat, bytes(7), strikes."""
    data = json.loads(GT_PATH.read_text())
    events = []
    for e in data["events"]:
        events.append({
            "bar": e["bar"],
            "beat": e["beat"],
            "bytes": bytes(e["event_decimal"]),
            "hex": e["event_hex"],
            "strikes": e["expected_strikes"],
        })
    return events


def bit_count(x: int) -> int:
    return bin(x).count("1")


def byte_xor(a: bytes, b: bytes) -> bytes:
    return bytes(x ^ y for x, y in zip(a, b))


def rotate_right(val: int, r: int, width: int = 56) -> int:
    r %= width
    mask = (1 << width) - 1
    return ((val >> r) | (val << (width - r))) & mask


def rotate_left(val: int, r: int, width: int = 56) -> int:
    return rotate_right(val, (-r) % width, width)


def int_from_bytes(b: bytes) -> int:
    return int.from_bytes(b, "big")


def int_to_bytes(v: int, n: int = 7) -> bytes:
    return v.to_bytes(n, "big")


def extract_9bit_fields(val: int):
    """Return 6 9-bit fields + 2-bit remainder for 56-bit value."""
    fields = []
    for i in range(6):
        shift = 2 + (5 - i) * 9
        fields.append((val >> shift) & 0x1FF)
    rem = val & 0x3
    return fields, rem


def byte_invariants_by_beat(events):
    """For each beat position, which byte positions are invariant across bars 1,2,4,5 (excluding bar 3 FILL)."""
    print("\n=== A) Byte-level invariants per beat (excl bar 3) ===")
    by_beat = defaultdict(list)
    for e in events:
        by_beat[e["beat"]].append(e)

    for beat, evs in sorted(by_beat.items()):
        main_evs = [e for e in evs if e["bar"] != 3]  # exclude FILL
        fill_evs = [e for e in evs if e["bar"] == 3]
        if len(main_evs) < 2:
            continue
        invariant_bytes = []
        for pos in range(7):
            vals = {e["bytes"][pos] for e in main_evs}
            if len(vals) == 1:
                invariant_bytes.append((pos, next(iter(vals))))
        inv_str = " ".join(f"B{p}={v:02x}" for p, v in invariant_bytes)
        print(f"  Beat {beat}: {len(invariant_bytes)}/7 invariant bytes in MAIN bars: {inv_str}")
        if fill_evs:
            fill_bytes = fill_evs[0]["bytes"].hex()
            print(f"           FILL bar 3: {fill_bytes}")


def bit_invariants_by_beat(events):
    """Bit-level invariant analysis — how many of the 56 bits are constant across MAIN bars per beat."""
    print("\n=== B) Bit-level invariants per beat (excl bar 3) ===")
    by_beat = defaultdict(list)
    for e in events:
        by_beat[e["beat"]].append(e)

    for beat, evs in sorted(by_beat.items()):
        main_evs = [e for e in evs if e["bar"] != 3]
        if len(main_evs) < 2:
            continue
        # For each bit, check if constant across all MAIN events
        const_bits = 0
        bit_mask = 0
        for bit in range(56):
            vals = {(int_from_bytes(e["bytes"]) >> bit) & 1 for e in main_evs}
            if len(vals) == 1:
                const_bits += 1
                bit_mask |= (1 << bit)
        print(f"  Beat {beat}: {const_bits}/56 bits constant, mask=0x{bit_mask:014x}")


def pattern_id_vs_strike_pattern(events):
    """Group events by strike-pattern (note+subdivision tuple, ignore velocity)
       and check invariant bits within each group."""
    print("\n=== C) Strike-pattern grouping + bit invariants ===")

    def strike_sig(strikes):
        return tuple((s["note"], s["subdivision_8th"]) for s in strikes)

    groups = defaultdict(list)
    for e in events:
        groups[strike_sig(e["strikes"])].append(e)

    for sig, evs in sorted(groups.items(), key=lambda x: -len(x[1])):
        bars = [e["bar"] for e in evs]
        beats = {e["beat"] for e in evs}
        print(f"\n  Strike pattern {sig}: {len(evs)} events, bars={bars}, beats={sorted(beats)}")
        # Invariant bits across events with SAME strike pattern
        vals = [int_from_bytes(e["bytes"]) for e in evs]
        const_mask = 0
        for bit in range(56):
            if len({(v >> bit) & 1 for v in vals}) == 1:
                const_mask |= (1 << bit)
        print(f"    Invariant mask: 0x{const_mask:014x} ({bin(const_mask).count('1')}/56 bits)")
        # Which bytes vary?
        var_bytes = set()
        for pos in range(7):
            pos_vals = {(v >> (8 * (6 - pos))) & 0xFF for v in vals}
            if len(pos_vals) > 1:
                var_bytes.add(pos)
        print(f"    Variable byte positions: {sorted(var_bytes)}")


def rotation_test_per_beat(events):
    """Apply per-beat rotation (R=0/2/1/0 or similar) and check if 9-bit fields align."""
    print("\n=== D) Per-beat rotation test — look for note number in F0 ===")
    # Session 29b: beat 0/1/2/3 → R=0/2/1/0 (left-rotate before reading)
    # Our beat values in JSON are 1-indexed (1,2,3,4), so map beat→R
    R_table = {1: 0, 2: 2, 3: 1, 4: 0}

    for e in events:
        R = R_table.get(e["beat"], 0)
        raw = int_from_bytes(e["bytes"])
        rot = rotate_left(raw, R * 8)  # try bit or byte rotation?
        fields, rem = extract_9bit_fields(rot)
        notes_present = {s["note"] for s in e["strikes"]}
        f0_note = fields[0] & 0x7F
        mark = "✓" if f0_note in notes_present else " "
        print(f"  Bar{e['bar']} Beat{e['beat']} R={R:2d} raw={e['hex']} "
              f"F=[{','.join(f'{f:03x}' for f in fields)}] rem={rem:x} "
              f"F0_note={f0_note:3d} strikes={notes_present} {mark}")


def raw_bit_rotation_per_beat(events):
    """Test per-beat BIT rotation (not byte) for each R in 0-55."""
    print("\n=== D2) Per-beat bit rotation exhaustive sweep ===")
    by_beat = defaultdict(list)
    for e in events:
        by_beat[e["beat"]].append(e)

    for beat, evs in sorted(by_beat.items()):
        main_evs = [e for e in evs if e["bar"] != 3]
        main_vals = [int_from_bytes(e["bytes"]) for e in main_evs]
        # For each R, count invariant bits after left-rotation
        best = []
        for R in range(56):
            rotated = [rotate_left(v, R) for v in main_vals]
            const_bits = sum(1 for b in range(56)
                             if len({(v >> b) & 1 for v in rotated}) == 1)
            best.append((const_bits, R))
        best.sort(reverse=True)
        top3 = best[:3]
        print(f"  Beat {beat}: top3 R by invariant bits: {[(c, R) for c, R in top3]}")


def cross_event_within_bar(events):
    """Within a single bar, how similar are consecutive beats' events?"""
    print("\n=== E) Consecutive beats within same bar ===")
    by_bar = defaultdict(list)
    for e in events:
        by_bar[e["bar"]].append(e)
    for bar, evs in sorted(by_bar.items()):
        evs.sort(key=lambda x: x["beat"])
        for i in range(len(evs) - 1):
            a, b = evs[i], evs[i + 1]
            xor = byte_xor(a["bytes"], b["bytes"])
            bits_diff = sum(bit_count(x) for x in xor)
            print(f"  Bar{bar} beat{a['beat']}→beat{b['beat']}: XOR={xor.hex()} "
                  f"bits_diff={bits_diff}")


def beat_templates_map(events):
    """Per beat, extract the invariant template + list variable byte patterns."""
    print("\n=== F) Beat template + variable content summary ===")
    by_beat = defaultdict(list)
    for e in events:
        by_beat[e["beat"]].append(e)

    for beat, evs in sorted(by_beat.items()):
        main_evs = [e for e in evs if e["bar"] != 3]
        if not main_evs:
            continue
        # Template = byte-positions invariant across MAIN bars
        template_bytes = {}
        for pos in range(7):
            vals = {e["bytes"][pos] for e in main_evs}
            if len(vals) == 1:
                template_bytes[pos] = next(iter(vals))
        print(f"\n  Beat {beat} template: {template_bytes}")
        for e in evs:
            # Show variable bytes only
            var = []
            for pos in range(7):
                if pos not in template_bytes or e["bar"] == 3:
                    var.append(f"B{pos}={e['bytes'][pos]:02x}")
            strikes_str = ", ".join(
                f"n{s['note']}v{s['velocity']}@{s['subdivision_8th']}"
                for s in e["strikes"]
            )
            print(f"    Bar{e['bar']}: var=[{' '.join(var)}]  strikes={strikes_str}")


def main():
    events = load_events()
    print(f"Loaded {len(events)} events from {GT_PATH.name}")

    byte_invariants_by_beat(events)
    bit_invariants_by_beat(events)
    pattern_id_vs_strike_pattern(events)
    rotation_test_per_beat(events)
    raw_bit_rotation_per_beat(events)
    cross_event_within_bar(events)
    beat_templates_map(events)


if __name__ == "__main__":
    main()
