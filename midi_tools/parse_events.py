#!/usr/bin/env python3
"""
Definitive QY70 SysEx Event Parser

Tests whether QY70 track data (decoded, bytes 24+) uses the same
command set as Q7P: D0/E0/C1/A0-A7/BE/BC/F0/F2/DC/00.

Resolves the contradiction between:
  1. Q7P analysis that claimed both formats share D0/E0/A0-A7/BE/F2 commands
  2. QY70 deep analysis that found a "packed bitstream" with no clear commands

Usage:
    cd /Volumes/Data/DK/XG/T700/qyconv
    source .venv/bin/activate
    python3 midi_tools/parse_events.py
"""

import sys
from pathlib import Path
from collections import Counter, defaultdict
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent))
from qymanager.utils.yamaha_7bit import decode_7bit

# ── Constants ────────────────────────────────────────────────────────────────

SYX_FILE = Path(__file__).parent.parent / "tests" / "fixtures" / "QY70_SGT.syx"

SYSEX_START = 0xF0
SYSEX_END = 0xF7
YAMAHA_ID = 0x43
QY70_MODEL = 0x5F

TRACK_NAMES = ["D1  ", "D2  ", "PC  ", "BA  ", "C1  ", "C2  ", "C3  ", "C4  "]
TRACK_TYPES = ["drum", "drum", "drum", "bass", "chord", "chord", "chord", "chord"]

GM_DRUM_MAP = {
    35: "Kick2",
    36: "Kick1",
    37: "SStick",
    38: "Snare1",
    39: "Clap",
    40: "Snare2",
    41: "FlTom2",
    42: "HH-Cl",
    43: "FlTom1",
    44: "HH-Pd",
    45: "LoTom",
    46: "HH-Op",
    47: "MdTom2",
    48: "MdTom1",
    49: "Crash1",
    50: "HiTom",
    51: "Ride1",
    52: "China",
    53: "RideBl",
    54: "Tamb",
    55: "Splash",
    56: "Cowbell",
    57: "Crash2",
    69: "Cabasa",
    70: "Maracs",
}

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def midi_note_name(n: int) -> str:
    if 0 <= n <= 127:
        return f"{NOTE_NAMES[n % 12]}{(n // 12) - 1}"
    return f"?{n}"


# ── Q7P Command Set Definition ──────────────────────────────────────────────

Q7P_COMMANDS = {
    0xD0: ("DRUM_NOTE", 4),  # D0 nn vv xx
    0xE0: ("MELODY_NOTE", 4),  # E0 nn vv xx
    0xC0: ("ALT_NOTE2", 2),  # C0 xx
    0xC1: ("ALT_NOTE3", 3),  # C1 nn pp
    0xA0: ("DELTA_0", 2),  # A0 dd
    0xA1: ("DELTA_1", 2),
    0xA2: ("DELTA_2", 2),
    0xA3: ("DELTA_3", 2),
    0xA4: ("DELTA_4", 2),
    0xA5: ("DELTA_5", 2),
    0xA6: ("DELTA_6", 2),
    0xA7: ("DELTA_7", 2),
    0xBE: ("NOTE_OFF", 2),  # BE xx
    0xBC: ("CONTROL", 2),  # BC xx
    0xF0: ("START", 2),  # F0 00
    0xF2: ("END", 1),  # F2
    0xDC: ("BAR", 1),  # DC
    0x00: ("TERM", 1),  # 00
}


# ── SysEx Parsing ────────────────────────────────────────────────────────────


def parse_bulk_dumps(raw: bytes) -> Dict[int, bytearray]:
    """Parse SysEx, decode 7-bit, accumulate decoded data by AL address."""
    by_al: Dict[int, bytearray] = {}
    start = None
    for i, b in enumerate(raw):
        if b == SYSEX_START:
            start = i
        elif b == SYSEX_END and start is not None:
            msg = raw[start : i + 1]
            start = None
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


# ── Q7P Command Parser (State Machine) ──────────────────────────────────────


def parse_with_q7p_commands(data: bytes, label: str = "") -> dict:
    """
    Attempt to parse data using the Q7P command set.
    Returns parse statistics and event list.
    """
    result = {
        "total_bytes": len(data),
        "parsed_bytes": 0,
        "unknown_bytes": 0,
        "events": [],
        "unknowns": [],
        "cmd_counts": Counter(),
    }
    if not data:
        return result

    pos = 0
    while pos < len(data):
        b = data[pos]

        if b in Q7P_COMMANDS:
            name, length = Q7P_COMMANDS[b]
            if pos + length <= len(data):
                event_data = data[pos : pos + length]
                result["events"].append((pos, name, event_data))
                result["cmd_counts"][name] += 1
                result["parsed_bytes"] += length
                pos += length
            else:
                # Command found but not enough bytes remaining
                result["unknowns"].append((pos, b, "TRUNCATED"))
                result["unknown_bytes"] += 1
                pos += 1
        else:
            result["unknowns"].append((pos, b, "UNKNOWN"))
            result["unknown_bytes"] += 1
            pos += 1

    coverage = result["parsed_bytes"] / result["total_bytes"] * 100 if result["total_bytes"] else 0
    result["coverage_pct"] = coverage
    return result


def format_event(name: str, data: bytes, track_type: str) -> str:
    """Format a parsed event with musical meaning."""
    hex_str = " ".join(f"{b:02X}" for b in data)

    if name == "DRUM_NOTE" and len(data) == 4:
        note = data[1]
        vel = data[2]
        gate = data[3]
        drum = GM_DRUM_MAP.get(note, f"drum#{note}")
        return f"[{hex_str}]  {drum}, vel={vel}, gate={gate}"
    elif name == "MELODY_NOTE" and len(data) == 4:
        note = data[1]
        vel = data[2]
        gate = data[3]
        return f"[{hex_str}]  {midi_note_name(note)}, vel={vel}, gate={gate}"
    elif name.startswith("DELTA_") and len(data) == 2:
        step = data[0] & 0x07
        dd = data[1]
        total = (step << 8) | dd  # or (step << 7) | dd  -- unclear
        return f"[{hex_str}]  delta step={step}, dd={dd} (total ~{total} ticks)"
    elif name == "NOTE_OFF" and len(data) == 2:
        return f"[{hex_str}]  note off/reset param={data[1]}"
    elif name == "CONTROL" and len(data) == 2:
        return f"[{hex_str}]  control change val={data[1]}"
    elif name == "BAR":
        return f"[DC]        ──── BAR ────"
    elif name == "END":
        return f"[F2]        ──── END OF PHRASE ────"
    elif name == "START" and len(data) == 2:
        return f"[{hex_str}]  MIDI data start"
    elif name == "TERM":
        return f"[00]        terminator"
    else:
        return f"[{hex_str}]"


# ── Heuristic Command Byte Scanner ──────────────────────────────────────────


def scan_for_command_candidates(data: bytes) -> Dict[int, dict]:
    """
    Scan for ANY byte >= 0x80 that appears consistently with fixed-size
    payloads after it. This tests the hypothesis that QY70 uses different
    command byte values than Q7P.
    """
    candidates: Dict[int, dict] = {}

    for cmd_val in range(0x80, 0x100):
        positions = [i for i, b in enumerate(data) if b == cmd_val]
        if len(positions) < 2:
            continue

        # For each occurrence, look at how many bytes follow before
        # the next high-bit byte (>= 0x80) or end of data
        payload_lengths = []
        for p in positions:
            plen = 0
            j = p + 1
            while j < len(data) and data[j] < 0x80:
                plen += 1
                j += 1
            payload_lengths.append(plen)

        length_freq = Counter(payload_lengths)
        most_common_len, most_common_count = length_freq.most_common(1)[0]
        consistency = most_common_count / len(positions) * 100

        candidates[cmd_val] = {
            "count": len(positions),
            "most_common_payload_len": most_common_len,
            "total_cmd_size": 1 + most_common_len,
            "consistency_pct": consistency,
            "length_distribution": dict(length_freq.most_common(5)),
            "positions": positions[:10],
        }

    return candidates


# ── Main Analysis ────────────────────────────────────────────────────────────


def main():
    print("=" * 95)
    print("  DEFINITIVE QY70 SysEx Event Parser")
    print("  Testing Q7P command set: D0/E0/C1/A0-A7/BE/BC/F0/F2/DC/00")
    print("=" * 95)

    if not SYX_FILE.exists():
        print(f"ERROR: {SYX_FILE} not found")
        sys.exit(1)

    raw = SYX_FILE.read_bytes()
    by_al = parse_bulk_dumps(raw)
    print(f"\nFile: {SYX_FILE.name} ({len(raw)} bytes)")
    print(f"Decoded {len(by_al)} AL addresses: {sorted(by_al.keys())}")

    # Collect Section 0 tracks (AL 0x00-0x07)
    section0 = {}
    for t in range(8):
        if t in by_al:
            section0[t] = bytes(by_al[t])

    print(f"Section 0 tracks found: {sorted(section0.keys())}")
    for t in sorted(section0.keys()):
        print(
            f"  Track {t} ({TRACK_NAMES[t]}): {len(section0[t])} decoded bytes, "
            f"event data = {len(section0[t]) - 24} bytes (from byte 24)"
        )

    # ═════════════════════════════════════════════════════════════════════
    # TEST 1: Parse each track at multiple start offsets
    # ═════════════════════════════════════════════════════════════════════
    print("\n" + "=" * 95)
    print("  TEST 1: Q7P COMMAND SET PARSE — ALL TRACKS × OFFSETS 24-28")
    print("=" * 95)

    all_results: Dict[int, Dict[int, dict]] = {}  # track -> offset -> result

    for t in sorted(section0.keys()):
        data = section0[t]
        tname = TRACK_NAMES[t]
        ttype = TRACK_TYPES[t]
        print(f"\n{'─' * 95}")
        print(f"  Track {t} ({tname}) — {ttype} — {len(data)} bytes total")
        print(f"{'─' * 95}")

        all_results[t] = {}
        best_offset = 24
        best_coverage = 0

        for start_off in range(24, 29):
            if start_off >= len(data):
                continue
            event_data = data[start_off:]
            result = parse_with_q7p_commands(event_data, f"track{t}_off{start_off}")
            all_results[t][start_off] = result

            cov = result["coverage_pct"]
            parsed = result["parsed_bytes"]
            unk = result["unknown_bytes"]
            total = result["total_bytes"]

            marker = ""
            if cov > best_coverage:
                best_coverage = cov
                best_offset = start_off
                marker = " ← BEST"

            print(
                f"\n  Offset {start_off}: {total} bytes → "
                f"parsed={parsed} ({cov:.1f}%), unknown={unk} ({100 - cov:.1f}%){marker}"
            )

            # Command distribution
            if result["cmd_counts"]:
                cmds = ", ".join(
                    f"{name}={cnt}" for name, cnt in result["cmd_counts"].most_common()
                )
                print(f"    Commands: {cmds}")

            # Show first 10 unknowns
            if result["unknowns"][:10]:
                unk_sample = result["unknowns"][:10]
                unk_str = " ".join(f"@{pos}:0x{val:02X}" for pos, val, _ in unk_sample)
                print(f"    First unknowns: {unk_str}")

        # Print the best result in detail
        print(f"\n  ★ BEST OFFSET: {best_offset} (coverage: {best_coverage:.1f}%)")

        best_result = all_results[t][best_offset]
        if best_coverage > 50:
            print(f"\n  Decoded events (offset {best_offset}, first 40):")
            for i, (pos, name, edata) in enumerate(best_result["events"][:40]):
                fmt = format_event(name, edata, ttype)
                print(f"    {pos:4d}: {name:<14s} {fmt}")
            if len(best_result["events"]) > 40:
                print(f"    ... ({len(best_result['events'])} total)")
        else:
            print(f"  Coverage too low for meaningful event dump.")

    # ═════════════════════════════════════════════════════════════════════
    # TEST 2: Coverage Summary Table
    # ═════════════════════════════════════════════════════════════════════
    print("\n" + "=" * 95)
    print("  TEST 2: COVERAGE SUMMARY TABLE")
    print("=" * 95)

    print(f"\n  {'Track':<8} {'Type':<6} {'Bytes':<6} ", end="")
    for off in range(24, 29):
        print(f"{'Off' + str(off):<10}", end="")
    print(f"  {'Best':<10}")

    print(f"  {'─' * 8} {'─' * 6} {'─' * 6} ", end="")
    for _ in range(24, 29):
        print(f"{'─' * 10}", end="")
    print(f"  {'─' * 10}")

    for t in sorted(section0.keys()):
        data = section0[t]
        tname = TRACK_NAMES[t].strip()
        ttype = TRACK_TYPES[t]
        evlen = len(data) - 24
        print(f"  {tname:<8} {ttype:<6} {evlen:<6}", end="")

        best_cov = 0
        best_off = 24
        for off in range(24, 29):
            if t in all_results and off in all_results[t]:
                cov = all_results[t][off]["coverage_pct"]
                print(f" {cov:5.1f}%   ", end="")
                if cov > best_cov:
                    best_cov = cov
                    best_off = off
            else:
                print(f"   N/A    ", end="")
        print(f"  off={best_off} {best_cov:.1f}%")

    # ═════════════════════════════════════════════════════════════════════
    # TEST 3: Heuristic Command Byte Discovery
    # ═════════════════════════════════════════════════════════════════════
    print("\n" + "=" * 95)
    print("  TEST 3: HEURISTIC COMMAND BYTE DISCOVERY")
    print("  Scanning for ANY byte >= 0x80 with consistent payload lengths")
    print("=" * 95)

    for t in sorted(section0.keys()):
        data = section0[t]
        tname = TRACK_NAMES[t].strip()
        event_data = data[24:]
        if len(event_data) < 10:
            continue

        print(f"\n  Track {t} ({tname}) — {len(event_data)} event bytes:")
        candidates = scan_for_command_candidates(event_data)

        # Sort by count * consistency
        scored = []
        for cmd_val, info in candidates.items():
            score = info["count"] * info["consistency_pct"] / 100
            scored.append((score, cmd_val, info))
        scored.sort(reverse=True)

        print(
            f"    {'Byte':<6} {'Count':<7} {'PayLen':<8} {'TotSize':<9} "
            f"{'Consist%':<10} {'LenDist':<30} {'Q7P?'}"
        )
        print(f"    {'─' * 6} {'─' * 7} {'─' * 8} {'─' * 9} {'─' * 10} {'─' * 30} {'─' * 10}")

        for score, cmd_val, info in scored[:25]:
            q7p_match = ""
            if cmd_val in Q7P_COMMANDS:
                q7p_name, q7p_len = Q7P_COMMANDS[cmd_val]
                expected_payload = q7p_len - 1
                if info["most_common_payload_len"] == expected_payload:
                    q7p_match = f"✓ {q7p_name}"
                else:
                    q7p_match = f"≠ {q7p_name}(exp {expected_payload})"

            dist_str = str(info["length_distribution"])
            print(
                f"    0x{cmd_val:02X}  {info['count']:<7} {info['most_common_payload_len']:<8} "
                f"{info['total_cmd_size']:<9} {info['consistency_pct']:<10.1f} "
                f"{dist_str:<30} {q7p_match}"
            )

    # ═════════════════════════════════════════════════════════════════════
    # TEST 4: Raw hex dump of event data with high-byte highlighting
    # ═════════════════════════════════════════════════════════════════════
    print("\n" + "=" * 95)
    print("  TEST 4: RAW EVENT DATA HEX DUMP (bytes 24+, first 128 bytes per track)")
    print("  Bytes >= 0x80 shown with * prefix for visibility")
    print("=" * 95)

    for t in sorted(section0.keys()):
        data = section0[t]
        tname = TRACK_NAMES[t].strip()
        event_data = data[24:]
        show = event_data[:128]

        print(f"\n  Track {t} ({tname}) — showing {len(show)}/{len(event_data)} bytes:")

        for row_start in range(0, len(show), 16):
            chunk = show[row_start : row_start + 16]
            # Hex with high-byte marking
            hex_parts = []
            for b in chunk:
                if b >= 0x80:
                    hex_parts.append(f"*{b:02X}")
                else:
                    hex_parts.append(f" {b:02X}")
            hex_str = " ".join(hex_parts)
            # Annotation: mark Q7P commands
            annots = []
            for i, b in enumerate(chunk):
                if b in Q7P_COMMANDS:
                    name, _ = Q7P_COMMANDS[b]
                    annots.append(f"{name}@{row_start + i}")
            annot_str = f"  [{', '.join(annots)}]" if annots else ""
            print(f"    {row_start:04X}: {hex_str}{annot_str}")

    # ═════════════════════════════════════════════════════════════════════
    # TEST 5: DC delimiter analysis — does 0xDC work as bar delimiter?
    # ═════════════════════════════════════════════════════════════════════
    print("\n" + "=" * 95)
    print("  TEST 5: DC (0xDC) BAR DELIMITER ANALYSIS")
    print("=" * 95)

    for t in sorted(section0.keys()):
        data = section0[t]
        tname = TRACK_NAMES[t].strip()
        event_data = data[24:]

        dc_positions = [i for i, b in enumerate(event_data) if b == 0xDC]
        dc_count = len(dc_positions)

        if dc_count == 0:
            print(f"\n  Track {t} ({tname}): NO DC bytes found")
            continue

        # Compute bar sizes
        bar_boundaries = [-1] + dc_positions
        bar_sizes = []
        for i in range(1, len(bar_boundaries)):
            bar_sizes.append(bar_boundaries[i] - bar_boundaries[i - 1] - 1)

        # Also check what follows the last DC
        after_last_dc = len(event_data) - dc_positions[-1] - 1

        print(f"\n  Track {t} ({tname}): {dc_count} DC delimiters")
        print(f"    DC positions: {dc_positions}")
        print(f"    Bar sizes: {bar_sizes}")
        print(f"    Bytes after last DC: {after_last_dc}")

        # Check if bar sizes are consistent
        if bar_sizes:
            size_freq = Counter(bar_sizes)
            print(f"    Bar size distribution: {dict(size_freq.most_common())}")

    # ═════════════════════════════════════════════════════════════════════
    # TEST 6: Byte-pair pattern after high bytes
    # ═════════════════════════════════════════════════════════════════════
    print("\n" + "=" * 95)
    print("  TEST 6: WHAT FOLLOWS EACH HIGH BYTE? (context analysis)")
    print("=" * 95)

    # Aggregate all event data from section 0
    all_events = bytearray()
    for t in sorted(section0.keys()):
        all_events.extend(section0[t][24:])

    print(f"\n  Total event bytes (all section 0 tracks): {len(all_events)}")

    # For each unique high byte, show what typically follows it
    high_bytes = sorted(set(b for b in all_events if b >= 0x80))
    print(f"  Unique high bytes (>= 0x80): {len(high_bytes)}")
    print(f"  Values: {' '.join(f'{b:02X}' for b in high_bytes)}")

    print(f"\n  Context analysis (byte X -> what follows):")
    print(f"  {'Byte':<6} {'Count':<6} {'Next byte distribution (top 5)':<50} {'Q7P cmd?'}")
    print(f"  {'─' * 6} {'─' * 6} {'─' * 50} {'─' * 15}")

    for hb in high_bytes:
        positions = [i for i, b in enumerate(all_events) if b == hb]
        count = len(positions)

        # What follows this byte
        next_bytes = Counter()
        for p in positions:
            if p + 1 < len(all_events):
                next_bytes[all_events[p + 1]] += 1

        top5 = next_bytes.most_common(5)
        top5_str = ", ".join(f"0x{v:02X}:{c}" for v, c in top5)

        q7p_info = ""
        if hb in Q7P_COMMANDS:
            name, size = Q7P_COMMANDS[hb]
            q7p_info = f"{name}({size}b)"

        print(f"  0x{hb:02X}  {count:<6} {top5_str:<50} {q7p_info}")

    # ═════════════════════════════════════════════════════════════════════
    # TEST 7: Variable-length "status + data" parse (MIDI-style)
    # ═════════════════════════════════════════════════════════════════════
    print("\n" + "=" * 95)
    print("  TEST 7: MIDI-STYLE STATUS/DATA PARSE (high byte = status, low bytes = data)")
    print("=" * 95)

    for t in sorted(section0.keys()):
        data = section0[t]
        tname = TRACK_NAMES[t].strip()
        event_data = data[24:]
        if len(event_data) < 10:
            continue

        # Parse: each high byte is a "status", followed by 0+ low bytes
        events = []
        i = 0
        while i < len(event_data):
            b = event_data[i]
            if b >= 0x80:
                status = b
                params = bytearray()
                i += 1
                while i < len(event_data) and event_data[i] < 0x80:
                    params.append(event_data[i])
                    i += 1
                events.append((status, bytes(params)))
            else:
                # Orphan data byte (no preceding status)
                events.append((None, bytes([b])))
                i += 1

        # Statistics
        status_events = [e for e in events if e[0] is not None]
        orphan_events = [e for e in events if e[0] is None]

        status_sizes = Counter()
        for status, params in status_events:
            total_size = 1 + len(params)
            status_sizes[(status, total_size)] += 1

        print(
            f"\n  Track {t} ({tname}): {len(status_events)} status events, "
            f"{len(orphan_events)} orphan data bytes"
        )

        # Show distribution of (status_byte, total_event_size)
        print(f"    {'Status':<8} {'TotSize':<9} {'Count':<7} {'Interpretation'}")
        print(f"    {'─' * 8} {'─' * 9} {'─' * 7} {'─' * 30}")

        for (status, size), count in sorted(status_sizes.items(), key=lambda x: -x[1])[:20]:
            interp = ""
            if status in Q7P_COMMANDS:
                q7p_name, q7p_size = Q7P_COMMANDS[status]
                if size == q7p_size:
                    interp = f"matches Q7P {q7p_name}"
                else:
                    interp = f"Q7P expects {q7p_size}b, got {size}b"

            print(f"    0x{status:02X}   {size:<9} {count:<7} {interp}")

        # Show first 20 events
        print(f"\n    First 30 events:")
        for i, (status, params) in enumerate(events[:30]):
            if status is not None:
                params_hex = " ".join(f"{b:02X}" for b in params) if params else "(none)"
                print(f"      [{i:3d}] 0x{status:02X} + {len(params)} data: {params_hex}")
            else:
                print(f"      [{i:3d}] orphan: 0x{params[0]:02X}")

    # ═════════════════════════════════════════════════════════════════════
    # TEST 8: Bit-level analysis — is this a bitstream?
    # ═════════════════════════════════════════════════════════════════════
    print("\n" + "=" * 95)
    print("  TEST 8: BIT-LEVEL ANALYSIS — IS THIS A PACKED BITSTREAM?")
    print("=" * 95)

    for t in [0, 3, 4]:  # D1, BA, C1
        data = section0.get(t)
        if not data or len(data) <= 24:
            continue
        tname = TRACK_NAMES[t].strip()
        event_data = data[24:]

        # Check entropy / randomness
        freq = Counter(event_data)
        total = len(event_data)
        entropy = 0
        import math

        for count in freq.values():
            p = count / total
            if p > 0:
                entropy -= p * math.log2(p)

        # Check bit-level patterns
        bit_counts = [0] * 8
        for b in event_data:
            for bit in range(8):
                if b & (1 << bit):
                    bit_counts[bit] += 1

        print(f"\n  Track {t} ({tname}): {len(event_data)} bytes")
        print(f"    Shannon entropy: {entropy:.2f} bits/byte (max 8.0)")
        print(f"    Unique byte values: {len(freq)} / 256")
        print(f"    Bit position frequencies (out of {total}):")
        for bit in range(7, -1, -1):
            pct = bit_counts[bit] / total * 100
            bar = "#" * int(pct / 2)
            print(f"      bit {bit}: {bit_counts[bit]:5d} ({pct:5.1f}%) {bar}")

        # Check if high bit (bit 7) is rarely set — would suggest
        # mostly 7-bit data with occasional commands
        high_bit_pct = bit_counts[7] / total * 100
        if high_bit_pct < 30:
            print(
                f"    → Bit 7 is LOW ({high_bit_pct:.1f}%) — consistent with "
                f"MIDI-style status/data separation"
            )
        elif high_bit_pct > 70:
            print(
                f"    → Bit 7 is HIGH ({high_bit_pct:.1f}%) — unusual, "
                f"suggests packed/encoded format"
            )
        else:
            print(
                f"    → Bit 7 is MODERATE ({high_bit_pct:.1f}%) — "
                f"could be mixed format or bitstream"
            )

    # ═════════════════════════════════════════════════════════════════════
    # TEST 9: Compare first bar of D1 track between sections
    # ═════════════════════════════════════════════════════════════════════
    print("\n" + "=" * 95)
    print("  TEST 9: CROSS-SECTION D1 TRACK COMPARISON (first 32 event bytes)")
    print("=" * 95)

    d1_sections = {}
    for sec in range(6):
        al = sec * 8  # D1 track
        if al in by_al:
            decoded = bytes(by_al[al])
            if len(decoded) > 24:
                d1_sections[sec] = decoded[24:56]  # First 32 event bytes

    if len(d1_sections) > 1:
        sec_names = ["Intro", "MainA", "MainB", "FillAB", "FillBA", "Ending"]
        for sec, data in sorted(d1_sections.items()):
            hex_str = " ".join(f"{b:02X}" for b in data)
            print(f"  Section {sec} ({sec_names[sec]:<6}): {hex_str}")
    else:
        print("  Not enough sections for comparison.")

    # ═════════════════════════════════════════════════════════════════════
    # FINAL VERDICT
    # ═════════════════════════════════════════════════════════════════════
    print("\n" + "=" * 95)
    print("  FINAL VERDICT: DOES THE Q7P COMMAND SET PARSE QY70 DATA?")
    print("=" * 95)

    total_parsed = 0
    total_bytes = 0
    total_unknown = 0
    per_track_verdicts = []

    for t in sorted(section0.keys()):
        tname = TRACK_NAMES[t].strip()
        # Use best offset for each track
        best_off = 24
        best_cov = 0
        for off in range(24, 29):
            if t in all_results and off in all_results[t]:
                cov = all_results[t][off]["coverage_pct"]
                if cov > best_cov:
                    best_cov = cov
                    best_off = off

        if t in all_results and best_off in all_results[t]:
            r = all_results[t][best_off]
            total_parsed += r["parsed_bytes"]
            total_bytes += r["total_bytes"]
            total_unknown += r["unknown_bytes"]

            # Check how many unknowns are actually just low bytes that
            # happened to not match a command
            unk_vals = Counter(v for _, v, _ in r["unknowns"])
            unk_high = sum(c for v, c in unk_vals.items() if v >= 0x80)
            unk_low = sum(c for v, c in unk_vals.items() if v < 0x80)

            verdict = "GOOD" if best_cov >= 80 else "POOR" if best_cov >= 50 else "FAIL"
            per_track_verdicts.append((t, tname, best_off, best_cov, verdict, unk_high, unk_low))

    print(
        f"\n  Overall coverage: {total_parsed}/{total_bytes} bytes "
        f"({total_parsed / total_bytes * 100:.1f}%) parsed as Q7P commands"
    )
    print(f"  Unknown bytes: {total_unknown}")

    print(f"\n  Per-track results:")
    print(f"  {'Track':<6} {'Off':<5} {'Coverage':<10} {'Verdict':<8} {'UnkHigh':<9} {'UnkLow':<8}")
    print(f"  {'─' * 6} {'─' * 5} {'─' * 10} {'─' * 8} {'─' * 9} {'─' * 8}")
    for t, tname, off, cov, verdict, unk_h, unk_l in per_track_verdicts:
        print(f"  {tname:<6} {off:<5} {cov:>6.1f}%   {verdict:<8} {unk_h:<9} {unk_l:<8}")

    overall_cov = total_parsed / total_bytes * 100 if total_bytes else 0
    print(f"\n  {'=' * 70}")
    if overall_cov >= 75:
        print(f"  ANSWER: YES — Q7P command set DOES parse QY70 data ({overall_cov:.1f}% coverage)")
        print(f"  The D0/E0/A0-A7/BE/BC/F0/F2/DC/00 command set works for both formats.")
    elif overall_cov >= 40:
        print(f"  ANSWER: PARTIAL — Q7P commands parse {overall_cov:.1f}% of QY70 data")
        print(f"  Some commands may be shared, but the format is not identical.")
        print(f"  Check TEST 3 for alternative command byte candidates.")
    else:
        print(f"  ANSWER: NO — Q7P command set FAILS on QY70 data ({overall_cov:.1f}% coverage)")
        print(f"  The QY70 uses a DIFFERENT internal event format.")
        print(f"  Check TEST 3 and TEST 7 for the actual command structure.")
    print(f"  {'=' * 70}")


if __name__ == "__main__":
    main()
