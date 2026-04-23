#!/usr/bin/env python3
"""
Deep analysis of SGT 664B shared codebook content.

The 692B shared prefix = 24B track header + 4B preamble + 664B mystery data.
All 6 SGT sections share these 664 bytes BYTE-EXACT. This analyzer hunts for:

  1. Internal periodicity (groove table period?)
  2. Record/entry structure (fixed-length codebook)
  3. 7-byte events aligned at various offsets
  4. Comparison with Summer RHY1 data (4-bar user pattern)
  5. Compare section-specific 76B trailing content

Goal: identify if codebook is (a) groove template library, (b) chord/voice table,
(c) sparse event sequence, or (d) structural metadata.
"""

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from qymanager.formats.qy70.sysex_parser import SysExParser

SGT_PATH = Path(__file__).parent.parent / "tests" / "fixtures" / "QY70_SGT.syx"


def extract_sections(syx_path: Path) -> dict[int, bytes]:
    """Extract all RHY1 sections as concatenated bytes per section."""
    parser = SysExParser()
    msgs = parser.parse_file(str(syx_path))
    data_per_section = {}
    for m in msgs:
        if not m.is_style_data or not m.decoded_data:
            continue
        al = m.address_low
        if al % 8 == 0:
            sec = al // 8
            if sec not in data_per_section:
                data_per_section[sec] = b""
            data_per_section[sec] += m.decoded_data
    return data_per_section


def autocorr_period(data: bytes, max_period: int = 256) -> list[tuple[int, int]]:
    """Return list of (period, score) where score = # of aligned byte matches."""
    if len(data) < max_period * 2:
        max_period = len(data) // 2
    scores = []
    for period in range(1, max_period + 1):
        matches = sum(1 for i in range(len(data) - period) if data[i] == data[i + period])
        scores.append((period, matches))
    scores.sort(key=lambda x: -x[1])
    return scores[:15]


def find_repeating_blocks(data: bytes, block_size: int) -> dict[bytes, list[int]]:
    """Find all unique blocks of block_size bytes and their positions."""
    blocks = {}
    for i in range(0, len(data) - block_size + 1, block_size):
        blk = data[i:i + block_size]
        blocks.setdefault(blk, []).append(i)
    # Filter to only repeating ones
    return {k: v for k, v in blocks.items() if len(v) > 1}


def scan_for_entry_size(data: bytes, sizes: list[int] = None) -> None:
    """For each candidate entry size, score how 'table-like' the data looks
    (many repeating entries = higher score)."""
    if sizes is None:
        sizes = [2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 13, 14, 15, 16, 18, 21, 24, 28, 42]
    print(f"\n═══ Entry-size scan on {len(data)}B ═══")
    for size in sizes:
        if size > len(data):
            continue
        blocks = find_repeating_blocks(data, size)
        total_rep_bytes = sum(len(v) * size for v in blocks.values())
        n_entries = len(data) // size
        coverage = total_rep_bytes / len(data) * 100
        print(f"  Entry size {size:3d}: {len(blocks):3d} unique repeating blocks "
              f"(of {n_entries} total), coverage {coverage:5.1f}%")


def find_7byte_events_variable_R(data: bytes, n_events: int = 20, start: int = 0) -> None:
    """For each event position, find R that yields valid drum note."""
    print(f"\n═══ Per-event R sweep (first {n_events} events from offset {start}) ═══")

    def rot_right(val, shift, width=56):
        shift %= width
        return ((val >> shift) | (val << (width - shift))) & ((1 << width) - 1)

    for i in range(n_events):
        offset = start + i * 7
        if offset + 7 > len(data):
            break
        chunk = data[offset:offset + 7]
        val = int.from_bytes(chunk, "big")
        valid_Rs = []
        for R in range(56):
            derot = rot_right(val, R)
            f0 = (derot >> 47) & 0x1FF
            note = f0 & 0x7F
            if 35 <= note <= 60:  # common drum range
                valid_Rs.append((R, note))
        print(f"  Event {i:2d} @offset {offset:4d}: {chunk.hex()} → valid Rs: "
              f"{valid_Rs[:8]}" + ("..." if len(valid_Rs) > 8 else ""))


def compare_section_trailing(sections: dict[int, bytes], prefix_size: int = 692) -> None:
    """Show section-specific trailing bytes side-by-side."""
    print(f"\n═══ Section-specific trailing bytes (offset {prefix_size}+) ═══")
    for sec in sorted(sections.keys()):
        data = sections[sec]
        trailing = data[prefix_size:]
        print(f"\n  Sec{sec}: {len(trailing)} trailing bytes")
        for row in range(0, len(trailing), 16):
            hex_part = " ".join(f"{b:02x}" for b in trailing[row:row + 16])
            print(f"    {prefix_size + row:4d}: {hex_part}")


def trailing_events_analysis(sections: dict[int, bytes], prefix_size: int = 692) -> None:
    """Try to parse section-specific trailing as 7-byte events with per-event R."""
    print(f"\n═══ Trailing bytes per-section event analysis ═══")

    def rot_right(val, shift, width=56):
        shift %= width
        return ((val >> shift) | (val << (width - shift))) & ((1 << width) - 1)

    for sec in sorted(sections.keys()):
        trailing = sections[sec][prefix_size:]
        print(f"\n  Sec{sec}: {len(trailing)}B trailing")
        n_events = len(trailing) // 7
        for i in range(min(n_events, 12)):
            chunk = trailing[i * 7:(i + 1) * 7]
            val = int.from_bytes(chunk, "big")
            # Try cumulative R and find valid note
            best_Rs = []
            for R in range(56):
                derot = rot_right(val, R)
                f0 = (derot >> 47) & 0x1FF
                note = f0 & 0x7F
                if 13 <= note <= 87:
                    best_Rs.append((R, note))
            r_std = (9 * (i + 1)) % 56
            derot_std = rot_right(val, r_std)
            note_std = (derot_std >> 47) & 0x7F
            print(f"    Evt{i}: {chunk.hex()} std_R={r_std} → note={note_std} "
                  f"{'✓' if 13<=note_std<=87 else '✗'}  "
                  f"valid_Rs: {best_Rs[:5]}{'...' if len(best_Rs)>5 else ''}")


def compare_codebook_with_summer(sgt_data: bytes, summer_data: bytes) -> None:
    """Check if SGT codebook shares content with Summer."""
    print(f"\n═══ SGT vs Summer codebook overlap ═══")
    print(f"  SGT first 692B: {sgt_data[:692].hex()[:100]}...")
    print(f"  Summer first 28B: {summer_data[:28].hex()}")

    # Find longest common substring
    # Summer is small (384B) so just look for summer 28-byte prefix in SGT
    sgt_first_28 = sgt_data[:28]
    summer_first_28 = summer_data[:28]
    print(f"\n  SGT bytes 0-27 vs Summer bytes 0-27:")
    print(f"    SGT:    {sgt_first_28.hex()}")
    print(f"    Summer: {summer_first_28.hex()}")
    match = sum(1 for i in range(28) if sgt_first_28[i] == summer_first_28[i])
    print(f"    Match: {match}/28 bytes")

    # Search for Summer's bar headers (13B bar header pattern) in SGT codebook
    # First bar header of Summer likely starts after preamble at byte 28
    summer_bar_header = summer_data[28:41]
    print(f"\n  Summer first bar header (13B at offset 28): {summer_bar_header.hex()}")
    # Search in SGT codebook
    idx = sgt_data.find(summer_bar_header)
    if idx >= 0:
        print(f"    FOUND in SGT at offset {idx}!")
    else:
        print(f"    Not found in SGT")


def main():
    print(f"Analyzing SGT sections from: {SGT_PATH}")
    sections = extract_sections(SGT_PATH)
    print(f"Found {len(sections)} sections, each {len(sections[0])} bytes")

    # Analyze the shared 664-byte codebook (bytes 28-691 of any section)
    codebook = sections[0][28:692]
    print(f"\nShared codebook: {len(codebook)} bytes (SGT sec0 bytes 28-691)")

    # 1. Autocorrelation
    print("\n═══ Codebook autocorrelation (top 15 periods) ═══")
    top = autocorr_period(codebook, max_period=200)
    for period, score in top:
        pct = 100 * score / (len(codebook) - period)
        print(f"  Period {period:3d}: {score:3d} matches ({pct:5.2f}%)")

    # 2. Entry size scan
    scan_for_entry_size(codebook)

    # 3. Per-event R sweep on first 20 events
    find_7byte_events_variable_R(codebook, n_events=20, start=0)

    # 4. Section-specific trailing
    compare_section_trailing(sections, prefix_size=692)

    # 5. Trailing events analysis
    trailing_events_analysis(sections, prefix_size=692)

    # 6. Compare with Summer
    # Load Summer RHY1
    summer_path = Path(__file__).parent.parent / "midi_tools" / "captured" / "ground_truth_style.syx"
    if summer_path.exists():
        summer_sections = extract_sections(summer_path)
        if summer_sections:
            summer_sec0 = summer_sections[0]
            compare_codebook_with_summer(sections[0], summer_sec0)


if __name__ == "__main__":
    main()
