#!/usr/bin/env python3
"""Decode QY70 pattern name directory (AH=0x05).

Structure discovered Session 28:
- 20 slots × 16 bytes each
- Bytes 0-7: 8-char ASCII name (0x2A "*" = empty slot)
- Bytes 8-15: slot metadata (all zeros when empty)

Usage:
    python3 decode_pattern_names.py <ah_0x05.syx>
"""

import sys
from pathlib import Path


SLOT_COUNT = 20
SLOT_SIZE = 16
NAME_BYTES = 8
META_BYTES = SLOT_SIZE - NAME_BYTES


def parse_names(syx_bytes: bytes) -> list[dict]:
    """Parse a AH=0x05 SysEx dump and return a list of slot descriptors."""
    if syx_bytes[:4] != bytes([0xF0, 0x43, 0x00, 0x5F]):
        raise ValueError("Not a QY70 SysEx message (expected F0 43 00 5F prefix)")
    # Header: F0 43 00 5F 02 40 05 00 00 (9 bytes)
    # Trailer: CC F7 (2 bytes)
    body = syx_bytes[9:-2]
    if len(body) != SLOT_COUNT * SLOT_SIZE:
        raise ValueError(
            f"Unexpected body length {len(body)} (expected {SLOT_COUNT * SLOT_SIZE})"
        )
    out = []
    for i in range(SLOT_COUNT):
        chunk = body[i * SLOT_SIZE : (i + 1) * SLOT_SIZE]
        name_raw = chunk[:NAME_BYTES]
        name_str = name_raw.decode("ascii", errors="replace")
        is_empty = name_raw == b"\x2a" * NAME_BYTES
        out.append(
            {
                "index": i,
                "name": name_str,
                "name_hex": name_raw.hex(),
                "meta_hex": chunk[NAME_BYTES:].hex(),
                "empty": is_empty,
            }
        )
    return out


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    path = Path(sys.argv[1])
    syx = path.read_bytes()
    slots = parse_names(syx)
    print(f"Pattern directory: {path.name}")
    print(f"Slots: {len(slots)} (slot size {SLOT_SIZE}B, {NAME_BYTES}B name + {META_BYTES}B meta)")
    for slot in slots:
        marker = "EMPTY" if slot["empty"] else "     "
        print(
            f"  U{slot['index'] + 1:02}  [{marker}]  "
            f"name=[{slot['name']}]  meta={slot['meta_hex']}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
