#!/usr/bin/env python3
"""
SGT template extraction — scan SGT Section 0 for each track, align 7-byte
events with captured playback timing, extract per-event→per-hit mapping.

Strategy:
  For each track:
    1. Take bitstream bytes minus 28B header → N bytes data
    2. Take captured notes from R1 playback (time-sorted)
    3. Assume events are 7-byte aligned somewhere (try offsets 0-27)
    4. For each alignment hypothesis, try:
       - Sparse R=9×(i+1) per segment
       - Per-beat rotation R=[0,2,1,0]
       - Constant R=9
    5. Score: number of valid drum notes matching captured unique notes
    6. Pick best scoring scheme per track
    7. Record templates

Output:
  - data/sgt_rounds/R6_track_templates.json — per-track event→strike mapping
  - data/sgt_rounds/R7_encoder_candidates.json — encoding hypotheses ranked
"""

import json
import sys
from collections import defaultdict, Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from qymanager.formats.qy70.sysex_parser import SysExParser


SGT = Path(__file__).parent.parent / "tests" / "fixtures" / "QY70_SGT.syx"
R1 = Path(__file__).parent.parent / "data" / "sgt_rounds" / "R1_4bar" / "playback.json"
OUT_DIR = Path(__file__).parent.parent / "data" / "sgt_rounds"

TRACK_NAMES = {0: "RHY1", 1: "RHY2", 2: "PAD", 3: "BASS",
               4: "CHD1", 5: "CHD2", 6: "PHR1", 7: "PHR2"}
TRACK_CH = {0: 9, 1: 10, 2: 11, 3: 12, 4: 13, 5: 14, 6: 15, 7: 16}


def rot_right(val, s, w=56):
    s %= w
    return ((val >> s) | (val << (w - s))) & ((1 << w) - 1)


def rot_left(val, s, w=56):
    return rot_right(val, (-s) % w, w)


def extract_section0_tracks():
    parser = SysExParser()
    msgs = parser.parse_file(str(SGT))
    tracks = defaultdict(bytes)
    for m in msgs:
        if not m.is_style_data or not m.decoded_data:
            continue
        al = m.address_low
        if al == 0x7F or al // 8 != 0:
            continue
        tracks[al % 8] += m.decoded_data
    return dict(tracks)


def load_captured():
    r1 = json.loads(R1.read_text())
    by_ch = defaultdict(list)
    for n in r1["note_ons"]:
        by_ch[n["ch"]].append(n)
    return dict(by_ch)


def decode_7byte(chunk: bytes, R: int) -> dict:
    val = int.from_bytes(chunk, "big")
    derot = rot_right(val, R)
    f0 = (derot >> 47) & 0x1FF
    f5 = (derot >> 2) & 0x1FF
    f1 = (derot >> 38) & 0x1FF
    rem = derot & 0x3
    note = f0 & 0x7F
    bit7 = (f0 >> 7) & 1
    bit8 = (f0 >> 8) & 1
    vel_code = (bit8 << 3) | (bit7 << 2) | rem
    midi_vel = max(1, 127 - vel_code * 8)
    beat = f1 >> 7
    clock = ((f1 & 0x7F) << 2) | ((derot >> 29) & 0x1FF) >> 7
    return {"note": note, "vel": midi_vel, "gate": f5, "beat": beat, "clock": clock}


def score_sparse_cumulative(body: bytes, start: int, target_notes: set) -> dict:
    """Try sparse R=9×(i+1) from offset `start`. Return match count."""
    matches = 0
    total = 0
    events = []
    idx = 0
    for off in range(start, len(body) - 6, 7):
        chunk = body[off:off + 7]
        R = (9 * (idx + 1)) % 56
        ev = decode_7byte(chunk, R)
        total += 1
        if ev["note"] in target_notes:
            matches += 1
        events.append(ev)
        idx += 1
    return {"start": start, "matches": matches, "total": total,
            "events": events[:20], "target": list(target_notes)}


def score_constant_R(body: bytes, start: int, R: int, target_notes: set) -> dict:
    matches = 0
    total = 0
    for off in range(start, len(body) - 6, 7):
        chunk = body[off:off + 7]
        ev = decode_7byte(chunk, R)
        total += 1
        if ev["note"] in target_notes:
            matches += 1
    return {"start": start, "R": R, "matches": matches, "total": total}


def score_free_per_event(body: bytes, start: int, target_notes: set) -> dict:
    """For each 7-byte event, find ANY R that yields a target note."""
    hits = []
    for off in range(start, len(body) - 6, 7):
        chunk = body[off:off + 7]
        val = int.from_bytes(chunk, "big")
        found = None
        for R in range(56):
            derot = rot_right(val, R)
            f0 = (derot >> 47) & 0x1FF
            note = f0 & 0x7F
            if note in target_notes:
                found = {"R": R, "note": note}
                break
        hits.append({"offset": off, "hit": found})
    n_hit = sum(1 for h in hits if h["hit"])
    return {"start": start, "total": len(hits), "hit_count": n_hit,
            "hit_rate": n_hit / max(1, len(hits))}


def analyze_track(trk: int, body: bytes, captured: list) -> dict:
    target_notes = {n["note"] for n in captured}
    name = TRACK_NAMES[trk]
    ch = TRACK_CH[trk]
    result = {
        "track": trk, "name": name, "ch": ch,
        "bytes": len(body),
        "captured_count": len(captured),
        "unique_notes": sorted(target_notes),
        "notes_per_bar": round(len(captured) / 4, 2),
    }

    if not target_notes or len(body) < 14:
        result["analysis"] = "skipped (no captured notes or too little data)"
        return result

    # Try sparse cumulative at start offsets 0-27
    sparse_scores = []
    for start in range(0, 28):
        s = score_sparse_cumulative(body, start, target_notes)
        sparse_scores.append(s)
    sparse_scores.sort(key=lambda x: -x["matches"])
    result["sparse_best_start"] = sparse_scores[0]

    # Try constant R, best start offset
    const_scores = []
    for start in (0, 13, 14, 28, 41):
        for R in (9, 18, 27, 0, 47):
            s = score_constant_R(body, start, R, target_notes)
            const_scores.append(s)
    const_scores.sort(key=lambda x: -x["matches"])
    result["const_R_best"] = const_scores[0]

    # Free per-event search
    free_scores = []
    for start in (0, 13, 14, 28, 41):
        s = score_free_per_event(body, start, target_notes)
        free_scores.append(s)
    free_scores.sort(key=lambda x: -x["hit_rate"])
    result["free_R_best"] = free_scores[0]

    # Stats
    n_events_sparse_best = result["sparse_best_start"]["total"]
    coverage_ratio_sparse = result["sparse_best_start"]["matches"] / max(1, len(captured))
    coverage_ratio_free = result["free_R_best"]["hit_count"] / max(1, len(captured))
    result["analysis"] = {
        "sparse_coverage_ratio": round(coverage_ratio_sparse, 3),
        "free_R_coverage_ratio": round(coverage_ratio_free, 3),
        "sparse_events_total": n_events_sparse_best,
    }

    return result


def main():
    tracks = extract_section0_tracks()
    captured = load_captured()

    results = {"bpm": 151, "bars": 4, "tracks": []}

    for trk in sorted(tracks.keys()):
        data = tracks[trk]
        body = data[28:]  # skip header + preamble
        cap = captured.get(TRACK_CH[trk], [])
        r = analyze_track(trk, body, cap)
        results["tracks"].append(r)
        print(f"\n═══ Track {trk} ({r['name']}) ch{r['ch']} ═══")
        print(f"  Body: {len(body)}B  Captured: {r['captured_count']} notes  "
              f"Unique: {r['unique_notes']}")
        if "analysis" in r and isinstance(r["analysis"], dict):
            sb = r["sparse_best_start"]
            cb = r["const_R_best"]
            fb = r["free_R_best"]
            print(f"  Sparse R=9×(i+1): best start={sb['start']}, "
                  f"{sb['matches']}/{sb['total']} match target notes")
            print(f"  Const R: best start={cb['start']} R={cb['R']}, "
                  f"{cb['matches']}/{cb['total']}")
            print(f"  Free R: best start={fb['start']}, {fb['hit_count']}/{fb['total']} "
                  f"({fb['hit_rate']*100:.1f}%)")
            a = r["analysis"]
            print(f"  Sparse coverage: {a['sparse_coverage_ratio']*100:.1f}% of captured")
            print(f"  Free-R coverage: {a['free_R_coverage_ratio']*100:.1f}% of captured")

    out = OUT_DIR / "R6_track_templates.json"
    out.write_text(json.dumps(results, indent=2, default=str))
    print(f"\n═══ Saved → {out} ═══")

    # Summary
    print(f"\n═══ SUMMARY ═══")
    print(f"{'Track':6s} {'Body':>5s} {'Notes':>6s} {'SparseMatch':>12s} {'FreeRCov':>10s}")
    for r in results["tracks"]:
        a = r.get("analysis", {})
        if not isinstance(a, dict):
            continue
        sb = r["sparse_best_start"]
        print(f"{r['name']:6s} {r['bytes']:>5d} {r['captured_count']:>6d} "
              f"{sb['matches']}/{sb['total']:<4d}     "
              f"{a['free_R_coverage_ratio']*100:>6.1f}%")


if __name__ == "__main__":
    main()
