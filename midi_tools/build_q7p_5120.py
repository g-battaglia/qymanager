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
SECTION_POINTERS = 0x100
SECTION_CONFIGS = 0x120
PHRASE_SLOT = 0x80  # phrase blocks align to 128-byte boundaries

# Phrase area size scales with Q7P size. Trailer layout differs between variants.
# Validated by inspecting DECAY (5120B) and SGT..Q7P (6144B) scaffolds.
PHRASE_AREA_END_BY_SIZE = {
    5120: 0x0A00,   # DECAY layout: 2048B phrase area, 2560B trailer
    6144: 0x1400,   # SGT layout: 4608B phrase area, 1024B trailer
}

# Back-compat alias. Default is the 5120-byte DECAY layout.
PHRASE_AREA_END = PHRASE_AREA_END_BY_SIZE[5120]


def _phrase_area_end(q7p_size: int) -> int:
    """Return the phrase-area end offset for a given scaffold size."""
    if q7p_size not in PHRASE_AREA_END_BY_SIZE:
        raise ValueError(
            f"Unsupported Q7P scaffold size {q7p_size}. "
            f"Supported: {sorted(PHRASE_AREA_END_BY_SIZE)}"
        )
    return PHRASE_AREA_END_BY_SIZE[q7p_size]


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


def pack_phrase_blocks(
    pattern: QuantizedPattern,
    phrase_area_size: int = PHRASE_AREA_END - PHRASE_AREA_START,
) -> Tuple[bytes, List[Tuple[int, int, int, int]]]:
    """Pack phrase blocks into the phrase area region.

    Args:
        pattern: quantized pattern with active tracks
        phrase_area_size: total bytes available for phrase blocks
            (2048 for 5120B Q7P, 4608 for 6144B Q7P)

    Returns:
        packed_bytes: bytes for the phrase area
        section_entries: list of (phrase_idx, track_idx, bar_count, slot_offset)
    """
    buf = bytearray(b"\x40" * phrase_area_size)
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
                f"doesn't fit in phrase area ({phrase_area_size}B, "
                f"used {cursor}B so far)"
            )

        buf[cursor:cursor + len(block)] = block
        slot_offset = cursor
        cursor += len(block)

        track_idx = CHANNEL_TO_SLOT.get(track.channel, phrase_idx)
        section_entries.append((phrase_idx, track_idx, track.bar_count, slot_offset))

    return bytes(buf), section_entries


def build_q7p(
    pattern: QuantizedPattern,
    scaffold_path: str,
) -> bytes:
    """Build a Q7P file by replacing phrases in a scaffold.

    Supports 5120B (DECAY layout, 4-bar max) and 6144B (SGT layout, 6-bar+).

    The scaffold provides:
      - Header magic
      - Pattern metadata (0x010-0x01F)
      - Section pointer region (0x100 — REWRITTEN)
      - Section configs (0x120+ — REWRITTEN)
      - Unknown parameter tables and trailer (preserved)
    """
    with open(scaffold_path, "rb") as f:
        buf = bytearray(f.read())

    phrase_area_end = _phrase_area_end(len(buf))
    phrase_area_size = phrase_area_end - PHRASE_AREA_START

    # 1. Replace phrase blocks
    packed, section_entries = pack_phrase_blocks(pattern, phrase_area_size)
    buf[PHRASE_AREA_START:phrase_area_end] = packed

    # 2. Rewrite section pointers (0x100-0x11F)
    pointers = bytearray(b"\xFE\xFE" * 16)
    for i in range(len(section_entries)):
        ptr = 0x0020 + i * 9  # offset relative to 0x100
        struct.pack_into(">H", pointers, i * 2, ptr)
    buf[SECTION_POINTERS:SECTION_POINTERS + 32] = pointers

    # 3. Rewrite section configs (0x120+)
    cfg_buf = bytearray()
    for phrase_idx, track_idx, bar_count, _ in section_entries:
        cfg_buf.extend(build_section_config(phrase_idx, track_idx, bar_count))
    if cfg_buf:
        cfg_buf.extend(bytes([0xF1, 0x00]))
    buf[SECTION_CONFIGS:SECTION_CONFIGS + len(cfg_buf)] = cfg_buf
    buf[SECTION_CONFIGS + len(cfg_buf):PHRASE_AREA_START] = (
        b"\x00" * (PHRASE_AREA_START - SECTION_CONFIGS - len(cfg_buf))
    )

    return bytes(buf)


def build_5120_q7p(
    pattern: QuantizedPattern,
    scaffold_path: str,
) -> bytes:
    """Back-compat alias — requires a 5120-byte scaffold.

    New callers should use build_q7p() which handles both 5120B and 6144B.
    """
    with open(scaffold_path, "rb") as f:
        size = len(f.read())
    if size != 5120:
        raise ValueError(
            f"build_5120_q7p requires a 5120-byte scaffold, got {size}. "
            f"Use build_q7p() for 6144B scaffolds."
        )
    return build_q7p(pattern, scaffold_path)


def _validate_phrase_stream(data: bytes, offset: int, name: str) -> List[str]:
    """Walk a single phrase event stream. Flag anything unrecognized."""
    warnings = []
    start = offset + 0x1A
    if data[start:start+2] != b"\xF0\x00":
        warnings.append(
            f"Phrase {name!r} @0x{offset:04x}: missing F0 00 marker at +0x1A"
        )
        return warnings
    # Tempo sanity (1-300 BPM)
    tempo_raw = struct.unpack(">H", data[offset + 0x18:offset + 0x1A])[0]
    bpm = tempo_raw / 10
    if not (20 <= bpm <= 300):
        warnings.append(
            f"Phrase {name!r} @0x{offset:04x}: suspicious tempo {bpm} BPM "
            f"(raw=0x{tempo_raw:04x})"
        )
    # Walk events
    i = start + 2
    saw_f2 = False
    unknown_cmds = set()
    while i < len(data):
        b = data[i]
        if b == 0xF2:
            saw_f2 = True
            break
        elif 0xA0 <= b <= 0xAF:
            i += 2
        elif b == 0xD0:
            if i + 3 >= len(data):
                warnings.append(f"Phrase {name!r}: truncated D0 at 0x{i:04x}")
                break
            # Validate ranges
            vel = data[i+1]; note = data[i+2]; gate = data[i+3]
            if vel > 0x7F or note > 0x7F or gate > 0x7F:
                warnings.append(
                    f"Phrase {name!r}: D0 @0x{i:04x} bad bytes "
                    f"(vel={vel}, note={note}, gate={gate}) — expected 0-127"
                )
            i += 4
        elif b == 0xE0:
            if i + 4 >= len(data):
                warnings.append(f"Phrase {name!r}: truncated E0 at 0x{i:04x}")
                break
            gate = data[i+1]; note = data[i+3]; vel = data[i+4]
            if vel > 0x7F or note > 0x7F or gate > 0x7F:
                warnings.append(
                    f"Phrase {name!r}: E0 @0x{i:04x} bad bytes "
                    f"(gate={gate}, note={note}, vel={vel}) — expected 0-127"
                )
            i += 5
        elif 0xD1 <= b <= 0xDF:
            # Drum variants (rim, accent, ghost, etc.) — same 4-byte format as D0
            i += 4
        elif b == 0xC1:
            # Short note (arpeggios/ticks), 3 bytes
            i += 3
        elif 0xBA <= b <= 0xBF:
            # Control change events, 2 bytes
            i += 2
        elif b == 0x40:
            # Padding, normally only at end of slot
            i += 1
        else:
            unknown_cmds.add(b)
            i += 1
    if not saw_f2:
        warnings.append(f"Phrase {name!r}: missing F2 terminator")
    if unknown_cmds:
        warnings.append(
            f"Phrase {name!r}: unknown commands {sorted(f'0x{c:02x}' for c in unknown_cmds)}"
        )
    return warnings


def validate_q7p(data: bytes, scaffold: bytes = None) -> List[str]:
    """Validate a Q7P file structure. Returns list of warnings.

    For 5120/6144-byte files: compares against scaffold to ensure only phrase
    area and section metadata (0x100-0x1FF) were changed.
    Additionally walks every phrase block and validates its event stream
    plus global invariant: phrase count ≤ 16, track count ≤ 16, unique
    non-empty phrases, no phrase-block overlap.
    """
    warnings = []

    if len(data) not in (3072, 5120, 4096, 4608, 5632, 6144):
        warnings.append(f"Unusual file size: {len(data)} (expected 3072/5120/6144)")

    if not data[:6] == b"YQ7PAT":
        warnings.append(f"Invalid magic: {data[:16]!r}")

    # Section pointers must be sensible (< phrase area start + typical trailer)
    max_ptr = 0x0400 if len(data) == 5120 else 0x1400 if len(data) == 6144 else 0x0400
    for i in range(16):
        ptr = struct.unpack(">H", data[0x100 + i*2:0x100 + i*2 + 2])[0]
        if ptr != 0xFEFE and ptr > max_ptr:
            warnings.append(f"Section pointer [{i}]=0x{ptr:04x} out of range")

    # Section pointers must be unique (each points to a distinct config)
    live_ptrs = [
        struct.unpack(">H", data[0x100 + i*2:0x100 + i*2 + 2])[0]
        for i in range(16)
    ]
    live_ptrs = [p for p in live_ptrs if p != 0xFEFE]
    if len(live_ptrs) != len(set(live_ptrs)):
        dupes = {p for p in live_ptrs if live_ptrs.count(p) > 1}
        warnings.append(f"Duplicate section pointers: {sorted(f'0x{p:04x}' for p in dupes)}")

    # Section pointers must be strictly increasing by 9 bytes (config slot size)
    sorted_ptrs = sorted(live_ptrs)
    for a, b in zip(sorted_ptrs, sorted_ptrs[1:]):
        if b - a != 9:
            warnings.append(
                f"Section pointers not contiguous: 0x{a:04x} → 0x{b:04x} "
                f"(expected step=9)"
            )
            break

    # For 3072-byte files: check classic bricking offsets (0x1E6/0x1F6/0x206)
    # For 5120/6144-byte files: 0x200+ is phrase blocks, so those offsets don't apply
    if len(data) == 3072:
        for off in (0x1E6, 0x1F6, 0x206):
            if any(b != 0 for b in data[off:off+16]):
                warnings.append(
                    f"NON-ZERO at 0x{off:04x} (3072B bricking area)"
                )

    # Determine phrase area end from scaffold size
    phrase_area_end = None
    if len(data) in PHRASE_AREA_END_BY_SIZE:
        phrase_area_end = PHRASE_AREA_END_BY_SIZE[len(data)]

    # For 5120/6144-byte with scaffold: verify we only changed expected regions
    if phrase_area_end is not None and scaffold is not None and len(scaffold) == len(data):
        safe_change_regions = [
            (0x100, 0x200),                # section pointers + configs
            (0x200, phrase_area_end),      # phrase blocks
        ]
        for i in range(len(data)):
            if data[i] == scaffold[i]:
                continue
            if not any(lo <= i < hi for lo, hi in safe_change_regions):
                warnings.append(
                    f"Modified byte 0x{i:04x} outside safe region "
                    f"(scaffold={scaffold[i]:02x}, output={data[i]:02x})"
                )
                if len([w for w in warnings if "Modified byte" in w]) > 10:
                    warnings.append("  ... (more unsafe modifications suppressed)")
                    break

    # Walk each phrase block and validate its event stream
    if phrase_area_end is not None:
        try:
            from midi_tools.q7p_to_midi import find_phrase_blocks
            blocks = find_phrase_blocks(data)

            if len(blocks) > 16:
                warnings.append(
                    f"Too many phrase blocks: {len(blocks)} > 16 (QY700 max tracks)"
                )

            # Overlap detection: phrase blocks must not overlap
            sorted_blocks = sorted(blocks)
            for (a_off, a_name), (b_off, b_name) in zip(sorted_blocks, sorted_blocks[1:]):
                if b_off < a_off + PHRASE_SLOT:
                    # Phrase must occupy at least one PHRASE_SLOT
                    warnings.append(
                        f"Phrase overlap: {a_name!r}@0x{a_off:04x} "
                        f"too close to {b_name!r}@0x{b_off:04x}"
                    )

            # Phrase must lie inside phrase area
            for offset, name in blocks:
                if offset < PHRASE_AREA_START or offset >= phrase_area_end:
                    warnings.append(
                        f"Phrase {name!r}@0x{offset:04x} outside phrase area "
                        f"[0x{PHRASE_AREA_START:04x}, 0x{phrase_area_end:04x})"
                    )

            for offset, name in blocks:
                warnings.extend(_validate_phrase_stream(data, offset, name))
        except Exception as e:
            warnings.append(f"Phrase stream validation failed: {e}")

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
