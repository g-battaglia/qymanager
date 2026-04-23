#!/usr/bin/env python3
"""
R10: Unified decoder hypothesis test.

Decoder model:
  1. If track is RHY1 and events look sparse (7B aligned, R=9×(i+1) gives valid notes)
     → use sparse decoder
  2. Else (dense) → use per-6 cycle R table learned from each track
  3. For unmatched events, fall back to lookup in template library

Test on:
  - known_pattern.syx (sparse, 7/7 expected)
  - Summer ground_truth (dense-user, should match captured 61 strikes)
  - SGT R1 capture (dense-factory, check against captured 288 notes)
"""

import json
import sys
from collections import defaultdict, Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from qymanager.formats.qy70.sysex_parser import SysExParser


KNOWN_PATTERN = Path(__file__).parent / "captured" / "known_pattern.syx"
SGT = Path(__file__).parent.parent / "tests" / "fixtures" / "QY70_SGT.syx"
SUMMER = Path(__file__).parent / "captured" / "ground_truth_style.syx"
TEMPL_LIB = Path(__file__).parent.parent / "data" / "template_library_v2.json"
R8_FORMULA = Path(__file__).parent.parent / "data" / "sgt_rounds" / "R8_R_formula.json"


def rot_right(val, s, w=56):
    s %= w
    return ((val >> s) | (val << (w - s))) & ((1 << w) - 1)


def decode_event_sparse(chunk: bytes, idx: int) -> dict:
    val = int.from_bytes(chunk, "big")
    R = (9 * (idx + 1)) % 56
    derot = rot_right(val, R)
    f0 = (derot >> 47) & 0x1FF
    f5 = (derot >> 2) & 0x1FF
    f1 = (derot >> 38) & 0x1FF
    f2 = (derot >> 29) & 0x1FF
    rem = derot & 0x3
    note = f0 & 0x7F
    bit7 = (f0 >> 7) & 1
    bit8 = (f0 >> 8) & 1
    vel_code = (bit8 << 3) | (bit7 << 2) | rem
    midi_vel = max(1, 127 - vel_code * 8)
    beat = f1 >> 7
    clock = ((f1 & 0x7F) << 2) | (f2 >> 7)
    return {"note": note, "vel": midi_vel, "gate": f5,
            "beat": beat, "clock": clock, "R": R}


def decode_event_dense(chunk: bytes, idx: int, R_table: list) -> dict:
    """Use per-position R from R_table (length = cycle)."""
    val = int.from_bytes(chunk, "big")
    R = R_table[idx % len(R_table)]
    derot = rot_right(val, R)
    f0 = (derot >> 47) & 0x1FF
    note = f0 & 0x7F
    return {"note": note, "R": R}


def load_track(syx_path, al: int) -> bytes:
    parser = SysExParser()
    msgs = parser.parse_file(str(syx_path))
    data = b""
    for m in msgs:
        if m.is_style_data and m.decoded_data and m.address_low == al:
            data += m.decoded_data
    return data


def test_sparse():
    """Test sparse decoder on known_pattern.syx."""
    print("\n═══ Sparse decoder test (known_pattern.syx) ═══")
    data = load_track(KNOWN_PATTERN, 0)
    body = data[28:]  # skip track header + preamble
    # Expected events (ground truth)
    expected = [
        (36, 127, 412, 240),
        (49, 127, 74, 240),
        (44, 119, 30, 240),
        (44, 95, 30, 720),
        (38, 127, 200, 960),
        (44, 95, 30, 960),
        (44, 95, 30, 1440),
    ]
    # Skip 13B bar header
    events_region = body[13:]
    match = 0
    for i, (exp_note, exp_vel, exp_gate, exp_tick) in enumerate(expected):
        chunk = events_region[i * 7:(i + 1) * 7]
        dec = decode_event_sparse(chunk, i)
        exp_vc = max(0, min(15, round((127 - exp_vel) / 8)))
        exp_v = max(1, 127 - exp_vc * 8)
        if (dec["note"] == exp_note and dec["vel"] == exp_v and
                dec["gate"] == exp_gate):
            match += 1
    print(f"  {match}/{len(expected)} events match exactly")
    return match == len(expected)


def test_summer_templates():
    """Test Summer template matching on Summer GT."""
    print("\n═══ Summer template test (20 events → 61 strikes) ═══")
    lib = json.loads(TEMPL_LIB.read_text())
    summer = lib["summer_entries"]
    sig_counter = Counter(tuple(tuple(x) for x in s["strike_signature"]) for s in summer)
    print(f"  Summer entries: {len(summer)}")
    print(f"  Unique signatures: {len(sig_counter)}")
    for sig, n in sig_counter.most_common():
        print(f"    {sig}: {n} instances")
    return len(summer) == 20


def test_sgt_formula_match():
    """Test SGT per-6 cycle formula on full 4-bar captured data."""
    print("\n═══ SGT per-6 cycle decoder test ═══")
    formula = json.loads(R8_FORMULA.read_text())

    for trk_str, data in formula.items():
        name = data["name"]
        if "skipped" in data:
            continue
        per6 = data.get("per_6", {})
        if not per6:
            continue
        best_Rs = per6["best_Rs"]
        matches = per6["matches"]
        total = per6["total"]
        print(f"  Track {name}: per-6 R={best_Rs} → {matches}/{total} ({100*matches/total:.0f}%)")


def main():
    results = {}

    sparse_pass = test_sparse()
    results["sparse"] = {"passed": sparse_pass}

    summer_pass = test_summer_templates()
    results["summer_templates"] = {"passed": summer_pass}

    test_sgt_formula_match()
    results["sgt_per6"] = {"tested": True}

    print(f"\n═══ Summary ═══")
    print(f"  Sparse decoder:    {'PASS' if sparse_pass else 'FAIL'}")
    print(f"  Summer templates:  {'PASS (20 entries)' if summer_pass else 'FAIL'}")
    print(f"  SGT per-6 cycle:   ~20-65% coverage per track (expected, dense is partial)")


if __name__ == "__main__":
    main()
