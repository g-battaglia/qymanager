#!/usr/bin/env python3
"""
Bit-level analysis of QY70 SysEx track event data.

Previous byte-level analysis confirmed the event data is a packed bitstream,
not byte-oriented MIDI commands. This script attacks the problem at the bit level.

Analyses performed:
  1. Load SGT.syx, decode Section 0 tracks, extract event data (bytes 24+)
  2. Bit-level frequency per position within candidate event sizes
  3. Autocorrelation analysis on the bitstream
  4. Sliding window repeated bit-pattern search (CHD2)
  5. Cross-bar bit alignment analysis
  6. Known value correlation (drum notes, MIDI values)
  7. Differential analysis between sections
  8. Summary of best candidate event sizes
"""

import sys
import math
from pathlib import Path
from collections import Counter, defaultdict
from typing import Dict, List, Tuple, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))
from qymanager.utils.yamaha_7bit import decode_7bit


# ── Constants ────────────────────────────────────────────────────────────────

SYX_FILE = Path(__file__).parent.parent / "tests" / "fixtures" / "QY70_SGT.syx"

SYSEX_START = 0xF0
SYSEX_END = 0xF7
YAMAHA_ID = 0x43
QY70_MODEL = 0x5F

TRACK_NAMES = ["RHY1", "RHY2", "BASS", "CHD1", "CHD2", "PAD ", "PHR1", "PHR2"]
TRACK_TYPES = ["drum", "drum", "bass", "chord", "chord", "chord", "chord", "chord"]
SECTION_NAMES = ["Intro", "MainA", "MainB", "FillAB", "FillBA", "Ending"]

GM_DRUM_MAP = {
    35: "Kick2",
    36: "Kick1",
    37: "SStick",
    38: "Snare1",
    39: "Clap",
    40: "Snare2",
    41: "FlTom2",
    42: "HH-Cl",
    43: "FlTom1",
    44: "HH-Pd",
    45: "LoTom",
    46: "HH-Op",
    47: "MdTom2",
    48: "MdTom1",
    49: "Crash1",
    50: "HiTom",
    51: "Ride1",
}


# ── SysEx Parsing (reused from analyze_events.py) ───────────────────────────


def split_sysex(data: bytes) -> List[bytes]:
    """Split raw .syx file into individual F0..F7 messages."""
    msgs = []
    start = None
    for i, b in enumerate(data):
        if b == SYSEX_START:
            start = i
        elif b == SYSEX_END and start is not None:
            msgs.append(data[start : i + 1])
            start = None
    return msgs


def parse_bulk_dumps(raw: bytes) -> Dict[int, bytearray]:
    """Parse all bulk dump messages, accumulate decoded data by AL address."""
    msgs = split_sysex(raw)
    by_al: Dict[int, bytearray] = {}
    for msg in msgs:
        if len(msg) < 11:
            continue
        if msg[1] != YAMAHA_ID or msg[3] != QY70_MODEL:
            continue
        if (msg[2] & 0xF0) != 0x00:
            continue
        ah, am, al = msg[6], msg[7], msg[8]
        if ah != 0x02 or am != 0x7E:
            continue
        payload = msg[9:-2]
        decoded = decode_7bit(payload)
        if al not in by_al:
            by_al[al] = bytearray()
        by_al[al].extend(decoded)
    return by_al


# ── Bitstream Utilities ─────────────────────────────────────────────────────


def bytes_to_bits(data: bytes) -> List[int]:
    """Convert bytes to list of bits (MSB first per byte)."""
    bits = []
    for byte in data:
        for i in range(7, -1, -1):
            bits.append((byte >> i) & 1)
    return bits


def bits_to_str(bits: List[int]) -> str:
    """Convert bit list to string of 0s and 1s."""
    return "".join(str(b) for b in bits)


def bits_to_int(bits: List[int]) -> int:
    """Convert bit list to integer (MSB first)."""
    val = 0
    for b in bits:
        val = (val << 1) | b
    return val


def split_by_delimiter(data: bytes, delim: int = 0xDC) -> List[bytes]:
    """Split data by delimiter byte. Strips trailing 0x00 terminator first."""
    work = data.rstrip(b"\x00")
    if not work:
        return []
    parts = []
    current = bytearray()
    for b in work:
        if b == delim:
            parts.append(bytes(current))
            current = bytearray()
        else:
            current.append(b)
    if current:
        parts.append(bytes(current))
    return parts


# ── Analysis 1: Load and Extract ────────────────────────────────────────────


def load_section0_tracks(syx_path: Path) -> Dict[int, bytes]:
    """Load SGT.syx, return dict of track_idx -> full decoded data for Section 0."""
    raw = syx_path.read_bytes()
    by_al = parse_bulk_dumps(raw)
    tracks = {}
    for track_idx in range(8):
        al = track_idx  # Section 0
        if al in by_al:
            tracks[track_idx] = bytes(by_al[al])
    return tracks


def load_all_sections(syx_path: Path) -> Dict[int, bytes]:
    """Load all AL addresses from the SysEx file."""
    raw = syx_path.read_bytes()
    return {al: bytes(data) for al, data in parse_bulk_dumps(raw).items()}


# ── Analysis 2: Bit-Level Frequency Per Position ────────────────────────────


def bit_frequency_analysis(data: bytes, event_sizes: List[int], label: str = ""):
    """For each candidate event size, show bit frequency per position."""
    bits = bytes_to_bits(data)
    total_bits = len(bits)

    print(f"\n  {'─' * 80}")
    print(f"  BIT FREQUENCY PER POSITION — {label} ({len(data)} bytes = {total_bits} bits)")
    print(f"  {'─' * 80}")

    results = {}

    for esize in event_sizes:
        num_events = total_bits // esize
        if num_events < 2:
            continue

        # Count 1s at each bit position within the event
        ones_count = [0] * esize
        for ev_idx in range(num_events):
            for bit_pos in range(esize):
                idx = ev_idx * esize + bit_pos
                if idx < total_bits:
                    ones_count[bit_pos] += bits[idx]

        # Calculate frequencies and bias
        biases = []
        for pos in range(esize):
            freq_1 = ones_count[pos] / num_events
            bias = abs(freq_1 - 0.5)
            biases.append((pos, freq_1, bias))

        avg_bias = sum(b[2] for b in biases) / len(biases) if biases else 0
        max_bias = max(b[2] for b in biases) if biases else 0
        # Positions with very high bias (>0.35) suggest structural significance
        high_bias_positions = [b for b in biases if b[2] > 0.35]

        results[esize] = {
            "avg_bias": avg_bias,
            "max_bias": max_bias,
            "high_bias_count": len(high_bias_positions),
            "biases": biases,
            "num_events": num_events,
        }

        print(
            f"\n    Event size: {esize} bits ({num_events} events, remainder {total_bits % esize})"
        )

        # Visual: show frequency bar for each bit position
        for pos, freq_1, bias in biases:
            bar_len = 40
            filled = int(freq_1 * bar_len)
            bar = "█" * filled + "░" * (bar_len - filled)
            marker = (
                " ***" if bias > 0.35 else " **" if bias > 0.25 else " *" if bias > 0.15 else ""
            )
            print(f"      bit[{pos:2d}]: {freq_1:.3f} [{bar}] bias={bias:.3f}{marker}")

        if high_bias_positions:
            hbp = [f"bit[{p[0]}]={p[1]:.2f}" for p in high_bias_positions]
            print(f"      HIGH BIAS positions: {', '.join(hbp)}")

    # Rank event sizes by average bias (higher = more structured)
    print(f"\n    EVENT SIZE RANKING by average bias (higher = more structured):")
    ranked = sorted(results.items(), key=lambda x: x[1]["avg_bias"], reverse=True)
    for esize, info in ranked[:10]:
        print(
            f"      {esize:3d} bits: avg_bias={info['avg_bias']:.4f}, "
            f"max_bias={info['max_bias']:.4f}, "
            f"high_bias_positions={info['high_bias_count']}/{esize}, "
            f"events={info['num_events']}"
        )

    return results


# ── Analysis 3: Autocorrelation ─────────────────────────────────────────────


def autocorrelation_analysis(data: bytes, max_lag: int = 256, label: str = ""):
    """Calculate bit-level autocorrelation for lags 1 to max_lag."""
    bits = bytes_to_bits(data)
    n = len(bits)

    print(f"\n  {'─' * 80}")
    print(f"  AUTOCORRELATION ANALYSIS — {label} ({n} bits)")
    print(f"  {'─' * 80}")

    # Convert to +1/-1 for correlation
    signal = [2 * b - 1 for b in bits]

    # Calculate mean
    mean = sum(signal) / n

    # Variance
    variance = sum((s - mean) ** 2 for s in signal) / n
    if variance < 1e-10:
        print("    Signal has zero variance — cannot compute autocorrelation")
        return []

    # Autocorrelation for each lag
    correlations = []
    for lag in range(1, min(max_lag + 1, n)):
        cov = sum((signal[i] - mean) * (signal[i + lag] - mean) for i in range(n - lag))
        cov /= n - lag
        r = cov / variance
        correlations.append((lag, r))

    # Sort by absolute correlation strength
    ranked = sorted(correlations, key=lambda x: abs(x[1]), reverse=True)

    print(f"\n    Top 20 autocorrelation lags:")
    print(f"    {'Lag':>6s}  {'R':>8s}  {'|R|':>6s}  {'Interpretation':30s}  Visual")
    print(f"    {'─' * 6}  {'─' * 8}  {'─' * 6}  {'─' * 30}  {'─' * 30}")

    for lag, r in ranked[:20]:
        abs_r = abs(r)
        bar_len = int(abs_r * 30)
        bar = ("+" if r > 0 else "-") * bar_len
        interp = ""
        if lag % 8 == 0:
            interp = f"= {lag // 8} bytes"
        elif lag % 7 == 0:
            interp = f"= {lag // 7} × 7 bits"
        elif lag % 4 == 0:
            interp = f"= {lag // 4} nibbles"
        if lag in [3, 5, 6, 7, 10, 12, 14, 21, 24, 28]:
            interp += f" (candidate event size)"
        print(f"    {lag:6d}  {r:+8.4f}  {abs_r:6.4f}  {interp:30s}  [{bar}]")

    # Also show all lags with |R| > 0.1 in lag order
    significant = [(lag, r) for lag, r in correlations if abs(r) > 0.08]
    if significant:
        print(f"\n    All lags with |R| > 0.08 (in order):")
        for lag, r in significant:
            marker = " <<<" if abs(r) > 0.15 else ""
            print(f"      lag={lag:4d}: R={r:+.4f}{marker}")

    return correlations


# ── Analysis 4: Sliding Window Bit Pattern Search ───────────────────────────


def sliding_window_patterns(
    data: bytes, min_pat: int = 8, max_pat: int = 32, label: str = "", top_n: int = 30
):
    """Find repeated bit patterns of length min_pat to max_pat."""
    bits = bytes_to_bits(data)
    n = len(bits)

    print(f"\n  {'─' * 80}")
    print(f"  SLIDING WINDOW BIT PATTERNS — {label} ({n} bits)")
    print(f"  {'─' * 80}")

    for pat_len in [8, 10, 12, 14, 16, 20, 21, 24, 28, 32]:
        if pat_len < min_pat or pat_len > max_pat or pat_len >= n:
            continue

        patterns: Dict[str, List[int]] = defaultdict(list)
        for i in range(n - pat_len + 1):
            pat = bits_to_str(bits[i : i + pat_len])
            patterns[pat].append(i)

        # Filter to patterns appearing 3+ times
        repeated = {p: pos for p, pos in patterns.items() if len(pos) >= 3}
        if not repeated:
            print(f"\n    {pat_len}-bit patterns: no patterns repeat 3+ times")
            continue

        # Sort by frequency
        sorted_pats = sorted(repeated.items(), key=lambda x: len(x[1]), reverse=True)

        print(
            f"\n    {pat_len}-bit patterns (top {min(top_n, len(sorted_pats))}, "
            f"{len(repeated)} unique repeating):"
        )

        for pat_str, positions in sorted_pats[:top_n]:
            val = int(pat_str, 2)
            hex_approx = f"0x{val:0{(pat_len + 3) // 4}X}"
            # Show positions modulo various candidate event sizes
            mod_info = ""
            for mod in [7, 8, 10, 12, 14, 16, 21]:
                mods = [p % mod for p in positions]
                if len(set(mods)) == 1:
                    mod_info += f" aligned@{mod}(pos%{mod}={mods[0]})"
            print(
                f"      {pat_str} ({hex_approx}): {len(positions)}x "
                f"at bits {positions[:8]}{'...' if len(positions) > 8 else ''}"
                f"{mod_info}"
            )


# ── Analysis 5: Cross-Bar Bit Alignment ─────────────────────────────────────


def cross_bar_alignment(tracks: Dict[int, bytes]):
    """Analyze CHD2 (identical bars) and CHD1 for beat-level structure."""
    print(f"\n{'=' * 90}")
    print("ANALYSIS 5: CROSS-BAR BIT ALIGNMENT")
    print(f"{'=' * 90}")

    for track_idx, tname in [(4, "CHD2"), (3, "CHD1")]:
        if track_idx not in tracks:
            continue

        data = tracks[track_idx]
        events = data[24:]
        bars = split_by_delimiter(events, 0xDC)

        print(f"\n  {'─' * 80}")
        print(f"  {tname} — {len(bars)} bars, sizes: {[len(b) for b in bars]}")
        print(f"  {'─' * 80}")

        if not bars:
            continue

        bar0 = bars[0]
        bar0_bits = bytes_to_bits(bar0)
        nbits = len(bar0_bits)

        print(f"\n    Bar 0: {len(bar0)} bytes = {nbits} bits")
        print(f"    Binary: {bits_to_str(bar0_bits[:80])}...")

        # a) Try beat divisions
        print(f"\n    Beat division analysis ({nbits} bits per bar):")
        for label, divisor in [
            ("4 beats (quarter notes)", 4),
            ("8 divisions (eighth notes)", 8),
            ("12 divisions (triplet eighths)", 12),
            ("16 divisions (sixteenth notes)", 16),
            ("24 divisions (MIDI clock)", 24),
            ("32 divisions (32nd notes)", 32),
        ]:
            if nbits % divisor == 0:
                bits_per_div = nbits // divisor
                print(f"      {label}: {bits_per_div} bits/division — DIVIDES EVENLY")

                # Show each division
                for d in range(min(divisor, 8)):
                    chunk = bar0_bits[d * bits_per_div : (d + 1) * bits_per_div]
                    chunk_str = bits_to_str(chunk)
                    chunk_val = bits_to_int(chunk)
                    print(
                        f"        div[{d:2d}]: {chunk_str} (0x{chunk_val:0{(bits_per_div + 3) // 4}X} = {chunk_val})"
                    )

                # Check if divisions repeat
                divisions = []
                for d in range(divisor):
                    chunk = bar0_bits[d * bits_per_div : (d + 1) * bits_per_div]
                    divisions.append(bits_to_str(chunk))

                unique_divs = len(set(divisions))
                print(f"        Unique divisions: {unique_divs}/{divisor}")
                if unique_divs < divisor:
                    div_counts = Counter(divisions)
                    for pat, cnt in div_counts.most_common(5):
                        val = int(pat, 2)
                        print(f"          pattern {pat} (0x{val:X}): {cnt}x")

            else:
                bits_per_div = nbits / divisor
                print(f"      {label}: {bits_per_div:.1f} bits/division — does NOT divide evenly")

        # b) Compare bars bit-by-bit
        if len(bars) >= 2:
            bar1 = bars[1]
            bar1_bits = bytes_to_bits(bar1)
            print(f"\n    Bar 0 vs Bar 1 bit comparison:")
            if len(bar0_bits) == len(bar1_bits):
                diff_positions = [i for i in range(len(bar0_bits)) if bar0_bits[i] != bar1_bits[i]]
                print(
                    f"      Same length ({len(bar0_bits)} bits), {len(diff_positions)} differing bits"
                )
                if diff_positions:
                    print(f"      Diff positions: {diff_positions[:50]}")
                    # Check if diffs are periodic
                    if len(diff_positions) >= 2:
                        diff_spacings = [
                            diff_positions[i + 1] - diff_positions[i]
                            for i in range(len(diff_positions) - 1)
                        ]
                        spacing_counts = Counter(diff_spacings)
                        print(f"      Diff spacing distribution: {spacing_counts.most_common(10)}")
                else:
                    print(f"      BARS ARE BIT-IDENTICAL")
            else:
                print(f"      Different lengths: {len(bar0_bits)} vs {len(bar1_bits)} bits")

        # c) Variable-length event hypothesis: look for bit-level delimiters
        print(f"\n    Searching for potential bit-level delimiters in Bar 0:")
        # Look for single-bit patterns that could mark event boundaries
        for marker_len in [1, 2, 3]:
            for marker_val in range(1 << marker_len):
                marker_bits = [(marker_val >> (marker_len - 1 - j)) & 1 for j in range(marker_len)]
                positions = []
                for i in range(nbits - marker_len + 1):
                    if bar0_bits[i : i + marker_len] == marker_bits:
                        positions.append(i)
                if 4 <= len(positions) <= 32:
                    spacings = [positions[j + 1] - positions[j] for j in range(len(positions) - 1)]
                    spacing_counts = Counter(spacings)
                    dominant = spacing_counts.most_common(1)[0] if spacing_counts else (0, 0)
                    if dominant[1] >= len(spacings) * 0.4:  # >40% same spacing
                        marker_str = bits_to_str(marker_bits)
                        print(
                            f"      marker '{marker_str}': {len(positions)} occurrences, "
                            f"dominant spacing={dominant[0]} ({dominant[1]}/{len(spacings)}), "
                            f"positions={positions[:20]}"
                        )


# ── Analysis 6: Known Value Correlation ─────────────────────────────────────


def known_value_correlation(tracks: Dict[int, bytes]):
    """Search for known MIDI note values at all bit offsets."""
    print(f"\n{'=' * 90}")
    print("ANALYSIS 6: KNOWN VALUE CORRELATION")
    print(f"{'=' * 90}")

    # Drum track analysis
    for track_idx in [0, 1]:
        tname = TRACK_NAMES[track_idx]
        if track_idx not in tracks:
            continue

        data = tracks[track_idx]
        events = data[24:]
        bits = bytes_to_bits(events)
        nbits = len(bits)

        print(f"\n  {'─' * 80}")
        print(f"  {tname} — Searching for drum note bit patterns ({nbits} bits)")
        print(f"  {'─' * 80}")

        # Search for kick (36), snare (38), hi-hat closed (42), hi-hat open (46)
        target_notes = {
            36: "Kick1",
            38: "Snare1",
            42: "HH-Cl",
            44: "HH-Pd",
            46: "HH-Op",
            51: "Ride1",
            49: "Crash1",
        }

        for note_width in [7, 8]:
            print(f"\n    Searching as {note_width}-bit values:")

            for note_val, note_name in target_notes.items():
                # Generate bit pattern for this note
                note_bits = [(note_val >> (note_width - 1 - j)) & 1 for j in range(note_width)]
                note_str = bits_to_str(note_bits)

                # Find all occurrences at every bit offset
                positions = []
                for i in range(nbits - note_width + 1):
                    if bits[i : i + note_width] == note_bits:
                        positions.append(i)

                if not positions:
                    continue

                # Analyze position modulo candidate event sizes
                mod_analysis = {}
                for mod in [7, 8, 10, 12, 14, 16, 20, 21, 24, 28]:
                    mod_positions = [p % mod for p in positions]
                    mod_counts = Counter(mod_positions)
                    most_common_mod = mod_counts.most_common(1)[0]
                    # Concentration: what fraction lands at the most common modular position
                    concentration = most_common_mod[1] / len(positions)
                    if concentration > 0.3:
                        mod_analysis[mod] = (most_common_mod[0], concentration, most_common_mod[1])

                print(
                    f"      note {note_val:3d} ({note_name:>7s}) = {note_str}: "
                    f"{len(positions)} hits"
                )
                if mod_analysis:
                    for mod, (pos, conc, cnt) in sorted(
                        mod_analysis.items(), key=lambda x: x[1][1], reverse=True
                    ):
                        if conc > 0.4:
                            print(
                                f"        mod {mod:2d}: position {pos:2d} has {cnt}/{len(positions)} "
                                f"= {conc:.0%} concentration <<<"
                            )
                        else:
                            print(
                                f"        mod {mod:2d}: position {pos:2d} has {cnt}/{len(positions)} "
                                f"= {conc:.0%} concentration"
                            )

    # Bass track — look for common bass notes
    if 2 in tracks:
        data = tracks[2]
        events = data[24:]
        bits = bytes_to_bits(events)
        nbits = len(bits)

        print(f"\n  {'─' * 80}")
        print(f"  BASS — Searching for bass note bit patterns ({nbits} bits)")
        print(f"  {'─' * 80}")

        # Common bass notes: C2=36, E2=40, G2=43, C3=48, etc.
        bass_notes = {
            36: "C2",
            38: "D2",
            40: "E2",
            41: "F2",
            43: "G2",
            45: "A2",
            47: "B2",
            48: "C3",
            50: "D3",
            52: "E3",
        }

        for note_width in [7, 8]:
            print(f"\n    Searching as {note_width}-bit values:")
            for note_val, note_name in bass_notes.items():
                note_bits = [(note_val >> (note_width - 1 - j)) & 1 for j in range(note_width)]
                positions = []
                for i in range(nbits - note_width + 1):
                    if bits[i : i + note_width] == note_bits:
                        positions.append(i)

                if not positions:
                    continue

                # Quick mod analysis
                best_mod = None
                best_conc = 0
                for mod in [7, 8, 10, 12, 14, 16, 21, 24, 28]:
                    mod_counts = Counter(p % mod for p in positions)
                    mc = mod_counts.most_common(1)[0]
                    conc = mc[1] / len(positions)
                    if conc > best_conc:
                        best_conc = conc
                        best_mod = (mod, mc[0], conc, mc[1])

                mod_str = ""
                if best_mod and best_mod[2] > 0.35:
                    mod_str = f" best_mod={best_mod[0]} pos={best_mod[1]} conc={best_mod[2]:.0%}"

                print(
                    f"      note {note_val:3d} ({note_name:>3s}) [{note_width}b]: "
                    f"{len(positions)} hits{mod_str}"
                )


# ── Analysis 7: Differential Analysis Between Sections ──────────────────────


def differential_analysis(all_data: Dict[int, bytes]):
    """Compare tracks across sections to find minimal differences."""
    print(f"\n{'=' * 90}")
    print("ANALYSIS 7: DIFFERENTIAL ANALYSIS BETWEEN SECTIONS")
    print(f"{'=' * 90}")

    # D2 track (RHY2 = track index 1) across sections
    # Previous analysis: Sections 1-5 identical, Section 0 differs at bytes 220-231
    print(f"\n  {'─' * 80}")
    print(f"  RHY2 (D2) — Section 0 vs others (12-byte difference region)")
    print(f"  {'─' * 80}")

    rhy2_sections = {}
    for sec_idx in range(6):
        al = sec_idx * 8 + 1  # Track 1 = RHY2
        if al in all_data:
            rhy2_sections[sec_idx] = all_data[al]

    if 0 in rhy2_sections and len(rhy2_sections) >= 2:
        sec0 = rhy2_sections[0]
        # Find a reference section
        ref_sec = None
        for s in range(1, 6):
            if s in rhy2_sections:
                ref_sec = s
                break

        if ref_sec is not None:
            sec_ref = rhy2_sections[ref_sec]
            events_0 = sec0[24:]
            events_ref = sec_ref[24:]

            min_len = min(len(events_0), len(events_ref))
            diff_bytes = []
            for i in range(min_len):
                if events_0[i] != events_ref[i]:
                    diff_bytes.append(i)

            print(f"    Section 0: {len(events_0)} event bytes")
            print(f"    Section {ref_sec}: {len(events_ref)} event bytes")
            print(f"    Differing byte offsets (in event data): {diff_bytes}")

            if diff_bytes:
                start = diff_bytes[0]
                end = diff_bytes[-1] + 1
                diff_region_len = end - start
                print(
                    f"    Diff region: bytes {start}-{end - 1} ({diff_region_len} bytes = {diff_region_len * 8} bits)"
                )

                print(f"\n    Section 0 diff region bytes:")
                region_0 = events_0[start:end]
                print(f"      HEX: {' '.join(f'{b:02X}' for b in region_0)}")
                bits_0 = bytes_to_bits(region_0)
                print(f"      BIN: {bits_to_str(bits_0)}")

                print(f"\n    Section {ref_sec} diff region bytes:")
                region_ref = events_ref[start:end]
                print(f"      HEX: {' '.join(f'{b:02X}' for b in region_ref)}")
                bits_ref = bytes_to_bits(region_ref)
                print(f"      BIN: {bits_to_str(bits_ref)}")

                # XOR to show which bits differ
                xor_bits = [a ^ b for a, b in zip(bits_0, bits_ref)]
                print(f"\n    XOR (differing bits = 1):")
                print(f"      BIN: {bits_to_str(xor_bits)}")
                print(f"      Differing bit count: {sum(xor_bits)} / {len(xor_bits)}")

                # Positions of differing bits
                diff_bit_positions = [i for i, x in enumerate(xor_bits) if x == 1]
                print(f"      Differing bit positions: {diff_bit_positions}")

                # Check if diffs are periodic
                if len(diff_bit_positions) >= 2:
                    spacings = [
                        diff_bit_positions[i + 1] - diff_bit_positions[i]
                        for i in range(len(diff_bit_positions) - 1)
                    ]
                    print(f"      Bit diff spacings: {spacings}")

                # Try interpreting region with different event sizes
                print(f"\n    Interpreting diff region with candidate event sizes:")
                for esize in [7, 8, 10, 12, 14, 16, 21, 24]:
                    n_events = len(bits_0) // esize
                    if n_events < 1:
                        continue
                    print(
                        f"\n      {esize}-bit events ({n_events} events, remainder {len(bits_0) % esize}):"
                    )
                    for ev_idx in range(n_events):
                        chunk_0 = bits_0[ev_idx * esize : (ev_idx + 1) * esize]
                        chunk_ref = bits_ref[ev_idx * esize : (ev_idx + 1) * esize]
                        val_0 = bits_to_int(chunk_0)
                        val_ref = bits_to_int(chunk_ref)
                        differs = "DIFFERS" if chunk_0 != chunk_ref else "same"
                        print(
                            f"        ev[{ev_idx}]: sec0={bits_to_str(chunk_0)} "
                            f"(0x{val_0:0{(esize + 3) // 4}X}={val_0:4d})  "
                            f"ref ={bits_to_str(chunk_ref)} "
                            f"(0x{val_ref:0{(esize + 3) // 4}X}={val_ref:4d})  {differs}"
                        )

    # BASS track comparison
    print(f"\n  {'─' * 80}")
    print(f"  BASS — Cross-section bit-level comparison")
    print(f"  {'─' * 80}")

    bass_sections = {}
    for sec_idx in range(6):
        al = sec_idx * 8 + 2  # Track 2 = BASS
        if al in all_data:
            bass_sections[sec_idx] = all_data[al]

    if len(bass_sections) >= 2:
        # Find pairs that differ
        sec_keys = sorted(bass_sections.keys())
        for i in range(len(sec_keys)):
            for j in range(i + 1, len(sec_keys)):
                si, sj = sec_keys[i], sec_keys[j]
                di = bass_sections[si][24:]  # event data only
                dj = bass_sections[sj][24:]

                if di == dj:
                    print(f"    Section {si} vs {sj}: IDENTICAL")
                    continue

                min_len = min(len(di), len(dj))
                byte_diffs = [(k, di[k], dj[k]) for k in range(min_len) if di[k] != dj[k]]

                if len(byte_diffs) > 30:
                    print(
                        f"    Section {si} vs {sj}: {len(byte_diffs)} byte differences "
                        f"(too many for bit analysis)"
                    )
                    continue

                print(
                    f"\n    Section {si} ({SECTION_NAMES[si]}) vs "
                    f"Section {sj} ({SECTION_NAMES[sj]}): "
                    f"{len(byte_diffs)} byte diffs"
                )

                if byte_diffs and len(byte_diffs) <= 20:
                    for offset, v_i, v_j in byte_diffs:
                        bits_i = bytes_to_bits(bytes([v_i]))
                        bits_j = bytes_to_bits(bytes([v_j]))
                        xor = [a ^ b for a, b in zip(bits_i, bits_j)]
                        print(
                            f"      offset {offset:4d}: "
                            f"{v_i:02X}={bits_to_str(bits_i)} vs "
                            f"{v_j:02X}={bits_to_str(bits_j)} "
                            f"XOR={bits_to_str(xor)}"
                        )


# ── Analysis 8: Summary ────────────────────────────────────────────────────


def print_summary(
    autocorr_results: Dict[str, List[Tuple[int, float]]], freq_results: Dict[str, Dict[int, dict]]
):
    """Print consolidated summary of findings."""
    print(f"\n{'=' * 90}")
    print("ANALYSIS 8: CONSOLIDATED SUMMARY")
    print(f"{'=' * 90}")

    print(f"\n  AUTOCORRELATION — Best lags per track:")
    for tname, corrs in autocorr_results.items():
        if not corrs:
            continue
        ranked = sorted(corrs, key=lambda x: abs(x[1]), reverse=True)[:5]
        lags_str = ", ".join(f"{lag}(R={r:+.3f})" for lag, r in ranked)
        print(f"    {tname}: {lags_str}")

    print(f"\n  BIT FREQUENCY — Best event sizes per track:")
    for tname, freq_res in freq_results.items():
        if not freq_res:
            continue
        # Rank by average bias
        ranked = sorted(freq_res.items(), key=lambda x: x[1]["avg_bias"], reverse=True)[:5]
        for esize, info in ranked:
            high_bias = info["high_bias_count"]
            print(
                f"    {tname}: {esize:3d} bits — avg_bias={info['avg_bias']:.4f}, "
                f"max_bias={info['max_bias']:.4f}, "
                f"{high_bias}/{esize} positions with bias>0.35"
            )

    # Cross-reference: lags that appear in both autocorrelation AND frequency analysis
    print(f"\n  CROSS-REFERENCE — Event sizes supported by multiple analyses:")
    candidate_sizes = Counter()
    for tname, corrs in autocorr_results.items():
        if not corrs:
            continue
        ranked = sorted(corrs, key=lambda x: abs(x[1]), reverse=True)
        for lag, r in ranked[:10]:
            if abs(r) > 0.08:
                candidate_sizes[lag] += 1

    for tname, freq_res in freq_results.items():
        ranked = sorted(freq_res.items(), key=lambda x: x[1]["avg_bias"], reverse=True)
        for esize, info in ranked[:5]:
            if info["avg_bias"] > 0.05:
                candidate_sizes[esize] += 1

    print(f"    Candidate sizes (by number of supporting signals):")
    for size, count in candidate_sizes.most_common(15):
        byte_equiv = f"= {size / 8:.1f} bytes" if size % 8 == 0 else f"≈ {size / 8:.2f} bytes"
        print(f"      {size:4d} bits ({byte_equiv}): supported by {count} signals")


# ── Main ────────────────────────────────────────────────────────────────────


def main():
    print("=" * 90)
    print("QY70 SysEx Track Event Data — BIT-LEVEL ANALYSIS")
    print(f"File: {SYX_FILE}")
    print("=" * 90)

    if not SYX_FILE.exists():
        print(f"ERROR: File not found: {SYX_FILE}")
        sys.exit(1)

    # ── 1. Load and Extract ──────────────────────────────────────────────
    print(f"\n{'=' * 90}")
    print("ANALYSIS 1: LOAD AND EXTRACT")
    print(f"{'=' * 90}")

    tracks = load_section0_tracks(SYX_FILE)
    all_data = load_all_sections(SYX_FILE)

    for track_idx in range(8):
        if track_idx not in tracks:
            print(f"  Track {track_idx} ({TRACK_NAMES[track_idx]}): NO DATA")
            continue
        data = tracks[track_idx]
        events = data[24:]
        bars = split_by_delimiter(events, 0xDC)
        bar_sizes = [len(b) for b in bars]

        # Voice info from header
        voice_msb = data[14] if len(data) > 14 else 0
        voice_lsb = data[15] if len(data) > 15 else 0

        print(
            f"  Track {track_idx} ({TRACK_NAMES[track_idx]}): "
            f"{len(data)} total, {len(events)} event bytes, "
            f"{len(bars)} bars (sizes: {bar_sizes}), "
            f"voice={voice_msb:02X}/{voice_lsb:02X}"
        )

    # ── 2. Bit Frequency Analysis ────────────────────────────────────────
    print(f"\n{'=' * 90}")
    print("ANALYSIS 2: BIT-LEVEL FREQUENCY PER POSITION")
    print(f"{'=' * 90}")

    event_sizes = [3, 4, 5, 6, 7, 8, 10, 12, 14, 16, 21, 24, 28]
    freq_results = {}

    for track_idx in [0, 2, 3, 4]:  # RHY1, BASS, CHD1, CHD2
        if track_idx not in tracks:
            continue
        tname = TRACK_NAMES[track_idx]
        events = tracks[track_idx][24:]

        # For tracks with bars, use just bar data (exclude DC delimiters)
        bars = split_by_delimiter(events, 0xDC)
        if bars:
            # Use first bar for analysis (cleanest data without delimiter contamination)
            bar_data = bars[0]
            result = bit_frequency_analysis(bar_data, event_sizes, f"{tname} Bar 0")
            freq_results[tname] = result

    # ── 3. Autocorrelation ───────────────────────────────────────────────
    print(f"\n{'=' * 90}")
    print("ANALYSIS 3: AUTOCORRELATION")
    print(f"{'=' * 90}")

    autocorr_results = {}

    for track_idx in [0, 2, 3, 4]:  # RHY1, BASS, CHD1, CHD2
        if track_idx not in tracks:
            continue
        tname = TRACK_NAMES[track_idx]
        events = tracks[track_idx][24:]

        bars = split_by_delimiter(events, 0xDC)
        if bars:
            # Use first bar
            bar_data = bars[0]
            corrs = autocorrelation_analysis(bar_data, max_lag=256, label=f"{tname} Bar 0")
            autocorr_results[tname] = corrs

    # ── 4. Sliding Window Patterns (CHD2) ────────────────────────────────
    print(f"\n{'=' * 90}")
    print("ANALYSIS 4: SLIDING WINDOW BIT PATTERNS")
    print(f"{'=' * 90}")

    for track_idx in [4, 3]:  # CHD2 first, then CHD1
        if track_idx not in tracks:
            continue
        tname = TRACK_NAMES[track_idx]
        events = tracks[track_idx][24:]
        bars = split_by_delimiter(events, 0xDC)

        if bars:
            # For CHD2, use full event data (both bars) to find cross-bar patterns
            # Strip DC and terminator
            clean_data = bytearray()
            for bar in bars:
                clean_data.extend(bar)
            sliding_window_patterns(
                bytes(clean_data), min_pat=8, max_pat=32, label=f"{tname} (all bars concatenated)"
            )

    # Also analyze RHY1 bar 0
    if 0 in tracks:
        events = tracks[0][24:]
        bars = split_by_delimiter(events, 0xDC)
        if bars:
            sliding_window_patterns(bars[0], min_pat=8, max_pat=28, label="RHY1 Bar 0")

    # ── 5. Cross-Bar Bit Alignment ───────────────────────────────────────
    cross_bar_alignment(tracks)

    # ── 6. Known Value Correlation ───────────────────────────────────────
    known_value_correlation(tracks)

    # ── 7. Differential Analysis ─────────────────────────────────────────
    differential_analysis(all_data)

    # ── 8. Summary ───────────────────────────────────────────────────────
    print_summary(autocorr_results, freq_results)

    print(f"\n{'=' * 90}")
    print("BIT-LEVEL ANALYSIS COMPLETE")
    print(f"{'=' * 90}")


if __name__ == "__main__":
    main()
