#!/usr/bin/env python3
"""
Analyze bar headers and trailing bytes as possible velocity sources.

If per-beat velocities aren't in the event data, they must be in:
1. Bar headers (13 bytes = 104 bits = 11 × 9-bit fields)
2. Trailing bytes after events
3. A global table elsewhere in the track

Also: establish definitive mapping between bitstream segments and GT bar patterns
by comparing which segments are most similar to each other.
"""

import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qymanager.formats.qy70.sysex_parser import SysExParser
from midi_tools.event_decoder import rot_right, extract_9bit


def load_syx_track(syx_path, section=0, track=0):
    parser = SysExParser()
    messages = parser.parse_file(syx_path)
    al = section * 8 + track
    data = b""
    for m in messages:
        if m.is_style_data and m.address_low == al:
            if m.decoded_data is not None:
                data += m.decoded_data
    return data


def load_gt_rhy1(json_path, bpm=120.0):
    with open(json_path) as f:
        capture = json.load(f)
    rhy1_notes = []
    for evt in capture["events"]:
        d = evt["data"]
        if len(d) == 3:
            ch = d[0] & 0x0F
            msg = d[0] & 0xF0
            if ch == 8 and msg == 0x90 and d[2] > 0:
                rhy1_notes.append({"t": evt["t"], "note": d[1], "vel": d[2]})
    if not rhy1_notes:
        return {}
    bar_dur = 60.0 / bpm * 4
    t0 = rhy1_notes[0]["t"]
    bars = {}
    for n in rhy1_notes:
        dt = n["t"] - t0
        bar_idx = int(dt / bar_dur)
        tick = (dt - bar_idx * bar_dur) / (60.0 / bpm) * 480
        if bar_idx not in bars:
            bars[bar_idx] = []
        bars[bar_idx].append({"note": n["note"], "vel": n["vel"], "tick": tick})
    return bars


def main():
    syx_path = "data/qy70_sysx/P -  Summer - 20231101.syx"
    gt_path = "midi_tools/captured/summer_playback_s25.json"

    data = load_syx_track(syx_path, section=0, track=0)

    # Parse raw
    event_data = data[28:]
    delim_pos = [i for i, b in enumerate(event_data) if b in (0xDC, 0x9E)]
    prev = 0
    raw_segments = []
    for dp in delim_pos:
        raw_segments.append(event_data[prev:dp])
        prev = dp + 1
    raw_segments.append(event_data[prev:])

    # Filter real segments
    segments = []
    for seg in raw_segments:
        if len(seg) >= 20:
            header = seg[:13]
            evtdata = seg[13:]
            n_evt = len(evtdata) // 7
            trailing = evtdata[n_evt*7:]
            evts = [evtdata[i*7:(i+1)*7] for i in range(n_evt)]
            segments.append({"header": header, "events": evts, "trailing": trailing,
                             "raw": seg})

    gt_bars = load_gt_rhy1(gt_path)

    # GT pattern identification
    # Bars 0,4,8 are identical, 1,5,9 identical, etc.
    gt_patterns = {}
    for pi in range(4):
        bar_notes = gt_bars.get(pi, [])
        instruments = {}
        for n in sorted(bar_notes, key=lambda x: x["tick"]):
            instruments.setdefault(n["note"], []).append(n["vel"])
        gt_patterns[pi] = instruments

    print("=" * 80)
    print("BAR HEADER DEEP ANALYSIS")
    print("=" * 80)

    # First: the 24-byte track preamble area (before preamble bytes)
    print(f"\nTrack metadata (bytes 0-23): {data[:24].hex()}")
    print(f"Preamble (bytes 24-27): {data[24:28].hex()}")

    # Show all data before first delimiter
    init_seg = raw_segments[0] if raw_segments else b""
    print(f"\nInit segment (before first DC): {len(init_seg)} bytes")
    print(f"  Hex: {init_seg.hex()}")

    # Decompose init segment as 9-bit fields
    if len(init_seg) >= 13:
        hval = int.from_bytes(init_seg[:13], "big")
        hfields = [(hval >> (104 - (i+1)*9)) & 0x1FF for i in range(11)]
        print(f"  As 11×9-bit: {hfields}")
        print(f"  Remaining byte: {init_seg[13:].hex()}")

    # For each segment, show header fields and trailing bytes
    print(f"\n{'='*80}")
    print(f"HEADER FIELDS AND TRAILING BYTES")
    print(f"{'='*80}")

    for si, seg in enumerate(segments):
        hval = int.from_bytes(seg["header"], "big")
        hfields = [(hval >> (104 - (i+1)*9)) & 0x1FF for i in range(11)]
        rem_bits = hval & 0x1F  # 5 remaining bits

        print(f"\nSeg {si}: {len(seg['events'])} events")
        print(f"  Header hex: {seg['header'].hex()}")
        print(f"  Fields: {hfields}")
        print(f"  Remainder (5 bits): {rem_bits:05b} = {rem_bits}")

        if seg["trailing"]:
            trail = seg["trailing"]
            print(f"  Trailing ({len(trail)}B): {trail.hex()}")
            # Try 9-bit decomposition of trailing
            if len(trail) >= 2:
                tval = int.from_bytes(trail, "big")
                tbits = len(trail) * 8
                tfields = []
                for i in range(tbits // 9):
                    shift = tbits - (i+1) * 9
                    if shift >= 0:
                        tfields.append((tval >> shift) & 0x1FF)
                if tfields:
                    print(f"  Trail as 9-bit: {tfields}")

    # Look for velocity-like values in headers
    print(f"\n{'='*80}")
    print(f"HEADER FIELD CORRELATION WITH GT VELOCITIES")
    print(f"{'='*80}")

    print(f"\nGT velocity summary (unique values seen):")
    all_vels = set()
    for pi, instr in gt_patterns.items():
        for note, vels in instr.items():
            all_vels.update(vels)
    print(f"  All velocities: {sorted(all_vels)}")
    print(f"  Range: {min(all_vels)}-{max(all_vels)}")

    # Check if any header field values match GT velocity values
    print(f"\n  Header field values across all segments:")
    for fi in range(11):
        vals = [0] * len(segments)
        for si, seg in enumerate(segments):
            hval = int.from_bytes(seg["header"], "big")
            vals[si] = (hval >> (104 - (fi+1)*9)) & 0x1FF
        in_vel_range = [v for v in vals if 100 <= v <= 130]
        print(f"  F{fi:2d}: {vals}"
              + (f"  ← {len(in_vel_range)} in vel range!" if in_vel_range else ""))

    # Compare header bytes as raw 8-bit values
    print(f"\n  Header bytes (raw 8-bit) across segments:")
    for bi in range(13):
        vals = [seg["header"][bi] for seg in segments]
        in_vel = [v for v in vals if 100 <= v <= 130]
        print(f"  Byte[{bi:2d}]: {[f'{v:3d}(0x{v:02x})' for v in vals]}"
              + (f"  ← vel range!" if in_vel else ""))

    # The real question: what's in the TRACK-LEVEL data (first 24 bytes)?
    print(f"\n{'='*80}")
    print(f"TRACK-LEVEL DATA ANALYSIS (first 24 bytes)")
    print(f"{'='*80}")

    header_24 = data[:24]
    print(f"Raw: {header_24.hex()}")
    for i, b in enumerate(header_24):
        if 100 <= b <= 130:
            print(f"  Byte[{i}] = {b} (0x{b:02x}) — IN VELOCITY RANGE!")

    # Decompose as various field sizes
    val_192 = int.from_bytes(header_24, "big")
    print(f"\n  As 7-bit fields ({192//7}): ", end="")
    f7 = [(val_192 >> (192 - (i+1)*7)) & 0x7F for i in range(192//7)]
    print(f7)

    # Check which 7-bit values are in velocity range
    vel_matches = [(i, v) for i, v in enumerate(f7) if 100 <= v <= 130]
    if vel_matches:
        print(f"  7-bit values in vel range: {vel_matches}")

    # Now look at the FULL 384-byte track for velocity values
    print(f"\n{'='*80}")
    print(f"FULL TRACK SCAN: Where are values 112-127 concentrated?")
    print(f"{'='*80}")

    # Count bytes in velocity range per 16-byte region
    for region_start in range(0, len(data), 16):
        region = data[region_start:region_start+16]
        vel_count = sum(1 for b in region if 112 <= b <= 127)
        if vel_count >= 3:
            hex_str = region.hex()
            print(f"  [{region_start:3d}-{region_start+15:3d}]: "
                  f"{vel_count} vel-range bytes: {hex_str}")
            # Show which bytes
            markers = ""
            for i, b in enumerate(region):
                if 112 <= b <= 127:
                    markers += f" [{region_start+i}]={b}"
            print(f"    {markers}")

    # Alternative: check the ENTIRE track for patterns matching
    # GT velocity sequences
    print(f"\n{'='*80}")
    print(f"VELOCITY SEQUENCE SEARCH in raw track data")
    print(f"{'='*80}")

    # Look for the GT HH velocity sequence [122,116,122,117,118,112,121,114]
    target_seq = [122, 116, 122, 117, 118, 112, 121, 114]
    print(f"\nSearching for HH velocity sequence: {target_seq}")

    # Search in raw bytes
    for i in range(len(data) - 8):
        match = True
        for j, v in enumerate(target_seq):
            if data[i+j] != v:
                match = False
                break
        if match:
            print(f"  EXACT MATCH at offset {i} (0x{i:03x})!")

    # Search with tolerance ±2
    print(f"\nSearching with ±2 tolerance:")
    for i in range(len(data) - 8):
        diffs = [abs(data[i+j] - v) for j, v in enumerate(target_seq)]
        if max(diffs) <= 2:
            print(f"  Near match at offset {i} (0x{i:03x}): "
                  f"{[data[i+j] for j in range(8)]} diffs={diffs}")

    # Also search in the derotated 56-bit values (maybe velocities are
    # embedded after derotation)
    print(f"\nSearching in derotated 7-byte values:")
    for si, seg in enumerate(segments):
        for ei, evt in enumerate(seg["events"][:4]):
            for r in range(56):
                val = int.from_bytes(evt, "big")
                derot = rot_right(val, r)
                # Extract 7 bytes from derotated value
                dbytes = [(derot >> (48 - i*8)) & 0xFF for i in range(7)]
                diffs = [abs(dbytes[j] - v) for j, v in enumerate(target_seq[:7])]
                if max(diffs) <= 3:
                    print(f"  Seg{si}/e{ei} R={r}: derot bytes={dbytes[:7]} "
                          f"diffs={diffs}")

    print("\nDone.")


if __name__ == "__main__":
    main()
