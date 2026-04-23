#!/usr/bin/env python3
"""
R7: Timeline-based event→strike alignment.

For each SGT Section 0 track:
  1. Bitstream body (after 28B header) split into N events
  2. Assume events uniformly distributed in 4 bars @ 151 BPM
  3. For each event, compute its expected playback time
  4. Find captured notes within time window around event time
  5. For each matched (event, note), find R that decodes to that note
  6. Record (event_idx, byte_offset, matched_note, R_used)

Output: data/sgt_rounds/R7_timeline_align.json
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from qymanager.formats.qy70.sysex_parser import SysExParser


SGT = Path(__file__).parent.parent / "tests" / "fixtures" / "QY70_SGT.syx"
R1 = Path(__file__).parent.parent / "data" / "sgt_rounds" / "R1_4bar" / "playback.json"
OUT = Path(__file__).parent.parent / "data" / "sgt_rounds" / "R7_timeline_align.json"

TRACK_NAMES = {0: "RHY1", 1: "RHY2", 2: "PAD", 3: "BASS",
               4: "CHD1", 5: "CHD2", 6: "PHR1", 7: "PHR2"}
TRACK_CH = {0: 9, 1: 10, 2: 11, 3: 12, 4: 13, 5: 14, 6: 15, 7: 16}

BPM = 151
BARS = 4
BAR_DURATION = 60.0 / BPM * 4  # 4 beats/bar


def rot_right(val, s, w=56):
    s %= w
    return ((val >> s) | (val << (w - s))) & ((1 << w) - 1)


def decode_r(val: int, R: int) -> dict:
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
    return {"note": note, "vel": midi_vel, "gate": f5, "f1": f1}


def find_Rs_for_note(chunk: bytes, target_note: int) -> list[int]:
    """Return all R values yielding target note."""
    val = int.from_bytes(chunk, "big")
    return [R for R in range(56) if (rot_right(val, R) >> 47) & 0x7F == target_note]


def extract_sec0():
    parser = SysExParser()
    msgs = parser.parse_file(str(SGT))
    tracks = defaultdict(bytes)
    for m in msgs:
        if m.is_style_data and m.decoded_data and 0 <= m.address_low <= 7:
            tracks[m.address_low] += m.decoded_data
    return dict(tracks)


def align_track(trk: int, body: bytes, captured: list, bar_duration: float) -> dict:
    """Align events in body with captured notes via timing."""
    if not captured or len(body) < 7:
        return {"aligned": [], "coverage": 0.0}

    total_duration = bar_duration * BARS
    n_events_candidates = len(body) // 7
    if n_events_candidates == 0:
        return {"aligned": [], "coverage": 0.0}

    # Time per event if uniformly distributed
    t_per_event = total_duration / n_events_candidates

    # For each event, find captured note closest in time AND with a valid R
    aligned = []
    used_note_idxs = set()

    for ei in range(n_events_candidates):
        event_t = ei * t_per_event
        off = ei * 7
        chunk = body[off:off + 7]

        # Find captured notes within ±half event window of event_t
        window = t_per_event * 1.5
        candidates = [(ni, n) for ni, n in enumerate(captured)
                      if abs(n["t"] - event_t) < window and ni not in used_note_idxs]
        candidates.sort(key=lambda x: abs(x[1]["t"] - event_t))

        # For each candidate, check if some R produces that note
        matched = None
        for ni, n in candidates:
            Rs = find_Rs_for_note(chunk, n["note"])
            if Rs:
                # Pick R yielding velocity closest to captured
                val = int.from_bytes(chunk, "big")
                best_R = min(Rs, key=lambda R: abs(decode_r(val, R)["vel"] - n["vel"]))
                matched = {
                    "captured_idx": ni,
                    "note": n["note"],
                    "captured_vel": n["vel"],
                    "captured_t": n["t"],
                    "event_t": event_t,
                    "R": best_R,
                    "decoded": decode_r(val, best_R),
                }
                used_note_idxs.add(ni)
                break

        aligned.append({
            "event_idx": ei,
            "offset": off,
            "hex": chunk.hex(),
            "match": matched,
        })

    n_matched = sum(1 for a in aligned if a["match"])
    return {
        "aligned": aligned,
        "n_events": n_events_candidates,
        "n_matched": n_matched,
        "coverage": n_matched / max(1, len(captured)),
        "t_per_event": t_per_event,
    }


def extract_R_pattern(aligned: list) -> dict:
    """From aligned events, extract R sequence."""
    R_seq = [a["match"]["R"] for a in aligned if a["match"]]
    if not R_seq:
        return {}
    # Check if R_seq follows pattern
    diffs = [R_seq[i+1] - R_seq[i] for i in range(len(R_seq)-1)]
    mod_diffs = [d % 56 for d in diffs]
    return {
        "R_sequence_first_20": R_seq[:20],
        "R_diffs_mod56": mod_diffs[:20],
        "R_value_counts": dict(sorted(
            {r: R_seq.count(r) for r in set(R_seq)}.items(),
            key=lambda x: -x[1])[:10]
        ),
        "mean_R_diff": round(sum(mod_diffs) / max(1, len(mod_diffs)), 2),
    }


def main():
    tracks = extract_sec0()
    r1 = json.loads(R1.read_text())
    captured_per_ch = defaultdict(list)
    for n in r1["note_ons"]:
        captured_per_ch[n["ch"]].append(n)

    result = {"bpm": BPM, "bars": BARS, "bar_duration": BAR_DURATION, "tracks": {}}

    for trk, data in sorted(tracks.items()):
        body = data[28:]
        captured = captured_per_ch.get(TRACK_CH[trk], [])
        align = align_track(trk, body, captured, BAR_DURATION)
        if "n_events" not in align:
            result["tracks"][trk] = {
                "name": TRACK_NAMES[trk], "ch": TRACK_CH[trk],
                "bytes": len(body), "captured": len(captured),
                "skipped": "no captured notes or too little data",
            }
            print(f"\n═══ Track {trk} ({TRACK_NAMES[trk]}) ch{TRACK_CH[trk]}: SKIPPED ═══")
            continue
        R_pat = extract_R_pattern(align["aligned"])
        result["tracks"][trk] = {
            "name": TRACK_NAMES[trk],
            "ch": TRACK_CH[trk],
            "bytes": len(body),
            "captured": len(captured),
            "n_events": align["n_events"],
            "n_matched": align["n_matched"],
            "coverage": round(align["coverage"], 3),
            "t_per_event_ms": round(align["t_per_event"] * 1000, 1),
            "R_pattern": R_pat,
            "first_aligned": [
                {"i": a["event_idx"], "off": a["offset"], "R": a["match"]["R"],
                 "note": a["match"]["note"], "capt_vel": a["match"]["captured_vel"],
                 "dec_vel": a["match"]["decoded"]["vel"]}
                for a in align["aligned"][:20] if a["match"]
            ],
        }
        print(f"\n═══ Track {trk} ({TRACK_NAMES[trk]}) ch{TRACK_CH[trk]} ═══")
        print(f"  Body: {len(body)}B  Events: {align['n_events']}  "
              f"Captured: {len(captured)}  Matched: {align['n_matched']}")
        print(f"  t_per_event: {align['t_per_event']*1000:.1f}ms")
        print(f"  Coverage: {align['coverage']*100:.1f}%")
        if R_pat:
            print(f"  R sequence first 10: {R_pat['R_sequence_first_20'][:10]}")
            print(f"  R diffs mod56 first 10: {R_pat['R_diffs_mod56'][:10]}")
            print(f"  R value counts: {R_pat['R_value_counts']}")
            print(f"  Mean R diff: {R_pat['mean_R_diff']}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, default=str))
    print(f"\n═══ Saved → {OUT} ═══")


if __name__ == "__main__":
    main()
