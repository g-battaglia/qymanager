#!/usr/bin/env python3
"""Validate Q7P files before loading on QY700 hardware.

Safety tool: checks structural integrity and known-dangerous patterns
to prevent bricking. Run this on ANY Q7P before loading on hardware.

Usage:
    python3 midi_tools/q7p_validator.py tests/fixtures/TXX.Q7P
    python3 midi_tools/q7p_validator.py output.Q7P --reference tests/fixtures/TXX.Q7P

Exit codes:
    0 = SAFE (all checks passed)
    1 = UNSAFE (critical issues found)
    2 = WARNING (non-critical issues)
"""

import sys
import struct
from pathlib import Path

# Known-safe reference values from TXX.Q7P template
SAFE_REFERENCE = {
    "header": b"YQ7PAT     V1.00",
    "size_marker": 0x0990,
    "reserved_0x1E6": bytes(16),  # All zeros
    "reserved_0x1F6": bytes(16),  # All zeros
    "reserved_0x206": bytes(16),  # All zeros
    "fill_area_byte": 0xFE,
    "pad_area_byte": 0xF8,
}


def validate_q7p(filepath, reference_path=None):
    """Validate a Q7P file for hardware safety."""
    data = Path(filepath).read_bytes()
    issues = []
    warnings = []

    print(f"{'='*60}")
    print(f"  Q7P VALIDATOR: {filepath}")
    print(f"{'='*60}")
    print(f"  File size: {len(data)} bytes")

    # 1. Size check
    if len(data) not in (3072, 5120):
        issues.append(f"CRITICAL: Invalid size {len(data)} (expected 3072 or 5120)")
        print(f"  [FAIL] Size: {len(data)} bytes")
    else:
        print(f"  [OK]   Size: {len(data)} bytes")

    # 2. Header magic
    header = data[:16]
    if header != SAFE_REFERENCE["header"]:
        issues.append(f"CRITICAL: Invalid header: {header}")
        print(f"  [FAIL] Header: {header}")
    else:
        print(f"  [OK]   Header: YQ7PAT V1.00")

    # Only continue detailed checks for 3072-byte files
    if len(data) != 3072:
        print(f"  [SKIP] Detailed checks (5120-byte file)")
        return issues, warnings

    # 3. Size marker
    size_marker = struct.unpack(">H", data[0x30:0x32])[0]
    if size_marker != SAFE_REFERENCE["size_marker"]:
        warnings.append(f"Size marker: 0x{size_marker:04X} (expected 0x0990)")
        print(f"  [WARN] Size marker: 0x{size_marker:04X}")
    else:
        print(f"  [OK]   Size marker: 0x0990")

    # 4. CRITICAL: Reserved areas (bricking danger)
    reserved_areas = [
        (0x1E6, 16, "Bank MSB area"),
        (0x1F6, 16, "Program area"),
        (0x206, 16, "Bank LSB area"),
    ]
    for offset, size, name in reserved_areas:
        area = data[offset : offset + size]
        if area != bytes(size):
            non_zero = [(i, b) for i, b in enumerate(area) if b != 0]
            issues.append(
                f"CRITICAL: {name} (0x{offset:03X}) has non-zero bytes: "
                f"{[(f'0x{offset+i:03X}=0x{b:02X}') for i, b in non_zero[:5]]}"
            )
            print(f"  [FAIL] {name}: NON-ZERO at {[f'0x{offset+i:03X}' for i, _ in non_zero[:3]]}")
        else:
            print(f"  [OK]   {name}: all zeros")

    # 5. Section pointers sanity
    valid_sections = 0
    for i in range(8):
        ptr = struct.unpack(">H", data[0x100 + i * 2 : 0x102 + i * 2])[0]
        if ptr != 0xFEFE:
            valid_sections += 1
            eff = ptr + 0x100
            if eff >= 0x180:
                warnings.append(f"Section {i} pointer 0x{ptr:04X} → 0x{eff:03X} past config area")
    print(f"  [OK]   Sections: {valid_sections} active")

    # 6. Tempo range
    tempo_raw = struct.unpack(">H", data[0x188:0x18A])[0]
    tempo = tempo_raw / 10.0
    if tempo < 40 or tempo > 240:
        warnings.append(f"Tempo {tempo} BPM out of normal range (40-240)")
        print(f"  [WARN] Tempo: {tempo} BPM")
    else:
        print(f"  [OK]   Tempo: {tempo} BPM")

    # 7. Name is printable ASCII
    name = data[0x876:0x880]
    name_str = name.decode("ascii", errors="replace").rstrip()
    if all(0x20 <= b <= 0x7E for b in name):
        print(f"  [OK]   Name: '{name_str}'")
    else:
        warnings.append(f"Name has non-ASCII bytes: {[f'0x{b:02X}' for b in name if b < 0x20 or b > 0x7E]}")
        print(f"  [WARN] Name: '{name_str}' (non-ASCII)")

    # 8. Fill area integrity
    # Fill area may contain valid pattern fill data (not just 0xFE padding)
    fill_area = data[0x9C0 : 0x9C0 + 336]
    non_fe = sum(1 for b in fill_area if b != 0xFE and b != 0x00 and b != 0x64)
    if non_fe > 50:
        warnings.append(f"Fill area: {non_fe}/336 unexpected bytes")
        print(f"  [WARN] Fill area: {non_fe} unexpected bytes")
    else:
        print(f"  [OK]   Fill area: valid")

    # 9. Pad area integrity
    pad_area = data[0xB10 : 0xB10 + 240]
    non_f8 = sum(1 for b in pad_area if b != 0xF8)
    if non_f8 > 0:
        warnings.append(f"Pad area: {non_f8}/240 bytes not 0xF8")
        print(f"  [WARN] Pad area: {non_f8} non-0xF8 bytes")
    else:
        print(f"  [OK]   Pad area: 240 × 0xF8")

    # 10. Compare with reference if provided
    if reference_path:
        ref_data = Path(reference_path).read_bytes()
        if len(ref_data) == len(data):
            diffs = sum(1 for a, b in zip(data, ref_data) if a != b)
            critical_diffs = []
            for area_name, start, size in [
                ("Reserved 0x1E6", 0x1E6, 48),
                ("Fill area", 0x9C0, 336),
                ("Pad area", 0xB10, 240),
            ]:
                area_diff = sum(
                    1 for i in range(start, start + size)
                    if data[i] != ref_data[i]
                )
                if area_diff > 0:
                    critical_diffs.append(f"{area_name}: {area_diff} bytes")

            print(f"\n  Reference comparison ({reference_path}):")
            print(f"    Total diffs: {diffs} bytes")
            if critical_diffs:
                for d in critical_diffs:
                    print(f"    [WARN] {d}")
                    warnings.append(f"Reference diff: {d}")
            else:
                print(f"    [OK] No diffs in critical areas")

    # Summary
    print(f"\n  {'='*50}")
    if issues:
        print(f"  RESULT: *** UNSAFE *** — {len(issues)} critical issue(s)")
        for i in issues:
            print(f"    ✗ {i}")
        return issues, warnings
    elif warnings:
        print(f"  RESULT: WARNING — {len(warnings)} non-critical issue(s)")
        for w in warnings:
            print(f"    ! {w}")
        return issues, warnings
    else:
        print(f"  RESULT: SAFE — all checks passed")
        return issues, warnings


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Validate Q7P files for hardware safety")
    parser.add_argument("file", help="Q7P file to validate")
    parser.add_argument("--reference", "-r", help="Reference Q7P file for comparison")
    args = parser.parse_args()

    issues, warnings = validate_q7p(args.file, args.reference)

    if issues:
        sys.exit(1)
    elif warnings:
        sys.exit(2)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
