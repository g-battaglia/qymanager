#!/usr/bin/env python3
"""Analyze Q7P Sequence Events area (0x678-0x870) in 3072-byte files.

Session 18 discovery: the actual musical data in 3072-byte Q7P files
lives in the Sequence Events area, NOT in the Phrase Data area (0x360-0x677).
The 5120-byte D0/E0 command format does NOT apply.

Structure:
  0x678-0x6A7  Config header (48 bytes)
  0x6C6-0x6E5  Velocity LUT 1 (32 × 0x64)
  0x716-0x755  Velocity LUT 2 (64 × 0x64)
  0x756-0x7D5  Event data — 16 groups × 8 bytes (128 bytes)
  0x7D6-0x815  Velocity LUT 3 (64 × 0x64)
  0x856-0x865  Track flags (16 × 0x03)

Event data is organized as 16 groups of 8 bytes each:
  Groups 0-7:  Sequence pattern (commands 0x83/0x84/0x88 + note data)
  Groups 8-15: Note table (per-instrument note palette, 0x7F = inactive)

Usage:
    python3 midi_tools/q7p_sequence_analyzer.py tests/fixtures/T01.Q7P
    python3 midi_tools/q7p_sequence_analyzer.py tests/fixtures/TXX.Q7P
"""

import sys
import struct
from pathlib import Path

GM_DRUMS = {
    24: "Kick2", 25: "Kick3", 26: "SnrRoll", 27: "FngrSnp", 28: "HiQ",
    29: "Slap", 31: "Sticks", 33: "Metrnme", 34: "BD2/MetBl",
    35: "Kick2b", 36: "Kick1", 37: "SideStk", 38: "Snare1", 39: "Clap",
    40: "Snare2", 41: "LowTom2", 42: "HHclose", 43: "LowTom1",
    44: "HHpedal", 45: "MidTom2", 46: "HHopen", 47: "MidTom1",
    48: "HiTom2", 49: "Crash1", 50: "HiTom1", 51: "Ride1",
    52: "Chinese", 53: "RideBel", 54: "Tamb", 56: "Cowbell",
    57: "Crash2", 59: "Ride2", 62: "MuHiCng", 63: "OpHiCng",
    64: "LoConHi", 65: "HiTimba", 66: "LoTimba", 69: "Cabasa",
    70: "Maracas", 75: "Claves", 82: "Shaker",
}

CMD_NAMES = {
    0x83: "NOTE_GROUP",
    0x84: "TIMING",
    0x88: "SECTION_END",
    0x87: "SECTION_CFG",
    0x82: "UNKNOWN_82",
}


def analyze_q7p(filepath):
    data = Path(filepath).read_bytes()
    if len(data) != 3072:
        print(f"WARNING: Expected 3072 bytes, got {len(data)}")

    # Header
    magic = data[0:16].decode("ascii", errors="replace")
    pat_num = data[0x10]
    tempo_raw = struct.unpack(">H", data[0x188:0x18A])[0]
    tempo = tempo_raw / 10.0
    name = data[0x876:0x880].decode("ascii", errors="replace").strip()

    print(f"{'='*70}")
    print(f"  Q7P Sequence Analyzer: {filepath}")
    print(f"{'='*70}")
    print(f"  Magic:   {magic.strip()}")
    print(f"  Name:    '{name}'")
    print(f"  Pattern: #{pat_num}")
    print(f"  Tempo:   {tempo} BPM")
    print()

    # Section pointers
    print("  Section Pointers (0x100):")
    sections = []
    for i in range(8):
        ptr = struct.unpack(">H", data[0x100 + i * 2 : 0x102 + i * 2])[0]
        if ptr != 0xFEFE:
            eff = ptr + 0x100
            sections.append((i, ptr, eff))
            # Read section config (9 bytes)
            cfg = data[eff : eff + 9]
            bars = cfg[7] if len(cfg) > 7 else 0
            phrase = cfg[3] if len(cfg) > 3 else 0
            track = cfg[5] if len(cfg) > 5 else 0
            print(
                f"    S{i}: ptr=0x{ptr:04X} → 0x{eff:03X}  "
                f"phrase={phrase} track={track} bars={bars}  "
                f"cfg=[{' '.join(f'{b:02X}' for b in cfg)}]"
            )
        else:
            print(f"    S{i}: empty")
    print()

    # Velocity LUT blocks
    print("  Velocity LUT Blocks:")
    vel_blocks = []
    in_run = False
    run_start = 0
    for i in range(0x6A8, 0x870):
        if data[i] == 0x64:
            if not in_run:
                run_start = i
                in_run = True
        else:
            if in_run:
                run_len = i - run_start
                if run_len >= 4:
                    vel_blocks.append((run_start, i - 1, run_len))
                    print(f"    0x{run_start:03X}-0x{i - 1:03X}: {run_len} bytes (vel=100)")
                in_run = False
    if in_run:
        run_len = 0x870 - run_start
        if run_len >= 4:
            vel_blocks.append((run_start, 0x86F, run_len))
            print(f"    0x{run_start:03X}-0x{0x86F:03X}: {run_len} bytes (vel=100)")
    print()

    # Config header
    print("  Config Header (0x678-0x6A7):")
    for i in range(0x678, 0x6A8, 16):
        end = min(i + 16, 0x6A8)
        vals = data[i:end]
        hex_str = " ".join(f"{b:02X}" for b in vals)
        print(f"    0x{i:03X}: {hex_str}")
    print()

    # Event data — 16 groups × 8 bytes
    print("  Event Data (0x756-0x7D5) — 16 × 8 byte groups:")
    print()
    groups = []
    for g in range(16):
        offset = 0x756 + g * 8
        group = list(data[offset : offset + 8])
        groups.append(group)

    # Print as grid
    label = "     "
    for g in range(16):
        label += f" G{g:X}   "
    print(label)
    print("     " + "-" * (16 * 6))
    for row in range(8):
        cells = []
        for g in range(16):
            b = groups[g][row]
            if b == 0x7F:
                cells.append("  .  ")
            elif b >= 0x80:
                name = CMD_NAMES.get(b, f"*{b:02X}")
                cells.append(f"{name[:5]:>5s}")
            else:
                name = GM_DRUMS.get(b, f"x{b:02X}")
                cells.append(f"{name[:5]:>5s}")
        print(f" R{row}:  " + " ".join(cells))
    print()

    # Sequence area analysis (G0-G7)
    print("  === SEQUENCE AREA (Groups 0-7) ===")
    for g in range(8):
        vals = groups[g]
        non_pad = [(i, v) for i, v in enumerate(vals) if v != 0x7F]
        cmds = [(i, v) for i, v in non_pad if v >= 0x80]
        notes = [(i, v) for i, v in non_pad if v < 0x80]

        cmd_str = ", ".join(f"{CMD_NAMES.get(v, f'0x{v:02X}')}@{i}" for i, v in cmds)
        note_str = ", ".join(
            f"{GM_DRUMS.get(v, f'n{v}')}({v})@{i}" for i, v in notes
        )
        print(f"    G{g}: cmds=[{cmd_str}]  notes=[{note_str}]")
    print()

    # Note table analysis (G8-GF)
    print("  === NOTE TABLE (Groups 8-15) ===")
    print("  Per-instrument note palette (0x7F = inactive slot)")
    print()
    for g in range(8, 16):
        vals = groups[g]
        active = [(i, v) for i, v in enumerate(vals) if v != 0x7F]
        if not active:
            print(f"    G{g:X}: (empty)")
            continue

        notes = [v for _, v in active]
        primary = max(set(notes), key=notes.count)
        variants = sorted(set(notes) - {primary})
        primary_name = GM_DRUMS.get(primary, f"n{primary}")
        var_names = [GM_DRUMS.get(v, f"n{v}") for v in variants]

        print(
            f"    G{g:X}: primary={primary_name}({primary})  "
            f"variants={var_names}  "
            f"active_slots={[i for i, _ in active]}"
        )
    print()

    # Command byte statistics
    print("  === COMMAND BYTE SUMMARY ===")
    cmd_counts = {}
    for g in range(8):
        for b in groups[g]:
            if b >= 0x80 and b != 0x7F:
                cmd_counts[b] = cmd_counts.get(b, 0) + 1
    for cmd in sorted(cmd_counts):
        name = CMD_NAMES.get(cmd, "UNKNOWN")
        print(f"    0x{cmd:02X} ({name}): {cmd_counts[cmd]}×")

    # Track flags (0x856-0x865)
    print()
    flags = data[0x856:0x866]
    non_zero = sum(1 for b in flags if b != 0)
    if non_zero:
        unique = set(flags)
        print(f"  Track Flags (0x856): {' '.join(f'{b:02X}' for b in flags)}")
        print(f"    Unique values: {sorted(unique)}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 midi_tools/q7p_sequence_analyzer.py <file.Q7P>")
        print()
        # Default: analyze both test fixtures
        for f in ["tests/fixtures/T01.Q7P", "tests/fixtures/TXX.Q7P"]:
            p = Path(f)
            if p.exists():
                analyze_q7p(f)
                print()
        return

    for f in sys.argv[1:]:
        analyze_q7p(f)
        print()


if __name__ == "__main__":
    main()
