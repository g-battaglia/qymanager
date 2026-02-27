#!/usr/bin/env python3
"""
Decode QY70 SysEx header name encoding.

The QY70 stores style names in the header (AL=0x7F). This script attempts
to find and decode the name by:
  1. Searching for known ASCII patterns in the raw and decoded data
  2. Analyzing the raw SysEx payload (before 7-bit decoding) for name bytes
  3. Trying various bit manipulations on candidate regions
  4. Cross-referencing with the captured pattern dump

Known style names to search for:
  - SGT file: name should contain "SGT" or similar
  - Captured pattern: unknown name

Usage:
    cd /Volumes/Data/DK/XG/T700/qyconv
    source .venv/bin/activate
    python3 midi_tools/decode_header_name.py
"""

import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent))
from qymanager.utils.yamaha_7bit import decode_7bit, encode_7bit

# ── Constants ────────────────────────────────────────────────────────────────

FIXTURES = Path(__file__).parent.parent / "tests" / "fixtures"
SGT_FILE = FIXTURES / "QY70_SGT.syx"
CAPTURED_FILE = Path(__file__).parent / "captured" / "qy70_dump_20260226_200743.syx"
NEONGROOVE_FILE = FIXTURES / "NEONGROOVE.syx"

SYSEX_START = 0xF0
SYSEX_END = 0xF7
YAMAHA_ID = 0x43
QY70_MODEL = 0x5F


# ── SysEx Parsing ────────────────────────────────────────────────────────────


def parse_sysex_messages(raw: bytes) -> List[bytes]:
    """Split raw .syx into individual F0..F7 messages."""
    msgs = []
    start = None
    for i, b in enumerate(raw):
        if b == SYSEX_START:
            start = i
        elif b == SYSEX_END and start is not None:
            msgs.append(raw[start : i + 1])
            start = None
    return msgs


def get_header_messages(raw: bytes) -> List[bytes]:
    """Return only bulk dump messages for AL=0x7F (header)."""
    header_msgs = []
    for msg in parse_sysex_messages(raw):
        if len(msg) < 11:
            continue
        if msg[1] != YAMAHA_ID or msg[3] != QY70_MODEL:
            continue
        if (msg[2] & 0xF0) != 0x00:
            continue
        ah, am, al = msg[6], msg[7], msg[8]
        if ah == 0x02 and am == 0x7E and al == 0x7F:
            header_msgs.append(msg)
    return header_msgs


def get_full_header_decoded(raw: bytes) -> bytes:
    """Get concatenated decoded header data."""
    header = bytearray()
    for msg in get_header_messages(raw):
        payload = msg[9:-2]  # Between address and checksum
        decoded = decode_7bit(payload)
        header.extend(decoded)
    return bytes(header)


def get_raw_payloads(raw: bytes) -> List[bytes]:
    """Get raw (pre-7bit-decode) payloads of header messages."""
    payloads = []
    for msg in get_header_messages(raw):
        payload = msg[9:-2]
        payloads.append(payload)
    return payloads


# ── Analysis Functions ───────────────────────────────────────────────────────


def search_ascii(data: bytes, label: str) -> None:
    """Search for printable ASCII strings in data."""
    print(f"\n  --- ASCII search in {label} ({len(data)} bytes) ---")

    # Find all runs of 3+ printable ASCII chars
    runs = []
    current_start = None
    current_chars = []

    for i, b in enumerate(data):
        if 32 <= b < 127:
            if current_start is None:
                current_start = i
                current_chars = []
            current_chars.append(chr(b))
        else:
            if current_start is not None and len(current_chars) >= 3:
                runs.append((current_start, "".join(current_chars)))
            current_start = None
            current_chars = []

    if current_start is not None and len(current_chars) >= 3:
        runs.append((current_start, "".join(current_chars)))

    if runs:
        for off, text in runs:
            # Show context
            ctx_start = max(0, off - 4)
            ctx_end = min(len(data), off + len(text) + 4)
            ctx = data[ctx_start:ctx_end]
            ctx_hex = " ".join(f"{b:02X}" for b in ctx)
            print(f'    0x{off:03X}: "{text}" ({len(text)} chars)  ctx: [{ctx_hex}]')
    else:
        print("    No ASCII strings found (3+ chars)")


def analyze_name_region(decoded: bytes, raw_payloads: List[bytes], label: str) -> None:
    """Deep analysis of potential name regions in the header."""
    print(f"\n{'=' * 90}")
    print(f"NAME ENCODING ANALYSIS: {label}")
    print(f"{'=' * 90}")

    # 1. Search decoded header for ASCII
    search_ascii(decoded, f"{label} decoded header")

    # 2. Search raw payloads for ASCII
    for i, payload in enumerate(raw_payloads):
        search_ascii(payload, f"{label} raw payload msg {i}")

    # 3. First message raw payload — most likely to contain name
    if raw_payloads:
        first_raw = raw_payloads[0]
        first_decoded = decode_7bit(first_raw)
        print(f"\n  --- First header message raw payload ({len(first_raw)} bytes) ---")
        for row in range(0, min(len(first_raw), 160), 16):
            chunk = first_raw[row : row + 16]
            hex_str = " ".join(f"{b:02X}" for b in chunk)
            asc = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
            print(f"    {row:04X}: {hex_str:<52} {asc}")

        print(f"\n  --- First header message decoded ({len(first_decoded)} bytes) ---")
        for row in range(0, min(len(first_decoded), 128), 16):
            chunk = first_decoded[row : row + 16]
            hex_str = " ".join(f"{b:02X}" for b in chunk)
            asc = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
            print(f"    {row:04X}: {hex_str:<52} {asc}")

    # 4. Try various bit manipulations on decoded header bytes 0-30
    print(f"\n  --- Bit manipulation attempts on decoded[0:32] ---")
    region = decoded[:32]

    # a) Direct ASCII (already done above, but show explicitly)
    direct = "".join(chr(b) if 32 <= b < 127 else "." for b in region)
    print(f"    Direct:      {direct}")

    # b) Mask off bit 7
    masked = "".join(chr(b & 0x7F) if 32 <= (b & 0x7F) < 127 else "." for b in region)
    print(f"    Masked 0x7F: {masked}")

    # c) Each nibble as BCD
    nibbles = []
    for b in region:
        nibbles.append((b >> 4) & 0x0F)
        nibbles.append(b & 0x0F)
    # Try pairs of nibbles as ASCII
    bcd = ""
    for i in range(0, len(nibbles) - 1, 2):
        val = nibbles[i] * 16 + nibbles[i + 1]
        bcd += chr(val) if 32 <= val < 127 else "."
    print(f"    BCD nibbles: {bcd}")

    # d) Try 6-bit encoding (Yamaha sometimes uses 6-bit for names)
    print(f"\n  --- 6-bit character encoding attempt ---")
    # QY70 might use a 6-bit charset: 0-9=0x30-0x39, A-Z=0x41-0x5A, space=0x20
    # Packed 6 bits per char, 4 chars per 3 bytes

    def yamaha_6bit_decode(data: bytes, offset: int, num_chars: int) -> str:
        """Try to decode 6-bit packed characters."""
        # Extract bits
        bits = []
        for b in data[offset:]:
            for i in range(7, -1, -1):
                bits.append((b >> i) & 1)
            if len(bits) >= num_chars * 6:
                break

        result = []
        for i in range(0, min(len(bits), num_chars * 6), 6):
            val = 0
            for j in range(6):
                if i + j < len(bits):
                    val = (val << 1) | bits[i + j]
            # Map to character
            if val == 0:
                result.append(" ")
            elif 1 <= val <= 26:
                result.append(chr(ord("A") + val - 1))
            elif 27 <= val <= 36:
                result.append(chr(ord("0") + val - 27))
            elif val == 37:
                result.append("-")
            elif val == 38:
                result.append(".")
            elif val == 39:
                result.append("_")
            else:
                result.append(f"[{val}]")
        return "".join(result)

    # Try at various offsets in decoded header
    for off in range(0, 20):
        name_6bit = yamaha_6bit_decode(decoded, off, 8)
        if any(c.isalpha() for c in name_6bit):
            print(f'    offset 0x{off:02X}: "{name_6bit}"')

    # e) Try Yamaha 5-bit encoding
    print(f"\n  --- 5-bit character encoding attempt ---")
    for off in range(0, 20):
        bits = []
        for b in decoded[off : off + 8]:
            for i in range(7, -1, -1):
                bits.append((b >> i) & 1)

        result = []
        for i in range(0, min(len(bits), 12 * 5), 5):
            val = 0
            for j in range(5):
                if i + j < len(bits):
                    val = (val << 1) | bits[i + j]
            if val == 0:
                result.append(" ")
            elif 1 <= val <= 26:
                result.append(chr(ord("A") + val - 1))
            elif 27 <= val <= 31:
                result.append(chr(ord("0") + val - 27))
            else:
                result.append("?")
        name_5bit = "".join(result)
        if any(c.isalpha() for c in name_5bit):
            print(f'    offset 0x{off:02X}: "{name_5bit}"')

    # 5. QY700 name region for reference
    print(f"\n  --- QY700 Q7P name encoding for reference ---")
    q7p_files = list(FIXTURES.glob("*.Q7P"))
    for q7p_path in q7p_files:
        q7p_data = q7p_path.read_bytes()
        if len(q7p_data) >= 0x880:
            name_region = q7p_data[0x876:0x880]
            name_str = "".join(chr(b) if 32 <= b < 127 else "." for b in name_region)
            name_hex = " ".join(f"{b:02X}" for b in name_region)
            print(f'    {q7p_path.name}: name at 0x876 = [{name_hex}] = "{name_str}"')

    # 6. Focused search: look for "S", "G", "T" sequence or variations
    print(f"\n  --- Searching for 'SGT' variants in decoded header ---")
    sgt_bytes = [ord("S"), ord("G"), ord("T")]  # 0x53, 0x47, 0x54

    for spacing in [1, 2, 3]:
        for off in range(len(decoded) - spacing * 3):
            chars = [decoded[off + i * spacing] for i in range(3)]
            if chars == sgt_bytes:
                print(f"    EXACT 'SGT' at offset 0x{off:03X} with spacing {spacing}")
                ctx_start = max(0, off - 4)
                ctx_end = min(len(decoded), off + spacing * 3 + 4)
                ctx = decoded[ctx_start:ctx_end]
                print(f"    context: {' '.join(f'{b:02X}' for b in ctx)}")

    # Also search in raw payloads
    for pi, payload in enumerate(raw_payloads):
        for off in range(len(payload) - 2):
            if payload[off] == 0x53 and payload[off + 1] == 0x47:
                print(f"    'SG' found in raw payload {pi} at offset 0x{off:02X}")
                ctx = payload[max(0, off - 4) : off + 8]
                print(f"    context: {' '.join(f'{b:02X}' for b in ctx)}")

    # 7. Compare first 32 bytes between files
    print(f"\n  --- Decoded header[0:32] hex ---")
    hex_str = " ".join(f"{b:02X}" for b in decoded[:32])
    print(f"    {hex_str}")


def compare_name_regions(files: Dict[str, bytes]) -> None:
    """Compare potential name regions across files."""
    print(f"\n{'=' * 90}")
    print(f"CROSS-FILE NAME REGION COMPARISON")
    print(f"{'=' * 90}")

    decoded_headers = {}
    for name, raw in files.items():
        decoded_headers[name] = get_full_header_decoded(raw)

    # Compare decoded headers byte by byte in the first 32 bytes
    print(f"\n  First 32 decoded header bytes:")
    for name, decoded in decoded_headers.items():
        hex_str = " ".join(f"{b:02X}" for b in decoded[:32])
        asc = "".join(chr(b) if 32 <= b < 127 else "." for b in decoded[:32])
        print(f"    {name:12s}: {hex_str}")
        print(f"    {'':12s}  {asc}")

    # Find bytes that differ between files
    if len(decoded_headers) >= 2:
        names = list(decoded_headers.keys())
        headers = list(decoded_headers.values())
        min_len = min(len(h) for h in headers)

        print(f"\n  Bytes that differ in first 64 bytes:")
        for i in range(min(64, min_len)):
            vals = [h[i] for h in headers]
            if len(set(vals)) > 1:
                val_str = "  ".join(
                    f"{n}=0x{v:02X}({chr(v) if 32 <= v < 127 else '.'})"
                    for n, v in zip(names, vals)
                )
                print(f"    offset 0x{i:03X}: {val_str}")


def analyze_raw_message_structure(raw: bytes, label: str) -> None:
    """Analyze the raw SysEx message structure for header messages."""
    print(f"\n{'=' * 90}")
    print(f"RAW MESSAGE STRUCTURE: {label}")
    print(f"{'=' * 90}")

    msgs = get_header_messages(raw)
    print(f"\n  Header messages: {len(msgs)}")

    for i, msg in enumerate(msgs):
        # Show complete message structure
        bh, bl = msg[4], msg[5]
        ah, am, al = msg[6], msg[7], msg[8]
        byte_count = (bh << 7) | bl
        payload = msg[9:-2]
        checksum = msg[-2]

        print(f"\n  Message {i}:")
        print(f"    Device byte: 0x{msg[2]:02X}")
        print(f"    Byte count: BH=0x{bh:02X} BL=0x{bl:02X} -> {byte_count}")
        print(f"    Address: AH=0x{ah:02X} AM=0x{am:02X} AL=0x{al:02X}")
        print(f"    Payload: {len(payload)} bytes")
        print(f"    Checksum: 0x{checksum:02X}")

        # Show the raw payload with 7-bit header bytes highlighted
        print(f"\n    Raw payload (header bytes marked with *):")
        decoded = decode_7bit(payload)
        # In 7-bit encoding, every 8th byte (starting at 0) is a header byte
        for row in range(0, len(payload), 16):
            chunk = payload[row : row + 16]
            parts = []
            for j, b in enumerate(chunk):
                byte_pos = row + j
                if byte_pos % 8 == 0:
                    parts.append(f"*{b:02X}")
                else:
                    parts.append(f" {b:02X}")
            hex_str = " ".join(parts)
            print(f"      {row:04X}: {hex_str}")

        print(f"\n    Decoded ({len(decoded)} bytes):")
        for row in range(0, len(decoded), 16):
            chunk = decoded[row : row + 16]
            hex_str = " ".join(f"{b:02X}" for b in chunk)
            asc = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
            print(f"      {row:04X}: {hex_str:<52} {asc}")


# ── Main ─────────────────────────────────────────────────────────────────────


def main():
    print("=" * 90)
    print("QY70 HEADER NAME DECODING ANALYSIS")
    print("=" * 90)

    files = {}
    for name, path in [
        ("SGT", SGT_FILE),
        ("CAPTURED", CAPTURED_FILE),
        ("NEONGROOVE", NEONGROOVE_FILE),
    ]:
        if path.exists():
            files[name] = path.read_bytes()
            print(f"  Loaded {name}: {path} ({len(files[name])} bytes)")
        else:
            print(f"  Not found: {path}")

    if not files:
        print("ERROR: No files found")
        sys.exit(1)

    # Analyze each file
    for name, raw in files.items():
        decoded = get_full_header_decoded(raw)
        raw_payloads = get_raw_payloads(raw)
        analyze_name_region(decoded, raw_payloads, name)
        analyze_raw_message_structure(raw, name)

    # Compare across files
    compare_name_regions(files)

    print(f"\n{'=' * 90}")
    print("ANALYSIS COMPLETE")
    print(f"{'=' * 90}")


if __name__ == "__main__":
    main()
