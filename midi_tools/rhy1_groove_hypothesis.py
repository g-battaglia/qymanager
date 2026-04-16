#!/usr/bin/env python3
"""
Test GROOVE TEMPLATE hypothesis on RHY1.

Hypothesis: the bitstream encodes coarse velocity (vel_code × 8) + instrument
patterns + position. Fine velocity variation is applied by a runtime groove
template. Thus:

    - Bytes correlate with COARSE velocity (multiples of 8 near actual)
    - Actual velocities ≈ 127 - (vel_code × 8) ± groove_perturbation

Test:
    1. Extract bytes 1-3 and check if they "quantize" to vel_code × 8 ≈ actual
    2. Look for a 4-bit vel_code at fixed positions in the 7-byte event
    3. If found, the residual (actual - quantized) should be a small ±delta
       consistent with a template
"""

import json


def bytes_to_bits(b):
    return int.from_bytes(b, "big")


def extract_nbits(bits, offset, width, total=56):
    return (bits >> (total - offset - width)) & ((1 << width) - 1)


def main():
    with open("midi_tools/captured/summer_ground_truth_full.json") as f:
        gt = json.load(f)
    events = gt["tracks"]["RHY1"]["events"]

    # Build (event_bytes, [vels], [notes]) list
    samples = []
    for e in events:
        bits = bytes_to_bits(bytes(e["event_decimal"]))
        strikes = sorted(e["expected_strikes"],
                         key=lambda x: (x["subdivision_8th"], x["note"]))
        samples.append((e, bits, strikes))

    # Search: for each (offset, width, vel_idx), check if
    # MIDI_vel ≈ 127 - (extracted * k) where k ∈ {1, 2, 4, 8, 16}
    # with tolerance ±15

    print("=" * 72)
    print("COARSE VELOCITY QUANTIZATION: search for a 4-bit vel_code field")
    print("=" * 72)

    TOLERANCE = 15
    MULTIPLIERS = [8, 4, 2, 1, 16]

    for width in [3, 4, 5]:
        for vel_idx in range(3):
            # Only use samples where vel_idx exists
            relevant = [(e, b, s) for e, b, s in samples if vel_idx < len(s)]
            if not relevant:
                continue
            actual_vels = [s[vel_idx]["velocity"] for _, _, s in relevant]

            best = []
            for offset in range(56 - width + 1):
                for k in MULTIPLIERS:
                    # Test: actual ≈ 127 - (extracted * k)
                    matches = 0
                    for _, bits, strikes in relevant:
                        val = extract_nbits(bits, offset, width)
                        predicted = 127 - (val * k)
                        actual = strikes[vel_idx]["velocity"]
                        if abs(predicted - actual) <= TOLERANCE:
                            matches += 1
                    if matches >= len(relevant) * 0.8:  # 80% match
                        best.append((offset, k, matches, len(relevant)))

                    # Test: actual ≈ extracted * k
                    matches = 0
                    for _, bits, strikes in relevant:
                        val = extract_nbits(bits, offset, width)
                        predicted = val * k
                        actual = strikes[vel_idx]["velocity"]
                        if abs(predicted - actual) <= TOLERANCE:
                            matches += 1
                    if matches >= len(relevant) * 0.8:
                        best.append((offset, -k, matches, len(relevant)))

            if best:
                best.sort(key=lambda x: -x[2])
                print(f"\nWidth={width} vel[{vel_idx}]:")
                for offset, k, m, t in best[:5]:
                    formula = f"127 - val*{k}" if k > 0 else f"val*{-k}"
                    print(f"  offset={offset:2d} k={k:+d} ({formula}): "
                          f"{m}/{t} matches within ±{TOLERANCE}")

    print()
    print("=" * 72)
    print("INSTRUMENT LANE MODEL: each event = pattern for ONE instrument")
    print("=" * 72)
    print("Wiki model: e0=HH, e1=Snare, e2=HH, e3=Kick-pattern")
    print("Testing whether each event's notes match this lane model...")
    print()

    for e, bits, strikes in samples:
        beat = e["beat"]
        notes = sorted(set(s["note"] for s in strikes))
        drum_names = []
        for n in notes:
            drum_names.append({36: "K", 38: "S", 42: "H"}.get(n, f"N{n}"))
        print(f"  bar{e['bar']} beat{beat} ({len(strikes)} strikes): "
              f"notes={notes} ({'+'.join(drum_names)})")

    # Check if notes for a given beat are consistent across bars
    print()
    print("--- Notes per beat across bars ---")
    beat_notes = {}
    for e, bits, strikes in samples:
        beat = e["beat"]
        notes = tuple(sorted(set(s["note"] for s in strikes)))
        beat_notes.setdefault(beat, []).append((e["bar"], notes, e["event_hex"]))

    for beat in sorted(beat_notes):
        print(f"\nBeat {beat}:")
        for bar, notes, hx in beat_notes[beat]:
            print(f"   bar{bar}: notes={notes}, bytes={hx}")


if __name__ == "__main__":
    main()
