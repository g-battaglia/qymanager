#!/usr/bin/env python3
"""
Decode pattern header AL=0x7F (640 decoded bytes).

Hypothesis: header contains:
  - Pattern name (first bytes)
  - Tempo (already known: raw[0]*95 - 133 + raw[1])
  - Time signature
  - Per-track voice assignments (8 parts × N bytes)
  - Effect settings (reverb, chorus, variation)
  - Groove template reference

Cross-slot diff on first 128B header to identify fixed/variable regions.
"""

import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from qymanager.formats.qy70.sysex_parser import SysExParser

SLOTS = Path(__file__).parent.parent / "data" / "stored_slots"


def load_headers():
    headers = {}
    for f in sorted(SLOTS.iterdir()):
        if f.name.startswith(("._", "edit")) or not f.name.startswith("slot_"):
            continue
        parser = SysExParser()
        msgs = parser.parse_file(str(f))
        hdr = b""
        for m in msgs:
            if (m.address_high == 0x02 and
                (m.address_mid <= 0x1F or m.address_mid == 0x7E) and
                m.address_low == 0x7F and m.decoded_data):
                hdr += m.decoded_data
        if hdr:
            headers[f.name] = hdr
    return headers


def main():
    headers = load_headers()
    print(f"Loaded {len(headers)} pattern headers\n")

    sizes = {n: len(h) for n, h in headers.items()}
    print(f"Header sizes: {dict(Counter(sizes.values()).most_common())}")

    # First 64 bytes of each
    print(f"\n═══ First 64B of each header ═══")
    for name, hdr in list(headers.items())[:6]:
        print(f"\n  {name}:")
        for row in range(0, 64, 16):
            # Show hex + ASCII
            hex_str = hdr[row:row+16].hex(" ")
            ascii_str = "".join(chr(b) if 32 <= b < 127 else "." for b in hdr[row:row+16])
            print(f"    {row:4d}: {hex_str}  |{ascii_str}|")

    # Cross-header invariance first 256 bytes
    print(f"\n═══ Cross-slot byte invariance first 256B ═══")
    if len(headers) >= 2:
        hdr_list = list(headers.values())
        min_len = min(len(h) for h in hdr_list)
        check = min(256, min_len)
        distinct_counts = []
        for pos in range(check):
            vals = {h[pos] for h in hdr_list}
            distinct_counts.append(len(vals))
        # Print variable regions
        print(f"  Positions with different values across slots:")
        for pos in range(check):
            if distinct_counts[pos] > 1:
                vals = Counter(h[pos] for h in hdr_list)
                top = ", ".join(f"0x{v:02x}:{c}" for v, c in vals.most_common(4))
                print(f"    [{pos:4d}]: {distinct_counts[pos]} distinct → {top}")
                if pos > 60:
                    break

    # Look for pattern name: QY70 pattern names are up to 8 chars
    # Often at beginning of header
    print(f"\n═══ Pattern name extraction (first 16B as ASCII) ═══")
    for name, hdr in sorted(headers.items()):
        ascii_str = "".join(chr(b) if 32 <= b < 127 else "." for b in hdr[:16])
        print(f"  {name:30s}: [{ascii_str}]  raw={hdr[:16].hex(' ')}")


if __name__ == "__main__":
    main()
