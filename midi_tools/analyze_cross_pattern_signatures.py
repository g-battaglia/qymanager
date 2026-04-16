#!/usr/bin/env python3
"""
Cross-pattern signature analysis: find byte prefixes that recur identically
across multiple QY70 patterns.

If certain byte sequences appear as event prefixes in many unrelated patterns,
they likely represent "lane signatures" — constant markers the QY70 uses to
identify which drum/instrument lane an event belongs to.

This tests the hypothesis from Session 25e that Pattern C (solo kick) has
events with prefix `28ae8d81` identical to Summer's snare events, suggesting
these prefixes are universal lane markers rather than instrument data.
"""

import sys
import os
from pathlib import Path
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qymanager.formats.qy70.sysex_parser import SysExParser


def parse_all_tracks(syx_path):
    """Extract per-track decoded data from a .syx file."""
    parser = SysExParser()
    messages = parser.parse_file(str(syx_path))

    tracks = defaultdict(bytearray)
    seen_raw = set()

    for m in messages:
        if not m.is_bulk_dump or m.address_high != 0x02:
            continue
        # Deduplicate identical messages (some captures have repeats)
        key = bytes(m.raw)
        if key in seen_raw:
            continue
        seen_raw.add(key)
        if m.decoded_data is not None:
            tracks[m.address_low].extend(m.decoded_data)

    return {al: bytes(data) for al, data in tracks.items()}


def extract_events(track_data):
    """
    Extract 7-byte events from a drum track.
    Returns list of (segment_idx, event_idx, event_bytes, bar_header).
    """
    if len(track_data) < 28:
        return []

    event_area = track_data[28:]  # skip metadata + preamble

    # Split on DC/9E delimiters
    segments = []
    prev = 0
    for i, b in enumerate(event_area):
        if b in (0xDC, 0x9E):
            seg = event_area[prev:i]
            segments.append(seg)
            prev = i + 1
    if prev < len(event_area):
        seg = event_area[prev:]
        if seg:
            segments.append(seg)

    events = []
    for si, seg in enumerate(segments):
        if len(seg) < 13:
            continue
        header = seg[:13]
        body = seg[13:]
        n_events = len(body) // 7
        for ei in range(n_events):
            evt = body[ei * 7 : (ei + 1) * 7]
            events.append((si, ei, evt, header))

    return events


def prefix_analysis(all_events, prefix_lens=(2, 3, 4, 5, 6)):
    """Count prefix frequencies across all events."""
    results = {}
    for plen in prefix_lens:
        counter = Counter()
        for pattern_name, events in all_events.items():
            for si, ei, evt, hdr in events:
                prefix = evt[:plen].hex()
                counter[prefix] += 1
        results[plen] = counter
    return results


def find_cross_pattern_prefixes(all_events, prefix_len=4, min_patterns=2):
    """
    Find prefixes that appear in at least `min_patterns` different patterns.
    Returns: {prefix: {pattern_name: count}}
    """
    prefix_to_patterns = defaultdict(lambda: defaultdict(int))

    for pattern_name, events in all_events.items():
        for si, ei, evt, hdr in events:
            prefix = evt[:prefix_len].hex()
            prefix_to_patterns[prefix][pattern_name] += 1

    cross = {
        prefix: dict(patterns)
        for prefix, patterns in prefix_to_patterns.items()
        if len(patterns) >= min_patterns
    }
    return cross


def main():
    sources = [
        ("PatternC_kick", "midi_tools/captured/ground_truth_C_kick.syx"),
        ("Summer", "data/qy70_sysx/P -  Summer - 20231101.syx"),
        ("MR_Vain", "data/qy70_sysx/P -  MR. Vain - 20231101.syx"),
        ("A_QY70", "data/qy70_sysx/A - QY70 -20231106.syx"),
        ("NEONGROOVE", "tests/fixtures/NEONGROOVE.syx"),
        ("SGT", "tests/fixtures/QY70_SGT.syx"),
    ]

    # Load all tracks per pattern
    all_tracks = {}
    for name, path in sources:
        if not Path(path).exists():
            print(f"SKIP: {name} ({path}) not found")
            continue
        try:
            tracks = parse_all_tracks(path)
            all_tracks[name] = tracks
            print(f"LOADED: {name}: tracks={sorted(tracks.keys())}")
        except Exception as e:
            print(f"ERROR loading {name}: {e}")

    print()
    print("=" * 70)
    print("DRUM TRACK EVENT ANALYSIS (AL=0x00 RHY1, AL=0x01 RHY2)")
    print("=" * 70)

    # Collect events from drum tracks only (AL=0,1)
    drum_events = {}
    for name, tracks in all_tracks.items():
        events = []
        for al in (0x00, 0x01):
            if al in tracks:
                events.extend(extract_events(tracks[al]))
        drum_events[name] = events
        print(f"  {name}: {len(events)} drum events")

    print()
    print("=" * 70)
    print("CROSS-PATTERN PREFIX RECURRENCE (≥2 patterns)")
    print("=" * 70)

    for prefix_len in (3, 4, 5, 6):
        cross = find_cross_pattern_prefixes(drum_events, prefix_len=prefix_len, min_patterns=2)
        print(f"\n--- {prefix_len}-byte prefixes appearing in ≥2 patterns ---")

        # Sort by number of patterns (desc), then by total count (desc)
        sorted_cross = sorted(
            cross.items(),
            key=lambda x: (-len(x[1]), -sum(x[1].values()))
        )

        shown = 0
        for prefix, patterns in sorted_cross:
            if len(patterns) >= 3:  # show only prefixes in 3+ patterns for brevity
                n_patterns = len(patterns)
                total = sum(patterns.values())
                details = ", ".join(f"{p}={c}" for p, c in sorted(patterns.items()))
                print(f"  {prefix} ({n_patterns} patterns, {total} occurrences): {details}")
                shown += 1
            if shown >= 20:
                break

        if shown == 0 and cross:
            # Fallback: show top 5 by occurrence
            for prefix, patterns in sorted_cross[:5]:
                total = sum(patterns.values())
                details = ", ".join(f"{p}={c}" for p, c in sorted(patterns.items()))
                print(f"  {prefix} ({len(patterns)} patterns, {total} total): {details}")

    # Special focus: test the hypothesis that `28ae8d81` is a universal lane marker
    print()
    print("=" * 70)
    print("HYPOTHESIS TEST: Is '28ae8d81...' a universal lane signature?")
    print("=" * 70)

    test_prefixes = [
        "28ae8d81",  # Summer snare core from session 25d
        "ae8d81",    # shorter variant
        "28ae",      # 2-byte prefix
        "8c",        # Pattern C e2 prefix
        "1d",        # Pattern C e0 prefix
    ]

    for prefix in test_prefixes:
        print(f"\n--- Prefix '{prefix}' ---")
        plen = len(prefix) // 2
        for name, events in drum_events.items():
            matches = [
                (si, ei, evt.hex())
                for si, ei, evt, hdr in events
                if evt[:plen].hex() == prefix
            ]
            if matches:
                print(f"  {name}: {len(matches)} matches")
                for si, ei, evtx in matches[:5]:
                    print(f"    seg{si} e{ei}: {evtx}")
                if len(matches) > 5:
                    print(f"    ... and {len(matches) - 5} more")
            else:
                print(f"  {name}: (none)")

    # Position-based analysis: which events tend to have which prefixes?
    print()
    print("=" * 70)
    print("EVENT-POSITION vs PREFIX DISTRIBUTION (position within segment)")
    print("=" * 70)

    position_prefix = defaultdict(Counter)  # position -> Counter(prefix)
    for name, events in drum_events.items():
        for si, ei, evt, hdr in events:
            if evt[0] == 0:  # skip all-zero padding events
                continue
            position_prefix[ei][evt[:2].hex()] += 1

    for pos in sorted(position_prefix.keys())[:8]:
        top = position_prefix[pos].most_common(8)
        total = sum(position_prefix[pos].values())
        print(f"\n  Event position {pos} (total: {total}):")
        for prefix, count in top:
            pct = 100 * count / total if total else 0
            print(f"    {prefix}: {count} ({pct:.1f}%)")


if __name__ == "__main__":
    main()
