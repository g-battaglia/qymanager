#!/usr/bin/env python3
"""
Deep analysis of QY70 SysEx track event data (bytes 24+).

Parses the SGT reference file, decodes 7-bit payloads, and performs
exhaustive analysis of the internal MIDI event format used in each track.

Goals:
  - Understand byte frequency distribution in event data
  - Identify delimiters (DC = bar delimiter, 00 = terminator)
  - Split event data into bars and look for fixed-size events
  - Try 3-byte and variable-length event interpretations
  - Compare bars within tracks and tracks across sections
  - Special analysis for drums (GM note mapping) and bass (chromatic)
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

TRACK_NAMES = ["RHY1", "RHY2", "BASS", "CHD1", "CHD2", "PAD ", "PHR1", "PHR2"]
TRACK_TYPES = ["drum", "drum", "bass", "chord", "chord", "chord", "chord", "chord"]

SECTION_NAMES = ["Intro", "MainA", "MainB", "FillAB", "FillBA", "Ending"]

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
    58: "Vibslp",
    59: "Ride2",
    60: "HiBong",
    61: "LoBong",
    62: "MtCnga",
    63: "OpCnga",
    64: "LoCnga",
    65: "HiTimb",
    66: "LoTimb",
    67: "HiAgog",
    68: "LoAgog",
    69: "Cabasa",
    70: "Maracs",
    71: "ShWhis",
    72: "LgWhis",
    73: "ShGuir",
    74: "LgGuir",
    75: "Claves",
    76: "HiWdBl",
    77: "LoWdBl",
    78: "MtCuic",
    79: "OpCuic",
    80: "MtTri",
    81: "OpTri",
}

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def midi_note_name(n: int) -> str:
    """Convert MIDI note number to name like C4, D#5."""
    if n < 0 or n > 127:
        return f"?{n}"
    octave = (n // 12) - 1
    return f"{NOTE_NAMES[n % 12]}{octave}"


# ── SysEx Parsing ────────────────────────────────────────────────────────────


def split_sysex(data: bytes) -> List[bytes]:
    """Split raw .syx file into individual F0..F7 messages."""
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
    """
    Parse all bulk dump messages and accumulate decoded data by AL address.
    Returns dict: AL -> decoded_bytes (bytearray).
    """
    msgs = split_sysex(raw)
    by_al: Dict[int, bytearray] = {}

    for msg in msgs:
        if len(msg) < 11:
            continue
        if msg[1] != YAMAHA_ID or msg[3] != QY70_MODEL:
            continue
        if (msg[2] & 0xF0) != 0x00:  # Not bulk dump
            continue

        ah, am, al = msg[6], msg[7], msg[8]
        if ah != 0x02 or am != 0x7E:
            continue  # Not style data

        payload = msg[9:-2]
        decoded = decode_7bit(payload)

        if al not in by_al:
            by_al[al] = bytearray()
        by_al[al].extend(decoded)

    return by_al


# ── Hex Dump ─────────────────────────────────────────────────────────────────


def hexdump(
    data: bytes, prefix: str = "    ", bytes_per_line: int = 16, max_lines: int = 50
) -> str:
    """Pretty hex dump with ASCII sidebar."""
    lines = []
    for i in range(0, min(len(data), max_lines * bytes_per_line), bytes_per_line):
        chunk = data[i : i + bytes_per_line]
        hex_part = " ".join(f"{b:02X}" for b in chunk)
        ascii_part = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        lines.append(f"{prefix}{i:04X}: {hex_part:<{bytes_per_line * 3 - 1}s}  |{ascii_part}|")
    if len(data) > max_lines * bytes_per_line:
        lines.append(
            f"{prefix}... ({len(data)} bytes total, showing first {max_lines * bytes_per_line})"
        )
    return "\n".join(lines)


# ── Analysis Functions ───────────────────────────────────────────────────────


def byte_frequency(data: bytes) -> Counter:
    """Count frequency of each byte value."""
    return Counter(data)


def split_by_delimiter(data: bytes, delim: int = 0xDC) -> List[bytes]:
    """Split data by delimiter byte. Strips trailing 0x00 terminator first."""
    # Remove trailing 00 terminator if present
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


def find_repeating_patterns(data: bytes, min_len: int = 2, max_len: int = 8) -> Dict[bytes, int]:
    """Find repeating byte patterns and their counts."""
    patterns: Dict[bytes, int] = {}
    for plen in range(min_len, min(max_len + 1, len(data))):
        for i in range(len(data) - plen + 1):
            pat = data[i : i + plen]
            if pat in patterns:
                patterns[pat] += 1
            else:
                patterns[pat] = 1
    # Filter to patterns that appear more than once
    return {k: v for k, v in patterns.items() if v > 1}


def try_fixed_size_decode(bar_data: bytes, event_size: int) -> List[Tuple[int, ...]]:
    """Attempt to decode bar data as fixed-size events."""
    events = []
    for i in range(0, len(bar_data) - event_size + 1, event_size):
        event = tuple(bar_data[i : i + event_size])
        events.append(event)
    return events


def analyze_as_variable_length(data: bytes) -> List[dict]:
    """
    Try to interpret data as variable-length events.
    Look for command bytes (0x80-0xFF range) as event starters.
    """
    events = []
    i = 0
    while i < len(data):
        b = data[i]
        if b >= 0x80:
            # Potential command byte - collect until next command or end
            cmd = b
            params = bytearray()
            i += 1
            while i < len(data) and data[i] < 0x80:
                params.append(data[i])
                i += 1
            events.append({"cmd": cmd, "params": bytes(params), "offset": i - len(params) - 1})
        else:
            # Data byte without preceding command
            events.append({"cmd": None, "data": b, "offset": i})
            i += 1
    return events


def compare_bars(bars: List[bytes]) -> dict:
    """Compare bars within a track for similarity."""
    if len(bars) < 2:
        return {"identical_pairs": 0, "total_pairs": 0, "detail": "only 1 bar"}

    identical = 0
    similar = 0
    total = 0
    details = []

    for i in range(len(bars)):
        for j in range(i + 1, len(bars)):
            total += 1
            if bars[i] == bars[j]:
                identical += 1
                details.append(f"bar {i} == bar {j}")
            else:
                # Count differing bytes
                min_len = min(len(bars[i]), len(bars[j]))
                max_len = max(len(bars[i]), len(bars[j]))
                diffs = sum(1 for k in range(min_len) if bars[i][k] != bars[j][k])
                diffs += max_len - min_len
                pct = (1 - diffs / max_len) * 100 if max_len > 0 else 0
                if pct > 80:
                    similar += 1
                details.append(
                    f"bar {i} vs bar {j}: {diffs} byte diffs "
                    f"(len {len(bars[i])} vs {len(bars[j])}), {pct:.0f}% similar"
                )

    return {
        "identical_pairs": identical,
        "similar_pairs": similar,
        "total_pairs": total,
        "details": details,
    }


# ── Main Analysis ────────────────────────────────────────────────────────────


def main():
    print("=" * 90)
    print("QY70 SysEx Track Event Data - Deep Analysis")
    print(f"File: {SYX_FILE}")
    print("=" * 90)

    if not SYX_FILE.exists():
        print(f"ERROR: File not found: {SYX_FILE}")
        sys.exit(1)

    raw = SYX_FILE.read_bytes()
    print(f"File size: {len(raw)} bytes")

    by_al = parse_bulk_dumps(raw)
    print(f"Decoded {len(by_al)} AL addresses: {sorted(['0x%02X' % a for a in by_al.keys()])}")

    # Identify sections present
    track_als = sorted([al for al in by_al if al != 0x7F and al <= 0x2F])
    sections_present = sorted(set(al // 8 for al in track_als))
    print(f"Sections present: {sections_present} = {[SECTION_NAMES[s] for s in sections_present]}")
    print()

    # ──────────────────────────────────────────────────────────────────────
    # PART 1: Section 0 Track-by-Track Analysis
    # ──────────────────────────────────────────────────────────────────────
    print("=" * 90)
    print("PART 1: SECTION 0 (INTRO) - TRACK-BY-TRACK EVENT ANALYSIS")
    print("=" * 90)

    section0_tracks: Dict[int, bytes] = {}
    for track_idx in range(8):
        al = track_idx  # section 0
        if al in by_al:
            section0_tracks[track_idx] = bytes(by_al[al])

    for track_idx in range(8):
        if track_idx not in section0_tracks:
            print(f"\n--- Track {track_idx} ({TRACK_NAMES[track_idx]}) - NO DATA ---")
            continue

        data = section0_tracks[track_idx]
        tname = TRACK_NAMES[track_idx]
        ttype = TRACK_TYPES[track_idx]

        print(f"\n{'─' * 90}")
        print(f"Track {track_idx} ({tname}) - Type: {ttype} - Total decoded: {len(data)} bytes")
        print(f"{'─' * 90}")

        # 1a. Track header (first 24 bytes)
        header = data[:24]
        events = data[24:]
        print(f"\n  HEADER (24 bytes):")
        print(hexdump(header, prefix="    "))

        # Parse known header fields
        print(f"\n  Header decode:")
        print(f"    Common prefix:  {' '.join(f'{b:02X}' for b in header[:12])}")
        print(f"    Constant:       {header[12]:02X} {header[13]:02X}")
        print(f"    Voice (14-15):  {header[14]:02X} {header[15]:02X}")
        print(f"    Range (16-17):  {header[16]:02X} {header[17]:02X}")
        print(f"    Unknown (18-20):{header[18]:02X} {header[19]:02X} {header[20]:02X}")
        print(
            f"    Flag (21):      {header[21]:02X} ({'enabled' if header[21] == 0x41 else 'special/disabled'})"
        )
        print(f"    Pan (22):       {header[22]:02X} ({header[22]})")
        print(f"    Unknown (23):   {header[23]:02X}")

        print(f"\n  EVENT DATA: {len(events)} bytes")
        if len(events) == 0:
            print("    (empty)")
            continue

        # 1b. Byte frequency distribution
        freq = byte_frequency(events)
        print(f"\n  BYTE FREQUENCY (top 30):")
        for val, count in freq.most_common(30):
            pct = count / len(events) * 100
            bar = "#" * min(int(pct * 2), 60)
            label = ""
            if val == 0xDC:
                label = " <-- BAR DELIMITER"
            elif val == 0x00:
                label = " <-- TERMINATOR/PADDING"
            elif val == 0xFE:
                label = " <-- FILL BYTE"
            elif val == 0xF8:
                label = " <-- PADDING"
            elif val >= 0x80:
                label = f" <-- HIGH BIT SET"
            elif ttype == "drum" and val in GM_DRUM_MAP:
                label = f" <-- GM drum: {GM_DRUM_MAP[val]}"
            elif ttype == "bass" and 24 <= val <= 72:
                label = f" <-- note: {midi_note_name(val)}"
            print(f"    0x{val:02X} ({val:3d}): {count:4d} ({pct:5.1f}%) {bar}{label}")

        # 1c. High-bit byte analysis (potential command bytes)
        high_bytes = sorted(set(b for b in events if b >= 0x80))
        print(f"\n  HIGH-BIT BYTES (>= 0x80): {len(high_bytes)} unique values")
        for hb in high_bytes:
            positions = [i for i, b in enumerate(events) if b == hb]
            print(
                f"    0x{hb:02X} ({hb:3d}): appears {len(positions)}x at positions {positions[:20]}{'...' if len(positions) > 20 else ''}"
            )

        # 1d. Split by DC delimiter into bars
        bars = split_by_delimiter(events, 0xDC)
        print(f"\n  BAR ANALYSIS (split by 0xDC): {len(bars)} bars")
        for bi, bar in enumerate(bars):
            print(f"\n    Bar {bi}: {len(bar)} bytes")
            print(hexdump(bar, prefix="      ", max_lines=8))

            # Check for trailing data patterns
            if bar:
                # Byte distribution within this bar
                bar_freq = byte_frequency(bar)
                unique_vals = len(bar_freq)
                print(f"      Unique byte values: {unique_vals}")

                # Look at spacing of potential note bytes
                if ttype == "drum":
                    drum_notes = [(i, b) for i, b in enumerate(bar) if b in GM_DRUM_MAP]
                    if drum_notes:
                        print(f"      GM drum notes found: {len(drum_notes)}")
                        for pos, note in drum_notes[:15]:
                            print(f"        offset {pos:3d}: {note:3d} = {GM_DRUM_MAP[note]}")
                elif ttype == "bass":
                    note_bytes = [(i, b) for i, b in enumerate(bar) if 24 <= b <= 72]
                    if note_bytes:
                        print(f"      Potential bass notes: {len(note_bytes)}")
                        for pos, note in note_bytes[:15]:
                            print(f"        offset {pos:3d}: {note:3d} = {midi_note_name(note)}")

        # 1e. Try fixed-size event interpretations
        print(f"\n  FIXED-SIZE EVENT ATTEMPTS:")
        for event_size in [2, 3, 4, 5, 6]:
            for bi, bar in enumerate(bars[:2]):  # First 2 bars only
                if len(bar) < event_size:
                    continue
                evts = try_fixed_size_decode(bar, event_size)
                remainder = len(bar) % event_size
                print(
                    f"\n    {event_size}-byte events, Bar {bi}: {len(evts)} events, remainder={remainder}"
                )
                for ei, evt in enumerate(evts[:12]):
                    parts = " ".join(f"{b:02X}" for b in evt)
                    annotation = ""
                    if event_size == 3:
                        if ttype == "drum" and evt[1] in GM_DRUM_MAP:
                            annotation = f"  -> delta={evt[0]}, note={GM_DRUM_MAP[evt[1]]}, vel/gate={evt[2]}"
                        elif ttype == "drum" and evt[0] in GM_DRUM_MAP:
                            annotation = (
                                f"  -> note={GM_DRUM_MAP[evt[0]]}, p1={evt[1]}, p2={evt[2]}"
                            )
                        elif ttype == "bass":
                            if 24 <= evt[1] <= 72:
                                annotation = f"  -> delta={evt[0]}, note={midi_note_name(evt[1])}, vel/gate={evt[2]}"
                            elif 24 <= evt[0] <= 72:
                                annotation = (
                                    f"  -> note={midi_note_name(evt[0])}, p1={evt[1]}, p2={evt[2]}"
                                )
                    elif event_size == 4:
                        if ttype == "drum" and evt[1] in GM_DRUM_MAP:
                            annotation = f"  -> dt={evt[0]}, note={GM_DRUM_MAP[evt[1]]}, p2={evt[2]}, p3={evt[3]}"
                        elif ttype == "bass" and 24 <= evt[1] <= 72:
                            annotation = f"  -> dt={evt[0]}, note={midi_note_name(evt[1])}, p2={evt[2]}, p3={evt[3]}"
                    print(f"      [{ei:2d}] {parts}{annotation}")
                if len(evts) > 12:
                    print(f"      ... ({len(evts)} total)")

        # 1f. Variable-length event interpretation
        print(f"\n  VARIABLE-LENGTH EVENT ANALYSIS (first 2 bars):")
        for bi, bar in enumerate(bars[:2]):
            if not bar:
                continue
            var_events = analyze_as_variable_length(bar)
            cmd_events = [e for e in var_events if e.get("cmd") is not None]
            data_events = [e for e in var_events if e.get("cmd") is None]
            print(
                f"\n    Bar {bi}: {len(cmd_events)} command events, {len(data_events)} standalone data bytes"
            )
            for ei, evt in enumerate(var_events[:20]):
                if evt.get("cmd") is not None:
                    params_hex = " ".join(f"{b:02X}" for b in evt["params"])
                    print(
                        f"      off={evt['offset']:3d}: CMD 0x{evt['cmd']:02X} + {len(evt['params'])} params: [{params_hex}]"
                    )
                else:
                    print(f"      off={evt['offset']:3d}: DATA 0x{evt['data']:02X} ({evt['data']})")
            if len(var_events) > 20:
                print(f"      ... ({len(var_events)} total)")

        # 1g. Bar-to-bar comparison
        comp = compare_bars(bars)
        print(f"\n  BAR COMPARISON:")
        print(f"    Identical pairs: {comp['identical_pairs']} / {comp['total_pairs']}")
        if "similar_pairs" in comp:
            print(f"    Similar pairs (>80%): {comp['similar_pairs']}")
        if "details" in comp:
            for d in comp["details"]:
                print(f"    {d}")

    # ──────────────────────────────────────────────────────────────────────
    # PART 2: Cross-Section Comparison
    # ──────────────────────────────────────────────────────────────────────
    print()
    print("=" * 90)
    print("PART 2: CROSS-SECTION COMPARISON (same track across all 6 sections)")
    print("=" * 90)

    for track_idx in range(8):
        tname = TRACK_NAMES[track_idx]
        ttype = TRACK_TYPES[track_idx]
        print(f"\n{'─' * 90}")
        print(f"Track {track_idx} ({tname}) across sections")
        print(f"{'─' * 90}")

        # Collect this track from all sections
        track_sections: Dict[int, bytes] = {}
        for sec_idx in range(6):
            al = sec_idx * 8 + track_idx
            if al in by_al:
                track_sections[sec_idx] = bytes(by_al[al])

        if len(track_sections) < 2:
            print(
                f"  Only {len(track_sections)} section(s) have data for this track - skipping comparison"
            )
            for sec_idx, data in track_sections.items():
                print(f"  Section {sec_idx} ({SECTION_NAMES[sec_idx]}): {len(data)} bytes")
            continue

        # Print sizes
        for sec_idx in sorted(track_sections.keys()):
            data = track_sections[sec_idx]
            events = data[24:] if len(data) > 24 else b""
            bars = split_by_delimiter(events, 0xDC)
            print(
                f"  Section {sec_idx} ({SECTION_NAMES[sec_idx]:>6s}): {len(data):4d} total, "
                f"{len(events):4d} event bytes, {len(bars)} bars"
            )

        # Compare headers
        print(f"\n  HEADER COMPARISON (bytes 0-23):")
        headers = {si: d[:24] for si, d in track_sections.items() if len(d) >= 24}
        ref_sec = min(headers.keys())
        ref_header = headers[ref_sec]
        for si in sorted(headers.keys()):
            if si == ref_sec:
                print(
                    f"    Sec {si} ({SECTION_NAMES[si]:>6s}): {' '.join(f'{b:02X}' for b in headers[si])}"
                )
            else:
                diffs = []
                for bi in range(min(len(ref_header), len(headers[si]))):
                    if ref_header[bi] != headers[si][bi]:
                        diffs.append(bi)
                if not diffs:
                    print(f"    Sec {si} ({SECTION_NAMES[si]:>6s}): IDENTICAL to sec {ref_sec}")
                else:
                    diff_str = ", ".join(
                        f"byte {bi}: {ref_header[bi]:02X}->{headers[si][bi]:02X}" for bi in diffs
                    )
                    print(f"    Sec {si} ({SECTION_NAMES[si]:>6s}): DIFFERS at [{diff_str}]")

        # Compare event data
        print(f"\n  EVENT DATA COMPARISON:")
        event_data = {si: d[24:] for si, d in track_sections.items() if len(d) > 24}

        secs = sorted(event_data.keys())
        for i, si in enumerate(secs):
            for j in range(i + 1, len(secs)):
                sj = secs[j]
                di = event_data[si]
                dj = event_data[sj]
                if di == dj:
                    print(
                        f"    Sec {si} ({SECTION_NAMES[si]}) vs Sec {sj} ({SECTION_NAMES[sj]}): "
                        f"IDENTICAL ({len(di)} bytes)"
                    )
                else:
                    min_len = min(len(di), len(dj))
                    max_len = max(len(di), len(dj))
                    byte_diffs = sum(1 for k in range(min_len) if di[k] != dj[k])
                    byte_diffs += abs(len(di) - len(dj))
                    pct = (1 - byte_diffs / max_len) * 100 if max_len else 0
                    print(
                        f"    Sec {si} ({SECTION_NAMES[si]}) vs Sec {sj} ({SECTION_NAMES[sj]}): "
                        f"{byte_diffs} diffs (len {len(di)} vs {len(dj)}), {pct:.1f}% similar"
                    )

                    # Show first N differing bytes
                    if byte_diffs <= 30:
                        for k in range(min_len):
                            if di[k] != dj[k]:
                                print(f"      offset {k:4d}: {di[k]:02X} vs {dj[k]:02X}")
                        if len(di) != len(dj):
                            print(f"      length differs: {len(di)} vs {len(dj)}")

    # ──────────────────────────────────────────────────────────────────────
    # PART 3: Drum Track Deep Dive
    # ──────────────────────────────────────────────────────────────────────
    print()
    print("=" * 90)
    print("PART 3: DRUM TRACK DEEP DIVE (Section 0, Tracks 0-2)")
    print("=" * 90)

    for track_idx in [0, 1, 2]:
        al = track_idx
        if al not in by_al:
            continue

        data = bytes(by_al[al])
        tname = TRACK_NAMES[track_idx]
        events = data[24:]
        bars = split_by_delimiter(events, 0xDC)

        print(f"\n{'─' * 90}")
        print(f"Track {track_idx} ({tname}) - {len(events)} event bytes, {len(bars)} bars")
        print(f"{'─' * 90}")

        # Check where GM drum notes appear
        all_gm_positions = []
        for i, b in enumerate(events):
            if b in GM_DRUM_MAP:
                all_gm_positions.append((i, b))

        print(f"\n  GM drum note positions in raw event stream:")
        print(f"  Total: {len(all_gm_positions)} GM drum bytes out of {len(events)} total")

        # Check spacing between GM drum notes
        if len(all_gm_positions) >= 2:
            spacings = [
                all_gm_positions[i + 1][0] - all_gm_positions[i][0]
                for i in range(len(all_gm_positions) - 1)
            ]
            spacing_freq = Counter(spacings)
            print(f"\n  Spacing between GM drum notes:")
            for sp, cnt in spacing_freq.most_common(15):
                print(f"    spacing={sp}: {cnt}x")

        # For each bar, show the GM drum notes and their positions
        print(f"\n  Per-bar drum note analysis:")
        for bi, bar in enumerate(bars[:8]):
            drum_hits = [(i, b) for i, b in enumerate(bar) if b in GM_DRUM_MAP]
            print(f"\n    Bar {bi} ({len(bar)} bytes): {len(drum_hits)} potential drum hits")
            for pos, note in drum_hits:
                # Show context: 2 bytes before and after
                ctx_start = max(0, pos - 2)
                ctx_end = min(len(bar), pos + 3)
                ctx = bar[ctx_start:ctx_end]
                ctx_hex = " ".join(f"{b:02X}" for b in ctx)
                marker_pos = pos - ctx_start
                markers = "   " * marker_pos + "^^"
                print(
                    f"      pos {pos:3d}: note {note:3d} ({GM_DRUM_MAP[note]:>7s}) "
                    f" context: [{ctx_hex}]"
                )

        # Look for regular event patterns in drum data
        print(f"\n  Testing event size hypotheses on Bar 0:")
        if bars:
            bar0 = bars[0]
            for evsize in [2, 3, 4, 5, 6]:
                if len(bar0) < evsize:
                    continue
                remainder = len(bar0) % evsize
                evts = try_fixed_size_decode(bar0, evsize)
                # Check if note values consistently appear at the same position
                note_positions = {}
                for ei, evt in enumerate(evts):
                    for pos_in_evt, val in enumerate(evt):
                        if val in GM_DRUM_MAP:
                            if pos_in_evt not in note_positions:
                                note_positions[pos_in_evt] = 0
                            note_positions[pos_in_evt] += 1

                if note_positions:
                    total_notes = sum(note_positions.values())
                    best_pos = max(note_positions.items(), key=lambda x: x[1])
                    print(
                        f"    {evsize}-byte: {len(evts)} events, remainder={remainder}, "
                        f"drum notes at positions {dict(note_positions)}, "
                        f"best={best_pos[0]}({best_pos[1]}/{total_notes} = {best_pos[1] / total_notes * 100:.0f}%)"
                    )

    # ──────────────────────────────────────────────────────────────────────
    # PART 4: Bass Track Deep Dive
    # ──────────────────────────────────────────────────────────────────────
    print()
    print("=" * 90)
    print("PART 4: BASS TRACK DEEP DIVE (Section 0, Track 3)")
    print("=" * 90)

    al_bass = 3  # BASS is track index 3 in section 0
    if al_bass in by_al:
        data = bytes(by_al[al_bass])
        events = data[24:]
        bars = split_by_delimiter(events, 0xDC)

        print(f"  Event data: {len(events)} bytes, {len(bars)} bars")

        # Look for chromatic note values
        print(f"\n  Chromatic note search (MIDI 24-72 = C1-C5):")
        for bi, bar in enumerate(bars[:8]):
            note_hits = [(i, b) for i, b in enumerate(bar) if 24 <= b <= 72]
            print(f"\n    Bar {bi} ({len(bar)} bytes): {len(note_hits)} potential notes")
            for pos, note in note_hits:
                ctx_start = max(0, pos - 2)
                ctx_end = min(len(bar), pos + 3)
                ctx = bar[ctx_start:ctx_end]
                ctx_hex = " ".join(f"{b:02X}" for b in ctx)
                print(
                    f"      pos {pos:3d}: note {note:3d} ({midi_note_name(note):>4s})"
                    f"  context: [{ctx_hex}]"
                )

        # Check for root note patterns (C=0/12/24/36/48/60, etc.)
        print(f"\n  Chord root pattern check:")
        for bi, bar in enumerate(bars[:8]):
            roots = [(i, b, b % 12) for i, b in enumerate(bar) if 24 <= b <= 72]
            if roots:
                root_names = [f"{midi_note_name(r[1])}@{r[0]}" for r in roots]
                print(f"    Bar {bi}: {', '.join(root_names)}")

        # Test event sizes on bass
        print(f"\n  Testing event size hypotheses on Bass Bar 0:")
        if bars:
            bar0 = bars[0]
            for evsize in [2, 3, 4, 5, 6]:
                if len(bar0) < evsize:
                    continue
                remainder = len(bar0) % evsize
                evts = try_fixed_size_decode(bar0, evsize)
                note_positions = {}
                for ei, evt in enumerate(evts):
                    for pos_in_evt, val in enumerate(evt):
                        if 24 <= val <= 72:
                            if pos_in_evt not in note_positions:
                                note_positions[pos_in_evt] = 0
                            note_positions[pos_in_evt] += 1

                if note_positions:
                    total_notes = sum(note_positions.values())
                    best_pos = max(note_positions.items(), key=lambda x: x[1])
                    print(
                        f"    {evsize}-byte: {len(evts)} events, remainder={remainder}, "
                        f"notes at positions {dict(note_positions)}, "
                        f"best={best_pos[0]}({best_pos[1]}/{total_notes} = {best_pos[1] / total_notes * 100:.0f}%)"
                    )

    # ──────────────────────────────────────────────────────────────────────
    # PART 5: First 2 Bars Hexdump (Drum, Bass, Chord)
    # ──────────────────────────────────────────────────────────────────────
    print()
    print("=" * 90)
    print("PART 5: HEXDUMP - FIRST 2 BARS OF EACH TRACK TYPE (Section 0)")
    print("=" * 90)

    for track_idx in range(8):
        al = track_idx
        if al not in by_al:
            continue

        data = bytes(by_al[al])
        tname = TRACK_NAMES[track_idx]
        ttype = TRACK_TYPES[track_idx]
        events = data[24:]
        bars = split_by_delimiter(events, 0xDC)

        print(f"\n{'─' * 90}")
        print(f"Track {track_idx} ({tname}) - Type: {ttype}")
        print(f"{'─' * 90}")

        for bi in range(min(2, len(bars))):
            bar = bars[bi]
            print(f"\n  Bar {bi} ({len(bar)} bytes):")
            print(hexdump(bar, prefix="    ", max_lines=30))

            # Annotated interpretation attempt
            print(f"\n  Bar {bi} - Annotated (3-byte grouping):")
            for gi in range(0, len(bar), 3):
                chunk = bar[gi : gi + 3]
                hex_str = " ".join(f"{b:02X}" for b in chunk)
                annot = ""
                if len(chunk) >= 3:
                    if ttype == "drum":
                        if chunk[1] in GM_DRUM_MAP:
                            annot = f"delta={chunk[0]:3d}, note={GM_DRUM_MAP[chunk[1]]}, vel/gate={chunk[2]}"
                        elif chunk[0] in GM_DRUM_MAP:
                            annot = f"note={GM_DRUM_MAP[chunk[0]]}, p1={chunk[1]}, p2={chunk[2]}"
                    elif ttype == "bass":
                        if 24 <= chunk[1] <= 72:
                            annot = f"delta={chunk[0]:3d}, note={midi_note_name(chunk[1])}, vel/gate={chunk[2]}"
                        elif 24 <= chunk[0] <= 72:
                            annot = f"note={midi_note_name(chunk[0])}, p1={chunk[1]}, p2={chunk[2]}"
                    elif ttype == "chord":
                        if 24 <= chunk[1] <= 96:
                            annot = f"delta={chunk[0]:3d}, note={midi_note_name(chunk[1])}, vel/gate={chunk[2]}"
                elif len(chunk) == 2:
                    annot = f"(2-byte remainder)"
                elif len(chunk) == 1:
                    annot = f"(1-byte remainder)"

                print(f"      {gi:3d}: [{hex_str}]  {annot}")

    # ──────────────────────────────────────────────────────────────────────
    # PART 6: Global Statistics and Pattern Mining
    # ──────────────────────────────────────────────────────────────────────
    print()
    print("=" * 90)
    print("PART 6: GLOBAL STATISTICS AND PATTERN MINING")
    print("=" * 90)

    # Aggregate all event data from section 0
    all_events = bytearray()
    for track_idx in range(8):
        if track_idx in section0_tracks and len(section0_tracks[track_idx]) > 24:
            all_events.extend(section0_tracks[track_idx][24:])

    print(f"\n  Total event bytes across all section 0 tracks: {len(all_events)}")

    # Global byte frequency
    global_freq = byte_frequency(bytes(all_events))
    print(f"\n  GLOBAL BYTE FREQUENCY (top 40):")
    for val, count in global_freq.most_common(40):
        pct = count / len(all_events) * 100
        bar = "#" * min(int(pct * 2), 60)
        label = ""
        if val == 0xDC:
            label = " BAR_DELIM"
        elif val == 0x00:
            label = " TERMINATOR"
        elif val == 0xFE:
            label = " FILL"
        elif val == 0xF8:
            label = " PADDING"
        elif val >= 0x80:
            label = f" HIGH_BIT"
        print(f"    0x{val:02X} ({val:3d}): {count:5d} ({pct:5.1f}%) {bar}{label}")

    # Value range analysis
    print(f"\n  VALUE RANGE ANALYSIS:")
    range_counts = {
        "0x00-0x0F": 0,
        "0x10-0x1F": 0,
        "0x20-0x2F": 0,
        "0x30-0x3F": 0,
        "0x40-0x4F": 0,
        "0x50-0x5F": 0,
        "0x60-0x6F": 0,
        "0x70-0x7F": 0,
        "0x80-0x8F": 0,
        "0x90-0x9F": 0,
        "0xA0-0xAF": 0,
        "0xB0-0xBF": 0,
        "0xC0-0xCF": 0,
        "0xD0-0xDF": 0,
        "0xE0-0xEF": 0,
        "0xF0-0xFF": 0,
    }
    for b in all_events:
        range_key = f"0x{(b & 0xF0):02X}-0x{(b & 0xF0) | 0x0F:02X}"
        range_counts[range_key] += 1

    for rng, cnt in range_counts.items():
        pct = cnt / len(all_events) * 100
        bar = "#" * min(int(pct), 60)
        print(f"    {rng}: {cnt:5d} ({pct:5.1f}%) {bar}")

    # Consecutive byte pair analysis (bigrams)
    print(f"\n  MOST COMMON BYTE PAIRS (bigrams) in section 0 events:")
    bigrams: Counter = Counter()
    for i in range(len(all_events) - 1):
        bigrams[(all_events[i], all_events[i + 1])] += 1

    for (b1, b2), cnt in bigrams.most_common(30):
        pct = cnt / (len(all_events) - 1) * 100
        print(f"    {b1:02X} {b2:02X}: {cnt:4d} ({pct:4.1f}%)")

    # Trigrams
    print(f"\n  MOST COMMON BYTE TRIPLETS (trigrams) in section 0 events:")
    trigrams: Counter = Counter()
    for i in range(len(all_events) - 2):
        trigrams[(all_events[i], all_events[i + 1], all_events[i + 2])] += 1

    for (b1, b2, b3), cnt in trigrams.most_common(20):
        pct = cnt / (len(all_events) - 2) * 100
        print(f"    {b1:02X} {b2:02X} {b3:02X}: {cnt:4d} ({pct:4.1f}%)")

    # ──────────────────────────────────────────────────────────────────────
    # PART 7: Bar Length Statistics
    # ──────────────────────────────────────────────────────────────────────
    print()
    print("=" * 90)
    print("PART 7: BAR LENGTH STATISTICS (all sections, all tracks)")
    print("=" * 90)

    bar_lengths_by_type: Dict[str, List[int]] = {"drum": [], "bass": [], "chord": []}

    for sec_idx in range(6):
        for track_idx in range(8):
            al = sec_idx * 8 + track_idx
            if al not in by_al:
                continue
            data = bytes(by_al[al])
            if len(data) <= 24:
                continue
            events = data[24:]
            bars = split_by_delimiter(events, 0xDC)
            ttype = TRACK_TYPES[track_idx]
            for bar in bars:
                bar_lengths_by_type[ttype].append(len(bar))

    for ttype in ["drum", "bass", "chord"]:
        lengths = bar_lengths_by_type[ttype]
        if not lengths:
            continue
        freq = Counter(lengths)
        print(f"\n  {ttype.upper()} tracks - bar lengths ({len(lengths)} total bars):")
        print(
            f"    Min: {min(lengths)}, Max: {max(lengths)}, Mean: {sum(lengths) / len(lengths):.1f}"
        )
        print(f"    Distribution:")
        for length, count in sorted(freq.items()):
            bar = "#" * min(count * 2, 60)
            print(f"      {length:4d} bytes: {count:3d}x {bar}")

    # ──────────────────────────────────────────────────────────────────────
    # PART 8: Interval / Delta Analysis
    # ──────────────────────────────────────────────────────────────────────
    print()
    print("=" * 90)
    print("PART 8: POSITION / DELTA ANALYSIS WITHIN BARS")
    print("=" * 90)
    print("  Hypothesis: if events are N bytes, byte[0] might be a delta time.")
    print("  Check if first bytes of N-byte groups sum to a consistent 'bar length'.")

    for track_idx in [0, 3, 4]:  # RHY1, BASS, CHD1
        al = track_idx
        if al not in by_al:
            continue
        data = bytes(by_al[al])
        if len(data) <= 24:
            continue
        events = data[24:]
        bars = split_by_delimiter(events, 0xDC)
        tname = TRACK_NAMES[track_idx]

        print(f"\n  Track {track_idx} ({tname}):")

        for evsize in [3, 4, 5, 6]:
            print(f"\n    Assuming {evsize}-byte events:")
            for bi, bar in enumerate(bars[:4]):
                if len(bar) < evsize:
                    continue
                evts = try_fixed_size_decode(bar, evsize)
                # Try different positions as delta
                for delta_pos in range(min(evsize, 3)):
                    deltas = [evt[delta_pos] for evt in evts]
                    total = sum(deltas)
                    print(
                        f"      Bar {bi}: byte[{delta_pos}] as delta -> "
                        f"sum={total} (0x{total:02X}), "
                        f"values={deltas[:16]}{'...' if len(deltas) > 16 else ''}"
                    )

    # ──────────────────────────────────────────────────────────────────────
    # PART 9: Trailing Data / Terminator Pattern
    # ──────────────────────────────────────────────────────────────────────
    print()
    print("=" * 90)
    print("PART 9: TERMINATOR AND TRAILING DATA PATTERNS")
    print("=" * 90)

    for track_idx in range(8):
        al = track_idx
        if al not in by_al:
            continue
        data = bytes(by_al[al])
        events = data[24:]
        tname = TRACK_NAMES[track_idx]

        # Look at last 32 bytes of event data
        tail = events[-32:] if len(events) >= 32 else events
        print(f"\n  Track {track_idx} ({tname}) - Last {len(tail)} bytes:")
        print(f"    {' '.join(f'{b:02X}' for b in tail)}")

        # Find the 00 terminator position
        term_pos = None
        for i in range(len(events) - 1, -1, -1):
            if events[i] != 0x00:
                term_pos = i + 1
                break
        if term_pos is not None:
            trailing_zeros = len(events) - term_pos
            print(
                f"    Last non-zero byte at offset {term_pos - 1}, "
                f"followed by {trailing_zeros} zero bytes"
            )
        else:
            print(f"    All zeros!")

        # Count DC delimiters
        dc_count = events.count(0xDC)
        print(f"    DC (0xDC) delimiter count: {dc_count}")
        dc_positions = [i for i, b in enumerate(events) if b == 0xDC]
        if dc_positions:
            print(f"    DC positions: {dc_positions}")
            if len(dc_positions) >= 2:
                spacings = [
                    dc_positions[i + 1] - dc_positions[i] for i in range(len(dc_positions) - 1)
                ]
                print(f"    DC spacings: {spacings}")

    print()
    print("=" * 90)
    print("ANALYSIS COMPLETE")
    print("=" * 90)


if __name__ == "__main__":
    main()
