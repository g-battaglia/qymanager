#!/usr/bin/env python3
"""
Correlate SGT bitstream bytes (QY70_SGT.syx Section 0 per track) with
captured playback MIDI notes (data/sgt_rounds/R1_4bar).

For each track:
  1. Extract decoded bytes from QY70_SGT.syx at AL=section*8+track
  2. Identify event boundaries (7-byte events after preamble + headers)
  3. Count events
  4. Extract captured notes for corresponding channel
  5. Compute events-to-notes ratio
  6. Attempt 1:N mapping per event position

Output: data/sgt_rounds/R5_bitstream_map.json
"""

import json
import sys
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent))

from qymanager.formats.qy70.sysex_parser import SysExParser


SGT = Path(__file__).parent.parent / "tests" / "fixtures" / "QY70_SGT.syx"
R1 = Path(__file__).parent.parent / "data" / "sgt_rounds" / "R1_4bar" / "playback.json"
OUT = Path(__file__).parent.parent / "data" / "sgt_rounds" / "R5_bitstream_map.json"


TRACK_TO_CH = {
    0: 9,   # D1/RHY1
    1: 10,  # D2/RHY2
    2: 11,  # PC/PAD
    3: 12,  # BA/BASS
    4: 13,  # C1/CHD1 (usually no output)
    5: 14,  # C2/CHD2
    6: 15,  # C3/PHR1
    7: 16,  # C4/PHR2
}

TRACK_NAMES = {
    0: "RHY1", 1: "RHY2", 2: "PAD", 3: "BASS",
    4: "CHD1", 5: "CHD2", 6: "PHR1", 7: "PHR2",
}


def extract_section_tracks(syx_path: Path, section: int = 0) -> dict[int, bytes]:
    """Return {track_idx: decoded_bytes} for given section."""
    parser = SysExParser()
    msgs = parser.parse_file(str(syx_path))
    tracks = {}
    for m in msgs:
        if not m.is_style_data or not m.decoded_data:
            continue
        al = m.address_low
        if al == 0x7F:  # header, skip
            continue
        sec = al // 8
        trk = al % 8
        if sec == section:
            tracks.setdefault(trk, b"")
            tracks[trk] += m.decoded_data
    return tracks


def segment_events(data: bytes) -> dict:
    """Parse track bytes into segments (13B bar headers + 7B events + delimiters)."""
    # Skip 24B track header + 4B preamble = 28B
    body = data[28:]
    # Find 0xDC (bar) and 0x9E (sub-bar) delimiters
    dc_positions = [i for i, b in enumerate(body) if b == 0xDC]
    sub_positions = [i for i, b in enumerate(body) if b == 0x9E]
    return {
        "body_len": len(body),
        "dc_delimiters": dc_positions[:20],
        "sub_delimiters": sub_positions[:20],
        "first_32_bytes": body[:32].hex(),
    }


def rot_right(val, shift, width=56):
    shift %= width
    return ((val >> shift) | (val << (width - shift))) & ((1 << width) - 1)


def try_decode_events(data: bytes, start: int = 41, n: int = 10) -> list[dict]:
    """Try cumulative R=9×(i+1) decode on first N events starting at `start`."""
    results = []
    for i in range(n):
        off = start + i * 7
        if off + 7 > len(data):
            break
        chunk = data[off:off + 7]
        val = int.from_bytes(chunk, "big")
        r = (9 * (i + 1)) % 56
        derot = rot_right(val, r)
        f0 = (derot >> 47) & 0x1FF
        f5 = (derot >> 2) & 0x1FF
        rem = derot & 0x3
        note = f0 & 0x7F
        bit7 = (f0 >> 7) & 1
        bit8 = (f0 >> 8) & 1
        vel_code = (bit8 << 3) | (bit7 << 2) | rem
        midi_vel = max(1, 127 - vel_code * 8)
        results.append({
            "idx": i,
            "offset": off,
            "hex": chunk.hex(),
            "R": r,
            "note": note,
            "vel": midi_vel,
            "gate": f5,
            "valid_drum": 13 <= note <= 87,
        })
    return results


def main():
    print(f"Loading SGT from {SGT}")
    tracks = extract_section_tracks(SGT, section=0)
    print(f"Section 0 tracks: {sorted(tracks.keys())}")
    for trk, data in tracks.items():
        print(f"  Track {trk} ({TRACK_NAMES[trk]}): {len(data)}B")

    print(f"\nLoading captured playback from {R1}")
    r1 = json.loads(R1.read_text())
    note_ons = r1["note_ons"]
    print(f"Captured {len(note_ons)} note-ons across channels")

    # Per-channel captured notes
    notes_per_ch = defaultdict(list)
    for n in note_ons:
        notes_per_ch[n["ch"]].append(n)

    # Correlate
    result = {
        "source": "SGT Sec0 vs R1_4bar playback",
        "bars": 4,
        "bpm": 151,
        "tracks": {},
    }

    print(f"\n═══ Per-track correlation ═══")
    for trk in sorted(tracks.keys()):
        data = tracks[trk]
        ch = TRACK_TO_CH[trk]
        captured = notes_per_ch.get(ch, [])

        seg = segment_events(data)
        decoded = try_decode_events(data, start=41, n=15)
        valid_decoded = [d for d in decoded if d["valid_drum"]]

        # Events per bar estimate
        dc_count = len(seg["dc_delimiters"])
        n_events_sparse_est = sum(
            (p2 - p1 - 13) // 7 for p1, p2 in
            zip([28] + seg["dc_delimiters"], seg["dc_delimiters"] + [seg["body_len"] + 28])
        ) if dc_count > 0 else 0

        track_result = {
            "name": TRACK_NAMES[trk],
            "ch": ch,
            "bytes_total": len(data),
            "segments": seg,
            "captured_note_count": len(captured),
            "captured_unique_notes": sorted({n["note"] for n in captured}),
            "sparse_decode_first_15": decoded[:15],
            "valid_sparse_count": len(valid_decoded),
            "estimated_sparse_events": n_events_sparse_est,
            "notes_per_bar_captured": round(len(captured) / 4, 1),
            "events_per_bar_estimate": round(n_events_sparse_est / 4, 1) if n_events_sparse_est else None,
            "first_captured_notes": captured[:10],
        }
        result["tracks"][trk] = track_result

        print(f"\n  Track {trk} ({TRACK_NAMES[trk]}) ch{ch}:")
        print(f"    Bytes: {len(data)}, DC delimiters: {dc_count}")
        print(f"    Captured notes: {len(captured)} ({round(len(captured)/4, 1)}/bar)")
        print(f"    Unique captured notes: {sorted({n['note'] for n in captured})}")
        print(f"    Sparse decode (R=9×(i+1)): {len(valid_decoded)}/15 valid drum notes")
        if captured:
            first_captured_notes = sorted({n["note"] for n in captured[:4]})
            decoded_first_notes = [d["note"] for d in decoded[:4]]
            print(f"    First 4 captured unique: {first_captured_notes}")
            print(f"    First 4 decoded notes (sparse model): {decoded_first_notes}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, default=str))
    print(f"\n═══ Saved → {OUT} ═══")


if __name__ == "__main__":
    main()
