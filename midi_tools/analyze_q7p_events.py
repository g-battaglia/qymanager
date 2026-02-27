#!/usr/bin/env python3
"""
Q7P Event Data Format Analyzer

Compares Q7P (QY700) binary format with QY70 SysEx format.
Focuses on:
- Where phrase/sequence data lives in Q7P
- What event format Q7P uses (D0/E0/A0/BE/F2 commands?)
- Key structural differences vs QY70 SysEx
- Byte-by-byte comparison of T01 (data) vs TXX (empty template)

Usage:
    python3 midi_tools/analyze_q7p_events.py
"""

import struct
import sys
from pathlib import Path
from collections import Counter

# ─── File paths ───────────────────────────────────────────────────────────────
T01_PATH = Path("tests/fixtures/T01.Q7P")
TXX_PATH = Path("tests/fixtures/TXX.Q7P")
SYX_PATH = Path("tests/fixtures/QY70_SGT.syx")

# ─── Q7P offset tables (from q7p_analyzer.py) ────────────────────────────────
OFFSETS_3072 = {
    "HEADER": (0x000, 0x010, "File header magic"),
    "PATTERN_INFO": (0x010, 0x030, "Pattern number + flags"),
    "SIZE_MARKER": (0x030, 0x032, "Size marker word"),
    "RESERVED_1": (0x032, 0x100, "Reserved/unknown area 1"),
    "SECTION_PTRS": (0x100, 0x120, "Section pointers (6x2 bytes + padding)"),
    "SECTION_DATA": (0x120, 0x180, "Section encoded data (6x16 bytes)"),
    "TEMPO_AREA": (0x180, 0x190, "Tempo + time signature area"),
    "CHANNEL_CONFIG": (0x190, 0x1A0, "Channel assignments (16 tracks)"),
    "RESERVED_2": (0x1A0, 0x1DC, "Reserved/unknown area 2"),
    "TRACK_CONFIG": (0x1DC, 0x1E6, "Track numbering + flags"),
    "BANK_MSB": (0x1E6, 0x1F6, "Bank MSB (16 tracks)"),
    "PROGRAM": (0x1F6, 0x206, "Program number (16 tracks)"),
    "BANK_LSB": (0x206, 0x216, "Bank LSB (16 tracks)"),
    "RESERVED_3": (0x216, 0x220, "Reserved/unknown area 3"),
    "VOLUME_TABLE": (0x220, 0x250, "Volume table (header + 16 tracks x sections)"),
    "REVERB_TABLE": (0x250, 0x270, "Reverb send table"),
    "PAN_TABLE": (0x270, 0x2C0, "Pan table (header + 16 tracks x sections)"),
    "TABLE_3": (0x2C0, 0x360, "Unknown table 3 (chorus? variation?)"),
    "PHRASE_AREA": (0x360, 0x678, "Phrase data area (792 bytes)"),
    "SEQUENCE_AREA": (0x678, 0x870, "Sequence/event data area (504 bytes)"),
    "TEMPLATE_INFO": (0x870, 0x900, "Template name area"),
    "PATTERN_MAP": (0x900, 0x9C0, "Pattern mappings"),
    "FILL_AREA": (0x9C0, 0xB10, "Fill bytes (0xFE)"),
    "PAD_AREA": (0xB10, 0xC00, "Padding bytes (0xF8)"),
}

# ─── Known MIDI event commands (from phrase_parser.py) ────────────────────────
EVENT_COMMANDS = {
    0xD0: ("DRUM_NOTE", 4, "D0 nn vv xx - Drum note on"),
    0xE0: ("MELODY_NOTE", 4, "E0 nn vv xx - Melody note on"),
    0xC1: ("ALT_NOTE", 3, "C1 nn pp - Alternate note encoding"),
    0xA0: ("DELTA_A0", 2, "A0 dd - Delta time (step 0)"),
    0xA1: ("DELTA_A1", 2, "A1 dd - Delta time (step 1)"),
    0xA2: ("DELTA_A2", 2, "A2 dd - Delta time (step 2)"),
    0xA3: ("DELTA_A3", 2, "A3 dd - Delta time (step 3)"),
    0xA4: ("DELTA_A4", 2, "A4 dd - Delta time (step 4)"),
    0xA5: ("DELTA_A5", 2, "A5 dd - Delta time (step 5)"),
    0xA6: ("DELTA_A6", 2, "A6 dd - Delta time (step 6)"),
    0xA7: ("DELTA_A7", 2, "A7 dd - Delta time (step 7)"),
    0xBE: ("NOTE_OFF", 2, "BE xx - Note off / reset"),
    0xBC: ("CONTROL", 2, "BC xx - Control change"),
    0xF0: ("START_MARKER", 2, "F0 00 - Start of MIDI data"),
    0xF2: ("END_MARKER", 1, "F2 - End of phrase"),
}


def hex_dump(
    data: bytes, start_offset: int = 0, width: int = 16, max_lines: int = None, label: str = ""
) -> str:
    """Format a hex dump with offset, hex, and ASCII columns."""
    lines = []
    if label:
        lines.append(f"\n{'─' * 72}")
        lines.append(f"  {label}")
        lines.append(f"{'─' * 72}")

    count = 0
    for i in range(0, len(data), width):
        if max_lines and count >= max_lines:
            remaining = (len(data) - i) // width
            lines.append(f"  ... ({remaining} more lines, {len(data) - i} bytes remaining)")
            break
        chunk = data[i : i + width]
        hex_part = " ".join(f"{b:02X}" for b in chunk)
        ascii_part = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        lines.append(f"  {start_offset + i:04X}: {hex_part:<{width * 3}}  {ascii_part}")
        count += 1

    return "\n".join(lines)


def byte_stats(data: bytes, label: str = "") -> str:
    """Show byte value statistics for a region."""
    if not data:
        return f"  {label}: (empty)"

    counter = Counter(data)
    non_zero = sum(1 for b in data if b != 0x00)
    non_filler = sum(1 for b in data if b not in (0x00, 0xFE, 0xF8, 0x40, 0x20, 0x7F))

    lines = []
    if label:
        lines.append(f"  {label}:")
    lines.append(f"    Size: {len(data)} bytes")
    lines.append(f"    Non-zero: {non_zero}/{len(data)} ({100 * non_zero / len(data):.1f}%)")
    lines.append(f"    Non-filler: {non_filler}/{len(data)} ({100 * non_filler / len(data):.1f}%)")
    lines.append(f"    Unique values: {len(counter)}")

    # Top 10 byte values
    top = counter.most_common(10)
    lines.append(f"    Top values: {', '.join(f'0x{v:02X}={c}' for v, c in top)}")

    # Value range
    if non_zero:
        nz = [b for b in data if b != 0x00]
        lines.append(f"    Range (non-zero): 0x{min(nz):02X}-0x{max(nz):02X}")

    return "\n".join(lines)


def compare_regions(t01: bytes, txx: bytes, name: str, start: int, end: int) -> dict:
    """Compare a region between T01 and TXX, return diff info."""
    r1 = t01[start:end]
    r2 = txx[start:end]
    size = end - start
    diffs = sum(1 for a, b in zip(r1, r2) if a != b)
    return {
        "name": name,
        "start": start,
        "end": end,
        "size": size,
        "diffs": diffs,
        "pct": 100 * diffs / size if size > 0 else 0,
        "t01_data": r1,
        "txx_data": r2,
    }


def scan_for_events(data: bytes, label: str = "") -> dict:
    """Scan a data region for known Yamaha MIDI event command bytes."""
    results = {
        "total_bytes": len(data),
        "commands_found": Counter(),
        "events_parsed": [],
        "unknown_bytes": [],
    }

    pos = 0
    while pos < len(data):
        cmd = data[pos]

        # Skip pure padding
        if cmd == 0x40:
            pos += 1
            continue
        if cmd == 0x00:
            pos += 1
            continue

        if cmd in EVENT_COMMANDS:
            name, length, desc = EVENT_COMMANDS[cmd]
            if pos + length <= len(data):
                event_bytes = data[pos : pos + length]
                results["commands_found"][name] += 1
                results["events_parsed"].append((pos, name, event_bytes))
                pos += length
            else:
                results["unknown_bytes"].append((pos, cmd))
                pos += 1
        else:
            results["unknown_bytes"].append((pos, cmd))
            pos += 1

    return results


def analyze_phrase_substructure(data: bytes, start_offset: int, section_count: int = 6) -> str:
    """Try to detect sub-structure within the phrase area."""
    lines = []
    size = len(data)
    per_section = size // section_count if section_count > 0 else size

    lines.append(f"\n  Phrase area substructure analysis:")
    lines.append(f"    Total size: {size} bytes")
    lines.append(f"    If {section_count} sections: {per_section} bytes/section")
    lines.append(f"    If 16 tracks: {size // 16} bytes/track")
    lines.append(f"    If 6 sections x 16 tracks: {size // (6 * 16)} bytes per slot")

    # Look for repeating patterns
    lines.append(f"\n  Checking for repeating block boundaries:")
    for block_size in [80, 88, 96, 100, 112, 120, 128, 132, 176]:
        if size % block_size == 0:
            blocks = size // block_size
            lines.append(f"    {block_size}-byte blocks: {blocks} blocks (exact fit)")
        elif size > block_size:
            blocks = size // block_size
            remainder = size % block_size
            if remainder < 20:
                lines.append(
                    f"    {block_size}-byte blocks: {blocks} blocks + {remainder} remainder"
                )

    # Check for F0 00 markers (MIDI data start)
    f0_positions = []
    for i in range(len(data) - 1):
        if data[i] == 0xF0 and data[i + 1] == 0x00:
            f0_positions.append(i)
    if f0_positions:
        lines.append(
            f"\n  F0 00 (MIDI start) markers found at offsets: "
            f"{', '.join(f'0x{start_offset + p:04X}' for p in f0_positions)}"
        )

    # Check for F2 markers (end of phrase)
    f2_positions = [i for i, b in enumerate(data) if b == 0xF2]
    if f2_positions:
        lines.append(
            f"  F2 (end marker) found at offsets: "
            f"{', '.join(f'0x{start_offset + p:04X}' for p in f2_positions[:20])}"
        )
        if len(f2_positions) > 20:
            lines.append(f"    ... and {len(f2_positions) - 20} more")

    return "\n".join(lines)


def analyze_sysex_structure(syx_path: Path) -> str:
    """Analyze QY70 SysEx file structure for comparison."""
    lines = []

    if not syx_path.exists():
        return "  (SysEx file not found)"

    with open(syx_path, "rb") as f:
        syx_data = f.read()

    lines.append(f"\n  SysEx file: {syx_path.name}")
    lines.append(f"  Total size: {len(syx_data)} bytes")

    # Split into messages
    messages = []
    start = None
    for i, b in enumerate(syx_data):
        if b == 0xF0:
            start = i
        elif b == 0xF7 and start is not None:
            messages.append(syx_data[start : i + 1])
            start = None

    lines.append(f"  Message count: {len(messages)}")

    # Analyze messages
    section_msgs = {}
    for idx, msg in enumerate(messages):
        if len(msg) < 10:
            continue
        if msg[1] != 0x43:  # Not Yamaha
            continue
        if msg[3] != 0x5F:  # Not QY70
            continue

        dev_byte = msg[2]
        msg_type = dev_byte & 0xF0
        ah, am, al = msg[6], msg[7], msg[8]
        payload = msg[9:-2]
        data_size = len(payload)

        key = f"AH={ah:02X} AM={am:02X} AL={al:02X}"
        section_msgs.setdefault(key, []).append(
            {
                "index": idx,
                "type": "BULK" if msg_type == 0x00 else "PARAM",
                "payload_size": data_size,
                "raw_size": len(msg),
            }
        )

    lines.append(f"\n  Message groups by address:")
    for key, msgs in sorted(section_msgs.items()):
        total_payload = sum(m["payload_size"] for m in msgs)
        lines.append(
            f"    {key}: {len(msgs)} msg(s), "
            f"payload {total_payload} bytes (raw {sum(m['raw_size'] for m in msgs)})"
        )

    # Decode first style message to look for event commands
    lines.append(f"\n  Scanning SysEx payloads for Yamaha event commands:")
    total_events = Counter()
    for msg in messages:
        if len(msg) < 10:
            continue
        if msg[1] != 0x43 or msg[3] != 0x5F:
            continue
        payload = msg[9:-2]

        # Try 7-bit decode
        try:
            from qymanager.utils.yamaha_7bit import decode_7bit

            decoded = decode_7bit(payload)
        except Exception:
            decoded = payload

        scan = scan_for_events(decoded)
        for cmd, count in scan["commands_found"].items():
            total_events[cmd] += count

    if total_events:
        lines.append(f"    Event commands found across all messages:")
        for cmd, count in total_events.most_common():
            lines.append(f"      {cmd}: {count}")
    else:
        lines.append(f"    No known event commands found (may need different decoding)")

    return "\n".join(lines)


def main():
    print("=" * 78)
    print("  Q7P (QY700) EVENT DATA FORMAT ANALYZER")
    print("  Comparing Q7P binary format with QY70 SysEx format")
    print("=" * 78)

    # ─── Load files ───────────────────────────────────────────────────────
    if not T01_PATH.exists() or not TXX_PATH.exists():
        print(f"ERROR: Test fixtures not found. Run from project root.")
        sys.exit(1)

    t01 = T01_PATH.read_bytes()
    txx = TXX_PATH.read_bytes()

    print(f"\n  T01.Q7P: {len(t01)} bytes (pattern with data)")
    print(f"  TXX.Q7P: {len(txx)} bytes (empty template)")
    print(f"  Header T01: {t01[:16]}")
    print(f"  Header TXX: {txx[:16]}")

    # ═══════════════════════════════════════════════════════════════════════
    # SECTION 1: Region-by-region comparison T01 vs TXX
    # ═══════════════════════════════════════════════════════════════════════
    print("\n" + "=" * 78)
    print("  SECTION 1: REGION-BY-REGION COMPARISON (T01 vs TXX)")
    print("=" * 78)

    comparisons = []
    for name, (start, end, desc) in OFFSETS_3072.items():
        cmp = compare_regions(t01, txx, name, start, end)
        cmp["desc"] = desc
        comparisons.append(cmp)

    # Summary table
    print(f"\n  {'Region':<20} {'Offset':>12} {'Size':>6} {'Diffs':>6} {'%Diff':>7}  Description")
    print(f"  {'─' * 20} {'─' * 12} {'─' * 6} {'─' * 6} {'─' * 7}  {'─' * 25}")
    for c in comparisons:
        marker = "***" if c["diffs"] > 0 else "   "
        print(
            f"  {c['name']:<20} {c['start']:04X}-{c['end']:04X}   "
            f"{c['size']:>5} {c['diffs']:>5}  {c['pct']:>5.1f}%  {c['desc']} {marker}"
        )

    # ═══════════════════════════════════════════════════════════════════════
    # SECTION 2: Hex dumps of key regions that DIFFER
    # ═══════════════════════════════════════════════════════════════════════
    print("\n" + "=" * 78)
    print("  SECTION 2: HEX DUMPS OF REGIONS WITH DIFFERENCES")
    print("=" * 78)

    for c in comparisons:
        if c["diffs"] > 0:
            print(hex_dump(c["t01_data"], c["start"], label=f"T01 {c['name']} ({c['desc']})"))
            print(hex_dump(c["txx_data"], c["start"], label=f"TXX {c['name']} ({c['desc']})"))

            # Show specific byte differences
            diff_positions = []
            for i, (a, b) in enumerate(zip(c["t01_data"], c["txx_data"])):
                if a != b:
                    diff_positions.append((c["start"] + i, a, b))

            if len(diff_positions) <= 40:
                print(f"\n  Byte differences ({len(diff_positions)}):")
                for off, a, b in diff_positions:
                    print(
                        f"    0x{off:04X}: T01=0x{a:02X} TXX=0x{b:02X}  "
                        f"(T01={a:3d} TXX={b:3d}  "
                        f"T01='{chr(a) if 32 <= a < 127 else '.'}' "
                        f"TXX='{chr(b) if 32 <= b < 127 else '.'}')"
                    )
            else:
                print(f"\n  {len(diff_positions)} byte differences (showing first 20):")
                for off, a, b in diff_positions[:20]:
                    print(f"    0x{off:04X}: T01=0x{a:02X} TXX=0x{b:02X}")
                print(f"    ... and {len(diff_positions) - 20} more")

    # ═══════════════════════════════════════════════════════════════════════
    # SECTION 3: Deep analysis of PHRASE area (0x360-0x678)
    # ═══════════════════════════════════════════════════════════════════════
    print("\n" + "=" * 78)
    print("  SECTION 3: PHRASE AREA DEEP ANALYSIS (0x360-0x678)")
    print("=" * 78)

    phrase_t01 = t01[0x360:0x678]
    phrase_txx = txx[0x360:0x678]

    print(byte_stats(phrase_t01, "T01 Phrase Area"))
    print(byte_stats(phrase_txx, "TXX Phrase Area"))

    print(analyze_phrase_substructure(phrase_t01, 0x360, 6))

    # Scan for event commands
    print(f"\n  Scanning T01 Phrase Area for Yamaha event commands:")
    scan_phrase = scan_for_events(phrase_t01)
    if scan_phrase["commands_found"]:
        for cmd, count in scan_phrase["commands_found"].most_common():
            print(f"    {cmd}: {count}")
        print(f"\n  Parsed events ({len(scan_phrase['events_parsed'])}):")
        for pos, name, raw in scan_phrase["events_parsed"][:30]:
            hex_str = " ".join(f"{b:02X}" for b in raw)
            print(f"    0x{0x360 + pos:04X}: {name:<15} {hex_str}")
        if len(scan_phrase["events_parsed"]) > 30:
            print(f"    ... and {len(scan_phrase['events_parsed']) - 30} more")
    else:
        print(f"    No known event commands found in phrase area")

    # Show unknown bytes
    if scan_phrase["unknown_bytes"]:
        unk_values = Counter(v for _, v in scan_phrase["unknown_bytes"])
        print(
            f"\n  Unknown/non-event byte values in phrase area ({len(scan_phrase['unknown_bytes'])} bytes):"
        )
        for val, count in unk_values.most_common(20):
            print(f"    0x{val:02X} ({val:3d}): {count} occurrences")

    # Full hex dump of phrase area (T01 only, where data lives)
    print(hex_dump(phrase_t01, 0x360, label="T01 FULL Phrase Area Hex Dump"))

    # ═══════════════════════════════════════════════════════════════════════
    # SECTION 4: Deep analysis of SEQUENCE area (0x678-0x870)
    # ═══════════════════════════════════════════════════════════════════════
    print("\n" + "=" * 78)
    print("  SECTION 4: SEQUENCE AREA DEEP ANALYSIS (0x678-0x870)")
    print("=" * 78)

    seq_t01 = t01[0x678:0x870]
    seq_txx = txx[0x678:0x870]

    print(byte_stats(seq_t01, "T01 Sequence Area"))
    print(byte_stats(seq_txx, "TXX Sequence Area"))

    # Scan for event commands in sequence area
    print(f"\n  Scanning T01 Sequence Area for Yamaha event commands:")
    scan_seq = scan_for_events(seq_t01)
    if scan_seq["commands_found"]:
        for cmd, count in scan_seq["commands_found"].most_common():
            print(f"    {cmd}: {count}")
        print(f"\n  Parsed events ({len(scan_seq['events_parsed'])}):")
        for pos, name, raw in scan_seq["events_parsed"][:50]:
            hex_str = " ".join(f"{b:02X}" for b in raw)
            print(f"    0x{0x678 + pos:04X}: {name:<15} {hex_str}")
        if len(scan_seq["events_parsed"]) > 50:
            print(f"    ... and {len(scan_seq['events_parsed']) - 50} more")
    else:
        print(f"    No known event commands found in sequence area")

    # Unknown bytes in sequence
    if scan_seq["unknown_bytes"]:
        unk_values = Counter(v for _, v in scan_seq["unknown_bytes"])
        print(
            f"\n  Unknown/non-event byte values in sequence area ({len(scan_seq['unknown_bytes'])} bytes):"
        )
        for val, count in unk_values.most_common(20):
            print(f"    0x{val:02X} ({val:3d}): {count} occurrences")

    # Full hex dump
    print(hex_dump(seq_t01, 0x678, label="T01 FULL Sequence Area Hex Dump"))

    # ═══════════════════════════════════════════════════════════════════════
    # SECTION 5: Scan the ENTIRE T01 file for event commands
    # ═══════════════════════════════════════════════════════════════════════
    print("\n" + "=" * 78)
    print("  SECTION 5: FULL FILE EVENT COMMAND SCAN")
    print("=" * 78)

    print(f"\n  Scanning entire T01.Q7P ({len(t01)} bytes) for event commands:")

    # Scan in 256-byte windows to localize where events appear
    window = 256
    for offset in range(0, len(t01), window):
        chunk = t01[offset : offset + window]
        scan = scan_for_events(chunk)
        if scan["commands_found"]:
            cmds = ", ".join(f"{c}={n}" for c, n in scan["commands_found"].most_common())
            print(f"    0x{offset:04X}-0x{offset + window:04X}: {cmds}")

    # ═══════════════════════════════════════════════════════════════════════
    # SECTION 6: Track parameter regions (voice, volume, pan, reverb)
    # ═══════════════════════════════════════════════════════════════════════
    print("\n" + "=" * 78)
    print("  SECTION 6: TRACK PARAMETER REGIONS")
    print("=" * 78)

    # Channel config
    ch_t01 = t01[0x190:0x1A0]
    ch_txx = txx[0x190:0x1A0]
    print(hex_dump(ch_t01, 0x190, label="T01 Channel Config (0x190)"))
    print(hex_dump(ch_txx, 0x190, label="TXX Channel Config (0x190)"))

    # Bank MSB
    print(hex_dump(t01[0x1E6:0x1F6], 0x1E6, label="T01 Bank MSB (0x1E6)"))
    print(hex_dump(txx[0x1E6:0x1F6], 0x1E6, label="TXX Bank MSB (0x1E6)"))

    # Program
    print(hex_dump(t01[0x1F6:0x206], 0x1F6, label="T01 Program (0x1F6)"))
    print(hex_dump(txx[0x1F6:0x206], 0x1F6, label="TXX Program (0x1F6)"))

    # Bank LSB
    print(hex_dump(t01[0x206:0x216], 0x206, label="T01 Bank LSB (0x206)"))
    print(hex_dump(txx[0x206:0x216], 0x206, label="TXX Bank LSB (0x206)"))

    # Volume
    print(hex_dump(t01[0x220:0x250], 0x220, label="T01 Volume Table (0x220)"))
    print(hex_dump(txx[0x220:0x250], 0x220, label="TXX Volume Table (0x220)"))

    # Reverb
    print(hex_dump(t01[0x250:0x270], 0x250, label="T01 Reverb Table (0x250)"))
    print(hex_dump(txx[0x250:0x270], 0x250, label="TXX Reverb Table (0x250)"))

    # Pan
    print(hex_dump(t01[0x270:0x2C0], 0x270, label="T01 Pan Table (0x270)"))
    print(hex_dump(txx[0x270:0x2C0], 0x270, label="TXX Pan Table (0x270)"))

    # Table 3 (chorus/variation?)
    print(hex_dump(t01[0x2C0:0x360], 0x2C0, label="T01 Table 3 / Unknown (0x2C0)"))
    print(hex_dump(txx[0x2C0:0x360], 0x2C0, label="TXX Table 3 / Unknown (0x2C0)"))

    # ═══════════════════════════════════════════════════════════════════════
    # SECTION 7: Section pointers + section data
    # ═══════════════════════════════════════════════════════════════════════
    print("\n" + "=" * 78)
    print("  SECTION 7: SECTION POINTERS AND DATA")
    print("=" * 78)

    SECTION_NAMES = ["Intro", "Main A", "Main B", "Fill AB", "Fill BA", "Ending"]

    print(f"\n  Section pointer analysis:")
    for i in range(6):
        ptr_off = 0x100 + i * 2
        t01_ptr = struct.unpack(">H", t01[ptr_off : ptr_off + 2])[0]
        txx_ptr = struct.unpack(">H", txx[ptr_off : ptr_off + 2])[0]
        t01_hex = t01[ptr_off : ptr_off + 2].hex().upper()
        txx_hex = txx[ptr_off : ptr_off + 2].hex().upper()
        t01_empty = "EMPTY" if t01_ptr == 0xFEFE else f"0x{t01_ptr:04X}"
        txx_empty = "EMPTY" if txx_ptr == 0xFEFE else f"0x{txx_ptr:04X}"
        marker = " ***" if t01_hex != txx_hex else ""
        print(
            f"    Section {i} ({SECTION_NAMES[i]:>8}): "
            f"T01={t01_hex} ({t01_empty})  TXX={txx_hex} ({txx_empty}){marker}"
        )

    # Remaining pointer bytes
    print(f"\n  Remaining pointer area (0x10C-0x120):")
    print(hex_dump(t01[0x10C:0x120], 0x10C, label="T01 Ptr area tail"))
    print(hex_dump(txx[0x10C:0x120], 0x10C, label="TXX Ptr area tail"))

    # Section encoded data
    print(f"\n  Section encoded data (0x120-0x180):")
    for i in range(6):
        off = 0x120 + i * 16
        t01_sec = t01[off : off + 16]
        txx_sec = txx[off : off + 16]
        diff = "SAME" if t01_sec == txx_sec else "DIFF ***"
        print(f"    Section {i} ({SECTION_NAMES[i]:>8}):")
        print(f"      T01: {' '.join(f'{b:02X}' for b in t01_sec)}  [{diff}]")
        print(f"      TXX: {' '.join(f'{b:02X}' for b in txx_sec)}")

    # ═══════════════════════════════════════════════════════════════════════
    # SECTION 8: Template/pattern name area
    # ═══════════════════════════════════════════════════════════════════════
    print("\n" + "=" * 78)
    print("  SECTION 8: TEMPLATE/PATTERN NAME AND MAPPING")
    print("=" * 78)

    print(hex_dump(t01[0x870:0x900], 0x870, label="T01 Template Info (0x870-0x900)"))
    print(hex_dump(txx[0x870:0x900], 0x870, label="TXX Template Info (0x870-0x900)"))

    # Pattern mapping
    print(hex_dump(t01[0x900:0x9C0], 0x900, label="T01 Pattern Mapping (0x900-0x9C0)"))
    print(hex_dump(txx[0x900:0x9C0], 0x900, label="TXX Pattern Mapping (0x900-0x9C0)"))

    # ═══════════════════════════════════════════════════════════════════════
    # SECTION 9: QY70 SysEx comparison
    # ═══════════════════════════════════════════════════════════════════════
    print("\n" + "=" * 78)
    print("  SECTION 9: QY70 SYSEX FORMAT COMPARISON")
    print("=" * 78)

    print(analyze_sysex_structure(SYX_PATH))

    # ═══════════════════════════════════════════════════════════════════════
    # SECTION 10: FORMAT COMPARISON SUMMARY
    # ═══════════════════════════════════════════════════════════════════════
    print("\n" + "=" * 78)
    print("  SECTION 10: FORMAT COMPARISON SUMMARY")
    print("=" * 78)

    print("""
  ┌──────────────────────┬──────────────────────────────┬──────────────────────────────┐
  │ Feature              │ Q7P (QY700)                  │ QY70 SysEx                   │
  ├──────────────────────┼──────────────────────────────┼──────────────────────────────┤
  │ Container            │ Fixed-size binary (.Q7P)     │ SysEx messages (.syx)        │
  │ File sizes           │ 3072 or 5120 bytes           │ Variable (16KB+ typical)     │
  │ Byte width           │ 8-bit native                 │ 7-bit packed (SysEx limit)   │
  │ Header               │ "YQ7PAT     V1.00" (16b)    │ F0 43 0n 5F ... F7           │
  │ Sections             │ 6 (or 12 in 5120b)          │ 6 (AL=0x00-0x05)             │
  │ Section enable       │ 0xFEFE = empty pointer       │ Presence of message          │
  │ Tracks               │ 16 per pattern               │ 8 per section (style)        │
  │ Tempo encoding       │ BPM * 10, big-endian word    │ In header data (varies)      │
  │ Channel config       │ 16 bytes at 0x190            │ Per-track in section data     │
  │ Volume               │ Table at 0x226               │ In decoded track data         │
  │ Pan                  │ Table at 0x276               │ In decoded track data         │
  │ Reverb send          │ Table at 0x256               │ In decoded track data         │
  │ Voice selection      │ Bank MSB/LSB + Program       │ Bank MSB/LSB + Program       │
  │ Event commands       │ D0/E0/A0-A7/BE/F2 (Q7P)     │ Packed bitstream (DIFFERENT) │
  │ MIDI start marker    │ F0 00                        │ N/A (different format)       │
  │ Phrase end marker    │ F2                           │ N/A (different format)       │
  │ Padding byte         │ 0x40                         │ 0x40                         │
  │ Phrase area (3072b)  │ 0x360-0x678 (792 bytes)      │ Per-section in SysEx msgs    │
  │ Sequence area        │ 0x678-0x870 (504 bytes)      │ Inline in phrase data        │
  │ Name location        │ 0x876 (template name)        │ In style header (AL=0x7F)    │
  └──────────────────────┴──────────────────────────────┴──────────────────────────────┘

  KNOWN MAPPINGS (confirmed):
    - Header/magic identification
    - Tempo (BPM * 10 big-endian)
    - Section pointer system (enable/disable)
    - Channel assignments (0x190)
    - Volume table (0x226)
    - Pan table (0x276)
    - Reverb send table (0x256)
    - Bank MSB/LSB + Program (voice selection)
    - Template/pattern name (0x876)
    - Event command set: Q7P only (D0/E0/A0-A7/BE/BC/F0/F2) — QY70 uses DIFFERENT packed bitstream

  PARTIALLY MAPPED (needs verification):
    - Section encoded data (0x120-0x180): structure unclear
    - Table 3 (0x2C0-0x360): likely chorus/variation send
    - Pattern mappings (0x900-0x9C0): purpose unclear
    - Track flags at 0x1E4: bit encoding

  UNMAPPED / UNKNOWN:
    - Reserved area 0x032-0x0FF (206 bytes)
    - Reserved area 0x1A0-0x1DC (60 bytes)
    - Reserved area 0x216-0x220 (10 bytes)
    - Phrase area internal sub-structure (which bytes = which section/track)
    - Sequence area internal format (event ordering, track interleaving)
    - Fill area purpose (0x9C0-0xB10, all 0xFE)
    - Padding area purpose (0xB10-0xC00, all 0xF8)
""")

    # ═══════════════════════════════════════════════════════════════════════
    # SECTION 11: Detailed diff of non-trivial regions
    # ═══════════════════════════════════════════════════════════════════════
    print("\n" + "=" * 78)
    print("  SECTION 11: T01 vs TXX - FULL BYTE DIFF SUMMARY")
    print("=" * 78)

    total_diffs = 0
    for i in range(len(t01)):
        if t01[i] != txx[i]:
            total_diffs += 1

    print(
        f"\n  Total differing bytes: {total_diffs} / {len(t01)} "
        f"({100 * total_diffs / len(t01):.1f}%)"
    )

    # Group diffs into runs
    print(f"\n  Diff runs (contiguous differing regions):")
    in_diff = False
    run_start = 0
    runs = []
    for i in range(len(t01)):
        if t01[i] != txx[i]:
            if not in_diff:
                run_start = i
                in_diff = True
        else:
            if in_diff:
                runs.append((run_start, i))
                in_diff = False
    if in_diff:
        runs.append((run_start, len(t01)))

    for start, end in runs:
        size = end - start
        # Find which named region this falls in
        region = "???"
        for name, (rstart, rend, desc) in OFFSETS_3072.items():
            if start >= rstart and start < rend:
                region = name
                break
        print(f"    0x{start:04X}-0x{end:04X}: {size:4d} bytes  [{region}]")

    print(f"\n  Total diff runs: {len(runs)}")
    print(f"  Total differing bytes: {total_diffs}")

    print("\n" + "=" * 78)
    print("  ANALYSIS COMPLETE")
    print("=" * 78)


if __name__ == "__main__":
    main()
