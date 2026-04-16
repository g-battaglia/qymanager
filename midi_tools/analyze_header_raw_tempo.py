#!/usr/bin/env python3
"""
Search for tempo in RAW (pre-decode) SysEx message data.

The wiki claims: BPM = range × 95 - 133 + offset
where range and offset come from the raw data.

The 7-bit encoding means: for every 7 decoded bytes, there are 8 raw bytes.
Raw[0] = high-bit header, Raw[1-7] = data with MSB cleared.

So decoded[0] (the format marker) maps to raw[1] (low 7 bits) + raw[0] bit 6.

Let's check if raw[0] and raw[1] give us tempo via the formula.
Also check if the tempo is in the SysEx address bytes or message structure.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qymanager.formats.qy70.sysex_parser import SysExParser


def load_header_messages(syx_path):
    parser = SysExParser()
    messages = parser.parse_file(syx_path)
    header_msgs = []
    for msg in messages:
        if msg.is_style_data and msg.address_low == 0x7F:
            header_msgs.append(msg)
    return header_msgs


def analyze_raw(msgs, name, expected_bpm=None):
    print(f"\n{'='*70}")
    print(f"{name} — Header Messages ({len(msgs)} messages)")
    if expected_bpm:
        print(f"Expected BPM: {expected_bpm}")
    print("=" * 70)

    for mi, msg in enumerate(msgs):
        raw = msg.data
        decoded = msg.decoded_data
        print(f"\n  Message {mi}: raw={len(raw)}B, decoded={len(decoded)}B")
        print(f"    Raw first 16: {' '.join(f'{b:02X}' for b in raw[:16])}")
        print(f"    Decoded first 8: {' '.join(f'{b:02X}' for b in decoded[:8])}")

        # The raw data has 8-byte groups: [header, d0, d1, d2, d3, d4, d5, d6]
        # header bits 6-0 are MSBs for d0-d6 respectively
        print(f"\n    7-bit group analysis (first 4 groups):")
        for gi in range(min(4, len(raw) // 8)):
            group = raw[gi*8:(gi+1)*8]
            if len(group) < 8:
                break
            header_byte = group[0]
            data_bytes = group[1:8]
            print(f"      Group {gi}: header=0x{header_byte:02X} ({header_byte:07b})"
                  f" data=[{' '.join(f'{b:02X}' for b in data_bytes)}]")

            # Check tempo formula on header and first data byte
            # BPM = header_byte * 95 - 133 + data_bytes[0]
            if 0 < header_byte < 10:
                for offset_byte in data_bytes:
                    tempo = header_byte * 95 - 133 + offset_byte
                    if 40 <= tempo <= 300:
                        marker = ""
                        if expected_bpm and tempo == expected_bpm:
                            marker = " *** MATCH ***"
                        print(f"        Formula: {header_byte}×95-133+{offset_byte} = {tempo}{marker}")

        # Also try the formula on the RAW message as a whole
        # Check raw[0]*95-133+raw[1], raw[1]*95-133+raw[2], etc.
        if mi == 0:  # Only first message
            print(f"\n    Sequential raw byte tempo search:")
            for i in range(min(20, len(raw) - 1)):
                for j in range(i+1, min(i+8, len(raw))):
                    tempo = raw[i] * 95 - 133 + raw[j]
                    if expected_bpm and tempo == expected_bpm:
                        print(f"      raw[{i}]={raw[i]} × 95 - 133 + raw[{j}]={raw[j]} "
                              f"= {tempo} *** MATCH ***")
                    elif 40 <= tempo <= 300 and not expected_bpm:
                        print(f"      raw[{i}]={raw[i]} × 95 - 133 + raw[{j}]={raw[j]} = {tempo}")

    # Try DECODED byte formula: decoded[0] is format marker (3, 0x4C, 0x2C)
    # Maybe decoded[0] encodes range AND format, e.g. range = decoded[0] & 0x0F
    if msgs:
        d0 = msgs[0].decoded_data[0]
        d1 = msgs[0].decoded_data[1]
        print(f"\n  Decoded[0]={d0} (0x{d0:02X}), Decoded[1]={d1} (0x{d1:02X})")

        # Try range extraction methods
        for range_extract in [
            ("d0 raw", d0),
            ("d0 & 0x0F", d0 & 0x0F),
            ("d0 >> 4", d0 >> 4),
            ("d0 & 0x03", d0 & 0x03),
            ("d0 & 0x07", d0 & 0x07),
        ]:
            rname, rval = range_extract
            if 0 < rval < 10:
                base = rval * 95 - 133
                for offset_src in [d1, d1 & 0x7F, msgs[0].decoded_data[2] if len(msgs[0].decoded_data) > 2 else 0]:
                    tempo = base + offset_src
                    if 40 <= tempo <= 300:
                        marker = ""
                        if expected_bpm and tempo == expected_bpm:
                            marker = " *** MATCH ***"
                        print(f"    range={rname}={rval}, offset={offset_src}: "
                              f"{rval}×95-133+{offset_src} = {tempo}{marker}")


def main():
    files = [
        ("data/qy70_sysx/P -  Summer - 20231101.syx", "Summer", 110),
        ("data/qy70_sysx/P -  MR. Vain - 20231101.syx", "MR. Vain", 130),  # Guess
        ("midi_tools/captured/ground_truth_style.syx", "GT_style", None),
        ("midi_tools/captured/ground_truth_A.syx", "GT_A", 120),  # Default
    ]

    for path, name, bpm in files:
        if os.path.exists(path):
            msgs = load_header_messages(path)
            if msgs:
                analyze_raw(msgs, name, bpm)
            else:
                print(f"\n{name}: no header messages found")

    # Special: look at the raw SysEx bytes BEFORE the parser extracts data
    # The SysEx message format:
    # F0 43 00 5F 02 7E 7F [size_hi] [size_lo] [data...] [checksum] F7
    # The size bytes and data start might contain tempo
    print(f"\n{'='*70}")
    print("RAW SYSEX MESSAGE STRUCTURE ANALYSIS")
    print("=" * 70)

    for path, name, bpm in files:
        if not os.path.exists(path):
            continue
        msgs = load_header_messages(path)
        if not msgs:
            continue

        msg = msgs[0]  # First header message
        raw_syx = msg.raw  # Full raw SysEx bytes including F0...F7
        print(f"\n  {name}: raw SysEx first msg = {len(raw_syx)} bytes")
        print(f"    First 20: {' '.join(f'{b:02X}' for b in raw_syx[:20])}")

        # Address bytes: AH, AM, AL
        # AH = raw_syx[4] (should be 0x02)
        # AM = raw_syx[5] (should be 0x7E)
        # AL = raw_syx[6] (should be 0x7F)
        if len(raw_syx) > 10:
            print(f"    Address: AH=0x{raw_syx[4]:02X} AM=0x{raw_syx[5]:02X} AL=0x{raw_syx[6]:02X}")
            # Size bytes (if present)
            print(f"    After address: [{' '.join(f'{b:02X}' for b in raw_syx[7:12])}]")

            # Data starts after address bytes + potential size
            # Data payload is msg.data which we already analyzed
            # But maybe there are bytes between address and data that encode tempo?
            data_start = raw_syx.index(msg.data[0], 7) if msg.data else 7
            pre_data = raw_syx[7:data_start]
            if pre_data:
                print(f"    Pre-data bytes (between address and payload): "
                      f"{' '.join(f'{b:02X}' for b in pre_data)}")

    print("\nDone.")


if __name__ == "__main__":
    main()
