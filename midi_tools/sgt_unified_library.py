#!/usr/bin/env python3
"""
R9: Unified template library combining Summer GT + SGT captured data.

Library entries per strike signature:
  - Event byte pattern (7B)
  - Track type (RHY1/RHY2/BASS/CHD/PHR)
  - R used to decode
  - Source (Summer or SGT)
  - Confidence (exact match vs probabilistic)

Output: data/template_library_v2.json
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from qymanager.formats.qy70.sysex_parser import SysExParser


SUMMER_GT = Path(__file__).parent / "captured" / "summer_ground_truth.json"
SGT = Path(__file__).parent.parent / "tests" / "fixtures" / "QY70_SGT.syx"
R7_ALIGN = Path(__file__).parent.parent / "data" / "sgt_rounds" / "R7_timeline_align.json"
OUT = Path(__file__).parent.parent / "data" / "template_library_v2.json"


def build_summer_entries():
    """Load Summer GT events as exact template library."""
    gt = json.loads(SUMMER_GT.read_text())
    entries = []
    for ev in gt["events"]:
        entries.append({
            "source": "Summer_dense_user",
            "bar": ev["bar"],
            "beat": ev["beat"],
            "event_bytes_hex": ev["event_hex"],
            "strikes": ev["expected_strikes"],
            "strike_signature": sorted((s["note"], s["subdivision_8th"]) for s in ev["expected_strikes"]),
            "track": "RHY1",
            "encoding_regime": "dense-user",
            "confidence": "ground_truth_exact",
        })
    return entries


def build_sgt_entries():
    """Load SGT R7 timeline-aligned events as probabilistic templates."""
    data = json.loads(R7_ALIGN.read_text())
    entries = []
    for trk_id, trk_data in data["tracks"].items():
        if "skipped" in trk_data:
            continue
        name = trk_data["name"]
        for al in trk_data.get("first_aligned", []):
            entries.append({
                "source": "SGT_factory",
                "track": name,
                "track_idx": int(trk_id),
                "event_idx": al["i"],
                "byte_offset": al["off"],
                "R": al["R"],
                "note": al["note"],
                "captured_vel": al["capt_vel"],
                "decoded_vel": al["dec_vel"],
                "encoding_regime": "dense-factory",
                "confidence": "timeline_aligned",
            })
    return entries


def extract_sgt_bytes():
    """Get SGT Section 0 per-track body bytes for reference."""
    parser = SysExParser()
    msgs = parser.parse_file(str(SGT))
    tracks = defaultdict(bytes)
    for m in msgs:
        if m.is_style_data and m.decoded_data and 0 <= m.address_low <= 7:
            tracks[m.address_low] += m.decoded_data
    return {str(k): v.hex() for k, v in tracks.items()}


def main():
    summer = build_summer_entries()
    sgt = build_sgt_entries()
    sgt_bytes = extract_sgt_bytes()

    # Known sparse templates (from known_pattern.syx proven 7/7)
    sparse_templates = {
        "note_36_vel127_gate412_tick240_idx0": {
            "event_bytes_hex": "00000000078024",
            "R_model": "cumulative R=9×(i+1)",
            "R_value": 9,
            "confidence": "proven_7_of_7",
        },
    }

    library = {
        "version": "v2",
        "generation_date": "2026-04-22",
        "sources": {
            "summer_ground_truth": str(SUMMER_GT),
            "sgt_bitstream": str(SGT),
            "sgt_r7_align": str(R7_ALIGN),
        },
        "encoding_regimes": {
            "sparse": {
                "status": "SOLVED",
                "R_model": "cumulative R=9×(i+1)",
                "proof": "7/7 match on known_pattern.syx",
            },
            "dense-user": {
                "status": "TEMPLATES_EXTRACTED",
                "entries_count": len(summer),
                "strike_signatures_unique": 4,
                "notes": "Summer: 4-bar pattern, 20 events mapped to 61 strikes",
            },
            "dense-factory": {
                "status": "PARTIAL",
                "entries_count": len(sgt),
                "notes": "Per-6 cycle structure confirmed (42B super-cycle). R varies per position in cycle. Coverage ~40-68% via timeline alignment.",
            },
        },
        "sparse_templates": sparse_templates,
        "summer_entries": summer,
        "sgt_entries": sgt,
        "sgt_raw_bytes_per_track": sgt_bytes,
        "stats": {
            "summer_entry_count": len(summer),
            "sgt_entry_count": len(sgt),
            "total_entries": len(summer) + len(sgt),
        },
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(library, indent=2, default=str))
    print(f"═══ Template library v2 saved → {OUT} ═══")
    print(f"  Summer entries: {len(summer)}")
    print(f"  SGT entries:    {len(sgt)}")
    print(f"  Total:          {len(summer) + len(sgt)}")
    print(f"  Encoding regimes: sparse, dense-user (Summer), dense-factory (SGT)")


if __name__ == "__main__":
    main()
