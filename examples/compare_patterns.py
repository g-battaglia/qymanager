#!/usr/bin/env python3
"""
Example: Compare two Q7P pattern files

Shows differences between pattern configurations.
"""

import sys

sys.path.insert(0, "..")

from qyconv.analysis.q7p_analyzer import Q7PAnalyzer


def compare_patterns(file1: str, file2: str):
    """Compare two Q7P files and show differences."""

    analyzer = Q7PAnalyzer()

    a1 = analyzer.analyze_file(file1)
    a2 = analyzer.analyze_file(file2)

    print(f"=== Comparing Q7P Files ===")
    print(f"File 1: {a1.filepath}")
    print(f"File 2: {a2.filepath}")
    print()

    # Compare basic info
    print("Basic Info:")
    _compare("Pattern Name", a1.pattern_name, a2.pattern_name)
    _compare("Pattern Number", a1.pattern_number, a2.pattern_number)
    _compare("Tempo", a1.tempo, a2.tempo)
    _compare("Pattern Flags", f"0x{a1.pattern_flags:02X}", f"0x{a2.pattern_flags:02X}")
    print()

    # Compare sections
    print("Sections:")
    for i, (s1, s2) in enumerate(zip(a1.sections, a2.sections)):
        if s1.enabled != s2.enabled:
            print(f"  {s1.name}: {_status(s1.enabled)} -> {_status(s2.enabled)}")
        elif s1.pointer != s2.pointer:
            print(f"  {s1.name}: pointer {s1.pointer_hex} -> {s2.pointer_hex}")
    print()

    # Compare tracks
    print("Tracks:")
    if a1.sections and a2.sections:
        for t1, t2 in zip(a1.sections[0].tracks, a2.sections[0].tracks):
            diffs = []
            if t1.channel != t2.channel:
                diffs.append(f"ch {t1.channel}->{t2.channel}")
            if t1.volume != t2.volume:
                diffs.append(f"vol {t1.volume}->{t2.volume}")
            if t1.pan != t2.pan:
                diffs.append(f"pan {t1.pan}->{t2.pan}")
            if t1.enabled != t2.enabled:
                diffs.append(f"enabled {t1.enabled}->{t2.enabled}")

            if diffs:
                print(f"  {t1.name}: {', '.join(diffs)}")

    # Compare raw areas
    print()
    print("Raw Data Differences:")
    _compare_bytes("Section Pointers", a1.section_pointers_raw, a2.section_pointers_raw)
    _compare_bytes("Section Data", a1.section_data_raw, a2.section_data_raw)
    _compare_bytes("Tempo Area", a1.tempo_area_raw, a2.tempo_area_raw)
    _compare_bytes("Channel Area", a1.channel_area_raw, a2.channel_area_raw)


def _compare(name: str, val1, val2):
    """Compare and print if different."""
    if val1 != val2:
        print(f"  {name}: {val1} -> {val2}")
    else:
        print(f"  {name}: {val1} (same)")


def _compare_bytes(name: str, b1: bytes, b2: bytes):
    """Compare byte arrays and report differences."""
    if b1 == b2:
        print(f"  {name}: identical")
    else:
        diff_count = sum(1 for a, b in zip(b1, b2) if a != b)
        print(f"  {name}: {diff_count} bytes differ out of {len(b1)}")


def _status(enabled: bool) -> str:
    return "Active" if enabled else "Empty"


def main():
    # Compare template with actual pattern
    compare_patterns(
        "../tests/fixtures/TXX.Q7P",  # Template (mostly empty)
        "../tests/fixtures/T01.Q7P",  # Actual pattern
    )


if __name__ == "__main__":
    main()
