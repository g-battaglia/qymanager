#!/usr/bin/env python3
"""Analyze known_pattern.syx with exact ground truth.

known_pattern_spec.txt defines exactly 7 events:
  e0: Kick36  v127 g412 t240
  e1: Crash49 v127 g74  t240
  e2: HHpedal44 v119 g30 t240
  e3: HHpedal44 v95  g30 t720
  e4: Snare38 v127 g200 t960
  e5: HHpedal44 v95  g30  t960
  e6: HHpedal44 v95  g30  t1440

This is the definitive test for the rotation model.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qymanager.formats.qy70.sysex_parser import SysExParser
from midi_tools.event_decoder import rot_right, extract_9bit

GM_DRUMS = {
    36: 'Kick1', 38: 'Snare1', 44: 'HHpedal', 49: 'Crash1',
}

# Ground truth from known_pattern_spec.txt
GROUND_TRUTH = [
    {"note": 36, "velocity": 127, "gate": 412, "tick": 240, "name": "Kick1"},
    {"note": 49, "velocity": 127, "gate": 74,  "tick": 240, "name": "Crash1"},
    {"note": 44, "velocity": 119, "gate": 30,  "tick": 240, "name": "HHpedal"},
    {"note": 44, "velocity": 95,  "gate": 30,  "tick": 720, "name": "HHpedal"},
    {"note": 38, "velocity": 127, "gate": 200, "tick": 960, "name": "Snare1"},
    {"note": 44, "velocity": 95,  "gate": 30,  "tick": 960, "name": "HHpedal"},
    {"note": 44, "velocity": 95,  "gate": 30,  "tick": 1440, "name": "HHpedal"},
]


def get_track(syx_path, al_target):
    parser = SysExParser()
    messages = parser.parse_file(syx_path)
    data = b''
    for m in messages:
        if m.is_style_data and m.decoded_data and m.address_low == al_target:
            data += m.decoded_data
    return data


def get_segments(data):
    event_data = data[28:]
    delim_pos = [i for i, b in enumerate(event_data) if b in (0xDC, 0x9E)]
    segments = []
    prev = 0
    for dp in delim_pos:
        seg = event_data[prev:dp]
        if len(seg) >= 20:
            header = seg[:13]
            events = []
            for i in range((len(seg) - 13) // 7):
                evt = seg[13 + i*7:13 + (i+1)*7]
                if len(evt) == 7:
                    events.append(evt)
            segments.append((header, events))
        prev = dp + 1
    seg = event_data[prev:]
    if len(seg) >= 20:
        header = seg[:13]
        events = []
        for i in range((len(seg) - 13) // 7):
            evt = seg[13 + i*7:13 + (i+1)*7]
            if len(evt) == 7:
                events.append(evt)
        segments.append((header, events))
    return segments


def decode_at_r(evt_bytes, r_value):
    val = int.from_bytes(evt_bytes, "big")
    derot = rot_right(val, r_value)
    fields = [extract_9bit(derot, i) for i in range(6)]
    rem = derot & 0x3
    f0 = fields[0]
    note = f0 & 0x7F
    bit8 = (f0 >> 8) & 1
    bit7 = (f0 >> 7) & 1
    vel_code = (bit8 << 3) | (bit7 << 2) | rem
    velocity = max(1, 127 - vel_code * 8)
    f1 = fields[1]
    f2 = fields[2]
    beat = f1 >> 7
    clock = ((f1 & 0x7F) << 2) | (f2 >> 7)
    tick = beat * 480 + clock
    return {
        "note": note, "velocity": velocity, "tick": tick,
        "gate": fields[5], "fields": fields, "rem": rem, "f0": f0,
    }


def main():
    data = get_track("midi_tools/captured/known_pattern.syx", 0)
    if not data:
        print("known_pattern RHY1 not found — trying all AL values")
        parser = SysExParser()
        messages = parser.parse_file("midi_tools/captured/known_pattern.syx")
        for m in messages:
            if m.is_style_data and m.decoded_data:
                print(f"  AL={m.address_low:02X}: {len(m.decoded_data)} bytes")
        return

    print(f"Track data: {len(data)} bytes")
    print(f"Preamble area: {data[:28].hex()}")
    print(f"Preamble (24-27): {data[24:28].hex()}")

    segments = get_segments(data)
    print(f"Segments: {len(segments)}")

    # Collect ALL events across segments
    all_events = []
    for si, (header, events) in enumerate(segments):
        print(f"\n  Segment {si}: header={header.hex()}, {len(events)} events")
        for ei, evt in enumerate(events):
            all_events.append((si, ei, evt))
            print(f"    e{ei}: {evt.hex()}")

    print(f"\nTotal events: {len(all_events)}")
    print(f"Expected events: {len(GROUND_TRUTH)}")

    # For each event, find the R value that matches ground truth
    print(f"\n{'='*70}")
    print(f"  BRUTE FORCE: find R that matches ground truth per event")
    print(f"{'='*70}")

    for gi, gt in enumerate(GROUND_TRUTH):
        if gi >= len(all_events):
            print(f"\n  GT[{gi}]: {gt['name']} n={gt['note']} — NO EVENT!")
            continue

        si, ei, evt = all_events[gi]
        print(f"\n  GT[{gi}]: {gt['name']} n={gt['note']} v={gt['velocity']} "
              f"t={gt['tick']} g={gt['gate']}")
        print(f"    Raw: {evt.hex()} (seg{si} e{ei})")

        # Find ALL R values that give the correct note
        note_matches = []
        full_matches = []
        for r in range(56):
            d = decode_at_r(evt, r)
            if d["note"] == gt["note"]:
                note_ok = True
                vel_ok = d["velocity"] == gt["velocity"]
                tick_ok = d["tick"] == gt["tick"]
                gate_ok = d["gate"] == gt["gate"]

                if note_ok and vel_ok and tick_ok and gate_ok:
                    full_matches.append(r)
                elif note_ok and vel_ok:
                    note_matches.append((r, d["tick"], d["gate"], tick_ok, gate_ok))
                else:
                    note_matches.append((r, d["tick"], d["gate"], tick_ok, gate_ok))

        if full_matches:
            print(f"    FULL MATCH at R: {full_matches}")
        else:
            print(f"    No full match!")
        if note_matches:
            for r, tick, gate, tok, gok in note_matches[:8]:
                marks = f"{'t✓' if tok else f't={tick}'} {'g✓' if gok else f'g={gate}'}"
                print(f"    NOTE match R={r:2d}: {marks}")

    # Also check standard R models
    print(f"\n{'='*70}")
    print(f"  STANDARD MODELS vs GROUND TRUTH")
    print(f"{'='*70}")

    models = {
        "R=9 constant": lambda i: 9,
        "R=9*(i+1) cumulative": lambda i: 9 * (i + 1),
        "R=47 constant": lambda i: 47,
    }

    for model_name, r_func in models.items():
        print(f"\n  {model_name}:")
        note_ok = 0
        vel_ok = 0
        tick_ok = 0
        gate_ok = 0
        total = min(len(all_events), len(GROUND_TRUTH))

        for gi in range(total):
            gt = GROUND_TRUTH[gi]
            _, _, evt = all_events[gi]
            r = r_func(gi) % 56
            d = decode_at_r(evt, r)
            n = d["note"]
            v = d["velocity"]
            t = d["tick"]
            g = d["gate"]
            nname = GM_DRUMS.get(n, f"n{n}")
            nm = "✓" if n == gt["note"] else "✗"
            vm = "✓" if v == gt["velocity"] else "✗"
            tm = "✓" if t == gt["tick"] else "✗"
            gm = "✓" if g == gt["gate"] else "✗"
            print(f"    e{gi}: R={r:2d} → {nname:>10s} n={n:3d}{nm} v={v:3d}{vm} "
                  f"t={t:4d}{tm} g={g:3d}{gm}")
            if n == gt["note"]: note_ok += 1
            if v == gt["velocity"]: vel_ok += 1
            if t == gt["tick"]: tick_ok += 1
            if g == gt["gate"]: gate_ok += 1

        print(f"    Score: note={note_ok}/{total} vel={vel_ok}/{total} "
              f"tick={tick_ok}/{total} gate={gate_ok}/{total}")


if __name__ == "__main__":
    main()
