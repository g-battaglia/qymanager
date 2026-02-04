#!/usr/bin/env python3
"""
Example: Analyze QY70 SysEx file structure

Shows detailed breakdown of SysEx messages and section data.
"""

import sys

sys.path.insert(0, "..")

from qyconv.analysis.syx_analyzer import SyxAnalyzer


def main():
    # Analyze a SysEx file
    analyzer = SyxAnalyzer()
    analysis = analyzer.analyze_file("../tests/fixtures/QY70_SGT.syx")

    # Basic stats
    print("=== QY70 SysEx Analysis ===")
    print(f"File: {analysis.filepath}")
    print(f"Size: {analysis.filesize} bytes")
    print(f"Valid: {analysis.valid}")
    print()

    # Message statistics
    print("Message Statistics:")
    print(f"  Total messages: {analysis.total_messages}")
    print(f"  Bulk dump messages: {analysis.bulk_dump_messages}")
    print(f"  Parameter messages: {analysis.parameter_messages}")
    print(f"  Style data messages: {analysis.style_data_messages}")
    print(f"  Valid checksums: {analysis.valid_checksums}")
    print(f"  Invalid checksums: {analysis.invalid_checksums}")
    print()

    # Data sizes
    print("Data Sizes:")
    print(f"  Total encoded bytes: {analysis.total_encoded_bytes}")
    print(f"  Total decoded bytes: {analysis.total_decoded_bytes}")
    print()

    # Section summary
    print("Sections by AL Address:")
    print("-" * 60)
    for al, name, size in analysis.section_summary:
        section = analysis.sections[al]
        density = (section.non_zero_bytes / size * 100) if size > 0 else 0
        print(f"  0x{al:02X} {name:25} {size:5} bytes ({density:.0f}% used)")

    # Header section details
    if 0x7F in analysis.sections:
        print()
        print("Header Section (0x7F) first 64 bytes:")
        header = analysis.sections[0x7F].decoded_data[:64]
        for i in range(0, len(header), 16):
            chunk = header[i : i + 16]
            hex_str = " ".join(f"{b:02X}" for b in chunk)
            ascii_str = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
            print(f"  {i:04X}: {hex_str:<48} {ascii_str}")


if __name__ == "__main__":
    main()
