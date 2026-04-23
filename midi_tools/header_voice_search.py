#!/usr/bin/env python3
"""RE iter: deep search for voice encoding in pattern header AL=0x7F."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from qymanager.formats.qy70.sysex_parser import SysExParser


def get_header(path):
    parser = SysExParser()
    msgs = parser.parse_file(path)
    h = b""
    for m in msgs:
        if m.is_style_data and m.decoded_data and m.address_low == 0x7F:
            h += m.decoded_data
    return h


VOICES = {
    "SGT":    [(127,0,26,75,0),(127,0,26,60,40),(127,0,26,63,60),(0,96,38,95,0),(0,0,81,60,70),(0,16,89,95,40),(0,0,24,50,40),(0,35,98,45,0)],
    "AMB01":  [(127,0,25,90,40),(127,0,26,60,40),(127,0,26,50,40),(0,0,34,75,40),(0,0,89,90,97),(0,0,89,90,97),(0,40,44,92,40),(126,0,0,80,40)],
    "STYLE2": [(127,0,26,65,0),(127,0,26,50,0),(127,0,26,55,0),(0,66,38,60,40),(0,0,89,75,40),(0,32,56,110,40),(0,0,9,81,40),(0,66,38,45,40)],
}
FILES = {
    "SGT": "tests/fixtures/QY70_SGT.syx",
    "AMB01": "data/captures_2026_04_23/AMB01_bulk_20260423_113016.syx",
    "STYLE2": "data/captures_2026_04_23/STYLE2_bulk_20260423_113615.syx",
}


def main():
    hdrs = {k: get_header(v) for k, v in FILES.items()}

    # Cross-pattern analysis: find byte positions that correlate with voice changes
    # Compare voices per track_idx cross patterns → identify byte indices that change
    print("═══ Byte positions correlating with track voice change ═══\n")

    # For each track_idx, check if any byte position in header has value
    # that maps to prog/msb/lsb for that track across 3 patterns
    for trk_idx in range(8):
        voices_trk = {pat: VOICES[pat][trk_idx] for pat in VOICES}
        msbs = {v[0] for v in voices_trk.values()}
        progs = {v[2] for v in voices_trk.values()}
        vols = {v[3] for v in voices_trk.values()}

        if len(progs) < 2 and len(msbs) < 2 and len(vols) < 2:
            continue  # all same, nothing to correlate

        print(f"\n─── Track {trk_idx+1}: voices={voices_trk}")

        # For each byte position, see if it correlates
        min_hdr_len = min(len(h) for h in hdrs.values())
        matches_prog = []
        matches_vol = []
        matches_msb = []
        for pos in range(min_hdr_len):
            vals = {pat: hdrs[pat][pos] for pat in hdrs}
            # Check if this byte == prog for each pattern
            if all(vals[p] == voices_trk[p][2] for p in vals):
                matches_prog.append(pos)
            if all(vals[p] == voices_trk[p][3] for p in vals):
                matches_vol.append(pos)
            if all(vals[p] == voices_trk[p][0] for p in vals):
                matches_msb.append(pos)

        if matches_prog:
            print(f"    MATCH Prog at: {matches_prog[:20]}")
        if matches_vol:
            print(f"    MATCH Vol at: {matches_vol[:20]}")
        if matches_msb:
            print(f"    MATCH MSB at: {matches_msb[:20]}")


if __name__ == "__main__":
    main()
