#!/usr/bin/env python3
"""Byte-level editor per .syx QY70 (bulk dump).

Modifica campi sicuri senza passare dal bitstream encoder (che è rotto).

Campi supportati:
  --tempo BPM   Cambia tempo nel blocco header (AL=0x7F, primo chunk).
                Modifica decoded[0] (offset byte) usando formula:
                BPM = range*95 - 133 + offset, range=2 default.

Uso:
  python3 midi_tools/syx_edit.py input.syx --tempo 120 -o output.syx

Il file input deve essere un .syx QY70 valido (Init + bulk dumps + Close).
L'output mantiene tutti i messaggi originali tranne il primo AL=0x7F,
che viene ricodificato con il nuovo offset byte + checksum aggiornato.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from qymanager.utils.yamaha_7bit import decode_7bit, encode_7bit
from qymanager.utils.checksum import calculate_yamaha_checksum


def parse_sysex(data: bytes):
    """Split raw bytes into list of SysEx messages (F0..F7)."""
    msgs = []
    i = 0
    while i < len(data):
        if data[i] == 0xF0:
            j = i + 1
            while j < len(data) and data[j] != 0xF7:
                j += 1
            if j < len(data):
                msgs.append(data[i : j + 1])
                i = j + 1
            else:
                break
        else:
            i += 1
    return msgs


def is_bulk_header(msg: bytes) -> bool:
    """True if msg is a QY70 bulk dump with AL=0x7F."""
    return (
        len(msg) >= 11
        and msg[0] == 0xF0
        and msg[-1] == 0xF7
        and msg[1] == 0x43
        and (msg[2] & 0xF0) == 0x00
        and msg[3] == 0x5F
        and msg[8] == 0x7F
    )


def compute_tempo_encoding(bpm: int, preferred_range: int = 2):
    """Return (range_byte, offset_byte) that encodes target BPM.

    Tries ranges in order [preferred, 1, 3, 4, 2] to find a valid offset 0..127.
    """
    tried = [preferred_range] + [r for r in (1, 2, 3, 4) if r != preferred_range]
    for r in tried:
        base = r * 95 - 133
        off = bpm - base
        if 0 <= off <= 127:
            return r, off
    raise ValueError(f"BPM {bpm} cannot be encoded (out of range)")


def set_tempo_in_decoded(decoded: bytes, bpm: int) -> bytes:
    """Return new decoded bytes with first 7 bytes updated for target BPM.

    Preserves decoded[1..6] except for MSB bits that encode the range byte.
    """
    if len(decoded) < 7:
        raise ValueError("Decoded block too small")

    range_byte, offset_byte = compute_tempo_encoding(bpm)

    new_dec = bytearray(decoded)

    # decoded[0] = offset_byte (clear MSB, then set if range bit 6 wants it)
    new_dec[0] = offset_byte & 0x7F

    # The 7-bit group header at encoded[0] equals:
    #   header = sum over j in 0..6 of MSB(decoded[j]) << (6-j)
    # So to force header == range_byte, we set MSB(decoded[6-k]) = bit_k(range_byte)
    for k in range(7):
        bit = (range_byte >> k) & 1
        j_idx = 6 - k
        if bit:
            new_dec[j_idx] |= 0x80
        else:
            new_dec[j_idx] &= 0x7F

    # Re-enforce offset LSBs (decoded[0] MSB was just touched by range encoding)
    # k=6 sets MSB of decoded[0]. range_byte < 128 so bit 6 (k=6) can be 0 or 1.
    # For range=2, bit6=0 → MSB(decoded[0])=0 → decoded[0] stays at offset_byte & 0x7F.
    # Already handled by the loop.

    return bytes(new_dec)


def rebuild_bulk_message(original_msg: bytes, new_decoded: bytes) -> bytes:
    """Build a new bulk SysEx message preserving header/AL but with new 7-bit-encoded payload.

    Format: F0 43 0n 5F BH BL AH AM AL [encoded data] CS F7
    """
    header = original_msg[0:4]  # F0 43 0n 5F
    ah_am_al = original_msg[6:9]  # AH AM AL

    encoded = encode_7bit(new_decoded)
    bc = len(encoded)
    bh = (bc >> 7) & 0x7F
    bl = bc & 0x7F

    body = bytes([bh, bl]) + ah_am_al + encoded  # starts from BH
    cs = calculate_yamaha_checksum(body)

    return header + body + bytes([cs, 0xF7])


def edit_syx(input_data: bytes, *, bpm: int = None) -> bytes:
    """Apply edits to a .syx bulk dump. Returns new .syx bytes."""
    msgs = parse_sysex(input_data)
    if not msgs:
        raise ValueError("No SysEx messages found in input")

    first_header_idx = None
    for idx, msg in enumerate(msgs):
        if is_bulk_header(msg):
            first_header_idx = idx
            break

    if first_header_idx is None:
        raise ValueError("No AL=0x7F header block found")

    if bpm is not None:
        msg = msgs[first_header_idx]
        payload = bytes(msg[9:-2])
        decoded = decode_7bit(payload)
        new_decoded = set_tempo_in_decoded(decoded, bpm)
        msgs[first_header_idx] = rebuild_bulk_message(msg, new_decoded)

    return b"".join(msgs)


def main():
    ap = argparse.ArgumentParser(description="QY70 .syx byte-level editor")
    ap.add_argument("input", help="Input .syx file")
    ap.add_argument("-o", "--output", required=True, help="Output .syx path")
    ap.add_argument("--tempo", type=int, help="New tempo (BPM 30-300)")
    args = ap.parse_args()

    if args.tempo is None:
        ap.error("At least one edit flag required (--tempo)")

    if args.tempo is not None and not (30 <= args.tempo <= 300):
        ap.error(f"--tempo {args.tempo} out of range 30..300")

    data = Path(args.input).read_bytes()
    edited = edit_syx(data, bpm=args.tempo)
    Path(args.output).write_bytes(edited)

    print(f"Input:  {args.input} ({len(data)}B)")
    print(f"Output: {args.output} ({len(edited)}B)")
    if args.tempo is not None:
        r, off = compute_tempo_encoding(args.tempo)
        print(f"Tempo set: BPM={args.tempo} (range={r}, offset={off})")


if __name__ == "__main__":
    main()
