#!/usr/bin/env python3
"""
Analyze SGT 692-byte shared prefix across all 6 RHY1 sections.

Decoded SGT has 6 RHY1 preamble (25 43 60 00) at offsets:
  24, 2200, 4248, 6296, 8472, 10648

Per Session 29d: first 692 bytes after each preamble are "shared" across all 6
sections (divergence starts at byte 692). This analyzer:
  1. Verifies the 692B shared claim byte-by-byte
  2. Identifies EXACTLY where each section diverges
  3. Hunts for structural markers in the prefix (groove table, chord table)
  4. Tests if prefix contains 7-byte events (groove lookup?)
  5. Correlates prefix bytes with sparse decoder fields (if applicable)
"""

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from qymanager.formats.qy70.sysex_parser import SysExParser

SGT_PATH = Path(__file__).parent.parent / "tests" / "fixtures" / "QY70_SGT.syx"


def extract_rhy1_concatenated(syx_path: Path) -> bytes:
    """Return all AL=0x00 (RHY1) decoded bytes concatenated across sections."""
    parser = SysExParser()
    msgs = parser.parse_file(str(syx_path))
    # Find all RHY1 messages, group by section (address_mid?)
    # Actually for SGT multi-section, each section has AL=section*8+track
    # RHY1 track=0, so AL=0, 8, 16, 24, 32, 40 for sections 0-5
    data_per_section = {}
    for m in msgs:
        if not m.is_style_data or not m.decoded_data:
            continue
        al = m.address_low
        if al % 8 == 0:  # RHY1 in each section
            sec = al // 8
            if sec not in data_per_section:
                data_per_section[sec] = b""
            data_per_section[sec] += m.decoded_data
    return data_per_section


def find_preamble_positions(data: bytes, preamble: bytes = b"\x25\x43\x60\x00") -> list[int]:
    """Find all byte offsets where preamble appears."""
    positions = []
    start = 0
    while True:
        idx = data.find(preamble, start)
        if idx == -1:
            break
        positions.append(idx)
        start = idx + 1
    return positions


def cross_section_invariance(sections: dict[int, bytes], max_prefix: int = 2048) -> None:
    """For each byte offset within section prefix, check how many sections agree."""
    print(f"\n═══ Cross-section byte invariance (first {max_prefix}B per section) ═══")
    sec_keys = sorted(sections.keys())
    if len(sec_keys) < 2:
        print("Need at least 2 sections")
        return
    min_len = min(len(sections[k]) for k in sec_keys)
    check_len = min(max_prefix, min_len)
    all_const = 0
    first_divergence = None
    last_const = -1
    diverged = False
    for i in range(check_len):
        bytes_at_i = {sections[k][i] for k in sec_keys}
        if len(bytes_at_i) == 1:
            all_const += 1
            if not diverged:
                last_const = i
        else:
            if first_divergence is None:
                first_divergence = i
            diverged = True
    print(f"  Constant bytes in prefix: {all_const}/{check_len}")
    print(f"  First divergence at offset: {first_divergence}")
    print(f"  Last constant offset (before divergence): {last_const}")
    if first_divergence is not None:
        print(f"  Bytes at divergence point:")
        for k in sec_keys:
            ctx = sections[k][max(0, first_divergence - 4):first_divergence + 8]
            print(f"    Sec{k}: offset {first_divergence}: {ctx.hex()}")


def print_hex_dump(data: bytes, start: int = 0, count: int = 256, width: int = 16) -> None:
    """Hex dump with ASCII sidebar."""
    for row in range(start, min(start + count, len(data)), width):
        hex_part = " ".join(f"{b:02x}" for b in data[row:row + width])
        ascii_part = "".join(chr(b) if 32 <= b < 127 else "." for b in data[row:row + width])
        print(f"  {row:6d} ({row:04x}): {hex_part:<{width*3}}  {ascii_part}")


def structural_markers(data: bytes, max_offset: int = 700) -> None:
    """Look for known structural markers in the prefix."""
    print(f"\n═══ Structural markers in first {max_offset}B ═══")
    # Known markers
    markers = {
        b"\xdc": "bar delimiter",
        b"\x9e": "sub-bar delimiter",
        b"\x25\x43\x60\x00": "2543 preamble",
        b"\x1f\xa3": "1FA3 preamble",
        b"\x2d\x2b": "2D2B preamble",
        b"\x30\x3b": "303B preamble",
        b"\x29\xcb": "29CB preamble",
        b"\x29\xdc": "29DC preamble",
        b"\x29\x4b": "294B preamble",
        b"\x2b\xe3": "2BE3 preamble",
        b"\xbf\xdf\xef\xf7\xfb\xfd\xfe": "empty marker",
    }
    for marker, name in markers.items():
        positions = []
        start = 0
        while True:
            idx = data.find(marker, start)
            if idx == -1 or idx > max_offset:
                break
            positions.append(idx)
            start = idx + 1
        if positions:
            print(f"  {name:30s}: {positions}")


def hunt_for_7byte_events(data: bytes, start: int = 24, stop: int = 720) -> None:
    """Check if the prefix contains 7-byte event patterns.

    Try different event interpretations:
    - Cumulative rotation R=9×(i+1)
    - Per-beat rotation R=0/2/1/0
    - Constant R=9
    """
    print(f"\n═══ 7-byte event hunt in offset [{start}:{stop}] ═══")

    def rot_right(val, shift, width=56):
        shift %= width
        return ((val >> shift) | (val << (width - shift))) & ((1 << width) - 1)

    n_events = (stop - start) // 7
    print(f"  Events if aligned: {n_events}")

    R_schemes = [
        ("cumulative R=9*(i+1)", lambda i: (9 * (i + 1)) % 56),
        ("constant R=9", lambda i: 9),
        ("constant R=0", lambda i: 0),
    ]

    for name, R_fn in R_schemes:
        print(f"\n  Scheme: {name}")
        valid_notes = 0
        for i in range(min(n_events, 20)):  # first 20 events
            offset = start + i * 7
            chunk = data[offset:offset + 7]
            val = int.from_bytes(chunk, "big")
            R = R_fn(i)
            derot = rot_right(val, R)
            f0 = (derot >> 47) & 0x1FF
            note = f0 & 0x7F
            if 13 <= note <= 87:  # valid XG drum range
                valid_notes += 1
        print(f"    Valid-drum-note events (13-87): {valid_notes}/{min(n_events, 20)}")


def byte_frequency(data: bytes, start: int = 0, stop: int = None) -> None:
    """Byte value frequency distribution."""
    if stop is None:
        stop = len(data)
    region = data[start:stop]
    print(f"\n═══ Byte frequency [{start}:{stop}] ═══")
    counter = Counter(region)
    print(f"  Total bytes: {len(region)}")
    print(f"  Unique byte values: {len(counter)}")
    print(f"  Top 10 most common:")
    for byte, count in counter.most_common(10):
        pct = 100 * count / len(region)
        print(f"    0x{byte:02x}: {count:4d} ({pct:5.2f}%)")
    print(f"  Zero bytes: {counter.get(0, 0)} ({100 * counter.get(0, 0) / len(region):.2f}%)")
    # 0xbf-0xfe are empty markers
    empty_range_count = sum(counter.get(b, 0) for b in [0xbf, 0xdf, 0xef, 0xf7, 0xfb, 0xfd, 0xfe])
    print(f"  Empty-marker bytes: {empty_range_count} ({100 * empty_range_count / len(region):.2f}%)")


def main():
    print(f"Analyzing: {SGT_PATH}")
    sections = extract_rhy1_concatenated(SGT_PATH)
    print(f"\nFound {len(sections)} RHY1 section(s): {sorted(sections.keys())}")
    for k in sorted(sections.keys()):
        print(f"  Sec{k}: {len(sections[k])} bytes")

    # Strategy: if SGT has multi-section, each section is accessible as separate AL.
    # But per wiki, the sections are stored in a CONCATENATED RHY1 stream.
    # Let me check the raw SGT decoded bytes if we have just 1 section.

    if len(sections) == 1:
        print("\n⚠️  Only 1 RHY1 section found — this means the section data is concatenated.")
        print("    Looking for multi-preamble split in the full stream...")
        full = sections[list(sections.keys())[0]]
        print(f"    Full RHY1 stream: {len(full)} bytes")
        positions = find_preamble_positions(full)
        print(f"    2543 preamble positions: {positions}")
        # Split by preamble
        if len(positions) > 1:
            sub_sections = {}
            for i in range(len(positions)):
                start = positions[i]
                end = positions[i + 1] if i + 1 < len(positions) else len(full)
                sub_sections[i] = full[start:end]
            sections = sub_sections
            print(f"    Split into {len(sections)} sub-sections by preamble")
            for k in sorted(sections.keys()):
                print(f"      Sec{k}: {len(sections[k])} bytes")

    if len(sections) < 2:
        print("\n⚠️  Cannot compare <2 sections. Analyzing first section only.")

    if len(sections) >= 2:
        cross_section_invariance(sections, max_prefix=2048)

    # Detailed analysis of first section (byte 0 to ~720)
    first_sec = sections[sorted(sections.keys())[0]]
    print(f"\n\n═══ Section 0 first 256B hex dump ═══")
    print_hex_dump(first_sec, 0, 256)

    print(f"\n═══ Section 0 bytes 256-512 hex dump ═══")
    print_hex_dump(first_sec, 256, 256)

    print(f"\n═══ Section 0 bytes 512-720 hex dump ═══")
    print_hex_dump(first_sec, 512, 208)

    structural_markers(first_sec, max_offset=720)
    hunt_for_7byte_events(first_sec, start=28, stop=720)
    byte_frequency(first_sec, 0, 720)


if __name__ == "__main__":
    main()
