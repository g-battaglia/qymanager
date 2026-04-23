#!/usr/bin/env python3
"""Per-event R calibration using any bulk + playback GT pair."""

import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from qymanager.formats.qy70.sysex_parser import SysExParser


def rot_right(v, s, w=56):
    s %= w
    return ((v >> s) | (v << (w - s))) & ((1 << w) - 1)


def decode_note(val, R):
    return (rot_right(val, R) >> 47) & 0x7F


def extract_tracks(syx_path: Path, section: int = 0) -> dict:
    parser = SysExParser()
    msgs = parser.parse_file(str(syx_path))
    tracks = defaultdict(bytes)
    for m in msgs:
        if not (m.address_high == 0x02 and
                (m.address_mid <= 0x1F or m.address_mid == 0x7E) and m.decoded_data):
            continue
        if m.address_low == 0x7F:
            continue
        sec = m.address_low // 8
        trk = m.address_low % 8
        if sec == section:
            tracks[trk] += m.decoded_data
    return dict(tracks)


def calibrate(body: bytes, target_notes: set) -> dict:
    body = body[28:]
    n_events = len(body) // 7
    R_table = []
    matched = 0
    for i in range(n_events):
        chunk = body[i*7:(i+1)*7]
        val = int.from_bytes(chunk, "big")
        best_R = 0
        found = False
        for R in range(56):
            if decode_note(val, R) in target_notes:
                best_R = R
                found = True
                break
        R_table.append(best_R)
        if found:
            matched += 1
    return {"N": n_events, "R_table": R_table, "matched": matched}


TRACK_CH = {0:9, 1:10, 2:11, 3:12, 4:13, 5:14, 6:15, 7:16}
NAMES = {0:"RHY1",1:"RHY2",2:"PAD",3:"BASS",4:"CHD1",5:"CHD2",6:"PHR1",7:"PHR2"}


def run(bulk_path, play_path, section=0, label=""):
    tracks = extract_tracks(bulk_path, section)
    play = json.loads(play_path.read_text())
    captured = defaultdict(list)
    for e in play:
        d = bytes.fromhex(e["data"]) if isinstance(e.get("data"), str) else None
        if d and len(d) >= 3 and (d[0] & 0xF0) == 0x90 and d[2] > 0:
            ch = (d[0] & 0xF) + 1
            captured[ch].append(d[1])

    result = {"label": label, "bulk": str(bulk_path.name), "play": str(play_path.name),
              "section": section, "tracks": {}}
    print(f"\n═══ {label} Section {section} ═══")
    for trk, ch in TRACK_CH.items():
        if trk not in tracks:
            continue
        body = tracks[trk]
        target = set(captured[ch])
        if not target:
            continue
        cal = calibrate(body, target)
        cal["ch"] = ch
        cal["target_notes"] = sorted(target)
        cal["captured_count"] = len(captured[ch])
        result["tracks"][str(trk)] = cal
        pct = cal["matched"] / max(1, cal["N"]) * 100
        print(f"  {NAMES[trk]:5s} ch{ch:>2}: N={cal['N']:>4} matched={cal['matched']:>4} ({pct:5.1f}%)  targets={sorted(target)}")
    return result


if __name__ == "__main__":
    out_all = {}

    # AMB#01
    amb_bulk = Path("data/captures_2026_04_23/AMB01_bulk_20260423_113016.syx")
    amb_play = Path("data/captures_2026_04_23/AMB01_play_20260423_113240.json")
    if amb_bulk.exists() and amb_play.exists():
        out_all["AMB01"] = run(amb_bulk, amb_play, section=0, label="AMB#01")

    # STYLE2 for each section
    style2_bulk = Path("data/captures_2026_04_23/STYLE2_bulk_20260423_113615.syx")
    style2_plays = {
        "INTRO": (0, "STYLE2_INTRO_play_20260423_113837.json"),
        "MAIN_A": (1, "STYLE2_MAINA_play_20260423_114008.json"),
        "MAIN_B": (2, "STYLE2_MAINB_play_20260423_114108.json"),
        "FILL_AB": (3, "STYLE2_FILLAB_play_20260423_114211.json"),
        "FILL_BA": (4, "STYLE2_FILLBA_play_20260423_114308.json"),
        "ENDING": (5, "STYLE2_ENDING_play_20260423_114403.json"),
    }
    for label, (sec, fn) in style2_plays.items():
        play_path = Path("data/captures_2026_04_23") / fn
        if play_path.exists() and style2_bulk.exists():
            out_all[f"STYLE2_{label}"] = run(style2_bulk, play_path, section=sec, label=f"STYLE2_{label}")

    # Save
    out = Path("data/captures_2026_04_23/R_tables_all.json")
    out.write_text(json.dumps(out_all, indent=2))
    print(f"\n═══ Saved: {out} ═══")
