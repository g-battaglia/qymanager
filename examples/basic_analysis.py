#!/usr/bin/env python3
"""
Example: Basic pattern analysis

Shows how to use the Q7P analyzer to extract pattern information.
"""

import sys

sys.path.insert(0, "..")

from qymanager.analysis.q7p_analyzer import Q7PAnalyzer


def main():
    # Analyze a Q7P file
    analyzer = Q7PAnalyzer()
    analysis = analyzer.analyze_file("../tests/fixtures/T01.Q7P")

    # Basic info
    print(f"Pattern Name: {analysis.pattern_name}")
    print(f"Pattern Number: {analysis.pattern_number}")
    print(f"Tempo: {analysis.tempo} BPM")
    print(f"Time Signature: {analysis.time_signature[0]}/{analysis.time_signature[1]}")
    print(f"Valid: {analysis.valid}")
    print()

    # Sections
    print("Sections:")
    for section in analysis.sections:
        status = "Active" if section.enabled else "Empty"
        print(f"  {section.name}: {status} (pointer: {section.pointer_hex})")
    print()

    # Tracks (from first section)
    print("Tracks:")
    if analysis.sections:
        for track in analysis.sections[0].tracks:
            status = "On" if track.enabled else "Off"
            print(
                f"  {track.name}: Ch={track.channel} Vol={track.volume} Pan={track.pan} [{status}]"
            )
    print()

    # Data density
    print(f"Data Density: {analysis.data_density:.1f}%")

    # Hex dump of header
    print()
    print("Header raw bytes:")
    print(" ".join(f"{b:02X}" for b in analysis.header_raw))


if __name__ == "__main__":
    main()
