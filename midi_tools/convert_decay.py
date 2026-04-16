#!/usr/bin/env python3
"""
Convert DECAY.Q7P (QY700) to QY70 SysEx + Standard MIDI.

This script performs both conversions:
1. Standard MIDI file (.mid) — for playback/reference
2. QY70 SysEx file (.syx) — for loading onto QY70 hardware

The SysEx contains correct metadata (tempo, voice, pan, channel) but
track events are minimal since the QY70 bitstream format is not yet
fully decoded. The MIDI file provides the full musical content.

DECAY phrase-to-QY70 track mapping:
  RHY1 (ch10) ← kick       (main groove, BD1)
  RHY2 (ch10) ← hi hats    (secondary rhythm, HH)
  BASS (ch 2) ← bass       (C2/F2 bass line)
  CHD1 (ch 1) ← piano pad  (C/F major chords)
  CHD2 (ch 5) ← guitarpaddy (guitar chord stabs)
  PAD  (ch 3) ← dream bells (C/F arpeggio pad)
  PHR1 (ch 4) ← piano tik  (high ticking arpeggio)
  PHR2 (ch 6) ← bells      (bell melody)

Unmapped phrases (too many drums for 2 RHY slots):
  tom, rim, deepnoisetim, brum noise → merged summary in MIDI only

Usage:
    python3 midi_tools/convert_decay.py
    python3 midi_tools/convert_decay.py --output-dir data/q7p/converted/
"""

import argparse
import struct
import sys
from pathlib import Path

# Add parent for imports
sys.path.insert(0, str(Path(__file__).parent))

from q7p_to_midi import convert_q7p_to_midi


def main():
    parser = argparse.ArgumentParser(description="Convert DECAY.Q7P for QY70")
    parser.add_argument("--q7p", default="data/q7p/DECAY.Q7P",
                        help="Path to DECAY.Q7P")
    parser.add_argument("--output-dir", "-o", default="data/q7p",
                        help="Output directory")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    q7p_path = Path(args.q7p)
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    data = q7p_path.read_bytes()
    if len(data) != 5120:
        print(f"ERROR: Expected 5120-byte Q7P, got {len(data)}", file=sys.stderr)
        sys.exit(1)

    # Step 1: Generate MIDI
    print("=== Step 1: Q7P → MIDI ===")
    midi_path = out_dir / "DECAY.mid"
    convert_q7p_to_midi(str(q7p_path), str(midi_path), verbose=True)
    print()

    # Step 2: Generate QY70 SysEx
    print("=== Step 2: Q7P → QY70 SysEx ===")
    syx_path = out_dir / "DECAY_qy70.syx"
    generate_qy70_syx(data, syx_path, verbose=args.verbose)

    print(f"\n=== Output ===")
    print(f"  MIDI:  {midi_path} ({midi_path.stat().st_size} bytes)")
    print(f"  SysEx: {syx_path} ({syx_path.stat().st_size} bytes)")
    print()
    print("To play through QY70 via MIDI:")
    print(f'  python3 midi_tools/q7p_playback.py {q7p_path} --port "USB Midi"')
    print()
    print("To load SysEx onto QY70:")
    print(f'  python3 midi_tools/send_style.py {syx_path}')


# ─── QY70 SysEx Generation ───────────────────────────────────────────

SYSEX_START = 0xF0
SYSEX_END = 0xF7
YAMAHA_ID = 0x43
QY70_MODEL_ID = 0x5F
STYLE_AH = 0x02
STYLE_AM = 0x7E  # Edit buffer
PPQN = 480


def yamaha_checksum(data: bytes) -> int:
    """Calculate Yamaha SysEx checksum."""
    return (0x80 - (sum(data) & 0x7F)) & 0x7F


def encode_7bit(data: bytes) -> bytes:
    """Encode 8-bit data to 7-bit Yamaha format (MSB packing)."""
    result = bytearray()
    for i in range(0, len(data), 7):
        block = data[i:i + 7]
        msb_byte = 0
        for j, b in enumerate(block):
            if b & 0x80:
                msb_byte |= (1 << (6 - j))
        result.append(msb_byte)
        for b in block:
            result.append(b & 0x7F)
    return bytes(result)


def make_bulk_msg(al: int, payload: bytes, device: int = 0) -> bytes:
    """Create a QY70 bulk dump SysEx message."""
    encoded = encode_7bit(payload)
    bc = len(encoded)
    bh = (bc >> 7) & 0x7F
    bl = bc & 0x7F
    cs_data = bytes([bh, bl, STYLE_AH, STYLE_AM, al]) + encoded
    cs = yamaha_checksum(cs_data)
    msg = bytearray([
        SYSEX_START, YAMAHA_ID, 0x00 | (device & 0x0F), QY70_MODEL_ID,
        bh, bl, STYLE_AH, STYLE_AM, al,
    ])
    msg.extend(encoded)
    msg.append(cs)
    msg.append(SYSEX_END)
    return bytes(msg)


def make_init_msg(device: int = 0) -> bytes:
    """QY70 bulk init: F0 43 10 5F 00 00 00 01 F7"""
    return bytes([SYSEX_START, YAMAHA_ID, 0x10 | (device & 0x0F),
                  QY70_MODEL_ID, 0x00, 0x00, 0x00, 0x01, SYSEX_END])


def make_close_msg(device: int = 0) -> bytes:
    """QY70 bulk close: F0 43 10 5F 00 00 00 00 F7"""
    return bytes([SYSEX_START, YAMAHA_ID, 0x10 | (device & 0x0F),
                  QY70_MODEL_ID, 0x00, 0x00, 0x00, 0x00, SYSEX_END])


# DECAY phrase → QY70 track mapping
# QY70 tracks: RHY1(0), RHY2(1), BASS(2), CHD1(3), CHD2(4), PAD(5), PHR1(6), PHR2(7)
TRACK_MAP = {
    0: {"name": "kick",        "gm_prog": 0,   "bank_msb": 127, "is_drum": True,
        "notes": [36]},
    1: {"name": "hi hats",     "gm_prog": 0,   "bank_msb": 127, "is_drum": True,
        "notes": [42, 46]},
    2: {"name": "bass",        "gm_prog": 33,  "bank_msb": 0,   "is_drum": False,
        "notes": [36, 41]},
    3: {"name": "piano pad",   "gm_prog": 0,   "bank_msb": 0,   "is_drum": False,
        "notes": [48, 52, 55, 53, 57]},
    4: {"name": "guitarpaddy", "gm_prog": 25,  "bank_msb": 0,   "is_drum": False,
        "notes": [36, 41]},
    5: {"name": "dream bells", "gm_prog": 88,  "bank_msb": 0,   "is_drum": False,
        "notes": [84, 88, 91, 89, 93]},
    6: {"name": "piano tik",   "gm_prog": 115, "bank_msb": 0,   "is_drum": False,
        "notes": [96]},
    7: {"name": "bells",       "gm_prog": 14,  "bank_msb": 0,   "is_drum": False,
        "notes": [72, 74, 76]},
}


def build_track_header(track_num: int, info: dict) -> bytes:
    """Build 24-byte QY70 track header."""
    hdr = bytearray(24)

    # Common header (observed in all QY70 track dumps)
    hdr[0:12] = bytes([0x08, 0x04, 0x82, 0x01, 0x00, 0x40, 0x20,
                        0x08, 0x04, 0x82, 0x01, 0x00])
    hdr[12:14] = bytes([0x06, 0x1C])

    if info["is_drum"]:
        hdr[14] = 0x40  # Drum marker
        hdr[15] = 0x80
        hdr[16] = 0x87  # Drum note range
        hdr[17] = 0xF8
        hdr[18] = 0x80
        hdr[19] = 0x8E
        hdr[20] = 0x83
    elif track_num == 2:  # BASS
        hdr[14] = 0x00
        hdr[15] = 0x04  # Bass marker
        hdr[16] = 0x07
        hdr[17] = 0x78
        hdr[18] = 0x00
        hdr[19] = 0x07
        hdr[20] = 0x12
    else:
        # Melody/chord/pad
        hdr[14] = info["bank_msb"] & 0x7F
        hdr[15] = info["gm_prog"] & 0x7F
        hdr[16] = 0x07
        hdr[17] = 0x78
        hdr[18] = 0x00
        hdr[19] = 0x0F
        hdr[20] = 0x10

    # Pan area (bytes 21-23) — zeros = use XG default
    hdr[21] = 0x00
    hdr[22] = 0x00
    hdr[23] = 0x00

    return bytes(hdr)


def build_header_section(tempo_bpm: int) -> bytes:
    """Build the 640-byte QY70 header section (AL=0x7F)."""
    header = bytearray(640)

    # Tempo encoding: BPM = (range * 95 - 133) + offset
    range_byte = 2  # Range 2 covers 57-184 BPM
    for r in [2, 3, 1, 4]:
        base = r * 95 - 133
        off = tempo_bpm - base
        if 0 <= off <= 94:
            range_byte = r
            offset_byte = off
            break
    else:
        offset_byte = max(0, min(127, tempo_bpm - 57))

    header[0] = offset_byte & 0x7F

    # Encode range into MSBs of decoded[4:7]
    if range_byte & 0x04:
        header[4] |= 0x80
    if range_byte & 0x02:
        header[5] |= 0x80
    if range_byte & 0x01:
        header[6] |= 0x80

    # Style format marker: range >= 0x08 → style
    # For pattern: range < 0x08 (our range_byte is 1-4, so it's pattern format)

    # Yamaha fill pattern for "use XG defaults"
    FILL = bytes([0xBF, 0xDF, 0xEF, 0xF7, 0xFB, 0xFD, 0xFE])

    # Fill default regions
    for start, end in [(0x00F, 0x080), (0x137, 0x1B9), (0x1B9, 0x21C)]:
        for i in range(start, min(end, len(header))):
            header[i] = FILL[(i - start) % 7]

    # Structural constants (from captured QY70 patterns)
    if len(header) > 0x085:
        header[0x080:0x085] = bytes([0x03, 0x01, 0x40, 0x60, 0x30])

    return bytes(header)


def generate_qy70_syx(q7p_data: bytes, output_path: Path, verbose: bool = False):
    """Generate QY70 SysEx file from DECAY Q7P data."""
    # Extract tempo
    tempo_raw = struct.unpack(">H", q7p_data[0xA08:0xA0A])[0]
    tempo = tempo_raw // 10 if tempo_raw > 0 else 120

    messages = []

    # 1. Init
    messages.append(make_init_msg())

    # 2. Track data for Main A section (section 0, AL=0x00-0x07)
    # DECAY is a single-section pattern — put everything in Main A
    section_idx = 0
    tracks_sent = 0

    for track_num in range(8):
        info = TRACK_MAP.get(track_num)
        if info is None:
            continue

        al = section_idx * 8 + track_num

        # Build track block (128 bytes)
        block = bytearray(128)
        track_hdr = build_track_header(track_num, info)
        block[:24] = track_hdr

        # Minimal empty track data (after header)
        # Yamaha "empty track" fill pattern
        block[24:28] = bytes([0x1F, 0xA3, 0x60, 0x00])
        block[28:32] = bytes([0xDF, 0x77, 0xC0, 0x8F])

        msg = make_bulk_msg(al, bytes(block))
        messages.append(msg)
        tracks_sent += 1

        if verbose:
            voice_str = "DRUM" if info["is_drum"] else f"GM#{info['gm_prog']}"
            print(f"  Track {track_num} ({info['name']:14s}) → AL=0x{al:02X} {voice_str}")

    # 3. Header section (AL=0x7F)
    header_data = build_header_section(tempo)
    for chunk_start in range(0, len(header_data), 128):
        chunk = header_data[chunk_start:chunk_start + 128]
        msg = make_bulk_msg(0x7F, chunk)
        messages.append(msg)

    # 4. Close
    messages.append(make_close_msg())

    # Write SysEx file
    syx_data = b"".join(messages)
    output_path.write_bytes(syx_data)

    print(f"  Tempo: {tempo} BPM")
    print(f"  Tracks: {tracks_sent} (Main A section)")
    print(f"  Messages: {len(messages)} SysEx")
    print(f"  Size: {len(syx_data)} bytes")


if __name__ == "__main__":
    main()
