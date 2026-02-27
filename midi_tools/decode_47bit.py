#!/usr/bin/env python3
"""
Decode the 47-bit event structure in QY70 CHD1 (Chord 1) track.

Based on bitstream analysis findings:
  - CHD1 (AL=0x04, Section 0) has strongest autocorrelation at lag 47 bits (R=0.50)
  - Harmonics at 94, 141, 187, 242 bits confirm 47-bit periodicity
  - 47 is prime — cannot be split into equal-size sub-fields
  - 7-bit field widths are likely (Yamaha 7-bit codec philosophy)
  - 47 = various combinations of 7-bit and smaller fields
  - CHD1 uses voice 0x00 0x00 = Acoustic Grand Piano

This script systematically tries all plausible field decompositions and scores
them by how "musical" the extracted values look.
"""

import sys
from pathlib import Path
from collections import Counter
from typing import Dict, List, Tuple, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))
from qymanager.utils.yamaha_7bit import decode_7bit


# ── Constants ────────────────────────────────────────────────────────────────

SYX_FILE = Path(__file__).parent.parent / "tests" / "fixtures" / "QY70_SGT.syx"

SYSEX_START = 0xF0
SYSEX_END = 0xF7
YAMAHA_ID = 0x43
QY70_MODEL = 0x5F

SECTION_NAMES = ["Intro", "MainA", "MainB", "FillAB", "FillBA", "Ending"]
TRACK_LABELS = {
    0: "D1/RHY1",
    1: "D2/RHY2",
    2: "PC/PERC",
    3: "BA/BASS",
    4: "C1/CHD1",
    5: "C2/CHD2",
    6: "C3/PAD",
    7: "C4/PHR",
}

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
CHORD_TEMPLATES = {
    frozenset({0, 4, 7}): "major",
    frozenset({0, 3, 7}): "minor",
    frozenset({0, 4, 7, 11}): "maj7",
    frozenset({0, 3, 7, 10}): "min7",
    frozenset({0, 4, 7, 10}): "dom7",
    frozenset({0, 4, 7, 9}): "6th",
    frozenset({0, 3, 7, 9}): "min6",
    frozenset({0, 4, 8}): "aug",
    frozenset({0, 3, 6}): "dim",
    frozenset({0, 3, 6, 9}): "dim7",
    frozenset({0, 5, 7}): "sus4",
    frozenset({0, 2, 7}): "sus2",
    frozenset({0, 4}): "3rd",
    frozenset({0, 7}): "5th",
    frozenset({0, 3}): "min3",
}


def midi_note_name(n: int) -> str:
    if n < 0 or n > 127:
        return f"?{n}"
    octave = (n // 12) - 1
    return f"{NOTE_NAMES[n % 12]}{octave}"


def identify_chord(notes: List[int]) -> str:
    """Try to identify chord from a list of MIDI note values."""
    if not notes:
        return ""
    pcs = frozenset(n % 12 for n in notes)
    # Try each note as root
    for root in sorted(pcs):
        transposed = frozenset((pc - root) % 12 for pc in pcs)
        if transposed in CHORD_TEMPLATES:
            return f"{NOTE_NAMES[root]}{CHORD_TEMPLATES[transposed]}"
    return ""


# ── SysEx Parsing ────────────────────────────────────────────────────────────


def split_sysex(data: bytes) -> List[bytes]:
    msgs = []
    start = None
    for i, b in enumerate(data):
        if b == SYSEX_START:
            start = i
        elif b == SYSEX_END and start is not None:
            msgs.append(data[start : i + 1])
            start = None
    return msgs


def parse_bulk_dumps(raw: bytes) -> Dict[int, bytearray]:
    msgs = split_sysex(raw)
    by_al: Dict[int, bytearray] = {}
    for msg in msgs:
        if len(msg) < 11:
            continue
        if msg[1] != YAMAHA_ID or msg[3] != QY70_MODEL:
            continue
        if (msg[2] & 0xF0) != 0x00:
            continue
        ah, am, al = msg[6], msg[7], msg[8]
        if ah != 0x02 or am != 0x7E:
            continue
        payload = msg[9:-2]
        decoded = decode_7bit(payload)
        if al not in by_al:
            by_al[al] = bytearray()
        by_al[al].extend(decoded)
    return by_al


# ── Bitstream Utilities ─────────────────────────────────────────────────────


def bytes_to_bits(data: bytes) -> List[int]:
    bits = []
    for byte in data:
        for i in range(7, -1, -1):
            bits.append((byte >> i) & 1)
    return bits


def bits_to_str(bits: List[int]) -> str:
    return "".join(str(b) for b in bits)


def bits_to_int(bits: List[int]) -> int:
    val = 0
    for b in bits:
        val = (val << 1) | b
    return val


def split_by_delimiter(data: bytes, delim: int = 0xDC) -> List[bytes]:
    work = data.rstrip(b"\x00")
    if not work:
        return []
    parts = []
    current = bytearray()
    for b in work:
        if b == delim:
            parts.append(bytes(current))
            current = bytearray()
        else:
            current.append(b)
    if current:
        parts.append(bytes(current))
    return parts


def extract_fields(bits: List[int], widths: List[int]) -> List[int]:
    """Extract field values from bit list according to width specification."""
    values = []
    pos = 0
    for w in widths:
        if pos + w > len(bits):
            values.append(bits_to_int(bits[pos:]))
            break
        values.append(bits_to_int(bits[pos : pos + w]))
        pos += w
    return values


def autocorrelation_at_lag(bits: List[int], lag: int) -> float:
    """Compute autocorrelation R at a specific lag."""
    n = len(bits)
    if lag >= n:
        return 0.0
    signal = [2 * b - 1 for b in bits]
    mean = sum(signal) / n
    variance = sum((s - mean) ** 2 for s in signal) / n
    if variance < 1e-10:
        return 0.0
    cov = sum((signal[i] - mean) * (signal[i + lag] - mean) for i in range(n - lag))
    cov /= n - lag
    return cov / variance


# ── Scoring Engine ──────────────────────────────────────────────────────────


def score_decomposition(events_fields: List[List[int]], widths: List[int]) -> dict:
    """Score a field decomposition based on how musical the values look."""
    n_events = len(events_fields)
    n_fields = len(widths)
    if n_events == 0:
        return {"total": 0, "field_analysis": []}

    field_analysis = []

    for fi in range(n_fields):
        w = widths[fi]
        max_val = (1 << w) - 1
        vals = [ev[fi] for ev in events_fields if fi < len(ev)]
        if not vals:
            field_analysis.append({"width": w, "score": 0, "types": [], "values": []})
            continue

        analysis = {
            "width": w,
            "max_possible": max_val,
            "values": vals,
            "min": min(vals),
            "max": max(vals),
            "mean": sum(vals) / len(vals),
            "unique": len(set(vals)),
        }

        field_score = 0
        field_types = []

        # Check for MIDI note values (36-84 for piano, broader 24-96)
        in_piano = sum(1 for v in vals if 36 <= v <= 84)
        in_broad = sum(1 for v in vals if 24 <= v <= 96)
        if w >= 7 and in_piano > n_events * 0.5:
            field_score += 30 + in_piano * 3
            field_types.append(f"NOTE_PIANO({in_piano}/{len(vals)})")
        elif w >= 7 and in_broad > n_events * 0.4:
            field_score += 15 + in_broad * 2
            field_types.append(f"NOTE_BROAD({in_broad}/{len(vals)})")

        # Check for velocity values (typical: 40-127)
        in_vel = sum(1 for v in vals if 40 <= v <= 127)
        if w >= 7 and in_vel > n_events * 0.6:
            field_score += 10 + in_vel * 2
            field_types.append(f"VELOCITY({in_vel}/{len(vals)})")

        # Check for monotonically increasing (timing/position)
        strictly_mono = all(vals[i] < vals[i + 1] for i in range(len(vals) - 1))
        monotonic = all(vals[i] <= vals[i + 1] for i in range(len(vals) - 1))
        if strictly_mono and len(vals) > 2:
            field_score += 40
            field_types.append("MONOTONIC_STRICT")
            diffs = [vals[i + 1] - vals[i] for i in range(len(vals) - 1)]
            unique_diffs = len(set(diffs))
            if unique_diffs <= 3:
                field_score += 20
                field_types.append(f"REGULAR_STEP({sorted(set(diffs))})")
        elif monotonic and len(vals) > 2:
            field_score += 20
            field_types.append("MONOTONIC_WEAK")

        # Constant or near-constant
        if analysis["unique"] == 1:
            field_score += 10
            field_types.append(f"CONSTANT({vals[0]})")
        elif analysis["unique"] <= 3 and len(vals) > 3:
            field_score += 6
            field_types.append(f"FEW_VALUES({sorted(set(vals))})")

        # Gate/duration: values 1-127 in 7-bit field (non-zero MIDI range)
        if w >= 7:
            in_gate = sum(1 for v in vals if 1 <= v <= 127)
            if in_gate == len(vals):
                field_score += 5
                field_types.append(f"GATE_RANGE(1-127)")

        # Small control field (1-5 bits)
        if w <= 5:
            field_score += 3
            field_types.append(f"CTRL({w}b:0-{max_val})")

        # Penalty for all-zero in wide fields
        if analysis["unique"] == 1 and vals[0] == 0 and w >= 7:
            field_score -= 5
            field_types.append("ALL_ZERO_PENALTY")

        analysis["score"] = field_score
        analysis["types"] = field_types
        field_analysis.append(analysis)

    total_score = sum(a.get("score", 0) for a in field_analysis)
    return {"total": total_score, "field_analysis": field_analysis, "widths": widths}


# ── Main Analysis ────────────────────────────────────────────────────────────


def main():
    print("=" * 95)
    print("QY70 CHD1 TRACK — 47-BIT EVENT STRUCTURE DECODER")
    print(f"File: {SYX_FILE}")
    print("=" * 95)

    if not SYX_FILE.exists():
        print(f"ERROR: File not found: {SYX_FILE}")
        sys.exit(1)

    raw = SYX_FILE.read_bytes()
    by_al = parse_bulk_dumps(raw)

    print(f"\nAvailable ALs: {sorted([f'0x{a:02X}' for a in by_al.keys()])}")

    # ══════════════════════════════════════════════════════════════════════
    # 1. LOAD CHD1 TRACK DATA
    # ══════════════════════════════════════════════════════════════════════
    print(f"\n{'=' * 95}")
    print("1. LOAD AND EXTRACT CHD1 (AL=0x04, Section 0)")
    print(f"{'=' * 95}")

    chd1_al = 0x04
    if chd1_al not in by_al:
        print(f"ERROR: AL=0x{chd1_al:02X} not found!")
        print(f"Trying AL=0x03 (alternate CHD1 mapping)...")
        chd1_al = 0x03
        if chd1_al not in by_al:
            print("Also not found. Dumping available tracks for Section 0:")
            for al in sorted(by_al.keys()):
                if al < 8:
                    data = by_al[al]
                    lbl = TRACK_LABELS.get(al, f"Track{al}")
                    print(f"  AL=0x{al:02X} ({lbl}): {len(data)} bytes")
            sys.exit(1)

    chd1_data = bytes(by_al[chd1_al])
    print(f"  CHD1 at AL=0x{chd1_al:02X}: {len(chd1_data)} total decoded bytes")

    # Show header
    header = chd1_data[:24]
    print(f"\n  Track header (24 bytes):")
    print(f"    HEX: {' '.join(f'{b:02X}' for b in header)}")
    print(f"    Voice (14-15): 0x{header[14]:02X} 0x{header[15]:02X}")
    print(f"    Range (16-17): 0x{header[16]:02X} 0x{header[17]:02X}")
    print(f"    Flag  (21):    0x{header[21]:02X}")
    print(f"    Pan   (22):    0x{header[22]:02X} ({header[22]})")

    events = chd1_data[24:]
    print(f"\n  Event data: {len(events)} bytes = {len(events) * 8} bits")
    print(f"    First 64 bytes:")
    for off in range(0, min(64, len(events)), 16):
        chunk = events[off : off + 16]
        hex_str = " ".join(f"{b:02X}" for b in chunk)
        print(f"      +{off:3d}: {hex_str}")

    # ══════════════════════════════════════════════════════════════════════
    # 2. SPLIT INTO BARS, IDENTIFY STRUCTURE
    # ══════════════════════════════════════════════════════════════════════
    print(f"\n{'=' * 95}")
    print("2. BAR STRUCTURE ANALYSIS")
    print(f"{'=' * 95}")

    bars = split_by_delimiter(events, 0xDC)
    print(f"  Parts (split by 0xDC): {len(bars)}")

    dc_positions = [i for i, b in enumerate(events) if b == 0xDC]
    print(f"  DC positions in raw event data: {dc_positions}")

    for bi, bar in enumerate(bars):
        bar_bits = len(bar) * 8
        fit_47 = bar_bits / 47 if bar_bits >= 47 else 0
        hex_preview = " ".join(f"{b:02X}" for b in bar[:20])
        suffix = "..." if len(bar) > 20 else ""
        print(
            f"    Part[{bi}]: {len(bar):3d} bytes = {bar_bits:4d} bits"
            f"  (47-bit: {fit_47:.2f} events)"
            f"  [{hex_preview}{suffix}]"
        )

    # Identify preamble vs music bars
    # Small initial parts are likely preamble/sub-header
    preamble_parts = []
    music_parts = []
    for bi, bar in enumerate(bars):
        if len(bar) < 10:
            preamble_parts.append(bi)
        else:
            music_parts.append(bi)

    print(f"\n  Preamble parts (< 10 bytes): {preamble_parts}")
    print(f"  Music bar candidates (>= 10 bytes): {music_parts}")

    if preamble_parts:
        print(f"\n  Preamble data detail:")
        for pi in preamble_parts:
            p = bars[pi]
            print(f"    Part[{pi}]: {' '.join(f'{b:02X}' for b in p)}  = {[b for b in p]}")

    # Find largest music bar
    if not music_parts:
        print("ERROR: No music bars found!")
        sys.exit(1)

    largest_idx = max(music_parts, key=lambda i: len(bars[i]))
    largest_bar = bars[largest_idx]
    largest_bits = len(largest_bar) * 8

    print(f"\n  LARGEST MUSIC BAR: Part[{largest_idx}]")
    print(f"    {len(largest_bar)} bytes = {largest_bits} bits")
    print(f"    47-bit fit: {largest_bits / 47:.4f} events")
    print(f"    Remainder at 47: {largest_bits % 47} bits")
    print(f"    Full hex dump:")
    for offset in range(0, len(largest_bar), 16):
        chunk = largest_bar[offset : offset + 16]
        hex_str = " ".join(f"{b:02X}" for b in chunk)
        bin_chunk = " ".join(f"{b:08b}" for b in chunk[:4])
        print(f"      {offset:04X}: {hex_str}")

    # Check identical bars
    print(f"\n  Bar comparison:")
    for i in music_parts:
        for j in music_parts:
            if j <= i:
                continue
            if bars[i] == bars[j]:
                print(f"    Part[{i}] == Part[{j}] (IDENTICAL)")
            elif len(bars[i]) == len(bars[j]):
                diffs = sum(1 for a, b in zip(bars[i], bars[j]) if a != b)
                print(f"    Part[{i}] vs Part[{j}]: same size, {diffs} byte diffs")

    # ══════════════════════════════════════════════════════════════════════
    # 3. EXTRACT 47-BIT EVENTS
    # ══════════════════════════════════════════════════════════════════════
    print(f"\n{'=' * 95}")
    print("3. 47-BIT EVENT EXTRACTION")
    print(f"{'=' * 95}")

    bar_bits_list = bytes_to_bits(largest_bar)
    n_bits = len(bar_bits_list)

    print(f"\n  Working bar: {n_bits} bits")
    print(f"  47 × 6 = 282 bits  (remainder: {n_bits - 282})")
    print(f"  47 × 7 = 329 bits  (shortfall: {329 - n_bits})")
    print(f"  47 × 8 = 376 bits  (shortfall: {376 - n_bits})")

    n_events = n_bits // 47
    remainder = n_bits % 47
    print(f"\n  Extracting {n_events} complete 47-bit events (remainder: {remainder} bits)")

    events_47 = []
    for ei in range(n_events):
        start = ei * 47
        end = start + 47
        ev_bits = bar_bits_list[start:end]
        events_47.append(ev_bits)
        ev_val = bits_to_int(ev_bits)

        # Show with visual grouping in 7-bit chunks for readability
        groups_7 = []
        for g in range(0, 47, 7):
            group = ev_bits[g : g + 7]
            gval = bits_to_int(group)
            groups_7.append(f"{bits_to_str(group)}({gval:3d})")
        group_str = " ".join(groups_7)

        print(f"\n    Event[{ei}] bits[{start:3d}:{end:3d}]:")
        print(f"      Raw:     {bits_to_str(ev_bits)}")
        print(f"      7-bit:   {group_str}")
        print(f"      Hex:     0x{ev_val:012X}")

    if remainder > 0:
        tail = bar_bits_list[n_events * 47 :]
        print(f"\n    Remainder: {bits_to_str(tail)} ({remainder} bits = {bits_to_int(tail)})")

    # ══════════════════════════════════════════════════════════════════════
    # 4. FIELD DECOMPOSITION SEARCH
    # ══════════════════════════════════════════════════════════════════════
    print(f"\n{'=' * 95}")
    print("4. FIELD DECOMPOSITION SEARCH (47 bits → fields)")
    print(f"{'=' * 95}")

    # Define decompositions to test — all must sum to 47
    decompositions_raw = [
        # Primary: 7-bit focused with one 5-bit field in each position
        ("7+7+7+7+7+5+7", [7, 7, 7, 7, 7, 5, 7]),
        ("7+7+7+7+7+7+5", [7, 7, 7, 7, 7, 7, 5]),
        ("5+7+7+7+7+7+7", [5, 7, 7, 7, 7, 7, 7]),
        ("7+5+7+7+7+7+7", [7, 5, 7, 7, 7, 7, 7]),
        ("7+7+5+7+7+7+7", [7, 7, 5, 7, 7, 7, 7]),
        ("7+7+7+5+7+7+7", [7, 7, 7, 5, 7, 7, 7]),
        ("7+7+7+7+5+7+7", [7, 7, 7, 7, 5, 7, 7]),
        # Wider fields
        ("12+7+7+7+7+7", [12, 7, 7, 7, 7, 7]),
        ("7+12+7+7+7+7", [7, 12, 7, 7, 7, 7]),
        ("7+7+12+7+7+7", [7, 7, 12, 7, 7, 7]),
        ("7+7+7+12+7+7", [7, 7, 7, 12, 7, 7]),
        ("7+7+7+7+12+7", [7, 7, 7, 7, 12, 7]),
        ("7+7+7+7+7+12", [7, 7, 7, 7, 7, 12]),
        # 14-bit + rest
        ("14+7+7+7+5+7", [14, 7, 7, 7, 5, 7]),
        ("14+7+7+5+7+7", [14, 7, 7, 5, 7, 7]),
        ("7+14+7+7+5+7", [7, 14, 7, 7, 5, 7]),
        ("7+7+14+7+5+7", [7, 7, 14, 7, 5, 7]),
        # Flag bit decompositions
        ("1+7+7+7+7+7+4+7", [1, 7, 7, 7, 7, 7, 4, 7]),
        ("1+7+7+7+7+4+7+7", [1, 7, 7, 7, 7, 4, 7, 7]),
        ("1+4+7+7+7+7+7+7", [1, 4, 7, 7, 7, 7, 7, 7]),
        ("1+7+4+7+7+7+7+7", [1, 7, 4, 7, 7, 7, 7, 7]),
        ("1+7+7+4+7+7+7+7", [1, 7, 7, 4, 7, 7, 7, 7]),
        # 2-bit + 3-bit combos
        ("2+7+7+7+7+7+3+7", [2, 7, 7, 7, 7, 7, 3, 7]),
        ("3+7+7+7+7+7+2+7", [3, 7, 7, 7, 7, 7, 2, 7]),
        ("7+7+7+7+7+3+2+7", [7, 7, 7, 7, 7, 3, 2, 7]),
        ("7+7+7+7+7+2+3+7", [7, 7, 7, 7, 7, 2, 3, 7]),
        # 4-bit combos
        ("4+7+7+7+7+7+1+7", [4, 7, 7, 7, 7, 7, 1, 7]),
        ("7+7+7+7+4+7+1+7", [7, 7, 7, 7, 4, 7, 1, 7]),
        ("7+4+7+7+7+7+1+7", [7, 4, 7, 7, 7, 7, 1, 7]),
        # 6-bit combos
        ("7+7+7+7+7+1+6+5", [7, 7, 7, 7, 7, 1, 6, 5]),
        ("6+7+7+7+7+7+6", [6, 7, 7, 7, 7, 7, 6]),
        ("7+6+7+7+7+7+6", [7, 6, 7, 7, 7, 7, 6]),
        # All 7-bit + 5-bit at different positions (ensure we have all 7)
        # Also try: timing field might be wider
        ("10+7+7+7+7+2+7", [10, 7, 7, 7, 7, 2, 7]),
        ("7+10+7+7+7+2+7", [7, 10, 7, 7, 7, 2, 7]),
        ("9+7+7+7+7+3+7", [9, 7, 7, 7, 7, 3, 7]),
        ("7+7+7+7+7+5+7", [7, 7, 7, 7, 7, 5, 7]),  # same as first
    ]

    # Deduplicate and validate
    seen = set()
    decompositions = []
    for label, widths in decompositions_raw:
        key = tuple(widths)
        if key not in seen:
            if sum(widths) != 47:
                print(f"  WARNING: {label} sums to {sum(widths)}, not 47 — skipping")
                continue
            seen.add(key)
            decompositions.append((label, widths))

    print(f"  Testing {len(decompositions)} unique field decompositions on {len(events_47)} events")

    # Score each decomposition
    results = []
    for label, widths in decompositions:
        events_fields = [extract_fields(ev, widths) for ev in events_47]
        score_info = score_decomposition(events_fields, widths)
        results.append((label, widths, events_fields, score_info))

    # Sort by total score
    results.sort(key=lambda x: x[3]["total"], reverse=True)

    # Print all results briefly
    print(f"\n  ALL DECOMPOSITIONS RANKED:")
    print(f"  {'Rank':<5} {'Score':<7} {'Layout':<30} {'Key findings'}")
    print(f"  {'─' * 5} {'─' * 7} {'─' * 30} {'─' * 40}")
    for rank, (label, widths, ef, si) in enumerate(results):
        key_types = []
        for fa in si.get("field_analysis", []):
            if isinstance(fa, dict):
                for t in fa.get("types", []):
                    if t not in key_types and "PENALTY" not in t and "CTRL" not in t:
                        key_types.append(t)
        types_str = ", ".join(key_types[:3]) if key_types else "---"
        print(f"  {rank + 1:<5} {si['total']:<7} {label:<30} {types_str}")

    # ══════════════════════════════════════════════════════════════════════
    # 4b. DETAILED TOP 10 RESULTS
    # ══════════════════════════════════════════════════════════════════════
    print(f"\n  {'━' * 90}")
    print(f"  DETAILED TOP 10 DECOMPOSITIONS")
    print(f"  {'━' * 90}")

    for rank, (label, widths, events_fields, score_info) in enumerate(results[:10]):
        print(f"\n  ┌─ #{rank + 1}: {label}  (total score = {score_info['total']})")
        print(f"  │  Field widths: {widths}  (sum = {sum(widths)})")

        # Field-by-field analysis
        for fi, fa in enumerate(score_info.get("field_analysis", [])):
            if not isinstance(fa, dict) or "values" not in fa:
                continue
            types_str = ", ".join(fa.get("types", [])) or "---"
            vals = fa["values"]
            vals_str = ", ".join(str(v) for v in vals)
            print(
                f"  │  F{fi}({fa['width']:2d}b): [{vals_str}]"
                f"  range=[{fa['min']}-{fa['max']}]"
                f"  uniq={fa['unique']}"
                f"  score={fa.get('score', 0):+d}"
            )
            print(f"  │         {types_str}")

            # Musical interpretation for note-like fields
            if any("NOTE" in t for t in fa.get("types", [])):
                names = [midi_note_name(v) for v in vals]
                chord = identify_chord(vals)
                print(f"  │         Notes: {names}{'  → CHORD: ' + chord if chord else ''}")

        # Event table
        field_headers = [f"F{i}({w})" for i, w in enumerate(widths)]
        print(f"  │")
        print(
            f"  │  {'Ev':>4} │ "
            + " │ ".join(f"{h:>{max(6, w + 2)}}" for h, w in zip(field_headers, widths))
        )
        print(f"  │  {'─' * 4}─┼─" + "─┼─".join("─" * max(6, w + 2) for w in widths))
        for ei, fields in enumerate(events_fields):
            vals_str = " │ ".join(f"{v:>{max(6, w + 2)}}" for v, w in zip(fields, widths))
            # Note annotation
            note_parts = []
            for fi, (v, w) in enumerate(zip(fields, widths)):
                if w >= 7 and 24 <= v <= 96:
                    note_parts.append(f"{midi_note_name(v)}")
            note_str = f"  ({', '.join(note_parts)})" if note_parts else ""
            print(f"  │  [{ei}] │ {vals_str}{note_str}")

        print(f"  └{'─' * 89}")

    # ══════════════════════════════════════════════════════════════════════
    # 5. CROSS-BAR VALIDATION
    # ══════════════════════════════════════════════════════════════════════
    print(f"\n{'=' * 95}")
    print("5. CROSS-BAR VALIDATION (top 3 decompositions across all bars)")
    print(f"{'=' * 95}")

    for rank, (label, widths, _, _) in enumerate(results[:3]):
        print(f"\n  ┌─ #{rank + 1}: {label}")

        for bi in music_parts:
            bar = bars[bi]
            bb = bytes_to_bits(bar)
            nb = len(bb)
            n_ev = nb // 47
            rem = nb % 47
            if n_ev == 0:
                continue

            ev_fields_all = [extract_fields(bb[e * 47 : (e + 1) * 47], widths) for e in range(n_ev)]

            # Per-field summary
            summaries = []
            for fi in range(len(widths)):
                vals = [ef[fi] for ef in ev_fields_all if fi < len(ef)]
                if vals:
                    summaries.append(f"F{fi}:[{min(vals)}-{max(vals)}]")

            print(
                f"  │  Part[{bi}]: {len(bar):3d}B = {nb}b → {n_ev} ev (rem={rem})  "
                + " ".join(summaries)
            )

            # Show individual events for this bar
            for ei, fields in enumerate(ev_fields_all[:8]):
                vals_str = " ".join(f"{v:4d}" for v in fields)
                note_parts = [
                    midi_note_name(v)
                    for fi, v in enumerate(fields)
                    if widths[fi] >= 7 and 24 <= v <= 96
                ]
                note_str = f"  ({', '.join(note_parts)})" if note_parts else ""
                print(f"  │    Ev[{ei}]: [{vals_str}]{note_str}")
            if n_ev > 8:
                print(f"  │    ... ({n_ev} total events)")

        print(f"  └{'─' * 89}")

    # ══════════════════════════════════════════════════════════════════════
    # 6. CROSS-SECTION VALIDATION (CHD1 across all 6 sections)
    # ══════════════════════════════════════════════════════════════════════
    print(f"\n{'=' * 95}")
    print("6. CROSS-SECTION VALIDATION (CHD1 across all 6 sections)")
    print(f"{'=' * 95}")

    best_label, best_widths = results[0][0], results[0][1]
    print(f"\n  Using best decomposition: {best_label}")

    # Determine the track offset used (chd1_al was resolved above)
    track_offset = chd1_al  # 0x03 or 0x04

    for sec_idx in range(6):
        al = sec_idx * 8 + track_offset
        if al not in by_al:
            print(f"\n  Section {sec_idx} ({SECTION_NAMES[sec_idx]}): NO DATA (AL=0x{al:02X})")
            continue

        sec_data = bytes(by_al[al])
        if len(sec_data) <= 24:
            print(f"\n  Section {sec_idx} ({SECTION_NAMES[sec_idx]}): NO EVENT DATA")
            continue

        sec_events = sec_data[24:]
        sec_bars = split_by_delimiter(sec_events, 0xDC)
        print(
            f"\n  Section {sec_idx} ({SECTION_NAMES[sec_idx]}): "
            f"{len(sec_events)} event bytes, {len(sec_bars)} parts"
        )

        for bi, bdata in enumerate(sec_bars):
            if len(bdata) < 6:
                print(f"    Part[{bi}]: {len(bdata)}B (preamble/short)")
                continue
            bb = bytes_to_bits(bdata)
            n_ev = len(bb) // 47
            if n_ev == 0:
                print(f"    Part[{bi}]: {len(bdata)}B = {len(bb)}b (< 47 bits)")
                continue

            print(
                f"    Part[{bi}]: {len(bdata)}B = {len(bb)}b → {n_ev} events (rem={len(bb) % 47})"
            )
            for ei in range(min(n_ev, 8)):
                s = ei * 47
                fields = extract_fields(bb[s : s + 47], best_widths)
                vals_str = " ".join(f"{v:4d}" for v in fields)
                note_parts = [
                    midi_note_name(v)
                    for fi, v in enumerate(fields)
                    if best_widths[fi] >= 7 and 24 <= v <= 96
                ]
                note_str = f"  ({', '.join(note_parts)})" if note_parts else ""
                print(f"      Ev[{ei}]: [{vals_str}]{note_str}")
            if n_ev > 8:
                print(f"      ... ({n_ev} total)")

    # ══════════════════════════════════════════════════════════════════════
    # 7. CROSS-TRACK VALIDATION
    # ══════════════════════════════════════════════════════════════════════
    print(f"\n{'=' * 95}")
    print("7. CROSS-TRACK VALIDATION (47-bit decomposition on other tracks)")
    print(f"{'=' * 95}")

    # Test on other chord-type tracks (Section 0)
    other_als = []
    for t in range(8):
        if t != track_offset and t in by_al:
            other_als.append(t)

    for track_al in other_als:
        lbl = TRACK_LABELS.get(track_al, f"Track{track_al}")
        trk_data = bytes(by_al[track_al])
        if len(trk_data) <= 24:
            print(f"\n  {lbl} (AL=0x{track_al:02X}): NO EVENT DATA")
            continue

        trk_events = trk_data[24:]
        trk_bars = split_by_delimiter(trk_events, 0xDC)

        print(
            f"\n  {lbl} (AL=0x{track_al:02X}): {len(trk_events)} event bytes, "
            f"{len(trk_bars)} parts, sizes={[len(b) for b in trk_bars]}"
        )

        # Autocorrelation at lags 47, 56, 48 on concatenated bar data
        concat_bits = []
        for b in trk_bars:
            if len(b) >= 6:
                concat_bits.extend(bytes_to_bits(b))

        if len(concat_bits) > 100:
            print(f"    Autocorrelation on concatenated bar data ({len(concat_bits)} bits):")
            for test_lag in [47, 48, 56, 42, 40, 35, 28, 24, 21, 14]:
                r = autocorrelation_at_lag(concat_bits, test_lag)
                strength = "STRONG" if abs(r) > 0.3 else "MODERATE" if abs(r) > 0.15 else "weak"
                marker = " <<<" if abs(r) > 0.25 else ""
                print(f"      lag={test_lag:3d}: R={r:+.4f} ({strength}){marker}")

        # Apply best 47-bit decomposition on largest bar
        if trk_bars:
            largest_local = max(trk_bars, key=len)
            if len(largest_local) >= 6:
                lb = bytes_to_bits(largest_local)
                n_ev = len(lb) // 47
                rem = len(lb) % 47
                print(
                    f"\n    Largest bar: {len(largest_local)}B = {len(lb)}b → "
                    f"{n_ev} events@47 (rem={rem})"
                )
                if n_ev > 0:
                    print(f"    Applying {best_label}:")
                    for ei in range(min(n_ev, 6)):
                        fields = extract_fields(lb[ei * 47 : (ei + 1) * 47], best_widths)
                        vals_str = " ".join(f"{v:4d}" for v in fields)
                        note_parts = [
                            midi_note_name(v)
                            for fi, v in enumerate(fields)
                            if best_widths[fi] >= 7 and 24 <= v <= 96
                        ]
                        note_str = f"  ({', '.join(note_parts)})" if note_parts else ""
                        print(f"      Ev[{ei}]: [{vals_str}]{note_str}")

        # Special: BASS track — also try 56-bit period
        if track_al == 3 or lbl.endswith("BASS"):
            print(f"\n    BASS: also trying 56-bit period (= 7×8):")
            if trk_bars:
                lb_bass = max(trk_bars, key=len)
                bb_bass = bytes_to_bits(lb_bass)
                n56 = len(bb_bass) // 56
                rem56 = len(bb_bass) % 56
                print(f"    {len(lb_bass)}B = {len(bb_bass)}b → {n56} events@56 (rem={rem56})")
                w56 = [7, 7, 7, 7, 7, 7, 7, 7]
                for ei in range(min(n56, 6)):
                    fields = extract_fields(bb_bass[ei * 56 : (ei + 1) * 56], w56)
                    vals_str = " ".join(f"{v:4d}" for v in fields)
                    notes = [midi_note_name(v) for v in fields if 24 <= v <= 72]
                    note_str = f"  bass notes: {notes}" if notes else ""
                    print(f"      Ev[{ei}]: [{vals_str}]{note_str}")

    # ══════════════════════════════════════════════════════════════════════
    # 8. ALTERNATIVE INTERPRETATIONS
    # ══════════════════════════════════════════════════════════════════════
    print(f"\n{'=' * 95}")
    print("8. ALTERNATIVE: VARIABLE-LENGTH EVENTS WITHIN 47-BIT FRAME")
    print(f"{'=' * 95}")

    print(f"\n  8a. Two sub-events within 47-bit frame:")
    for a, b in [(23, 24), (24, 23), (21, 26), (26, 21), (14, 33), (28, 19)]:
        if a + b != 47:
            continue
        print(f"\n    Split: {a}+{b} bits")
        for ei in range(min(len(events_47), 4)):
            ev = events_47[ei]
            v1 = bits_to_int(ev[:a])
            v2 = bits_to_int(ev[a : a + b])
            n1 = midi_note_name(v1) if 24 <= v1 <= 96 else ""
            n2 = midi_note_name(v2) if 24 <= v2 <= 96 else ""
            print(
                f"      Ev[{ei}]: [{v1:8d}, {v2:8d}]"
                f"{'  ' + n1 if n1 else ''}"
                f"{'  ' + n2 if n2 else ''}"
            )

    print(f"\n  8b. Three sub-events within 47-bit frame:")
    for split in [
        (16, 16, 15),
        (15, 16, 16),
        (14, 14, 19),
        (7, 21, 19),
        (7, 14, 26),
        (7, 20, 20),
        (14, 7, 26),
        (21, 7, 19),
    ]:
        a, b, c = split
        if a + b + c != 47:
            continue
        print(f"\n    Split: {a}+{b}+{c} bits")
        for ei in range(min(len(events_47), 4)):
            ev = events_47[ei]
            v1 = bits_to_int(ev[:a])
            v2 = bits_to_int(ev[a : a + b])
            v3 = bits_to_int(ev[a + b : a + b + c])
            print(f"      Ev[{ei}]: [{v1:6d}, {v2:6d}, {v3:6d}]")

    print(f"\n  8c. Non-47 periods — what if the true period is different?")
    print(f"    Testing other candidate periods on bar data:")
    bar_concat = bytearray()
    for bi in music_parts:
        bar_concat.extend(bars[bi])
    concat_all_bits = bytes_to_bits(bytes(bar_concat))

    if len(concat_all_bits) > 100:
        print(f"    Concatenated bar data: {len(concat_all_bits)} bits")
        print(
            f"\n    {'Lag':>6} {'R':>8} {'Strength':<10} {'Events from {0}b'.format(largest_bits)}"
        )
        print(f"    {'─' * 6} {'─' * 8} {'─' * 10} {'─' * 20}")
        for lag in range(30, 65):
            r = autocorrelation_at_lag(concat_all_bits, lag)
            if abs(r) > 0.10:
                n_ev_fit = largest_bits / lag
                strength = "STRONG" if abs(r) > 0.3 else "MODERATE" if abs(r) > 0.15 else "weak"
                marker = " <<<" if abs(r) > 0.25 else ""
                print(f"    {lag:6d} {r:+8.4f} {strength:<10} {n_ev_fit:.2f} events{marker}")

    # ══════════════════════════════════════════════════════════════════════
    # 9. BYTE-ALIGNED SANITY CHECK
    # ══════════════════════════════════════════════════════════════════════
    print(f"\n{'=' * 95}")
    print("9. BYTE-ALIGNED SANITY CHECK")
    print(f"{'=' * 95}")

    bar_data = largest_bar
    print(f"\n  Bar size: {len(bar_data)} bytes")
    for evsize in [4, 5, 6, 7, 8]:
        n_ev = len(bar_data) // evsize
        remainder = len(bar_data) % evsize
        print(f"\n  {evsize}-byte events: {n_ev} events, remainder={remainder}")
        for ei in range(min(n_ev, 8)):
            chunk = bar_data[ei * evsize : (ei + 1) * evsize]
            hex_str = " ".join(f"{b:02X}" for b in chunk)
            vals = list(chunk)
            notes = [f"{midi_note_name(v)}" for v in vals if 24 <= v <= 96]
            note_str = f"  notes: {notes}" if notes else ""
            print(f"    [{hex_str}]  dec: {vals}{note_str}")

    # ══════════════════════════════════════════════════════════════════════
    # 10. DEEP DIVE: BEST DECOMPOSITION MUSICAL ANALYSIS
    # ══════════════════════════════════════════════════════════════════════
    print(f"\n{'=' * 95}")
    print("10. DEEP DIVE: MUSICAL ANALYSIS OF BEST DECOMPOSITION")
    print(f"{'=' * 95}")

    best_label, best_widths = results[0][0], results[0][1]
    print(f"\n  Best decomposition: {best_label}")
    print(f"  Widths: {best_widths}")

    # Apply to ALL bars across ALL sections
    print(f"\n  Full extraction across all sections and bars:")
    all_field_values = [[] for _ in best_widths]

    for sec_idx in range(6):
        al = sec_idx * 8 + track_offset
        if al not in by_al:
            continue
        sec_data = bytes(by_al[al])
        if len(sec_data) <= 24:
            continue
        sec_events = sec_data[24:]
        sec_bars = split_by_delimiter(sec_events, 0xDC)

        for bi, bdata in enumerate(sec_bars):
            if len(bdata) < 6:
                continue
            bb = bytes_to_bits(bdata)
            n_ev = len(bb) // 47
            for ei in range(n_ev):
                fields = extract_fields(bb[ei * 47 : (ei + 1) * 47], best_widths)
                for fi, v in enumerate(fields):
                    if fi < len(all_field_values):
                        all_field_values[fi].append(v)

    print(f"\n  Aggregate field statistics (all sections, all bars):")
    for fi, vals in enumerate(all_field_values):
        if not vals:
            continue
        w = best_widths[fi]
        freq = Counter(vals)
        print(f"\n    Field[{fi}] ({w}-bit, max={2**w - 1}):")
        print(f"      Count: {len(vals)} values")
        print(f"      Range: [{min(vals)}, {max(vals)}]")
        print(f"      Mean:  {sum(vals) / len(vals):.1f}")
        print(f"      Unique: {len(freq)} values")
        print(f"      Top 10: {freq.most_common(10)}")

        # Musical interpretation
        note_vals = [v for v in vals if 24 <= v <= 96]
        if note_vals and w >= 7:
            note_names = [midi_note_name(v) for v in sorted(set(note_vals))]
            pitch_classes = sorted(set(v % 12 for v in note_vals))
            pc_names = [NOTE_NAMES[pc] for pc in pitch_classes]
            chord = identify_chord(list(set(note_vals)))
            print(f"      As notes: {note_names}")
            print(f"      Pitch classes: {pc_names}")
            if chord:
                print(f"      Chord match: {chord}")

    # ══════════════════════════════════════════════════════════════════════
    # 11. SECOND-BEST AND THIRD-BEST COMPARISON
    # ══════════════════════════════════════════════════════════════════════
    print(f"\n{'=' * 95}")
    print("11. CONFIDENCE ASSESSMENT")
    print(f"{'=' * 95}")

    if len(results) >= 3:
        s1 = results[0][3]["total"]
        s2 = results[1][3]["total"]
        s3 = results[2][3]["total"]
        gap_12 = s1 - s2
        gap_13 = s1 - s3

        print(f"\n  Score gap analysis:")
        print(f"    #1 ({results[0][0]}): score = {s1}")
        print(f"    #2 ({results[1][0]}): score = {s2}  (gap = {gap_12})")
        print(f"    #3 ({results[2][0]}): score = {s3}  (gap = {gap_13})")

        if gap_12 > 20:
            print(f"\n  ASSESSMENT: #1 is clearly dominant (gap > 20)")
        elif gap_12 > 10:
            print(f"\n  ASSESSMENT: #1 is moderately preferred (gap 10-20)")
        else:
            print(f"\n  ASSESSMENT: Top decompositions are close — more data needed")

    # Overall bit-fit quality
    print(f"\n  47-bit fit quality across all CHD1 data:")
    total_bits = 0
    total_remainder = 0
    bar_count = 0
    for sec_idx in range(6):
        al = sec_idx * 8 + track_offset
        if al not in by_al:
            continue
        sec_data = bytes(by_al[al])
        if len(sec_data) <= 24:
            continue
        sec_bars = split_by_delimiter(sec_data[24:], 0xDC)
        for bdata in sec_bars:
            if len(bdata) < 6:
                continue
            nb = len(bdata) * 8
            rem = nb % 47
            total_bits += nb
            total_remainder += rem
            bar_count += 1
            quality = "EXACT" if rem == 0 else f"rem={rem}"
            n_ev = nb // 47
            print(
                f"    Sec{sec_idx} bar: {len(bdata):3d}B = {nb:4d}b → {n_ev:2d} events ({quality})"
            )

    if bar_count > 0:
        avg_rem = total_remainder / bar_count
        print(f"\n    Total: {bar_count} bars, {total_bits} bits")
        print(f"    Average remainder: {avg_rem:.1f} bits")
        if avg_rem < 5:
            print(f"    47-bit period fits well (avg remainder < 5)")
        elif avg_rem < 15:
            print(f"    47-bit period fits moderately")
        else:
            print(f"    47-bit period may not be the right event size")

    # ══════════════════════════════════════════════════════════════════════
    # FINAL SUMMARY
    # ══════════════════════════════════════════════════════════════════════
    print(f"\n{'=' * 95}")
    print("FINAL SUMMARY")
    print(f"{'=' * 95}")

    print(f"\n  Best decomposition: {results[0][0]}")
    print(f"  Score: {results[0][3]['total']}")
    print(f"  Widths: {results[0][1]}")
    print(f"\n  Field interpretations:")
    for fi, fa in enumerate(results[0][3].get("field_analysis", [])):
        if isinstance(fa, dict) and fa.get("types"):
            print(f"    F{fi} ({fa['width']}b): {', '.join(fa['types'])}")
        elif isinstance(fa, dict):
            print(
                f"    F{fi} ({fa['width']}b): uncharacterized, "
                f"range=[{fa.get('min', '?')}-{fa.get('max', '?')}]"
            )

    print(f"\n  Runner-up: {results[1][0]}")
    print(f"  Score: {results[1][3]['total']}")

    if len(results) >= 2:
        print(f"\n  Key differences between #1 and #2:")
        w1 = results[0][1]
        w2 = results[1][1]
        print(f"    #1 widths: {w1}")
        print(f"    #2 widths: {w2}")

    print(f"\n{'=' * 95}")
    print("ANALYSIS COMPLETE")
    print(f"{'=' * 95}")


if __name__ == "__main__":
    main()
