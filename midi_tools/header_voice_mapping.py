#!/usr/bin/env python3
"""
Extract voice info from AL=0x7F pattern header.

Hypothesis: first 16-20B of 640B header contain per-part voice assignments.
QY70 has 8 parts in pattern mode. Each part has voice (Bank+Prog) + mix.

8 parts × 4 bytes = 32 bytes potentially. Bytes 0-13 look like metadata
(pattern name packed + tempo). Bytes 14+ may be part voice/config.
"""

import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from qymanager.formats.qy70.sysex_parser import SysExParser

SLOTS = Path(__file__).parent.parent / "data" / "stored_slots"
SGT = Path(__file__).parent.parent / "tests" / "fixtures" / "QY70_SGT.syx"


def parse_header(path):
    parser = SysExParser()
    msgs = parser.parse_file(str(path))
    hdr = b""
    for m in msgs:
        if not (m.address_high == 0x02 and
                (m.address_mid <= 0x1F or m.address_mid == 0x7E)
                and m.decoded_data and m.address_low == 0x7F):
            continue
        hdr += m.decoded_data
    return hdr


def main():
    headers = {}
    for f in sorted(SLOTS.iterdir()):
        if f.name.startswith(("._", "edit")) or not f.name.startswith("slot_"):
            continue
        h = parse_header(f)
        if h:
            headers[f.name] = h

    # Add SGT file header for reference
    sgt_hdr = parse_header(SGT)
    if sgt_hdr:
        headers["SGT_file.syx"] = sgt_hdr

    print(f"Loaded {len(headers)} headers (size {len(list(headers.values())[0]) if headers else 0}B each)\n")

    # Show first 48B of each — expect voice info per part
    print(f"═══ First 48B of each header (hex + ASCII) ═══")
    for name, hdr in list(headers.items())[:6]:
        print(f"\n  {name}:")
        for row in range(0, 48, 16):
            hex_str = hdr[row:row+16].hex(" ")
            ascii_str = "".join(chr(b) if 32 <= b < 127 else "." for b in hdr[row:row+16])
            print(f"    {row:4d}: {hex_str}  |{ascii_str}|")

    # Decode name: first try bytes 0-13 as 7-bit packed ASCII or direct bytes
    print(f"\n═══ Pattern name candidates (bytes 0-13) ═══")
    for name, hdr in headers.items():
        raw = hdr[:14]
        # Try 7-bit ASCII direct (if high bit set strip)
        ascii_try = "".join(chr(b & 0x7F) if 32 <= (b & 0x7F) < 127 else "." for b in raw)
        print(f"  {name:30s}: hex={raw.hex(' ')}  try1=[{ascii_try}]")

    # Byte-level entropy per position 0-32
    print(f"\n═══ Byte entropy positions 0-32 (cross-slot) ═══")
    hdr_list = list(headers.values())
    for pos in range(32):
        vals = Counter(h[pos] for h in hdr_list)
        top = ", ".join(f"0x{v:02x}:{c}" for v, c in vals.most_common(4))
        print(f"  [{pos:3d}]: {len(vals)} distinct → {top}")


if __name__ == "__main__":
    main()
