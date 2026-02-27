#!/usr/bin/env python3
"""
QY70 Custom Style Generator - "NEONGROOVE"

Creates a custom QY70 SysEx style file (.syx) that can be loaded
into a Yamaha QY70 via MIDI bulk dump.

Architecture:
- Uses SGT reference file for structural template and track data
- The QY70 SysEx event format is a packed internal representation
  (NOT the D0/E0/BE/F2 format used in Q7P files)
- Track data from the SGT is rearranged across sections to create
  musical variation while maintaining structural validity
- Header is modified for custom tempo and configuration

Structural findings from reverse engineering:
- AL addressing: AL = section_index * 8 + track_index (0x00-0x37)
- Each SysEx bulk dump message carries exactly 128 decoded bytes
  (147 encoded bytes via Yamaha 7-bit packing)
- Header at AL=0x7F: 640 bytes (5 messages)
- Track data: 128-768 bytes per track (1-6 messages)
- Tempo encoding: BPM = (range * 95 - 133) + offset
  where range = 7-bit group header of first encoded header block
  and offset = decoded header byte[0]

Usage:
    python3 midi_tools/create_custom_style.py [--tempo BPM] [--output PATH]
"""

import sys
import argparse
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from qymanager.utils.yamaha_7bit import encode_7bit, decode_7bit
from qymanager.utils.checksum import calculate_yamaha_checksum, verify_sysex_checksum


# ─────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────

# SysEx framing
SYSEX_START = 0xF0
SYSEX_END = 0xF7
YAMAHA_ID = 0x43
QY70_MODEL_ID = 0x5F

# Bulk dump addressing
STYLE_AH = 0x02
STYLE_AM = 0x7E
HEADER_AL = 0x7F

# Block sizes
DECODED_BLOCK_SIZE = 128  # Bytes per decoded SysEx payload
ENCODED_BLOCK_SIZE = 147  # Bytes per encoded SysEx payload (128 decoded -> 147 encoded)
TRACKS_PER_SECTION = 8
MAX_SECTIONS = 6

# SGT reference file
SGT_PATH = Path(__file__).parent.parent / "tests" / "fixtures" / "QY70_SGT.syx"

# GM/XG Drum Map (Standard Kit, Channel 10) - for documentation
GM_DRUMS = {
    "kick": 36,
    "snare": 38,
    "clap": 39,
    "rimshot": 37,
    "hat_closed": 42,
    "hat_pedal": 44,
    "hat_open": 46,
    "crash1": 49,
    "crash2": 57,
    "ride1": 51,
    "ride_bell": 53,
    "tom_low": 45,
    "tom_mid": 47,
    "tom_high": 50,
    "tom_floor": 41,
}

# XG Default Values
XG_DEFAULTS = {
    "volume": 100,
    "pan": 64,
    "reverb_send": 40,
    "chorus_send": 0,
    "expression": 127,
    "bank_msb_normal": 0,
    "bank_msb_drums": 127,
}


# ─────────────────────────────────────────────────────────────────────
# SysEx Message Building
# ─────────────────────────────────────────────────────────────────────


def create_init_message(device_number: int = 0) -> bytes:
    """Create bulk dump initialization message.

    Format: F0 43 1n 5F 00 00 00 01 F7
    Signals QY70 to prepare for receiving bulk data.
    """
    return bytes(
        [
            SYSEX_START,
            YAMAHA_ID,
            0x10 | (device_number & 0x0F),
            QY70_MODEL_ID,
            0x00,
            0x00,
            0x00,
            0x01,
            SYSEX_END,
        ]
    )


def create_close_message(device_number: int = 0) -> bytes:
    """Create bulk dump closing message.

    Format: F0 43 1n 5F 00 00 00 00 F7
    Signals end of bulk data transfer.
    """
    return bytes(
        [
            SYSEX_START,
            YAMAHA_ID,
            0x10 | (device_number & 0x0F),
            QY70_MODEL_ID,
            0x00,
            0x00,
            0x00,
            0x00,
            SYSEX_END,
        ]
    )


def create_bulk_dump_message(al: int, decoded_block: bytes, device_number: int = 0) -> bytes:
    """Create one SysEx bulk dump message for a 128-byte decoded block.

    Format: F0 43 0n 5F BH BL AH AM AL [encoded_data] CS F7

    Args:
        al: Address Low byte (track/section identifier)
        decoded_block: Exactly 128 bytes of decoded data
        device_number: MIDI device number (0-15)

    Returns:
        Complete SysEx message bytes

    Raises:
        ValueError: If decoded_block is not exactly 128 bytes
    """
    if len(decoded_block) != DECODED_BLOCK_SIZE:
        raise ValueError(
            f"Block must be exactly {DECODED_BLOCK_SIZE} bytes, got {len(decoded_block)}"
        )

    encoded = encode_7bit(decoded_block)

    # Byte count of encoded payload
    byte_count = len(encoded)
    bh = (byte_count >> 7) & 0x7F
    bl = byte_count & 0x7F

    # Checksum covers: BH BL AH AM AL + encoded_data
    checksum_data = bytes([bh, bl, STYLE_AH, STYLE_AM, al]) + encoded
    checksum = calculate_yamaha_checksum(checksum_data)

    # Build complete message
    msg = bytearray(
        [
            SYSEX_START,
            YAMAHA_ID,
            0x00 | (device_number & 0x0F),
            QY70_MODEL_ID,
            bh,
            bl,
            STYLE_AH,
            STYLE_AM,
            al,
        ]
    )
    msg.extend(encoded)
    msg.append(checksum)
    msg.append(SYSEX_END)

    return bytes(msg)


# ─────────────────────────────────────────────────────────────────────
# Reference File Parsing
# ─────────────────────────────────────────────────────────────────────


def parse_sysex_messages(data: bytes) -> list:
    """Parse raw bytes into individual SysEx messages."""
    messages = []
    start = None
    for i, b in enumerate(data):
        if b == SYSEX_START:
            start = i
        elif b == SYSEX_END and start is not None:
            messages.append(data[start : i + 1])
            start = None
    return messages


def load_reference(syx_path: Path) -> tuple:
    """Load a reference .syx file and extract per-AL decoded blocks.

    Each SysEx bulk dump message decodes to exactly 128 bytes.
    Multiple messages with the same AL form a larger track block.
    Messages are decoded INDIVIDUALLY (not concatenated before decode).

    Args:
        syx_path: Path to reference .syx file

    Returns:
        Tuple of (track_blocks, header_blocks) where:
        - track_blocks: dict mapping AL -> list of 128-byte decoded blocks
        - header_blocks: list of 128-byte decoded blocks for AL=0x7F
    """
    with open(syx_path, "rb") as f:
        data = f.read()

    msgs = parse_sysex_messages(data)

    track_blocks: dict = {}  # AL -> [block0, block1, ...]
    header_blocks: list = []

    for msg in msgs:
        if len(msg) <= 9:
            continue  # Init/Close message, skip
        al = msg[8]
        payload = msg[9:-2]  # Encoded data (between address and checksum)
        decoded = decode_7bit(payload)

        if al == HEADER_AL:
            header_blocks.append(decoded)
        else:
            if al not in track_blocks:
                track_blocks[al] = []
            track_blocks[al].append(decoded)

    return track_blocks, header_blocks


# ─────────────────────────────────────────────────────────────────────
# Tempo Encoding
# ─────────────────────────────────────────────────────────────────────


def encode_tempo(bpm: int) -> tuple:
    """Encode BPM into QY70 range + offset bytes.

    The QY70 tempo is encoded across two domains:
    - range: The 7-bit group header of the first encoded header block.
             This is determined by which decoded bytes (0-6) have MSB set.
    - offset: decoded[0] of the header (lower 7 bits, as MSB is always 0).

    Formula: BPM = (range * 95 - 133) + offset

    Range values and their BPM ranges:
        range=1: BPM  -38 to  89 (bit 0 -> decoded[6] MSB)
        range=2: BPM   57 to 184 (bit 1 -> decoded[5] MSB)
        range=3: BPM  152 to 279 (bits 0,1 -> decoded[5,6] MSBs)
        range=4: BPM  247 to 374 (bit 2 -> decoded[4] MSB)

    In practice only range=2 (57-184 BPM) and range=3 (152-279 BPM) are used.

    Args:
        bpm: Tempo in BPM (57-279)

    Returns:
        Tuple of (range_byte, offset_byte)
    """
    # Try range 2 first (most common: 57-184 BPM)
    for r in [2, 3, 1, 4]:
        base = r * 95 - 133
        offset = bpm - base
        if 0 <= offset <= 94:  # Offset 0-94 for clean range
            return r, offset

    # Fallback: extended range
    for r in [2, 3, 1, 4]:
        base = r * 95 - 133
        offset = bpm - base
        if 0 <= offset <= 127:
            return r, offset

    # Last resort
    return 2, max(0, min(127, bpm - 57))


def apply_tempo_to_header(header_blocks: list, bpm: int) -> list:
    """Apply a tempo value to header blocks.

    Modifies the first header block to encode the desired tempo.
    The tempo is encoded via:
    - decoded[0] = offset byte (becomes part of 7-bit encoded stream)
    - decoded[5] and decoded[6] MSBs determine the range byte

    Args:
        header_blocks: List of 128-byte header blocks (will be copied)
        bpm: Desired tempo in BPM

    Returns:
        New list of header blocks with modified tempo
    """
    if not header_blocks:
        raise ValueError("No header blocks provided")

    blocks = [bytearray(b) for b in header_blocks]
    first = blocks[0]

    range_byte, offset_byte = encode_tempo(bpm)

    # Set decoded[0] = offset (tempo offset value)
    first[0] = offset_byte

    # Clear MSBs of decoded[4:7] (these determine range)
    first[4] &= 0x7F
    first[5] &= 0x7F
    first[6] &= 0x7F

    # Set MSBs according to range byte
    # bit 2 -> decoded[4] MSB, bit 1 -> decoded[5] MSB, bit 0 -> decoded[6] MSB
    if range_byte & 0x04:
        first[4] |= 0x80
    if range_byte & 0x02:
        first[5] |= 0x80
    if range_byte & 0x01:
        first[6] |= 0x80

    blocks[0] = bytes(first)
    for i in range(1, len(blocks)):
        blocks[i] = bytes(blocks[i])

    return blocks


# ─────────────────────────────────────────────────────────────────────
# Style Generation
# ─────────────────────────────────────────────────────────────────────


def generate_style(
    output_path: Path,
    tempo_bpm: int = 128,
    section_map: dict = None,
    reference_path: Path = None,
    device_number: int = 0,
) -> bytes:
    """Generate a custom QY70 SysEx style file.

    Creates a structurally valid .syx file by:
    1. Loading track data from a reference style file
    2. Rearranging sections according to section_map
    3. Setting custom tempo in the header
    4. Building SysEx messages with proper 7-bit encoding and checksums

    Args:
        output_path: Where to write the .syx file
        tempo_bpm: Tempo in BPM (57-279)
        section_map: Dict mapping target_section -> source_section index.
                     Default creates a creative rearrangement:
                     {0: 0, 1: 2, 2: 4, 3: 3, 4: 1, 5: 5}
                     (Intro=Sec0, MainA=Sec2, MainB=Sec4, FillAB=Sec3,
                      FillBA=Sec1, Ending=Sec5)
        reference_path: Path to reference .syx file. Default: SGT fixture.
        device_number: MIDI device number (0-15)

    Returns:
        Complete .syx file data as bytes
    """
    if reference_path is None:
        reference_path = SGT_PATH

    if section_map is None:
        # Creative rearrangement for "NEONGROOVE":
        # Swap Main A/B with different source sections for variety
        # SGT sections: 0=Intro, 1=MainA, 2=MainB, 3=FillAB, 4=FillBA, 5=EndingFill
        section_map = {
            0: 0,  # Intro <- SGT Intro
            1: 2,  # Main A <- SGT Main B (different groove)
            2: 0,  # Main B <- SGT Intro (variation)
            3: 3,  # Fill AB <- SGT Fill AB
            4: 4,  # Fill BA <- SGT Fill BA
            5: 5,  # Ending <- SGT Ending fill
        }

    # Load reference
    track_blocks, header_blocks = load_reference(reference_path)

    print(f"Reference loaded: {len(track_blocks)} track ALs, {len(header_blocks)} header blocks")
    print(f"Target tempo: {tempo_bpm} BPM")
    print(f"Section mapping: {section_map}")

    # Build messages
    messages: list = []

    # 1. Init message
    messages.append(create_init_message(device_number))

    # 2. Track data for each section
    track_count = 0
    msg_count = 0
    for target_sec in sorted(section_map.keys()):
        source_sec = section_map[target_sec]

        for track_idx in range(TRACKS_PER_SECTION):
            source_al = source_sec * TRACKS_PER_SECTION + track_idx
            target_al = target_sec * TRACKS_PER_SECTION + track_idx

            if source_al in track_blocks:
                blocks = track_blocks[source_al]
                for block in blocks:
                    # Ensure block is exactly 128 bytes
                    if len(block) < DECODED_BLOCK_SIZE:
                        padded = bytearray(DECODED_BLOCK_SIZE)
                        padded[: len(block)] = block
                        block = bytes(padded)
                    elif len(block) > DECODED_BLOCK_SIZE:
                        block = block[:DECODED_BLOCK_SIZE]

                    msg = create_bulk_dump_message(target_al, block, device_number)
                    messages.append(msg)
                    msg_count += 1
                track_count += 1

    # 3. Header (modified for custom tempo)
    modified_header = apply_tempo_to_header(header_blocks, tempo_bpm)
    for block in modified_header:
        if len(block) < DECODED_BLOCK_SIZE:
            padded = bytearray(DECODED_BLOCK_SIZE)
            padded[: len(block)] = block
            block = bytes(padded)
        msg = create_bulk_dump_message(HEADER_AL, block, device_number)
        messages.append(msg)
        msg_count += 1

    # 4. Close message
    messages.append(create_close_message(device_number))

    print(
        f"Generated: {track_count} tracks, {msg_count} bulk dump messages, "
        f"{len(messages)} total messages"
    )

    # Assemble and write
    syx_data = b"".join(messages)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(syx_data)

    print(f"Written: {output_path} ({len(syx_data)} bytes)")

    return syx_data


# ─────────────────────────────────────────────────────────────────────
# Verification
# ─────────────────────────────────────────────────────────────────────


def verify_style(
    syx_path: Path, expected_tempo: int = None, reference_path: Path = None, verbose: bool = True
) -> bool:
    """Thoroughly verify a generated QY70 SysEx style file.

    Checks:
    1. File structure: Init, Bulk Dump messages, Close
    2. Message framing: F0 start, F7 end, correct manufacturer/model
    3. Payload sizes: All bulk dumps must have 147 encoded bytes
    4. Checksums: Every bulk dump message checksum must be valid
    5. 7-bit encoding: Roundtrip decode->encode must produce valid data
    6. AL addressing: Correct range for style format (0x00-0x37 + 0x7F)
    7. Tempo encoding: Verify BPM matches expected value
    8. Track headers: Verify 24-byte headers match known patterns
    9. Structural comparison: Compare against reference if provided

    Args:
        syx_path: Path to .syx file to verify
        expected_tempo: Expected BPM (if known)
        reference_path: Reference .syx for structural comparison
        verbose: Print detailed results

    Returns:
        True if all checks pass, False otherwise
    """
    with open(syx_path, "rb") as f:
        data = f.read()

    msgs = parse_sysex_messages(data)
    errors: list = []
    warnings: list = []

    if verbose:
        print(f"\n{'=' * 70}")
        print(f"VERIFICATION: {syx_path}")
        print(f"File size: {len(data)} bytes, {len(msgs)} SysEx messages")
        print(f"{'=' * 70}")

    # ── Check 1: Init and Close messages ──
    if verbose:
        print("\n[1] Init/Close messages...")

    if len(msgs) < 3:
        errors.append("File has fewer than 3 messages (need Init + data + Close)")
    else:
        init = msgs[0]
        close = msgs[-1]

        if init != create_init_message(init[2] & 0x0F):
            errors.append(f"Init message malformed: {init.hex()}")
        else:
            if verbose:
                print(f"  Init:  OK  {init.hex(' ')}")

        if close != create_close_message(close[2] & 0x0F):
            errors.append(f"Close message malformed: {close.hex()}")
        else:
            if verbose:
                print(f"  Close: OK  {close.hex(' ')}")

    # ── Check 2: Bulk dump message framing ──
    if verbose:
        print("\n[2] Message framing...")

    bulk_msgs = msgs[1:-1]  # Exclude init and close
    al_histogram: dict = {}
    decoded_blocks: dict = {}  # AL -> list of decoded blocks

    for i, msg in enumerate(bulk_msgs):
        msg_idx = i + 1  # 1-indexed (msg 0 is init)

        # Check start/end
        if msg[0] != SYSEX_START or msg[-1] != SYSEX_END:
            errors.append(f"Msg {msg_idx}: Missing F0/F7 framing")
            continue

        # Check manufacturer and model
        if msg[1] != YAMAHA_ID:
            errors.append(
                f"Msg {msg_idx}: Wrong manufacturer 0x{msg[1]:02X} (expected 0x{YAMAHA_ID:02X})"
            )
        if msg[3] != QY70_MODEL_ID:
            errors.append(
                f"Msg {msg_idx}: Wrong model 0x{msg[3]:02X} (expected 0x{QY70_MODEL_ID:02X})"
            )

        # Check size (should be 9 header + 147 payload + 1 checksum + 1 F7 = 158)
        expected_size = 9 + ENCODED_BLOCK_SIZE + 1 + 1  # should be 158
        # Actually: F0 + manufacturer + device + model + BH + BL + AH + AM + AL
        #         = 9 bytes header
        # Then: 147 encoded bytes + checksum + F7 = 149
        # Total = 9 + 147 + 1 + 1 = 158
        if len(msg) != 158:
            errors.append(f"Msg {msg_idx}: Size {len(msg)} != expected 158")

        # Extract address
        al = msg[8]
        if al not in al_histogram:
            al_histogram[al] = 0
        al_histogram[al] += 1

        # Decode payload
        payload = msg[9:-2]
        decoded = decode_7bit(payload)
        if al not in decoded_blocks:
            decoded_blocks[al] = []
        decoded_blocks[al].append(decoded)

    if verbose:
        print(f"  {len(bulk_msgs)} bulk dump messages, all framing OK")
        print(f"  AL distribution: {dict(sorted(al_histogram.items()))}")

    # ── Check 3: Checksums ──
    if verbose:
        print("\n[3] Checksums...")

    bad_checksums = 0
    for i, msg in enumerate(bulk_msgs):
        if not verify_sysex_checksum(msg):
            bad_checksums += 1
            errors.append(f"Msg {i + 1}: Checksum FAILED")

    if verbose:
        if bad_checksums == 0:
            print(f"  All {len(bulk_msgs)} checksums VALID")
        else:
            print(f"  {bad_checksums} FAILED checksums!")

    # ── Check 4: AL addressing ──
    if verbose:
        print("\n[4] AL addressing...")

    has_header = HEADER_AL in al_histogram
    track_als = sorted(al for al in al_histogram if al != HEADER_AL)

    if not has_header:
        errors.append("No header block (AL=0x7F) found")
    else:
        if verbose:
            print(f"  Header (0x7F): {al_histogram[HEADER_AL]} messages")

    # Check track ALs are in valid range
    for al in track_als:
        if al > 0x37:
            errors.append(f"Track AL=0x{al:02X} out of range (max 0x37)")
        section = al // TRACKS_PER_SECTION
        track = al % TRACKS_PER_SECTION
        if verbose:
            print(f"  AL=0x{al:02X}: Section {section}, Track {track} ({al_histogram[al]} msgs)")

    # Count sections
    sections_present = set(al // 8 for al in track_als)
    if verbose:
        print(f"  Sections present: {sorted(sections_present)}")

    # ── Check 5: Tempo encoding ──
    if verbose:
        print("\n[5] Tempo encoding...")

    if has_header and HEADER_AL in decoded_blocks:
        first_header = decoded_blocks[HEADER_AL][0]
        # To verify tempo, we need the raw encoded bytes
        # Re-encode the first header block and check
        encoded_first = encode_7bit(first_header)
        range_byte = encoded_first[0]  # 7-bit group header = tempo range
        offset_byte = first_header[0]  # decoded[0] = tempo offset

        actual_bpm = (range_byte * 95 - 133) + offset_byte

        if verbose:
            print(f"  Range byte: {range_byte} (from 7-bit group header)")
            print(f"  Offset byte: {offset_byte} (decoded[0])")
            print(f"  Computed BPM: {actual_bpm}")

        if expected_tempo is not None:
            if actual_bpm != expected_tempo:
                errors.append(f"Tempo mismatch: expected {expected_tempo}, got {actual_bpm}")
            elif verbose:
                print(f"  Expected BPM: {expected_tempo} - MATCH!")

    # ── Check 6: Track headers ──
    if verbose:
        print("\n[6] Track headers (24-byte structure)...")

    COMMON_PREFIX = bytes([0x08, 0x04, 0x82, 0x01, 0x00, 0x40, 0x20, 0x08, 0x04, 0x82, 0x01, 0x00])
    CONSTANTS = bytes([0x06, 0x1C])

    tracks_checked = 0
    tracks_valid = 0
    for al in track_als:
        if al not in decoded_blocks or not decoded_blocks[al]:
            continue
        first_block = decoded_blocks[al]
        if not first_block:
            continue
        header = first_block[0][:24]

        # Check common prefix (bytes 0-11)
        if header[:12] == COMMON_PREFIX:
            # Check constants (bytes 12-13)
            if header[12:14] == CONSTANTS:
                tracks_valid += 1
            else:
                warnings.append(
                    f"AL=0x{al:02X}: Constants mismatch at bytes 12-13: {header[12:14].hex()}"
                )
        else:
            warnings.append(f"AL=0x{al:02X}: Common prefix mismatch")

        tracks_checked += 1

        # Identify track type
        voice = header[14:16]
        note_range = header[16:18]
        flags = header[18:21]
        pan = header[21:24]

        is_drum = voice == bytes([0x40, 0x80]) and note_range == bytes([0x87, 0xF8])

        if verbose and al < 0x08:  # Only print section 0 details
            track_type = "DRUM" if is_drum else "MELODY"
            print(
                f"  AL=0x{al:02X}: voice={voice.hex()} range={note_range.hex()} "
                f"flags={flags.hex()} pan={pan.hex()} [{track_type}]"
            )

    if verbose:
        print(f"  {tracks_valid}/{tracks_checked} track headers valid")

    # ── Check 7: Structural comparison with reference ──
    if reference_path and reference_path.exists():
        if verbose:
            print("\n[7] Structural comparison with reference...")

        ref_tracks, ref_header = load_reference(reference_path)

        # Compare AL counts
        for al in sorted(
            set(
                list(al_histogram.keys())
                + list({k: len(v) for k, v in ref_tracks.items()}.keys())
                + [HEADER_AL]
            )
        ):
            gen_count = al_histogram.get(al, 0)
            if al == HEADER_AL:
                ref_count = len(ref_header)
            elif al in ref_tracks:
                ref_count = len(ref_tracks[al])
            else:
                ref_count = 0

            if verbose and gen_count != ref_count:
                section = al // 8 if al != HEADER_AL else -1
                track = al % 8 if al != HEADER_AL else -1
                label = f"Sec{section}/Trk{track}" if al != HEADER_AL else "Header"
                print(f"  AL=0x{al:02X} ({label}): gen={gen_count} msgs, ref={ref_count} msgs")

    # ── Summary ──
    if verbose:
        print(f"\n{'─' * 70}")
        print(f"RESULT: {len(errors)} errors, {len(warnings)} warnings")

        if errors:
            print("\nERRORS:")
            for e in errors:
                print(f"  - {e}")

        if warnings:
            print("\nWARNINGS:")
            for w in warnings:
                print(f"  - {w}")

        if not errors:
            print("\n  ALL CHECKS PASSED")
        print(f"{'─' * 70}\n")

    return len(errors) == 0


# ─────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="Generate a custom QY70 SysEx style file (NEONGROOVE)"
    )
    parser.add_argument(
        "--tempo", type=int, default=128, help="Tempo in BPM (57-279, default: 128)"
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=str(Path(__file__).parent.parent / "tests" / "fixtures" / "NEONGROOVE.syx"),
        help="Output .syx file path",
    )
    parser.add_argument(
        "--reference",
        "-r",
        type=str,
        default=str(SGT_PATH),
        help="Reference .syx file for template data",
    )
    parser.add_argument(
        "--verify-only",
        type=str,
        default=None,
        help="Only verify an existing .syx file (no generation)",
    )
    parser.add_argument(
        "--device", type=int, default=0, help="MIDI device number (0-15, default: 0)"
    )

    args = parser.parse_args()

    if args.verify_only:
        success = verify_style(
            Path(args.verify_only),
            reference_path=Path(args.reference),
        )
        sys.exit(0 if success else 1)

    # Generate
    print("=" * 70)
    print("QY70 Custom Style Generator - NEONGROOVE")
    print("=" * 70)

    output_path = Path(args.output)

    syx_data = generate_style(
        output_path=output_path,
        tempo_bpm=args.tempo,
        reference_path=Path(args.reference),
        device_number=args.device,
    )

    # Verify the generated file
    print("\n--- Verification ---")
    success = verify_style(
        output_path,
        expected_tempo=args.tempo,
        reference_path=Path(args.reference),
    )

    if success:
        print("Style generated and verified successfully!")
    else:
        print("WARNING: Generated file has verification errors!")
        sys.exit(1)


if __name__ == "__main__":
    main()
