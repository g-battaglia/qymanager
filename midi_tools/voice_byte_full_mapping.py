#!/usr/bin/env python3
"""
Voice byte → Bank/Prog mapping analysis using 24 data points.

For each (pattern, track), we have:
  - Pattern bytes B14-B23 (10 voice header bytes)
  - Voice captured (Bank MSB/LSB/Program/Vol/Pan/Rev/Chor)

Look for:
  - Direct byte→param correlations
  - XOR/sum patterns
  - LUT lookups
"""

import json
from pathlib import Path
from collections import defaultdict
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from qymanager.formats.qy70.sysex_parser import SysExParser

CAPTURES = Path("data/captures_2026_04_23")


# Voice captured from recordings (user data 2026-04-23)
VOICE_DATA = {
    "SGT": {
        # ch9=RHY1, ch10=RHY2, ... ch16=PHR2
        9:  {"msb": 127, "lsb": 0,  "prog": 26, "vol": 75, "pan": 64, "rev": 0,  "chor": 0},
        10: {"msb": 127, "lsb": 0,  "prog": 26, "vol": 60, "pan": 64, "rev": 40, "chor": 0},
        11: {"msb": 127, "lsb": 0,  "prog": 26, "vol": 63, "pan": 64, "rev": 60, "chor": 0},
        12: {"msb": 0,   "lsb": 96, "prog": 38, "vol": 95, "pan": 64, "rev": 0,  "chor": 0},
        13: {"msb": 0,   "lsb": 0,  "prog": 81, "vol": 60, "pan": 64, "rev": 70, "chor": 55},
        14: {"msb": 0,   "lsb": 16, "prog": 89, "vol": 95, "pan": 64, "rev": 40, "chor": 0},
        15: {"msb": 0,   "lsb": 0,  "prog": 24, "vol": 50, "pan": 64, "rev": 40, "chor": 0},
        16: {"msb": 0,   "lsb": 35, "prog": 98, "vol": 45, "pan": 64, "rev": 0,  "chor": 0},
    },
    "AMB01": {
        9:  {"msb": 127, "lsb": 0,  "prog": 25, "vol": 90, "pan": 64, "rev": 40, "chor": 0},
        10: {"msb": 127, "lsb": 0,  "prog": 26, "vol": 60, "pan": 64, "rev": 40, "chor": 0},
        11: {"msb": 127, "lsb": 0,  "prog": 26, "vol": 50, "pan": 64, "rev": 40, "chor": 0},
        12: {"msb": 0,   "lsb": 0,  "prog": 34, "vol": 75, "pan": 64, "rev": 40, "chor": 0},
        13: {"msb": 0,   "lsb": 0,  "prog": 89, "vol": 90, "pan": 64, "rev": 97, "chor": 127},
        14: {"msb": 0,   "lsb": 0,  "prog": 89, "vol": 90, "pan": 64, "rev": 97, "chor": 127},
        15: {"msb": 0,   "lsb": 40, "prog": 44, "vol": 92, "pan": 64, "rev": 40, "chor": 0},
        16: {"msb": 126, "lsb": 0,  "prog": 0,  "vol": 80, "pan": 64, "rev": 40, "chor": 0},
    },
}

PATTERN_BULK = {
    "SGT": CAPTURES / "SGT_backup_20260423_112505.syx",
    "AMB01": CAPTURES / "AMB01_bulk_20260423_113016.syx",
}

TRACK_CH = {0:9, 1:10, 2:11, 3:12, 4:13, 5:14, 6:15, 7:16}
NAMES = {0:"RHY1",1:"RHY2",2:"PAD",3:"BASS",4:"CHD1",5:"CHD2",6:"PHR1",7:"PHR2"}


def extract_track_headers(syx_path: Path, section: int = 0) -> dict:
    """Return {track_idx: first 28 bytes of decoded data}."""
    parser = SysExParser()
    msgs = parser.parse_file(str(syx_path))
    headers = {}
    for m in msgs:
        if not (m.address_high == 0x02 and
                (m.address_mid <= 0x1F or m.address_mid == 0x7E) and m.decoded_data):
            continue
        if m.address_low == 0x7F or m.address_low > 0x2F:
            continue
        sec = m.address_low // 8
        trk = m.address_low % 8
        if sec == section and trk not in headers:
            headers[trk] = m.decoded_data[:28]
    return headers


def main():
    # For each pattern, collect headers + voice
    data_points = []
    for name, bulk_path in PATTERN_BULK.items():
        if not bulk_path.exists():
            continue
        voice = VOICE_DATA.get(name, {})
        headers = extract_track_headers(bulk_path, section=0)
        for trk in range(8):
            ch = TRACK_CH[trk]
            if ch in voice and trk in headers:
                hdr = headers[trk]
                data_points.append({
                    "pattern": name,
                    "track": NAMES[trk],
                    "ch": ch,
                    "bytes_14_23": hdr[14:24].hex(),
                    "voice": voice[ch],
                })

    print(f"═══ {len(data_points)} voice data points ═══\n")
    print(f"{'Pattern':<7} {'Track':<5} {'Ch':>3} {'Bytes[14-23]':<24} {'MSB':>4} {'LSB':>4} {'Prog':>5} {'Vol':>4} {'Rev':>4}")
    print("─" * 100)
    for dp in data_points:
        v = dp["voice"]
        print(f"{dp['pattern']:<7} {dp['track']:<5} {dp['ch']:>3} {dp['bytes_14_23']:<24} "
              f"{v['msb']:>4} {v['lsb']:>4} {v['prog']:>5} {v['vol']:>4} {v['rev']:>4}")

    # Analysis per byte position
    print("\n═══ Per-byte position — correlation attempt ═══\n")
    for byte_pos in range(10):  # B14-B23
        print(f"\n  Byte B{14+byte_pos}: values observed:")
        by_voice = defaultdict(list)
        for dp in data_points:
            raw = bytes.fromhex(dp["bytes_14_23"])
            v = dp["voice"]
            key = f"MSB={v['msb']} LSB={v['lsb']} P={v['prog']}"
            by_voice[key].append(raw[byte_pos])
        for k in sorted(by_voice.keys()):
            vals = by_voice[k]
            from collections import Counter
            cnt = Counter(vals)
            print(f"    {k:<25}: {dict(cnt)}")

    # Output JSON for further analysis
    out = CAPTURES / "voice_byte_data.json"
    out.write_text(json.dumps(data_points, indent=2))
    print(f"\nSaved: {out}")


if __name__ == "__main__":
    main()
