#!/usr/bin/env python3
"""
Example: Hex dump and raw data inspection

Shows how to extract and display raw binary data from pattern files.
"""

import sys

sys.path.insert(0, "..")

from pathlib import Path
from qymanager.analysis.q7p_analyzer import Q7PAnalyzer


def hex_dump(data: bytes, start_offset: int = 0, bytes_per_line: int = 16) -> str:
    """Create formatted hex dump."""
    lines = []
    for i in range(0, len(data), bytes_per_line):
        chunk = data[i : i + bytes_per_line]

        # Hex part with space at midpoint
        hex_parts = []
        for j, b in enumerate(chunk):
            if j == 8:
                hex_parts.append(" ")
            hex_parts.append(f"{b:02X}")
        hex_str = " ".join(hex_parts)

        # ASCII part
        ascii_str = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)

        lines.append(f"{start_offset + i:08X}  {hex_str:<{bytes_per_line * 3 + 2}}  {ascii_str}")

    return "\n".join(lines)


def main():
    # Load Q7P file
    filepath = Path("../tests/fixtures/T01.Q7P")

    with open(filepath, "rb") as f:
        data = f.read()

    print(f"=== Q7P Raw Data Inspection: {filepath.name} ===")
    print(f"File size: {len(data)} bytes")
    print()

    # Key areas
    areas = [
        ("Header", 0x000, 16),
        ("Pattern Info", 0x010, 32),
        ("Size Marker", 0x030, 16),
        ("Section Pointers", 0x100, 32),
        ("Section Encoded Data", 0x120, 96),
        ("Tempo Area", 0x180, 16),
        ("Channel Config", 0x190, 16),
        ("Track Config", 0x1DC, 20),
        ("Volume Table", 0x220, 48),
        ("Pan Table", 0x270, 16),
        ("Template Name", 0x870, 16),
    ]

    for name, offset, size in areas:
        area_data = data[offset : offset + size]
        print(f"--- {name} (0x{offset:03X} - 0x{offset + size - 1:03X}) ---")
        print(hex_dump(area_data, offset))
        print()

    # Analyze specific bytes
    print("=== Interpreted Values ===")

    # Pattern number
    print(f"Pattern Number: {data[0x010]}")

    # Tempo (big-endian word at 0x188, divided by 10)
    tempo_raw = (data[0x188] << 8) | data[0x189]
    print(f"Tempo Raw: 0x{tempo_raw:04X} = {tempo_raw} -> {tempo_raw / 10} BPM")

    # Template name
    name = data[0x876:0x880].decode("ascii", errors="replace").rstrip("\x00 ")
    print(f"Template Name: '{name}'")

    # Track flags
    track_flags = (data[0x1E4] << 8) | data[0x1E5]
    print(f"Track Flags: 0x{track_flags:04X} = {bin(track_flags)}")
    for i in range(8):
        enabled = bool(track_flags & (1 << i))
        print(f"  Track {i + 1}: {'Enabled' if enabled else 'Disabled'}")


if __name__ == "__main__":
    main()
