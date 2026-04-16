#!/usr/bin/env python3
"""Build a 5120-byte Q7P file from captured MIDI data.

Uses DECAY.Q7P as structural scaffold: preserves all unknown regions
(header, parameter tables, trailing metadata) and replaces only the
phrase blocks (0x200-0x9FF) and section configs (0x120+).

SAFETY: Do NOT send the output to QY700 hardware without extensive
verification. The 5120-byte Q7P format has regions whose purpose is
still unknown, and writes to wrong offsets have caused bricking.

Usage:
    .venv/bin/python3 midi_tools/build_q7p_5120.py \\
        midi_tools/captured/summer_pipeline_phrases.bin \\
        -o midi_tools/captured/summer_5120.Q7P \\
        --scaffold data/q7p/DECAY.Q7P
"""

import argparse
import struct
import sys
from pathlib import Path
from typing import List, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent))

from midi_tools.quantizer import (
    QuantizedPattern,
    QuantizedTrack,
    quantize_capture,
)
from midi_tools.capture_to_q7p import (
    encode_phrase_events,
    build_phrase_block,
)


PHRASE_AREA_START = 0x200
PHRASE_AREA_END = 0xA00
SECTION_POINTERS = 0x100
SECTION_CONFIGS = 0x120
PHRASE_SLOT = 0x80  # phrase blocks align to 128-byte boundaries


# Track slot to AL mapping based on PATT OUT 9~16 channels.
# Slot order: RHY1, RHY2, BASS, CHD1, CHD2, PAD, PHR1, PHR2
# Slots 1-8 map to channels 9-16. DECAY uses tracks 0-12 (up to 13 slots).
CHANNEL_TO_SLOT = {
    9: 0, 10: 1, 11: 2, 12: 3,
    13: 4, 14: 5, 15: 6, 16: 7,
}


def build_section_config(phrase_idx: int, track_idx: int, bar_count: int) -> bytes:
    """Build a 9-byte section config: F0 00 FB pp 00 tt C0 bb F2."""
    return bytes([
        0xF0, 0x00, 0xFB,
        phrase_idx & 0x7F,
        0x00,
        track_idx & 0x7F,
        0xC0,
        bar_count & 0x7F,
        0xF2,
    ])


def pack_phrase_blocks(pattern: QuantizedPattern) -> Tuple[bytes, List[Tuple[int, int, int, int]]]:
    """Pack phrase blocks into the 0x200-0x9FF region.

    Returns:
        packed_bytes: bytes for 0x200-0x9FF (2048 bytes)
        section_entries: list of (phrase_idx, track_idx, bar_count, slot_offset)
    """
    buf = bytearray(b"\x40" * (PHRASE_AREA_END - PHRASE_AREA_START))
    section_entries = []
    cursor = 0  # offset from PHRASE_AREA_START

    for phrase_idx, track in enumerate(pattern.active_tracks):
        block = build_phrase_block(track, pattern, phrase_name=track.name)

        # Align cursor to next PHRASE_SLOT boundary
        if cursor % PHRASE_SLOT != 0:
            cursor += PHRASE_SLOT - (cursor % PHRASE_SLOT)

        if cursor + len(block) > len(buf):
            raise ValueError(
                f"Phrase {track.name} ({len(block)} bytes) "
                f"doesn't fit in phrase area"
            )

        buf[cursor:cursor + len(block)] = block
        slot_offset = cursor
        cursor += len(block)

        track_idx = CHANNEL_TO_SLOT.get(track.channel, phrase_idx)
        section_entries.append((phrase_idx, track_idx, track.bar_count, slot_offset))

    return bytes(buf), section_entries


def build_5120_q7p(
    pattern: QuantizedPattern,
    scaffold_path: str,
) -> bytes:
    """Build a 5120-byte Q7P file by replacing phrases in a scaffold.

    The scaffold (typically DECAY.Q7P) provides:
      - Header magic
      - Pattern metadata (0x010-0x01F)
      - Section pointer region (starts at 0x100 — REWRITTEN)
      - Section configs (0x120+ — REWRITTEN)
      - Unknown parameter tables (0x0A00+ — preserved)
      - All other unknown regions (preserved)
    """
    with open(scaffold_path, "rb") as f:
        buf = bytearray(f.read())

    if len(buf) != 5120:
        raise ValueError(f"Scaffold must be 5120 bytes, got {len(buf)}")

    # 1. Replace phrase blocks at 0x200-0x9FF
    packed, section_entries = pack_phrase_blocks(pattern)
    buf[PHRASE_AREA_START:PHRASE_AREA_END] = packed

    # 2. Rewrite section pointers (0x100-0x11F)
    # Point to 0x120, 0x129, 0x132, 0x13B (4 configs × 9 bytes)
    pointers = bytearray(b"\xFE\xFE" * 16)
    for i in range(len(section_entries)):
        ptr = 0x0020 + i * 9  # offset relative to 0x100
        struct.pack_into(">H", pointers, i * 2, ptr)
    buf[SECTION_POINTERS:SECTION_POINTERS + 32] = pointers

    # 3. Rewrite section configs (0x120+)
    cfg_buf = bytearray()
    for phrase_idx, track_idx, bar_count, _ in section_entries:
        cfg_buf.extend(build_section_config(phrase_idx, track_idx, bar_count))
    # Pad remaining config area to 0x200 with zeros (was F1 ... config terminators in DECAY)
    # Keep minimal: just our configs. DECAY had a F1 terminator after last valid config.
    if cfg_buf:
        cfg_buf.extend(bytes([0xF1, 0x00]))
    buf[SECTION_CONFIGS:SECTION_CONFIGS + len(cfg_buf)] = cfg_buf
    # Zero out rest of config area up to 0x200
    buf[SECTION_CONFIGS + len(cfg_buf):PHRASE_AREA_START] = (
        b"\x00" * (PHRASE_AREA_START - SECTION_CONFIGS - len(cfg_buf))
    )

    # 4. Update pattern name if scaffold has one
    # Name in 5120 format is at 0x0A00 area, but format varies.
    # We don't touch it — preserves scaffold metadata.

    return bytes(buf)


def validate_q7p(data: bytes, scaffold: bytes = None) -> List[str]:
    """Validate a Q7P file structure. Returns list of warnings.

    For 5120-byte files: compares against scaffold to ensure only phrase
    area (0x200-0x9FF) and section metadata (0x100-0x1FF) were changed.
    """
    warnings = []

    if len(data) not in (3072, 5120, 4096, 4608, 5632, 6144):
        warnings.append(f"Unusual file size: {len(data)} (expected 3072 or 5120)")

    if not data[:6] == b"YQ7PAT":
        warnings.append(f"Invalid magic: {data[:16]!r}")

    # Section pointers must be sensible
    for i in range(16):
        ptr = struct.unpack(">H", data[0x100 + i*2:0x100 + i*2 + 2])[0]
        if ptr != 0xFEFE and ptr > 0x0400:
            warnings.append(f"Section pointer [{i}]=0x{ptr:04x} out of range")

    # For 3072-byte files: check classic bricking offsets (0x1E6/0x1F6/0x206)
    # For 5120-byte files: 0x200+ is phrase blocks, so those offsets don't apply
    if len(data) == 3072:
        for off in (0x1E6, 0x1F6, 0x206):
            if any(b != 0 for b in data[off:off+16]):
                warnings.append(
                    f"NON-ZERO at 0x{off:04x} (3072B bricking area)"
                )

    # For 5120-byte with scaffold: verify we only changed expected regions
    if len(data) == 5120 and scaffold is not None and len(scaffold) == 5120:
        SAFE_CHANGE_REGIONS = [
            (0x100, 0x200),   # section pointers + configs
            (0x200, 0xA00),   # phrase blocks
        ]
        for i in range(len(data)):
            if data[i] == scaffold[i]:
                continue
            if not any(lo <= i < hi for lo, hi in SAFE_CHANGE_REGIONS):
                warnings.append(
                    f"Modified byte 0x{i:04x} outside safe region "
                    f"(scaffold={scaffold[i]:02x}, output={data[i]:02x})"
                )
                if len([w for w in warnings if "Modified byte" in w]) > 10:
                    warnings.append("  ... (more unsafe modifications suppressed)")
                    break

    return warnings


def main():
    parser = argparse.ArgumentParser(
        description="Build 5120-byte Q7P from MIDI capture (Pipeline B)"
    )
    parser.add_argument("capture", help="Capture JSON path (from capture_playback)")
    parser.add_argument("-o", "--output", required=True, help="Output .Q7P path")
    parser.add_argument("--scaffold", default="data/q7p/DECAY.Q7P",
                       help="Scaffold Q7P file (default: DECAY.Q7P)")
    parser.add_argument("-b", "--bpm", type=float, help="BPM override")
    parser.add_argument("-n", "--bars", type=int, help="Number of bars")
    parser.add_argument("--no-validate", action="store_true",
                       help="Skip validation (not recommended)")

    args = parser.parse_args()

    print(f"Reading capture: {args.capture}")
    pattern = quantize_capture(
        args.capture, bpm=args.bpm, bar_count=args.bars,
    )
    print(pattern.summary())
    print()

    print(f"Building 5120-byte Q7P (scaffold: {args.scaffold})")
    q7p_data = build_5120_q7p(pattern, args.scaffold)

    if not args.no_validate:
        with open(args.scaffold, "rb") as f:
            scaffold_data = f.read()
        warnings = validate_q7p(q7p_data, scaffold=scaffold_data)
        if warnings:
            print("\n⚠ VALIDATION WARNINGS:")
            for w in warnings:
                print(f"  {w}")
            print()

    with open(args.output, "wb") as f:
        f.write(q7p_data)
    print(f"Written: {args.output} ({len(q7p_data)} bytes)")

    print()
    print("=" * 60)
    print("SAFETY NOTICE")
    print("=" * 60)
    print("This 5120-byte Q7P is SOFTWARE-ONLY output.")
    print("DO NOT load onto QY700 hardware without further validation.")
    print("The 5120-byte format has unverified regions that could brick.")
    print("Use q7p_to_midi.py to verify the output roundtrips correctly.")


if __name__ == "__main__":
    main()
