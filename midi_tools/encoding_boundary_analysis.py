#!/usr/bin/env python3
"""
Encoding Boundary Analysis — Determine if 7-byte event periodicity
is a real structural boundary or an artifact of Yamaha 7-bit encoding.

Key question: Do QY70 events align to 7-byte decoded boundaries (= 8-byte
encoded boundaries), or do events freely cross encoding group boundaries?

Approach:
1. Look at raw encoded payloads — examine the header bytes (MSB carriers)
2. Compare encoded 8-byte groups with decoded 7-byte groups
3. Look for structural patterns that transcend encoding boundaries
4. Analyze the DC (0xDC) delimiter in both encoded and decoded domains
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qymanager.formats.qy70.sysex_parser import SysExParser
from qymanager.utils.yamaha_7bit import decode_7bit, encode_7bit


def hex_row(data, start=0, width=16):
    """Format bytes as hex with offset."""
    lines = []
    for i in range(0, len(data), width):
        chunk = data[i : i + width]
        hex_str = " ".join(f"{b:02X}" for b in chunk)
        lines.append(f"  {start + i:04X}: {hex_str}")
    return "\n".join(lines)


def analyze_encoding_boundaries(syx_path: str):
    """Main analysis."""
    parser = SysExParser()
    messages = parser.parse_file(syx_path)

    style_msgs = [m for m in messages if m.is_style_data]
    print(f"File: {syx_path}")
    print(f"Style messages: {len(style_msgs)}")
    print()

    # Focus on track messages (AL 0x00-0x2F), not header (AL 0x7F)
    track_names = {0: "D1", 1: "D2", 2: "BASS", 3: "C1", 4: "C2", 5: "PC", 6: "C3", 7: "C4/PHR"}
    section_names = {
        0: "S0/MAIN-A",
        1: "S1/MAIN-B",
        2: "S2/FILL-AB",
        3: "S3/INTRO",
        4: "S4/FILL-BA",
        5: "S5/ENDING",
    }

    # Find C1 track (track index 3) in section 0 (AL=0*8+3=3)
    c1_msgs = [m for m in style_msgs if m.address_low == 3]

    if not c1_msgs:
        print("No C1 messages found!")
        return

    msg = c1_msgs[0]
    print(f"=== C1 (Chord 1), Section 0, AL=0x{msg.address_low:02X} ===")
    print(f"Raw message size: {len(msg.raw)} bytes")
    print(f"Encoded payload size: {len(msg.data)} bytes")
    print(f"Decoded payload size: {len(msg.decoded_data)} bytes")
    print()

    # ---- PART 1: Show raw encoded data with 8-byte group boundaries ----
    print("=" * 80)
    print("PART 1: RAW ENCODED DATA (8-byte groups)")
    print("Each group: [HEADER] [7 data bytes]")
    print("Header byte carries the MSBs (bit 7) of the 7 data bytes")
    print("=" * 80)

    encoded = msg.data
    decoded = msg.decoded_data

    for group_idx in range(0, len(encoded), 8):
        enc_group = encoded[group_idx : group_idx + 8]
        if len(enc_group) < 2:
            break
        header = enc_group[0]
        data_bytes = enc_group[1:]

        # Decode this single group
        dec_group = decoded[group_idx * 7 // 8 : group_idx * 7 // 8 + 7]

        header_bits = f"{header:07b}"
        enc_hex = " ".join(f"{b:02X}" for b in enc_group)
        dec_hex = " ".join(f"{b:02X}" for b in dec_group)

        print(f"Group {group_idx // 8:2d} | Enc: {enc_hex}")
        print(f"         | Hdr: 0b{header_bits} (0x{header:02X})")
        print(f"         | Dec: {dec_hex}")
        print()

    # ---- PART 2: Look at the DC delimiter in encoded domain ----
    print("=" * 80)
    print("PART 2: DC (0xDC) DELIMITER POSITION IN BOTH DOMAINS")
    print("=" * 80)

    # Find DC in decoded data
    dc_positions_dec = [i for i, b in enumerate(decoded) if b == 0xDC]
    print(f"DC positions in DECODED data: {dc_positions_dec}")
    for pos in dc_positions_dec:
        group_num = pos // 7
        offset_in_group = pos % 7
        print(
            f"  Dec offset {pos}: decoded group {group_num}, position {offset_in_group} within group"
        )
        # Show context
        start = max(0, pos - 3)
        end = min(len(decoded), pos + 4)
        ctx = decoded[start:end]
        marker = pos - start
        hex_ctx = " ".join(f"[{b:02X}]" if i == marker else f" {b:02X} " for i, b in enumerate(ctx))
        print(f"  Context: {hex_ctx}")

    # Find DC in encoded data (note: 0xDC > 0x7F so it can't appear in encoded data!)
    dc_positions_enc = [
        i for i, b in enumerate(encoded) if b == 0x5C
    ]  # 0xDC with bit7 cleared = 0x5C
    print(
        f"\n0x5C positions in ENCODED data (could be 0xDC with MSB in header): {dc_positions_enc}"
    )
    for pos in dc_positions_enc:
        group_num = pos // 8
        offset_in_group = pos % 8
        # Check if the header bit for this position restores it to 0xDC
        if offset_in_group > 0:
            header = encoded[group_num * 8]
            bit_pos = 6 - (offset_in_group - 1)
            has_msb = (header >> bit_pos) & 1
            restored = 0x5C | (has_msb << 7)
            print(
                f"  Enc offset {pos}: group {group_num}, pos {offset_in_group} -> "
                f"header bit {bit_pos}={has_msb} -> restored 0x{restored:02X}"
            )

    # ---- PART 3: Alignment analysis ----
    print()
    print("=" * 80)
    print("PART 3: DO DC DELIMITERS FALL ON 7-BYTE GROUP BOUNDARIES?")
    print("=" * 80)

    for pos in dc_positions_dec:
        on_boundary = pos % 7 == 0
        print(
            f"  DC at decoded offset {pos}: group boundary? {'YES' if on_boundary else 'NO'} "
            f"(pos mod 7 = {pos % 7})"
        )

    # ---- PART 4: Header byte pattern analysis ----
    print()
    print("=" * 80)
    print("PART 4: HEADER BYTE (MSB) PATTERN")
    print("=" * 80)
    print("If events align to 7-byte groups, headers should show repeating patterns")
    print()

    headers = [encoded[i] for i in range(0, len(encoded), 8) if i < len(encoded)]
    print(f"Headers ({len(headers)} groups):")
    header_hex = " ".join(f"{h:02X}" for h in headers)
    print(f"  {header_hex}")
    header_bits_list = [f"{h:07b}" for h in headers]
    print(f"  {'  '.join(header_bits_list)}")

    # ---- PART 5: Cross-7-byte-boundary pattern search ----
    print()
    print("=" * 80)
    print("PART 5: CROSS-BOUNDARY PATTERN SEARCH")
    print("Look for repeating patterns that DON'T align to 7-byte groups")
    print("=" * 80)

    # Skip the 4-byte preamble
    event_data = decoded[4:]  # After XX XX 60 00 preamble
    print(f"Event data (after 4-byte preamble): {len(event_data)} bytes")

    # Test various period lengths
    for period in range(5, 12):
        # Count how many repeating n-byte patterns we find
        matches = 0
        total = 0
        for i in range(0, len(event_data) - period * 2, period):
            chunk1 = event_data[i : i + period]
            chunk2 = event_data[i + period : i + period * 2]
            total += 1
            if chunk1 == chunk2:
                matches += 1
        if total > 0:
            print(
                f"  Period {period}: {matches}/{total} exact repeats ({100 * matches / total:.1f}%)"
            )

    # ---- PART 6: Bit-level analysis across group boundaries ----
    print()
    print("=" * 80)
    print("PART 6: DECODED DATA AS CONTINUOUS BITSTREAM")
    print("Show the first 200 bytes as bits, marking 7-byte boundaries")
    print("=" * 80)

    # Convert decoded to bits
    bits = ""
    for b in decoded[:200]:
        bits += f"{b:08b}"

    # Print in rows of 56 bits (= 7 bytes = one decoded group)
    print("7-byte groups (56 bits each):")
    for i in range(0, min(len(bits), 56 * 20), 56):
        row = bits[i : i + 56]
        group_num = i // 56
        # Add spaces every 8 bits for readability
        spaced = " ".join(row[j : j + 8] for j in range(0, len(row), 8))
        print(f"  G{group_num:2d}: {spaced}")

    # Now print in rows of different sizes to see if another periodicity exists
    for test_bits in [40, 48, 56, 64, 72, 80]:
        test_bytes = test_bits / 8
        print(f"\n  --- {test_bits}-bit ({test_bytes:.0f}-byte) rows ---")
        # Skip first 32 bits (4-byte preamble)
        offset = 32
        for i in range(0, min(len(bits) - offset, test_bits * 8), test_bits):
            row = bits[offset + i : offset + i + test_bits]
            row_num = i // test_bits
            spaced = " ".join(row[j : j + 8] for j in range(0, len(row), 8))
            print(f"  R{row_num:2d}: {spaced}")

    # ---- PART 7: Compare ALL 8 tracks across section 0 ----
    print()
    print("=" * 80)
    print("PART 7: ALL TRACKS IN SECTION 0 — DC positions and event structure")
    print("=" * 80)

    for al in range(8):
        msgs = [m for m in style_msgs if m.address_low == al]
        if not msgs:
            continue
        m = msgs[0]
        name = track_names.get(al % 8, f"T{al}")
        dec = m.decoded_data
        dc_pos = [i for i, b in enumerate(dec) if b == 0xDC]
        print(f"\n  {name} (AL={al}): {len(dec)} decoded bytes, DC at {dc_pos}")

        # Show which 7-byte group each DC falls in
        for pos in dc_pos:
            print(f"    DC@{pos}: group {pos // 7}, offset_in_group {pos % 7}")

        # Check if DC always falls at position 0 of a 7-byte group
        if dc_pos:
            all_at_boundary = all(p % 7 == 0 for p in dc_pos)
            print(
                f"    All DC at 7-byte boundary? {'YES — artifact likely' if all_at_boundary else 'NO — real structure'}"
            )

    # ---- PART 8: Re-encode test ----
    print()
    print("=" * 80)
    print("PART 8: RE-ENCODE VERIFICATION")
    print("Decode then re-encode and compare to verify codec correctness")
    print("=" * 80)

    reencoded = encode_7bit(decoded)
    if reencoded == encoded[: len(reencoded)]:
        print("  PASS: Re-encoded data matches original encoded data")
    else:
        diffs = sum(1 for a, b in zip(reencoded, encoded) if a != b)
        print(f"  DIFF: {diffs} bytes differ between re-encoded and original")
        for i, (a, b) in enumerate(zip(reencoded, encoded)):
            if a != b:
                print(f"    Offset {i}: re-encoded 0x{a:02X} vs original 0x{b:02X}")
                if i > 10:
                    print(f"    ... ({diffs} total)")
                    break


def analyze_all_tracks_dc_alignment(syx_path: str):
    """Analyze DC alignment across ALL tracks in ALL sections."""
    parser = SysExParser()
    messages = parser.parse_file(syx_path)
    style_msgs = [m for m in messages if m.is_style_data]

    track_names = {0: "D1", 1: "D2", 2: "BASS", 3: "C1", 4: "C2", 5: "PC", 6: "C3", 7: "C4/PHR"}

    print()
    print("=" * 80)
    print("DC ALIGNMENT SUMMARY — ALL TRACKS, ALL SECTIONS")
    print("=" * 80)

    total_dc = 0
    at_boundary = 0
    not_at_boundary = 0

    for msg in style_msgs:
        al = msg.address_low
        if al == 0x7F:  # Skip header
            continue
        section = al // 8
        track = al % 8
        name = track_names.get(track, f"T{track}")
        dec = msg.decoded_data

        dc_pos = [i for i, b in enumerate(dec) if b == 0xDC]
        for pos in dc_pos:
            total_dc += 1
            if pos % 7 == 0:
                at_boundary += 1
            else:
                not_at_boundary += 1

    print(f"Total DC delimiters found: {total_dc}")
    print(f"  At 7-byte boundary (pos % 7 == 0): {at_boundary}")
    print(f"  NOT at boundary: {not_at_boundary}")
    if total_dc > 0:
        pct = at_boundary / total_dc * 100
        print(f"  Boundary alignment: {pct:.1f}%")
        if pct < 50:
            print("  CONCLUSION: DC does NOT align to encoding groups → events cross boundaries")
            print("  The 7-byte periodicity is an ENCODING ARTIFACT, not event structure")
        elif pct > 90:
            print("  CONCLUSION: DC strongly aligns to encoding groups → may be structural")
        else:
            print("  CONCLUSION: Partial alignment — needs more investigation")


def analyze_crossboundary_continuity(syx_path: str):
    """Check if data patterns continue across 7-byte group boundaries."""
    parser = SysExParser()
    messages = parser.parse_file(syx_path)
    style_msgs = [m for m in messages if m.is_style_data]

    track_names = {0: "D1", 1: "D2", 2: "BASS", 3: "C1", 4: "C2", 5: "PC", 6: "C3", 7: "C4/PHR"}

    print()
    print("=" * 80)
    print("CROSS-BOUNDARY CONTINUITY ANALYSIS")
    print("Look at bytes that straddle 7-byte group boundaries")
    print("=" * 80)

    # For each track, look at the byte BEFORE and AFTER each 7-byte boundary
    for msg in style_msgs:
        al = msg.address_low
        if al == 0x7F or al >= 8:  # Just section 0
            continue
        track = al % 8
        name = track_names.get(track, f"T{track}")
        dec = msg.decoded_data

        print(f"\n  {name} — boundary pairs (last_of_group, first_of_next):")
        pairs = []
        for boundary in range(7, len(dec) - 1, 7):
            before = dec[boundary - 1]
            after = dec[boundary]
            pairs.append((before, after))
            if len(pairs) <= 20:
                print(
                    f"    @{boundary}: ...{dec[boundary - 2]:02X} [{before:02X}|{after:02X}] {dec[boundary + 1]:02X}..."
                )

        # Check: do boundary bytes show any special values (like 0x00, 0xFF)?
        before_vals = [p[0] for p in pairs]
        after_vals = [p[1] for p in pairs]
        print(
            f"    Last-of-group values:  min=0x{min(before_vals):02X} max=0x{max(before_vals):02X} "
            f"mean={sum(before_vals) / len(before_vals):.1f}"
        )
        print(
            f"    First-of-next values:  min=0x{min(after_vals):02X} max=0x{max(after_vals):02X} "
            f"mean={sum(after_vals) / len(after_vals):.1f}"
        )


if __name__ == "__main__":
    syx_path = sys.argv[1] if len(sys.argv) > 1 else "tests/fixtures/QY70_SGT.syx"
    analyze_encoding_boundaries(syx_path)
    analyze_all_tracks_dc_alignment(syx_path)
    analyze_crossboundary_continuity(syx_path)
