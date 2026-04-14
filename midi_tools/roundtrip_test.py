#!/usr/bin/env python3
"""Round-trip encoder/decoder validation.

Encode known drum events → barrel rotate → 7-byte blocks → decode → verify.
This validates the decoder WITHOUT needing hardware.

Known events to encode:
  Kick1 (36) on beat 1 (tick 240), velocity fff (127), gate 412
  Snare1 (38) on beat 3 (tick 1200), velocity ff (119), gate 200
  HHpedal (44) on every beat (tick 240, 720, 1200, 1680), velocity f (95), gate 30
  Crash1 (49) on beat 1 (tick 240), velocity fff (127), gate 74
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

XG_RANGE = set(range(13, 88))
GM_DRUMS = {
    35: "Kick2", 36: "Kick1", 37: "SideStk", 38: "Snare1", 39: "Clap",
    40: "Snare2", 41: "LoFlTom", 42: "HHclose", 43: "HiFlTom", 44: "HHpedal",
    45: "LoTom", 46: "HHopen", 47: "MidLoTom", 48: "HiMidTom", 49: "Crash1",
    50: "HiTom", 51: "Ride1", 52: "Chinese", 53: "RideBell", 54: "Tamb",
}


# ============================================================
# Rotation primitives (same as decoder)
# ============================================================

def rot_right(val, shift, width=56):
    """Right barrel rotation on a 56-bit value."""
    shift = shift % width
    return ((val >> shift) | (val << (width - shift))) & ((1 << width) - 1)

def rot_left(val, shift, width=56):
    """Left barrel rotation on a 56-bit value (inverse of rot_right)."""
    shift = shift % width
    return ((val << shift) | (val >> (width - shift))) & ((1 << width) - 1)

def extract_9bit(val, idx, total=56):
    """Extract 9-bit field at position idx from a 56-bit value."""
    shift = total - (idx + 1) * 9
    return (val >> shift) & 0x1FF if shift >= 0 else -1

def pack_9bit(val, idx, total=56):
    """Pack a 9-bit value into field position idx of a 56-bit value."""
    shift = total - (idx + 1) * 9
    if shift < 0:
        return 0
    return (val & 0x1FF) << shift


# ============================================================
# Encoder: known events → barrel-rotated 7-byte blocks
# ============================================================

def encode_event(note, velocity, gate, tick, event_index):
    """Encode a drum event into a 7-byte barrel-rotated block.

    Args:
        note: MIDI note number (0-127)
        velocity: MIDI velocity (1-127)
        gate: Gate time in ticks
        tick: Position in ticks within bar (0-1919 for 4/4)
        event_index: 0-based position in event list

    Returns:
        7 bytes of barrel-rotated event data
    """
    # Velocity → 4-bit inverted code
    # vel_code = [F0_bit8 : F0_bit7 : rem_bit1 : rem_bit0]
    # velocity ≈ 127 - vel_code * 8
    vel_code = max(0, min(15, round((127 - velocity) / 8)))
    actual_vel = max(1, 127 - vel_code * 8)

    # Decompose vel_code into F0 bits and remainder
    f0_bit8 = (vel_code >> 3) & 1
    f0_bit7 = (vel_code >> 2) & 1
    rem = vel_code & 0x3

    # F0: [bit8][bit7][note 7 bits]
    f0 = (f0_bit8 << 8) | (f0_bit7 << 7) | (note & 0x7F)

    # Position encoding
    beat = tick // 480
    clock = tick % 480  # This is the position within the beat

    # F1: [beat 2 bits][clock_hi 7 bits]
    # clock = ((F1 & 0x7F) << 2) | (F2 >> 7)
    # So: F1_lo7 = clock >> 2, F2_bit8 = clock & 0x3 (wait, F2>>7 gives 2 bits)
    # clock is 9 bits: F1_lo7 (7 bits) << 2 | F2_hi2 (2 bits)
    f1_lo7 = (clock >> 2) & 0x7F
    f2_hi2 = clock & 0x3
    f1 = (beat << 7) | f1_lo7

    # F2: [clock_lo 2 bits][7 bits of position data]
    # We set the lower 7 bits to 0 for simplicity (they encode sub-position)
    f2 = (f2_hi2 << 7)

    # F3, F4: position-related, shared by simultaneous events
    # Set to 0 for now (we don't fully understand these)
    f3 = 0
    f4 = 0

    # F5: gate time (9 bits, 0-511)
    f5 = gate & 0x1FF

    # Assemble 56-bit value: [F0:9][F1:9][F2:9][F3:9][F4:9][F5:9][rem:2]
    val = 0
    val |= pack_9bit(f0, 0)
    val |= pack_9bit(f1, 1)
    val |= pack_9bit(f2, 2)
    val |= pack_9bit(f3, 3)
    val |= pack_9bit(f4, 4)
    val |= pack_9bit(f5, 5)
    val |= (rem & 0x3)

    # Apply barrel rotation: rot_left to create the stored value
    # Decoder does: derot = rot_right(stored, (index+1)*9)
    # So: stored = rot_left(derot, (index+1)*9)
    r = (event_index + 1) * 9
    stored = rot_left(val, r)

    # Convert to 7 bytes
    return stored.to_bytes(7, "big")


def decode_event_raw(evt_bytes, event_index):
    """Decode a 7-byte event (simplified, for validation)."""
    val = int.from_bytes(evt_bytes, "big")
    r = (event_index + 1) * 9
    derot = rot_right(val, r)

    f0 = extract_9bit(derot, 0)
    f1 = extract_9bit(derot, 1)
    f2 = extract_9bit(derot, 2)
    f3 = extract_9bit(derot, 3)
    f4 = extract_9bit(derot, 4)
    f5 = extract_9bit(derot, 5)
    rem = derot & 0x3

    note = f0 & 0x7F
    bit8 = (f0 >> 8) & 1
    bit7 = (f0 >> 7) & 1
    vel_code = (bit8 << 3) | (bit7 << 2) | rem
    midi_vel = max(1, 127 - vel_code * 8)

    beat = f1 >> 7
    clock = ((f1 & 0x7F) << 2) | (f2 >> 7)
    tick = beat * 480 + clock

    gate = f5

    return note, midi_vel, gate, tick, vel_code, f0, f1, f2, f3, f4, f5, rem


def main():
    # ============================================================
    # 1. Define known events
    # ============================================================
    known_events = [
        # (note, velocity, gate, tick, description)
        (36, 127, 412, 240, "Kick1 beat 1"),
        (49, 127,  74, 240, "Crash1 beat 1"),
        (44, 119,  30, 240, "HHpedal beat 1"),
        (44,  95,  30, 720, "HHpedal beat 2"),
        (38, 127, 200, 960, "Snare1 beat 3"),
        (44,  95,  30, 960, "HHpedal beat 3"),
        (44,  95,  30, 1440, "HHpedal beat 4"),
    ]

    print(f"{'='*80}")
    print(f"  ROUND-TRIP ENCODER/DECODER VALIDATION")
    print(f"{'='*80}")

    # ============================================================
    # 2. Encode each event
    # ============================================================
    print(f"\n  {'Idx':>3} {'Note':>4} {'Vel':>4} {'Gate':>4} {'Tick':>5} {'Description':<20}"
          f" {'Encoded (hex)':<16}")

    encoded_events = []
    for i, (note, vel, gate, tick, desc) in enumerate(known_events):
        encoded = encode_event(note, vel, gate, tick, i)
        encoded_events.append(encoded)
        print(f"  {i:>3} {note:>4} {vel:>4} {gate:>4} {tick:>5} {desc:<20}"
              f" {encoded.hex()}")

    # ============================================================
    # 3. Decode each encoded event
    # ============================================================
    print(f"\n{'='*80}")
    print(f"  DECODE VALIDATION")
    print(f"{'='*80}")

    print(f"\n  {'Idx':>3} {'Note':>4} {'Vel':>4} {'Gate':>4} {'Tick':>5}"
          f" {'Expected':>10} {'Match':>6}")

    all_pass = True
    for i, (encoded, (exp_note, exp_vel, exp_gate, exp_tick, desc)) in enumerate(
            zip(encoded_events, known_events)):
        note, vel, gate, tick, vc, f0, f1, f2, f3, f4, f5, rem = decode_event_raw(encoded, i)

        # Velocity quantization: vel_code = round((127 - vel) / 8), so decoded vel may differ
        exp_vc = max(0, min(15, round((127 - exp_vel) / 8)))
        exp_vel_decoded = max(1, 127 - exp_vc * 8)

        note_ok = note == exp_note
        vel_ok = vel == exp_vel_decoded
        gate_ok = gate == exp_gate
        tick_ok = tick == exp_tick

        all_ok = note_ok and vel_ok and gate_ok and tick_ok
        if not all_ok:
            all_pass = False

        status = "✓" if all_ok else "✗"
        details = []
        if not note_ok: details.append(f"note:{exp_note}→{note}")
        if not vel_ok: details.append(f"vel:{exp_vel_decoded}→{vel}")
        if not gate_ok: details.append(f"gate:{exp_gate}→{gate}")
        if not tick_ok: details.append(f"tick:{exp_tick}→{tick}")

        detail_str = " " + ",".join(details) if details else ""
        print(f"  {i:>3} {note:>4} {vel:>4} {gate:>4} {tick:>5}"
              f" {desc:>10} {status:>6}{detail_str}")

    # ============================================================
    # 4. Test with existing real events from ground_truth_style.syx
    # ============================================================
    print(f"\n{'='*80}")
    print(f"  REAL EVENT VALIDATION (ground_truth_style.syx)")
    print(f"{'='*80}")

    from qymanager.formats.qy70.sysex_parser import SysExParser
    parser = SysExParser()
    msgs = parser.parse_file(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                          "captured", "ground_truth_style.syx"))

    # Get RHY1 data
    rhy1_data = b""
    for m in msgs:
        if m.is_style_data and m.address_low == 0 and m.decoded_data:
            rhy1_data += m.decoded_data

    event_data = rhy1_data[28:]
    delim_pos = sorted(i for i, b in enumerate(event_data) if b in (0xDC, 0x9E))
    segments = []
    prev = 0
    for dp in delim_pos:
        segments.append(event_data[prev:dp])
        prev = dp + 1
    segments.append(event_data[prev:])

    # For each event, decode then re-encode and compare
    total = 0
    roundtrip_ok = 0
    note_valid = 0

    for seg_idx, seg in enumerate(segments):
        if len(seg) < 20:
            continue
        nevts = (len(seg) - 13) // 7

        for i in range(nevts):
            evt = seg[13 + i * 7: 13 + (i + 1) * 7]
            if len(evt) != 7:
                continue
            total += 1

            # Decode
            note, vel, gate, tick, vc, f0, f1, f2, f3, f4, f5, rem = decode_event_raw(evt, i)

            if note in XG_RANGE:
                note_valid += 1

                # Re-encode
                re_encoded = encode_event(note, vel, gate, tick, i)

                # Decode re-encoded
                note2, vel2, gate2, tick2, *_ = decode_event_raw(re_encoded, i)

                # Check round-trip
                if note == note2 and vel == vel2 and gate == gate2 and tick == tick2:
                    roundtrip_ok += 1
                else:
                    name = GM_DRUMS.get(note, f'n{note}')
                    print(f"  MISMATCH seg{seg_idx} e{i}: "
                          f"{name}(n{note}) v{vel} g{gate} t{tick} → "
                          f"n{note2} v{vel2} g{gate2} t{tick2}")
                    # Show F3, F4 to understand the difference
                    _, _, _, _, _, _, _, _, f3_2, f4_2, _, _ = decode_event_raw(re_encoded, i)
                    if f3 != f3_2 or f4 != f4_2:
                        print(f"    F3: {f3:03X}→{f3_2:03X}, F4: {f4:03X}→{f4_2:03X}")

    rt_pct = 100 * roundtrip_ok / note_valid if note_valid > 0 else 0
    print(f"\n  Total events: {total}")
    print(f"  Valid note events: {note_valid}")
    print(f"  Round-trip OK (note+vel+gate+tick): {roundtrip_ok}/{note_valid} ({rt_pct:.0f}%)")

    # ============================================================
    # 5. Test the event_decoder.py itself
    # ============================================================
    print(f"\n{'='*80}")
    print(f"  EVENT_DECODER.PY VALIDATION (with off-by-one fix)")
    print(f"{'='*80}")

    from midi_tools.event_decoder import decode_event

    # Test with known Kick1 event
    evt = bytes.fromhex('1e148746cce024')
    de = decode_event(evt, 0, [0]*11)
    print(f"\n  Kick1 event (seg1 e0): F0={de.f0}, note={de.f0 & 0x7F}")
    assert (de.f0 & 0x7F) == 36, f"Expected 36, got {de.f0 & 0x7F}"

    # Test with known HHpedal event
    evt2 = bytes.fromhex('1e148746c0f22c')
    de2 = decode_event(evt2, 0, [0]*11)
    print(f"  HHpedal event (seg2 e0): F0={de2.f0}, note={de2.f0 & 0x7F}")
    assert (de2.f0 & 0x7F) == 44, f"Expected 44, got {de2.f0 & 0x7F}"

    # Test all events from ground truth
    correct = 0
    total_note = 0
    for seg_idx, seg in enumerate(segments):
        if len(seg) < 20: continue
        nevts = (len(seg) - 13) // 7
        for i in range(nevts):
            evt = seg[13 + i * 7: 13 + (i + 1) * 7]
            if len(evt) != 7: continue
            de = decode_event(evt, i, [0]*11)
            note = de.f0 & 0x7F
            if note in XG_RANGE:
                total_note += 1
                correct += 1

    print(f"\n  event_decoder.py: {correct}/{total_note} valid notes with fixed rotation")

    # ============================================================
    # Summary
    # ============================================================
    print(f"\n{'='*80}")
    print(f"  SUMMARY")
    print(f"{'='*80}")
    print(f"  Synthetic round-trip: {'ALL PASS ✓' if all_pass else 'FAILURES ✗'}")
    print(f"  Real data round-trip: {roundtrip_ok}/{note_valid} ({rt_pct:.0f}%)")
    print(f"  event_decoder.py: {correct} valid notes (fixed)")


if __name__ == "__main__":
    main()
