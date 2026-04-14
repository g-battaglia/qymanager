#!/usr/bin/env python3
"""
Generate diagnostic Q7P test files for QY700 bricking investigation.

Creates a series of Q7P files, each modifying exactly ONE field from the
known-good TXX.Q7P template. Loading these on the QY700 in order of
increasing risk identifies which modification caused the brick.

Usage:
    python3 midi_tools/safe_q7p_tester.py [--output-dir DIR]

Test files generated (in order of increasing risk):
    test_01_unmodified.Q7P  - Exact copy of TXX.Q7P (baseline)
    test_02_name.Q7P        - Only name changed at 0x876
    test_03_tempo.Q7P       - Only tempo changed at 0x188
    test_04_volume.Q7P      - Only volume changed at 0x226
    test_05_pan.Q7P         - Only pan changed at 0x276
    test_06_chorus.Q7P      - Only chorus send at 0x246
    test_07_reverb.Q7P      - Only reverb send at 0x256
    test_08_voice_1e6.Q7P   - Write 0x7F at 0x1E6 (suspected bricking cause)
    test_09_voice_1f6.Q7P   - Write 0x01 at 0x1F6 (suspected Program)
    test_10_voice_206.Q7P   - Write 0x01 at 0x206 (suspected Bank LSB)

PROTOCOL:
    1. First load test_01 to confirm QY700 accepts unmodified template
    2. Load each subsequent file, checking QY700 after each
    3. If a file causes issues, that identifies the problematic offset
    4. Tests 08-10 are HIGH RISK - save QY700 state before loading
"""

import struct
import sys
from pathlib import Path

# Resolve template path relative to this script
SCRIPT_DIR = Path(__file__).parent
REPO_ROOT = SCRIPT_DIR.parent
TEMPLATE_PATH = REPO_ROOT / "tests" / "fixtures" / "TXX.Q7P"
DEFAULT_OUTPUT_DIR = SCRIPT_DIR / "q7p_test_files"


def load_template() -> bytearray:
    """Load TXX.Q7P template and return as mutable bytearray."""
    data = TEMPLATE_PATH.read_bytes()
    if len(data) != 3072:
        raise ValueError(f"Template size {len(data)} != 3072")
    if data[:16] != b"YQ7PAT     V1.00":
        raise ValueError("Invalid Q7P header")
    return bytearray(data)


def generate_tests(output_dir: Path) -> None:
    """Generate all diagnostic test files."""
    output_dir.mkdir(parents=True, exist_ok=True)

    template = load_template()
    tests = []

    # Test 01: Unmodified baseline
    def test_01(buf: bytearray) -> str:
        return "Exact copy of TXX.Q7P — baseline, no modifications"
    tests.append(("test_01_unmodified.Q7P", test_01))

    # Test 02: Name only
    def test_02(buf: bytearray) -> str:
        name = b"TESTNAME  "  # 10 bytes
        buf[0x876:0x876 + 10] = name
        return "Name 'TESTNAME' at 0x876 (10 bytes)"
    tests.append(("test_02_name.Q7P", test_02))

    # Test 03: Tempo only
    def test_03(buf: bytearray) -> str:
        tempo_val = 120 * 10  # 120 BPM * 10
        struct.pack_into(">H", buf, 0x188, tempo_val)
        return "Tempo 120 BPM (0x04B0) at 0x188 (2 bytes BE)"
    tests.append(("test_03_tempo.Q7P", test_03))

    # Test 04: Volume only
    def test_04(buf: bytearray) -> str:
        for i in range(8):
            buf[0x226 + i] = 100  # Volume=100 for all 8 tracks
        return "Volume=100 for all tracks at 0x226 (8 bytes)"
    tests.append(("test_04_volume.Q7P", test_04))

    # Test 05: Pan only
    def test_05(buf: bytearray) -> str:
        for i in range(8):
            buf[0x276 + i] = 64  # Pan=64 (center) for all 8 tracks
        return "Pan=64 (center) for all tracks at 0x276 (8 bytes)"
    tests.append(("test_05_pan.Q7P", test_05))

    # Test 06: Chorus send only
    def test_06(buf: bytearray) -> str:
        for i in range(8):
            buf[0x246 + i] = 10  # Chorus=10 for all tracks
        return "Chorus send=10 for all tracks at 0x246 (8 bytes)"
    tests.append(("test_06_chorus.Q7P", test_06))

    # Test 07: Reverb send only
    def test_07(buf: bytearray) -> str:
        for i in range(8):
            buf[0x256 + i] = 40  # Reverb=40 (XG default) for all tracks
        return "Reverb send=40 for all tracks at 0x256 (8 bytes)"
    tests.append(("test_07_reverb.Q7P", test_07))

    # Test 08: HIGH RISK — Write to 0x1E6 (suspected Bank MSB)
    def test_08(buf: bytearray) -> str:
        buf[0x1E6] = 0x7F  # This is what the converter did for drum tracks
        return "HIGH RISK: 0x7F at 0x1E6 (suspected Bank MSB — probable brick cause)"
    tests.append(("test_08_voice_1e6.Q7P", test_08))

    # Test 09: HIGH RISK — Write to 0x1F6 (suspected Program)
    def test_09(buf: bytearray) -> str:
        buf[0x1F6] = 0x01  # Write a non-zero Program value
        return "HIGH RISK: 0x01 at 0x1F6 (suspected Program Change)"
    tests.append(("test_09_voice_1f6.Q7P", test_09))

    # Test 10: HIGH RISK — Write to 0x206 (suspected Bank LSB)
    def test_10(buf: bytearray) -> str:
        buf[0x206] = 0x01  # Write a non-zero Bank LSB
        return "HIGH RISK: 0x01 at 0x206 (suspected Bank LSB)"
    tests.append(("test_10_voice_206.Q7P", test_10))

    # Generate and write all test files
    print(f"Generating {len(tests)} diagnostic Q7P files in {output_dir}/\n")
    print(f"Template: {TEMPLATE_PATH} ({len(template)} bytes)\n")

    for filename, modifier in tests:
        buf = bytearray(template)  # Fresh copy for each test
        description = modifier(buf)

        # Verify file size is still correct
        assert len(buf) == 3072, f"Size mismatch for {filename}"

        # Verify header is intact
        assert buf[:16] == b"YQ7PAT     V1.00", f"Header corrupted in {filename}"

        # Count bytes changed from template
        diff_count = sum(1 for a, b in zip(template, buf) if a != b)

        filepath = output_dir / filename
        filepath.write_bytes(bytes(buf))

        risk = "HIGH RISK" if "HIGH RISK" in description else "safe"
        print(f"  [{risk:>9s}] {filename:30s}  ({diff_count:2d} bytes changed)  {description}")

    print(f"\n{'='*72}")
    print("TESTING PROTOCOL:")
    print("  1. Load test_01_unmodified.Q7P first (must work — it's the template)")
    print("  2. Load files in order, checking QY700 after each")
    print("  3. If a file causes problems → that offset is the culprit")
    print("  4. Files 08-10 are HIGH RISK — save QY700 state before loading!")
    print(f"{'='*72}")

    # Also generate a hex diff summary
    diff_file = output_dir / "DIFF_SUMMARY.txt"
    with open(diff_file, "w") as f:
        f.write("Hex diff summary: each test file vs TXX.Q7P template\n")
        f.write("=" * 72 + "\n\n")
        for filename, modifier in tests:
            buf = bytearray(template)
            modifier(buf)
            f.write(f"--- {filename} ---\n")
            for i, (a, b) in enumerate(zip(template, buf)):
                if a != b:
                    f.write(f"  Offset 0x{i:03X}: 0x{a:02X} -> 0x{b:02X}\n")
            if all(a == b for a, b in zip(template, buf)):
                f.write("  (no changes)\n")
            f.write("\n")
    print(f"\nDiff summary written to {diff_file}")


if __name__ == "__main__":
    output_dir = DEFAULT_OUTPUT_DIR
    if len(sys.argv) > 2 and sys.argv[1] == "--output-dir":
        output_dir = Path(sys.argv[2])

    generate_tests(output_dir)
