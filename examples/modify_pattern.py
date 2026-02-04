#!/usr/bin/env python3
"""
Example: Modify pattern settings programmatically

Shows how to read, modify, and write pattern files.
"""

import sys

sys.path.insert(0, "..")

from pathlib import Path
import struct


def modify_q7p_tempo(input_file: str, output_file: str, new_tempo: float):
    """
    Modify the tempo of a Q7P pattern file.

    Args:
        input_file: Path to source Q7P file
        output_file: Path for output Q7P file
        new_tempo: New tempo in BPM (40-240)
    """
    # Read original file
    with open(input_file, "rb") as f:
        data = bytearray(f.read())

    if len(data) != 3072:
        raise ValueError(f"Invalid Q7P file size: {len(data)}")

    # Validate tempo
    if not 40 <= new_tempo <= 240:
        raise ValueError(f"Tempo must be 40-240 BPM, got {new_tempo}")

    # Tempo is stored at 0x188 as big-endian word, multiplied by 10
    tempo_value = int(new_tempo * 10)
    struct.pack_into(">H", data, 0x188, tempo_value)

    # Write modified file
    with open(output_file, "wb") as f:
        f.write(data)

    print(f"Modified tempo: {new_tempo} BPM")
    print(f"Saved to: {output_file}")


def modify_q7p_name(input_file: str, output_file: str, new_name: str):
    """
    Modify the pattern name of a Q7P file.

    Args:
        input_file: Path to source Q7P file
        output_file: Path for output Q7P file
        new_name: New pattern name (max 10 characters)
    """
    # Read original file
    with open(input_file, "rb") as f:
        data = bytearray(f.read())

    # Prepare name (uppercase, padded to 10 chars)
    name = new_name.upper()[:10].ljust(10)
    name_bytes = name.encode("ascii", errors="replace")

    # Template name is at 0x876 (10 bytes)
    data[0x876 : 0x876 + 10] = name_bytes

    # Write modified file
    with open(output_file, "wb") as f:
        f.write(data)

    print(f"Modified name: '{name}'")
    print(f"Saved to: {output_file}")


def modify_q7p_volume(input_file: str, output_file: str, track: int, volume: int):
    """
    Modify track volume in a Q7P file.

    Args:
        input_file: Path to source Q7P file
        output_file: Path for output Q7P file
        track: Track number (1-8)
        volume: New volume (0-127)
    """
    if not 1 <= track <= 8:
        raise ValueError("Track must be 1-8")
    if not 0 <= volume <= 127:
        raise ValueError("Volume must be 0-127")

    # Read original file
    with open(input_file, "rb") as f:
        data = bytearray(f.read())

    # Volume table starts at 0x226 (after 6-byte header at 0x220)
    volume_offset = 0x226 + (track - 1)
    old_volume = data[volume_offset]
    data[volume_offset] = volume

    # Write modified file
    with open(output_file, "wb") as f:
        f.write(data)

    print(f"Track {track} volume: {old_volume} -> {volume}")
    print(f"Saved to: {output_file}")


def main():
    input_file = "../tests/fixtures/T01.Q7P"
    output_file = "modified_pattern.Q7P"

    print("=== Modify Q7P Pattern ===")
    print()

    # Example 1: Change tempo
    print("1. Changing tempo to 140 BPM...")
    modify_q7p_tempo(input_file, output_file, 140)
    print()

    # Example 2: Change name (using the modified file)
    print("2. Changing name to 'MY STYLE'...")
    modify_q7p_name(output_file, output_file, "MY STYLE")
    print()

    # Example 3: Change track 1 volume
    print("3. Setting track 1 volume to 80...")
    modify_q7p_volume(output_file, output_file, 1, 80)
    print()

    # Verify changes
    print("=== Verifying Changes ===")
    from qyconv.analysis.q7p_analyzer import Q7PAnalyzer

    analyzer = Q7PAnalyzer()
    analysis = analyzer.analyze_file(output_file)

    print(f"Pattern Name: {analysis.pattern_name}")
    print(f"Tempo: {analysis.tempo} BPM")
    print(f"Track 1 Volume: {analysis.global_volumes[0]}")


if __name__ == "__main__":
    main()
