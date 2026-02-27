#!/usr/bin/env python3
"""
Deep analysis of QY70 SysEx header (AL=0x7F, 640 decoded bytes).

Searches for volume, reverb, chorus, pan, and other per-track mixer
parameters by examining byte patterns, XG default value clusters,
and comparing two different SysEx files.

Usage:
    cd /Volumes/Data/DK/XG/T700/qyconv
    source .venv/bin/activate
    python3 midi_tools/analyze_header.py
"""

import sys
from pathlib import Path
from collections import Counter
from typing import Dict, List, Optional, Tuple

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from qymanager.formats.qy70.sysex_parser import SysExParser, SysExMessage, MessageType
from qymanager.utils.yamaha_7bit import decode_7bit


# ─── Constants ───────────────────────────────────────────────────────────────

FIXTURES = Path(__file__).parent.parent / "tests" / "fixtures"
SGT_FILE = FIXTURES / "QY70_SGT.syx"
CAPTURED_FILE = Path(__file__).parent / "captured" / "qy70_dump_20260226_200743.syx"

# XG default values
XG_VOLUME = 100  # 0x64
XG_PAN_CENTER = 64  # 0x40
XG_REVERB = 40  # 0x28
XG_CHORUS = 0  # 0x00

QY70_TRACKS = ["D1", "D2", "PC", "BA", "C1", "C2", "C3", "C4"]
SECTION_NAMES = ["Intro", "MainA", "MainB", "FillAB", "FillBA", "Ending"]


# ─── SysEx extraction helpers ───────────────────────────────────────────────


def extract_header_blocks(filepath: Path) -> Tuple[bytes, Dict[int, bytes], List[SysExMessage]]:
    """
    Parse a SysEx file and extract AL=0x7F header blocks.

    Returns:
        (concatenated_header, section_data_dict, all_header_messages)
    """
    data = filepath.read_bytes()
    parser = SysExParser()
    messages = parser.parse_bytes(data)

    # Group decoded data by AL
    section_data: Dict[int, bytearray] = {}
    header_messages: List[SysExMessage] = []

    for msg in messages:
        if not msg.is_style_data:
            continue
        al = msg.address_low
        if msg.decoded_data:
            if al not in section_data:
                section_data[al] = bytearray()
            section_data[al].extend(msg.decoded_data)
        if al == 0x7F:
            header_messages.append(msg)

    header = bytes(section_data.get(0x7F, b""))
    return header, {k: bytes(v) for k, v in section_data.items()}, header_messages


def hex_row(data: bytes, max_bytes: int = 16) -> str:
    return " ".join(f"{b:02X}" for b in data[:max_bytes])


def ascii_col(data: bytes) -> str:
    return "".join(chr(b) if 32 <= b < 127 else "." for b in data)


# ─── Analysis functions ─────────────────────────────────────────────────────


def annotated_hexdump(header: bytes, label: str) -> None:
    """Full annotated hexdump of the 640-byte header."""
    print(f"\n{'=' * 100}")
    print(f"HEXDUMP: {label} ({len(header)} bytes)")
    print(f"{'=' * 100}")

    # Known field annotations
    annotations = {
        0x000: "Tempo range (raw payload byte 0)",
        0x004: "Tempo MSB bits area",
    }

    # XG default value markers
    xg_markers = {
        0x64: "VOL",  # Volume default 100
        0x28: "REV",  # Reverb default 40
        0x40: "PAN",  # Pan center 64
        0x00: "ZRO",  # Zero / chorus default
    }

    print(f"\n  Legend: VOL=0x64(100), REV=0x28(40), PAN=0x40(64), ZRO=0x00")
    print(f"  {'Offset':<8} {'Hex dump':<52} {'ASCII':<18} {'XG markers'}")
    print(f"  {'─' * 8} {'─' * 52} {'─' * 18} {'─' * 30}")

    for offset in range(0, len(header), 16):
        chunk = header[offset : min(offset + 16, len(header))]
        hex_str = " ".join(f"{b:02X}" for b in chunk)
        asc_str = ascii_col(chunk)

        # Build XG marker string
        markers = []
        for i, b in enumerate(chunk):
            if b in xg_markers and b != 0x00:  # Skip zero markers (too noisy)
                markers.append(f"+{i}={xg_markers[b]}")
            elif b == 0x00 and all(x == 0 for x in chunk):
                markers = ["ALL ZERO"]
                break

        marker_str = " ".join(markers) if markers else ""

        # Check for annotation
        ann = annotations.get(offset, "")
        if ann:
            marker_str = f"<< {ann}"

        print(f"  0x{offset:03X}:  {hex_str:<52} {asc_str:<18} {marker_str}")


def search_xg_default_clusters(header: bytes, label: str) -> None:
    """Search for clusters of XG default values (8 consecutive bytes)."""
    print(f"\n{'=' * 100}")
    print(f"XG DEFAULT VALUE CLUSTER SEARCH: {label}")
    print(f"{'=' * 100}")

    searches = [
        (0x64, 100, "Volume", "8 consecutive bytes = 0x64 (100)"),
        (0x28, 40, "Reverb Send", "8 consecutive bytes = 0x28 (40)"),
        (0x40, 64, "Pan Center", "8 consecutive bytes = 0x40 (64)"),
        (0x00, 0, "Chorus Send", "8 consecutive bytes = 0x00 (0)"),
    ]

    for val, dec, name, desc in searches:
        print(f"\n  --- {name} (0x{val:02X} = {dec}) ---")
        print(f"  Looking for: {desc}")

        # Exact match: 8 identical bytes
        exact_matches = []
        for i in range(len(header) - 7):
            if all(header[i + j] == val for j in range(8)):
                exact_matches.append(i)

        if exact_matches:
            print(f"  EXACT matches (8×0x{val:02X}):")
            for off in exact_matches:
                context_start = max(0, off - 4)
                context_end = min(len(header), off + 12)
                ctx = header[context_start:context_end]
                print(f"    0x{off:03X}: context = {hex_row(ctx, 20)}")
        else:
            print(f"  No exact 8-byte clusters found.")

        # Partial match: at least 6 of 8 bytes match
        partial_matches = []
        for i in range(len(header) - 7):
            match_count = sum(1 for j in range(8) if header[i + j] == val)
            if match_count >= 6 and match_count < 8:
                partial_matches.append((i, match_count))

        if partial_matches:
            print(f"  Partial matches (6-7 of 8 bytes = 0x{val:02X}):")
            for off, cnt in partial_matches[:10]:
                window = header[off : off + 8]
                print(f"    0x{off:03X}: [{hex_row(window)}] ({cnt}/8 match)")

        # Range match: 8 bytes all in reasonable range for this parameter
        if name == "Volume":
            range_matches = []
            for i in range(len(header) - 7):
                window = header[i : i + 8]
                if all(40 <= b <= 127 for b in window):
                    range_matches.append((i, list(window)))
            if range_matches:
                print(f"  Range matches (8 bytes in 40-127 = plausible volumes):")
                for off, vals in range_matches[:15]:
                    avg = sum(vals) / len(vals)
                    print(f"    0x{off:03X}: {vals} (avg={avg:.0f})")

        if name == "Pan Center":
            # Look for 8 bytes where values are in 0-127 and vary (different pans)
            varied_matches = []
            for i in range(len(header) - 7):
                window = header[i : i + 8]
                if all(0 <= b <= 127 for b in window):
                    unique = len(set(window))
                    if 2 <= unique <= 8 and any(30 <= b <= 98 for b in window):
                        varied_matches.append((i, list(window)))
            if varied_matches and len(varied_matches) < 50:
                print(f"  Varied pan candidates (8 bytes in 0-127 range, 2-8 unique values):")
                for off, vals in varied_matches[:15]:
                    pan_labels = []
                    for v in vals:
                        if v == 64:
                            pan_labels.append("C")
                        elif v < 64:
                            pan_labels.append(f"L{64 - v}")
                        elif v == 0:
                            pan_labels.append("Rnd")
                        else:
                            pan_labels.append(f"R{v - 64}")
                    print(f"    0x{off:03X}: {vals}  pans=[{', '.join(pan_labels)}]")

    # Also search for groups of 6 (one per section) or 48 (8 tracks × 6 sections)
    print(f"\n  --- Groups of 6 identical bytes (one value per section) ---")
    for val in [0x64, 0x28, 0x40, 0x00]:
        matches = []
        for i in range(len(header) - 5):
            if all(header[i + j] == val for j in range(6)):
                # Make sure it's not part of a larger run
                before = header[i - 1] if i > 0 else -1
                after = header[i + 6] if i + 6 < len(header) else -1
                if before != val or after != val:
                    matches.append(i)
        if matches:
            print(f"    0x{val:02X}: found at offsets {[f'0x{m:03X}' for m in matches[:10]]}")


def compare_headers(header_a: bytes, header_b: bytes, label_a: str, label_b: str) -> None:
    """Byte-by-byte comparison of two headers."""
    print(f"\n{'=' * 100}")
    print(f"HEADER COMPARISON: {label_a} vs {label_b}")
    print(f"{'=' * 100}")

    len_a = len(header_a)
    len_b = len(header_b)
    max_len = max(len_a, len_b)
    min_len = min(len_a, len_b)

    print(f"\n  Sizes: {label_a}={len_a} bytes, {label_b}={len_b} bytes")

    if len_a != len_b:
        print(f"  WARNING: Size mismatch! Delta = {abs(len_a - len_b)} bytes")

    # Count differences
    diffs = []
    identical_ranges = []
    diff_ranges = []

    in_identical = True
    range_start = 0

    for i in range(min_len):
        a = header_a[i]
        b = header_b[i]
        if a != b:
            diffs.append((i, a, b))
            if in_identical:
                if i > range_start:
                    identical_ranges.append((range_start, i - 1))
                range_start = i
                in_identical = False
        else:
            if not in_identical:
                diff_ranges.append((range_start, i - 1))
                range_start = i
                in_identical = True

    # Close final range
    if in_identical and range_start < min_len:
        identical_ranges.append((range_start, min_len - 1))
    elif not in_identical and range_start < min_len:
        diff_ranges.append((range_start, min_len - 1))

    print(
        f"\n  Total differences: {len(diffs)} out of {min_len} bytes ({len(diffs) / min_len * 100:.1f}%)"
    )
    print(f"  Identical ranges: {len(identical_ranges)}")
    print(f"  Different ranges: {len(diff_ranges)}")

    # Show identical ranges
    print(f"\n  --- Identical Regions ---")
    for start, end in identical_ranges:
        size = end - start + 1
        if size >= 4:
            print(f"    0x{start:03X}-0x{end:03X} ({size:3d} bytes) IDENTICAL")

    # Show different ranges with values
    print(f"\n  --- Different Regions (musical parameters likely here!) ---")
    for start, end in diff_ranges:
        size = end - start + 1
        chunk_a = header_a[start : end + 1]
        chunk_b = header_b[start : end + 1]
        print(f"    0x{start:03X}-0x{end:03X} ({size:3d} bytes) DIFFERENT")
        if size <= 32:
            print(f"      {label_a}: {hex_row(chunk_a, 32)}")
            print(f"      {label_b}: {hex_row(chunk_b, 32)}")
        else:
            print(f"      {label_a} first 16: {hex_row(chunk_a[:16])}")
            print(f"      {label_b} first 16: {hex_row(chunk_b[:16])}")
            print(f"      {label_a} last 16:  {hex_row(chunk_a[-16:])}")
            print(f"      {label_b} last 16:  {hex_row(chunk_b[-16:])}")

    # Detailed diff table for different bytes
    if len(diffs) <= 200:
        print(f"\n  --- Full Diff Table ---")
        print(f"  {'Offset':<8} {label_a:<6} {label_b:<6} {'Delta':<8} {'Notes'}")
        print(f"  {'─' * 8} {'─' * 6} {'─' * 6} {'─' * 8} {'─' * 40}")
        for off, a, b in diffs:
            delta = b - a
            notes = []
            if a == 0x64:
                notes.append(f"{label_a}=vol_default")
            if b == 0x64:
                notes.append(f"{label_b}=vol_default")
            if a == 0x28:
                notes.append(f"{label_a}=rev_default")
            if b == 0x28:
                notes.append(f"{label_b}=rev_default")
            if a == 0x40:
                notes.append(f"{label_a}=pan_center")
            if b == 0x40:
                notes.append(f"{label_b}=pan_center")
            if a == 0x00:
                notes.append(f"{label_a}=zero")
            if b == 0x00:
                notes.append(f"{label_b}=zero")
            note_str = ", ".join(notes) if notes else ""
            print(f"  0x{off:03X}   0x{a:02X}   0x{b:02X}   {delta:+4d}    {note_str}")


def structural_analysis(header: bytes, label: str) -> None:
    """Find repeating patterns in the header."""
    print(f"\n{'=' * 100}")
    print(f"STRUCTURAL ANALYSIS: {label}")
    print(f"{'=' * 100}")

    # 1. Find repeating 8-byte groups (one value per track)
    print(f"\n  --- Repeating 8-byte groups ---")
    for stride in [8]:
        print(f"  Stride = {stride}:")
        for start in range(0, min(len(header) - stride * 2, 400), 1):
            group1 = header[start : start + stride]
            group2 = header[start + stride : start + stride * 2]
            if group1 == group2 and len(set(group1)) > 1:  # Not all same byte
                # Check how many consecutive repeats
                repeats = 1
                pos = start + stride
                while pos + stride <= len(header):
                    if header[pos : pos + stride] == group1:
                        repeats += 1
                        pos += stride
                    else:
                        break
                if repeats >= 3:
                    print(
                        f"    0x{start:03X}: pattern [{hex_row(group1)}] repeats {repeats}x "
                        f"(spans 0x{start:03X}-0x{start + repeats * stride - 1:03X})"
                    )

    # 2. Find repeating 7-byte groups
    print(f"\n  --- Repeating 7-byte groups ---")
    for stride in [7]:
        found = set()
        for start in range(0, min(len(header) - stride * 2, 400), 1):
            group1 = header[start : start + stride]
            if start in found:
                continue
            repeats = 1
            pos = start + stride
            while pos + stride <= len(header):
                if header[pos : pos + stride] == group1:
                    repeats += 1
                    pos += stride
                else:
                    break
            if repeats >= 3 and len(set(group1)) > 1:
                found.update(range(start, start + repeats * stride))
                print(
                    f"    0x{start:03X}: pattern [{hex_row(group1, 7)}] repeats {repeats}x "
                    f"(spans 0x{start:03X}-0x{start + repeats * stride - 1:03X})"
                )

    # 3. Find 48-byte groups (8 tracks × 6 sections)
    print(f"\n  --- 48-byte blocks (8 tracks × 6 sections) ---")
    for start in range(0, len(header) - 48, 1):
        block = header[start : start + 48]
        # Check if it looks like 6 groups of 8 identical-structure bytes
        groups = [block[i * 8 : (i + 1) * 8] for i in range(6)]
        # Check if all groups are identical (all sections same = default values)
        if all(g == groups[0] for g in groups) and len(set(groups[0])) > 1:
            print(
                f"    0x{start:03X}: 48 bytes = 6 identical 8-byte groups: [{hex_row(groups[0])}]"
            )

    # 4. Identify the 130-byte "structural template" (0x137-0x1B8)
    print(f"\n  --- Known structural template region (0x137-0x1B8, 130 bytes) ---")
    if len(header) >= 0x1B8:
        template = header[0x137:0x1B8]
        non_zero = sum(1 for b in template if b != 0)
        unique = len(set(template))
        print(f"    Size: {len(template)} bytes")
        print(f"    Non-zero bytes: {non_zero}/{len(template)}")
        print(f"    Unique values: {unique}")
        print(f"    First 32: {hex_row(template[:32], 32)}")
        print(f"    Last 32:  {hex_row(template[-32:], 32)}")

    # 5. Zero regions
    print(f"\n  --- Zero regions (4+ consecutive 0x00 bytes) ---")
    zero_start = None
    for i in range(len(header)):
        if header[i] == 0x00:
            if zero_start is None:
                zero_start = i
        else:
            if zero_start is not None:
                length = i - zero_start
                if length >= 4:
                    print(f"    0x{zero_start:03X}-0x{i - 1:03X} ({length:3d} bytes of 0x00)")
                zero_start = None
    if zero_start is not None:
        length = len(header) - zero_start
        if length >= 4:
            print(f"    0x{zero_start:03X}-0x{len(header) - 1:03X} ({length:3d} bytes of 0x00)")

    # 6. Byte value frequency
    print(f"\n  --- Byte value frequency (top 20) ---")
    freq = Counter(header)
    for val, count in freq.most_common(20):
        pct = count / len(header) * 100
        bar = "█" * int(pct / 2)
        notes = []
        if val == 0x64:
            notes.append("XG_VOL_DEFAULT")
        if val == 0x28:
            notes.append("XG_REV_DEFAULT")
        if val == 0x40:
            notes.append("XG_PAN_CENTER")
        if val == 0x00:
            notes.append("ZERO/XG_CHORUS_DEFAULT")
        note_str = f"  ({', '.join(notes)})" if notes else ""
        print(f"    0x{val:02X} ({val:3d}): {count:4d} occurrences ({pct:5.1f}%) {bar}{note_str}")


def search_voice_patterns(header: bytes, label: str) -> None:
    """Search for known voice/program byte patterns in the header."""
    print(f"\n{'=' * 100}")
    print(f"VOICE/PROGRAM PATTERN SEARCH: {label}")
    print(f"{'=' * 100}")

    # Known QY70 voice patterns from SGT style track headers:
    # D1/D2: 0x40 0x80 (drum default)
    # BA:    0x00 0x04 (bass marker)
    # PC:    0x04 0x0B (vibraphone var)
    voice_patterns = [
        (b"\x40\x80", "Drum default (0x40 0x80)"),
        (b"\x00\x04", "Bass marker (0x00 0x04)"),
        (b"\x04\x0b", "Vibraphone var (0x04 0x0B)"),
        (b"\x00\x00", "Zero pair (0x00 0x00)"),
        (b"\x7f\x00", "Drum bank MSB 127 (0x7F 0x00)"),
    ]

    for pattern, desc in voice_patterns:
        matches = []
        for i in range(len(header) - len(pattern) + 1):
            if header[i : i + len(pattern)] == pattern:
                matches.append(i)
        if matches:
            print(f"\n  {desc}: found at offsets {[f'0x{m:03X}' for m in matches]}")
            for off in matches[:5]:
                ctx_start = max(0, off - 4)
                ctx_end = min(len(header), off + len(pattern) + 4)
                ctx = header[ctx_start:ctx_end]
                print(f"    context at 0x{off:03X}: {hex_row(ctx, 16)}")


def analyze_per_track_regions(header: bytes, label: str) -> None:
    """
    Identify regions where 8 consecutive bytes could represent per-track values.
    Score each 8-byte window by how plausible it is as mixer data.
    """
    print(f"\n{'=' * 100}")
    print(f"PER-TRACK MIXER PARAMETER CANDIDATES: {label}")
    print(f"{'=' * 100}")

    print(f"\n  Scoring each 8-byte window as potential per-track mixer data...")
    print(f"  Score criteria: all values in MIDI range (0-127), not all identical,")
    print(f"  not all zero, contains plausible mixer values.")

    candidates = []
    for i in range(len(header) - 7):
        window = header[i : i + 8]

        # Skip if all zero or all same
        if len(set(window)) <= 1:
            continue

        # All must be valid MIDI (0-127)
        if any(b > 127 for b in window):
            continue

        score = 0
        notes = []

        # Check if values look like volumes (typical: 50-127)
        vol_count = sum(1 for b in window if 50 <= b <= 127)
        if vol_count >= 6:
            score += vol_count
            notes.append(f"vol_range={vol_count}/8")

        # Check if values cluster around XG defaults
        at_vol_default = sum(1 for b in window if b == 0x64)
        at_rev_default = sum(1 for b in window if b == 0x28)
        at_pan_center = sum(1 for b in window if b == 0x40)

        if at_vol_default >= 3:
            score += at_vol_default * 2
            notes.append(f"vol_default={at_vol_default}/8")
        if at_rev_default >= 3:
            score += at_rev_default * 2
            notes.append(f"rev_default={at_rev_default}/8")
        if at_pan_center >= 3:
            score += at_pan_center * 2
            notes.append(f"pan_center={at_pan_center}/8")

        # Variety score: mixer values should have some variety
        unique = len(set(window))
        if 2 <= unique <= 8:
            score += unique

        if score >= 5:
            candidates.append((i, score, list(window), notes))

    # Sort by score descending
    candidates.sort(key=lambda x: -x[1])

    print(f"\n  Top 30 candidates (sorted by score):")
    print(f"  {'Offset':<8} {'Score':<6} {'Values':<35} {'Notes'}")
    print(f"  {'─' * 8} {'─' * 6} {'─' * 35} {'─' * 40}")
    for off, score, vals, notes in candidates[:30]:
        val_str = " ".join(f"{v:3d}" for v in vals)
        note_str = ", ".join(notes)
        print(f"  0x{off:03X}   {score:<6d} [{val_str}]  {note_str}")


def analyze_header_message_structure(messages: List[SysExMessage], label: str) -> None:
    """Analyze how the header is split across SysEx messages."""
    print(f"\n{'=' * 100}")
    print(f"HEADER MESSAGE STRUCTURE: {label}")
    print(f"{'=' * 100}")

    print(f"\n  Total header messages (AL=0x7F): {len(messages)}")
    total_encoded = 0
    total_decoded = 0

    for i, msg in enumerate(messages):
        enc_len = len(msg.data)
        dec_len = len(msg.decoded_data) if msg.decoded_data else 0
        total_encoded += enc_len
        total_decoded += dec_len
        print(
            f"  Msg {i}: encoded={enc_len:4d} bytes, decoded={dec_len:4d} bytes, "
            f"address=(0x{msg.address_high:02X}, 0x{msg.address_mid:02X}, 0x{msg.address_low:02X}), "
            f"checksum_valid={msg.checksum_valid}"
        )

    print(f"\n  Total encoded: {total_encoded} bytes")
    print(f"  Total decoded: {total_decoded} bytes")
    print(f"  Expected decoded: 640 bytes (5 × 128)")
    print(f"  Ratio: {total_encoded / total_decoded:.4f} (expected ~1.143 = 8/7)")


def cross_reference_with_track_data(
    header: bytes,
    section_data: Dict[int, bytes],
    label: str,
) -> None:
    """
    Cross-reference header bytes with track data to find correlations.
    Extract known values from track headers and search for them in the global header.
    """
    print(f"\n{'=' * 100}")
    print(f"CROSS-REFERENCE: TRACK DATA vs HEADER: {label}")
    print(f"{'=' * 100}")

    # Extract voice info from all section 0 tracks (AL=0x00 to 0x07)
    print(f"\n  --- Track header info (section 0, AL=0x00-0x07) ---")
    for track_idx in range(8):
        al = track_idx
        track_data = section_data.get(al, b"")
        if len(track_data) >= 24:
            hdr = track_data[:24]
            print(
                f"    Track {track_idx} ({QY70_TRACKS[track_idx]}): "
                f"first 24 bytes = {hex_row(hdr, 24)}"
            )
            if len(track_data) >= 26:
                print(f"      bytes 24-25 = {hex_row(track_data[24:26])}")
            # Voice at 14-15
            b14, b15 = hdr[14], hdr[15]
            print(f"      Voice: byte14=0x{b14:02X}, byte15=0x{b15:02X}")
            # Pan at 21-22
            pan_flag, pan_val = hdr[21], hdr[22]
            print(
                f"      Pan: flag=0x{pan_flag:02X}, val={pan_val} "
                f"({'C' if pan_val == 64 else f'L{64 - pan_val}' if pan_val < 64 else f'R{pan_val - 64}'})"
            )
        else:
            print(
                f"    Track {track_idx} ({QY70_TRACKS[track_idx]}): "
                f"data size = {len(track_data)} (insufficient)"
            )

    # Now look at track header byte 23 (the byte right before sequence data)
    print(f"\n  --- Track header byte 23 (potential volume/mixer byte?) ---")
    for track_idx in range(8):
        al = track_idx
        track_data = section_data.get(al, b"")
        if len(track_data) >= 24:
            b23 = track_data[23]
            print(f"    Track {track_idx} ({QY70_TRACKS[track_idx]}): byte23=0x{b23:02X} ({b23})")

    # Check if header contains track data patterns
    print(f"\n  --- Searching header for track byte values ---")
    # Look at first 8 bytes of all track blocks (bytes 0-7 of track header)
    for section_idx in range(6):
        section_tracks_byte0 = []
        for track_idx in range(8):
            al = section_idx * 8 + track_idx
            track_data = section_data.get(al, b"")
            if len(track_data) >= 1:
                section_tracks_byte0.append(track_data[0])
            else:
                section_tracks_byte0.append(None)
        if any(b is not None for b in section_tracks_byte0):
            vals = [f"0x{b:02X}" if b is not None else "---" for b in section_tracks_byte0]
            print(
                f"    Section {section_idx} ({SECTION_NAMES[section_idx]}): "
                f"track byte[0] = [{', '.join(vals)}]"
            )


def region_deep_dive(header: bytes, label: str) -> None:
    """
    Deep dive into specific header regions with per-section analysis.
    Divide the 640 bytes into logical regions and analyze each.
    """
    print(f"\n{'=' * 100}")
    print(f"REGION DEEP DIVE: {label}")
    print(f"{'=' * 100}")

    # Divide into 5 blocks of 128 bytes (matching the 5 SysEx messages)
    print(f"\n  --- Per-message block analysis (5 × 128 = 640 bytes) ---")
    for block in range(5):
        start = block * 128
        end = min(start + 128, len(header))
        chunk = header[start:end]

        non_zero = sum(1 for b in chunk if b != 0)
        unique = len(set(chunk))
        freq = Counter(chunk).most_common(3)

        print(f"\n  Block {block} (0x{start:03X}-0x{end - 1:03X}, {end - start} bytes):")
        print(f"    Non-zero: {non_zero}/{end - start}, Unique values: {unique}")
        print(f"    Top 3 values: {[(f'0x{v:02X}', c) for v, c in freq]}")

        # Show in 16-byte rows
        for row_off in range(0, end - start, 16):
            row = chunk[row_off : row_off + 16]
            abs_off = start + row_off
            hex_str = " ".join(f"{b:02X}" for b in row)
            asc = ascii_col(row)
            print(f"    0x{abs_off:03X}: {hex_str:<48} {asc}")

    # Special focus: look for 8-byte or 48-byte groupings in each block
    print(f"\n  --- Testing 8-byte groupings (per-track data) ---")
    for start_off in range(0, len(header) - 7, 8):
        group = header[start_off : start_off + 8]
        # Check if this is interesting (not all zero, not all same)
        if len(set(group)) > 1 and any(b != 0 for b in group):
            # Check if values look like mixer parameters
            all_midi = all(0 <= b <= 127 for b in group)
            if all_midi:
                avg = sum(group) / 8
                # Flag if average is near XG defaults
                flags = []
                if abs(avg - 100) < 20:
                    flags.append("~VOLUME")
                if abs(avg - 40) < 15:
                    flags.append("~REVERB")
                if abs(avg - 64) < 15:
                    flags.append("~PAN")
                if avg < 10:
                    flags.append("~CHORUS")
                if flags:
                    flag_str = " ".join(flags)
                    vals = " ".join(f"{b:3d}" for b in group)
                    print(f"    0x{start_off:03X}: [{vals}]  avg={avg:.1f}  {flag_str}")


def per_section_per_track_matrix(header: bytes, label: str) -> None:
    """
    Try to interpret regions as 6-section × 8-track matrices.
    Look for 48-byte blocks that could represent one parameter across all sections and tracks.
    """
    print(f"\n{'=' * 100}")
    print(f"SECTION×TRACK MATRIX SEARCH: {label}")
    print(f"{'=' * 100}")

    print(f"\n  Looking for 48-byte blocks (6 sections × 8 tracks) that could be mixer tables...")
    print(f"  Also checking 8-byte blocks repeated 6 times (same value per section).")
    print()

    for start in range(0, len(header) - 47, 1):
        block = header[start : start + 48]

        # Skip if all zero
        if all(b == 0 for b in block):
            continue

        # All values must be MIDI range
        if any(b > 127 for b in block):
            continue

        # Split into 6 groups of 8
        groups = [block[i * 8 : (i + 1) * 8] for i in range(6)]

        # Check: are most groups identical? (same defaults per section = likely mixer table)
        identical_pairs = sum(1 for i in range(5) if groups[i] == groups[i + 1])

        if identical_pairs >= 4:
            vals_str = " ".join(f"{b:3d}" for b in groups[0])
            avg = sum(groups[0]) / 8
            flags = []
            if abs(avg - 100) < 20:
                flags.append("VOLUME?")
            if abs(avg - 40) < 15:
                flags.append("REVERB?")
            if abs(avg - 64) < 15:
                flags.append("PAN?")
            if avg < 5:
                flags.append("CHORUS?")
            flag_str = " ".join(flags) if flags else ""
            print(f"  0x{start:03X}: 48 bytes, {identical_pairs}/5 adjacent pairs identical")
            print(f"    Group[0] = [{vals_str}]  avg={avg:.1f}  {flag_str}")
            # Show which groups differ
            for gi in range(6):
                marker = " *DIFF*" if gi > 0 and groups[gi] != groups[0] else ""
                g_str = " ".join(f"{b:3d}" for b in groups[gi])
                print(
                    f"    Sect {gi} ({SECTION_NAMES[gi] if gi < 6 else '?':>7}): [{g_str}]{marker}"
                )
            print()


# ─── Main ────────────────────────────────────────────────────────────────────


def main():
    print("=" * 100)
    print("QY70 HEADER (AL=0x7F) DEEP ANALYSIS")
    print("=" * 100)

    # ── Load files ───────────────────────────────────────────────────────
    files = {}
    for name, path in [("SGT", SGT_FILE), ("CAPTURED", CAPTURED_FILE)]:
        if path.exists():
            header, section_data, header_msgs = extract_header_blocks(path)
            files[name] = {
                "header": header,
                "section_data": section_data,
                "header_msgs": header_msgs,
                "path": path,
            }
            print(f"\n  Loaded {name}: {path.name}")
            print(f"    File size: {path.stat().st_size} bytes")
            print(f"    Header size: {len(header)} decoded bytes")
            print(f"    AL addresses: {sorted(f'0x{k:02X}' for k in section_data.keys())}")
        else:
            print(f"\n  WARNING: {name} file not found: {path}")

    if not files:
        print("\nERROR: No files loaded!")
        return

    # ── 1. Message structure ─────────────────────────────────────────────
    for name, info in files.items():
        analyze_header_message_structure(info["header_msgs"], name)

    # ── 2. Full hexdump ──────────────────────────────────────────────────
    for name, info in files.items():
        annotated_hexdump(info["header"], name)

    # ── 3. XG default cluster search ─────────────────────────────────────
    for name, info in files.items():
        search_xg_default_clusters(info["header"], name)

    # ── 4. Compare SGT vs CAPTURED ───────────────────────────────────────
    if "SGT" in files and "CAPTURED" in files:
        compare_headers(
            files["SGT"]["header"],
            files["CAPTURED"]["header"],
            "SGT",
            "CAPTURED",
        )

    # ── 5. Structural analysis ───────────────────────────────────────────
    for name, info in files.items():
        structural_analysis(info["header"], name)

    # ── 6. Voice pattern search ──────────────────────────────────────────
    for name, info in files.items():
        search_voice_patterns(info["header"], name)

    # ── 7. Per-track mixer candidate scoring ─────────────────────────────
    for name, info in files.items():
        analyze_per_track_regions(info["header"], name)

    # ── 8. Cross-reference with track data ───────────────────────────────
    for name, info in files.items():
        cross_reference_with_track_data(info["header"], info["section_data"], name)

    # ── 9. Region deep dive ──────────────────────────────────────────────
    for name, info in files.items():
        region_deep_dive(info["header"], name)

    # ── 10. Section×Track matrix search ──────────────────────────────────
    for name, info in files.items():
        per_section_per_track_matrix(info["header"], name)

    # ── SUMMARY ──────────────────────────────────────────────────────────
    print(f"\n{'=' * 100}")
    print(f"ANALYSIS SUMMARY")
    print(f"{'=' * 100}")

    if "SGT" in files:
        h = files["SGT"]["header"]
        print(f"\n  SGT header: {len(h)} bytes")
        print(f"  Non-zero bytes: {sum(1 for b in h if b != 0)}/{len(h)}")

        # Quick scan for most interesting findings
        print(f"\n  --- Key findings ---")

        # Count XG default values
        vol_count = sum(1 for b in h if b == 0x64)
        rev_count = sum(1 for b in h if b == 0x28)
        pan_count = sum(1 for b in h if b == 0x40)
        zero_count = sum(1 for b in h if b == 0x00)
        print(f"    0x64 (vol=100) occurrences: {vol_count}")
        print(f"    0x28 (rev=40) occurrences:  {rev_count}")
        print(f"    0x40 (pan=64) occurrences:  {pan_count}")
        print(f"    0x00 (zero) occurrences:     {zero_count}")

    print(f"\n{'=' * 100}")
    print(f"END OF ANALYSIS")
    print(f"{'=' * 100}")


if __name__ == "__main__":
    main()
