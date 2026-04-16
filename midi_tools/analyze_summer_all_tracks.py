#!/usr/bin/env python3
"""
Validate ALL Summer track decoders against ground truth capture.

Tracks in Summer .syx: RHY1(0), CHD1(3), CHD2(4), PAD(5), PHR1(6)
GT channels: ch9=RHY1, ch12=BASS, ch13=CHD1, ch15=PHR1

Focus on CHD1 (ch13) and PHR1 (ch15) which use chord/general encoding.
"""

import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qymanager.formats.qy70.sysex_parser import SysExParser
from midi_tools.event_decoder import (
    extract_bars, classify_encoding, decode_event, decode_drum_event,
    decode_header_notes, header_to_midi_notes, nn,
    rot_right, extract_9bit,
    ENCODING_CHORD, ENCODING_GENERAL, ENCODING_BASS_SLOT, ENCODING_DRUM_PRIMARY,
)


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


def load_gt_by_channel(json_path, bpm=120.0):
    """Load GT organized by MIDI channel."""
    with open(json_path) as f:
        capture = json.load(f)

    channels = {}
    for evt in capture["events"]:
        d = evt["data"]
        if len(d) == 3:
            ch = (d[0] & 0x0F) + 1  # 1-indexed
            msg = d[0] & 0xF0
            if msg == 0x90 and d[2] > 0:
                channels.setdefault(ch, []).append({
                    "t": evt["t"], "note": d[1], "vel": d[2]
                })
    return channels


def organize_by_bar(notes, bpm=120.0):
    if not notes:
        return {}
    bar_dur = 60.0 / bpm * 4
    t0 = notes[0]["t"]
    bars = {}
    for n in notes:
        dt = n["t"] - t0
        bar_idx = int(dt / bar_dur)
        tick = (dt - bar_idx * bar_dur) / (60.0 / bpm) * 480
        bars.setdefault(bar_idx, []).append({
            "note": n["note"], "vel": n["vel"], "tick": tick
        })
    return bars


def main():
    syx_path = "data/qy70_sysx/P -  Summer - 20231101.syx"
    gt_path = "midi_tools/captured/summer_playback_s25.json"

    gt_channels = load_gt_by_channel(gt_path)
    print("GT channels:")
    for ch, notes in sorted(gt_channels.items()):
        unique_notes = sorted(set(n["note"] for n in notes))
        print(f"  ch{ch}: {len(notes)} notes, unique: {[f'{nn(n)}({n})' for n in unique_notes]}")

    # Track mapping: SysEx track → MIDI channel
    track_map = {
        0: {"name": "RHY1", "ch": 9, "encoding": "drum"},
        3: {"name": "CHD1", "ch": 13, "encoding": "chord/general"},
        4: {"name": "CHD2", "ch": 14, "encoding": "chord"},
        5: {"name": "PAD",  "ch": 11, "encoding": "general"},
        6: {"name": "PHR1", "ch": 15, "encoding": "chord"},
    }

    for track_idx, info in track_map.items():
        print(f"\n{'='*70}")
        print(f"TRACK {info['name']} (idx={track_idx}, expected ch{info['ch']})")
        print(f"{'='*70}")

        data = load_syx_track(syx_path, section=0, track=track_idx)
        if not data:
            print("  No data!")
            continue

        print(f"  Decoded bytes: {len(data)}")
        preamble, bars = extract_bars(data)
        enc = classify_encoding(preamble)
        print(f"  Preamble: {preamble.hex()}, Encoding: {enc}")
        print(f"  Bars: {len(bars)}")

        # GT data for this channel
        gt_notes = gt_channels.get(info["ch"], [])
        gt_bars = organize_by_bar(gt_notes)
        print(f"  GT: {len(gt_notes)} notes in {len(gt_bars)} bars")

        if gt_notes:
            unique_gt = sorted(set(n["note"] for n in gt_notes))
            print(f"  GT unique notes: {[f'{nn(n)}({n})' for n in unique_gt]}")

        # Decode each bar
        for bar_idx, (header, events) in enumerate(bars):
            hfields = decode_header_notes(header)
            chord_notes = header_to_midi_notes(hfields)

            print(f"\n  Bar {bar_idx}: {len(events)} events, "
                  f"header chord notes: {[f'{nn(n)}({n})' for n in chord_notes]}")

            for evt_idx, evt in enumerate(events[:6]):
                if enc == ENCODING_CHORD:
                    # Chord decoding
                    decoded = decode_event(evt, evt_idx, hfields)
                    if decoded:
                        sel = decoded.selected_notes
                        print(f"    e{evt_idx}: beat={decoded.beat_number} "
                              f"F4_mask={decoded.f4_mask5:05b} "
                              f"notes={[f'{nn(n)}' for n in sel]} "
                              f"F5={decoded.f5}")
                    else:
                        print(f"    e{evt_idx}: decode failed")
                elif enc == ENCODING_DRUM_PRIMARY:
                    # Drum decoding with lane R
                    LANE_R = [9, 22, 12, 53]
                    r = LANE_R[evt_idx] if evt_idx < 4 else 9
                    val = int.from_bytes(evt, "big")
                    derot = rot_right(val, r)
                    f0 = extract_9bit(derot, 0)
                    note = f0 & 0x7F
                    if 13 <= note <= 87:
                        rem = derot & 0x3
                        vel_code = ((f0>>8)&1)<<3 | ((f0>>7)&1)<<2 | rem
                        velocity = max(1, 127 - vel_code*8)
                        print(f"    e{evt_idx} R={r}: {nn(note)}({note}) "
                              f"vel={velocity}")
                    else:
                        # Try cumulative
                        r2 = (9 * (evt_idx+1)) % 56
                        d = decode_drum_event(evt, evt_idx)
                        if d and d["type"] == "note":
                            print(f"    e{evt_idx} R={r2}(cum): {nn(d['note'])}({d['note']}) "
                                  f"vel={d['velocity']}")
                        else:
                            print(f"    e{evt_idx}: no valid decode")
                else:
                    # General encoding - try R=47 and cumulative
                    d = decode_drum_event(evt, evt_idx)
                    if d and d["type"] == "note":
                        print(f"    e{evt_idx}: {nn(d['note'])}({d['note']}) "
                              f"vel={d['velocity']} tick={d['tick']}")
                    elif d and d["type"] == "control":
                        print(f"    e{evt_idx}: CONTROL F0={d['f0']}")
                    else:
                        print(f"    e{evt_idx}: no valid decode")

        # GT bar-level comparison
        if gt_bars:
            print(f"\n  GT bar comparison:")
            for bi in sorted(gt_bars.keys())[:4]:
                notes = sorted(gt_bars[bi], key=lambda x: x["tick"])
                summary = [f"{nn(n['note'])}({n['note']}) v={n['vel']}" for n in notes[:8]]
                print(f"    GT bar {bi}: {', '.join(summary)}")
                if len(notes) > 8:
                    print(f"      + {len(notes)-8} more")

    print("\nDone.")


if __name__ == "__main__":
    main()
