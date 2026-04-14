#!/usr/bin/env python3
"""Build a .syx file with KNOWN drum pattern content for ground truth validation.

Creates a minimal QY70 style with known events in the RHY1 track,
keeping everything else (header, other tracks) from the existing
ground_truth_style.syx as template.

Known pattern (1 bar, 4/4):
  Beat 1: Kick1(36) + HHpedal(44) + Crash1(49)
  Beat 2: HHpedal(44)
  Beat 3: Snare1(38) + HHpedal(44)
  Beat 4: HHpedal(44)
"""

import sys, os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from qymanager.utils.yamaha_7bit import encode_7bit, decode_7bit
from qymanager.utils.checksum import calculate_yamaha_checksum


# ============================================================
# Rotation primitives
# ============================================================

def rot_left(val, shift, width=56):
    shift = shift % width
    return ((val << shift) | (val >> (width - shift))) & ((1 << width) - 1)

def pack_9bit(val, idx, total=56):
    shift = total - (idx + 1) * 9
    if shift < 0: return 0
    return (val & 0x1FF) << shift


def encode_event(note, velocity, gate, tick, event_index):
    """Encode a drum event into 7 barrel-rotated bytes."""
    vel_code = max(0, min(15, round((127 - velocity) / 8)))
    f0_bit8 = (vel_code >> 3) & 1
    f0_bit7 = (vel_code >> 2) & 1
    rem = vel_code & 0x3
    f0 = (f0_bit8 << 8) | (f0_bit7 << 7) | (note & 0x7F)

    beat = tick // 480
    clock = tick % 480
    f1 = (beat << 7) | ((clock >> 2) & 0x7F)
    f2 = (clock & 0x3) << 7
    f3 = 0
    f4 = 0
    f5 = gate & 0x1FF

    val = 0
    val |= pack_9bit(f0, 0)
    val |= pack_9bit(f1, 1)
    val |= pack_9bit(f2, 2)
    val |= pack_9bit(f3, 3)
    val |= pack_9bit(f4, 4)
    val |= pack_9bit(f5, 5)
    val |= (rem & 0x3)

    stored = rot_left(val, (event_index + 1) * 9)
    return stored.to_bytes(7, "big")


def build_sysex_msg(device_num, ah, am, al, raw_data):
    """Build a complete Yamaha SysEx bulk dump message.

    Format: F0 43 0n 5F BH BL AH AM AL [7bit-data] CS F7
    Checksum covers BH BL AH AM AL + encoded payload.

    raw_data is padded to 128 bytes (QY70 requires fixed-size messages).
    BC = len(encoded) = 147 for 128 decoded bytes.
    """
    # Pad to 128 bytes — QY70 requires all bulk messages to be 158 bytes total
    padded = raw_data + bytes(128 - len(raw_data)) if len(raw_data) < 128 else raw_data[:128]
    encoded = encode_7bit(padded)
    bc = len(encoded)
    bh = (bc >> 7) & 0x7F
    bl = bc & 0x7F

    # Checksum region: BH BL AH AM AL + encoded_data
    cs_region = bytes([bh, bl, ah, am, al]) + encoded
    cs = calculate_yamaha_checksum(cs_region)

    msg = bytes([0xF0, 0x43, device_num, 0x5F,
                 bh, bl, ah, am, al]) + encoded + bytes([cs, 0xF7])
    return msg


def build_init_msg(device_num=0x10):
    return bytes([0xF0, 0x43, device_num, 0x5F, 0x00, 0x00, 0x00, 0x01, 0xF7])

def build_close_msg(device_num=0x10):
    return bytes([0xF0, 0x43, device_num, 0x5F, 0x00, 0x00, 0x00, 0x00, 0xF7])


def main():
    base = os.path.dirname(os.path.abspath(__file__))
    template_path = os.path.join(base, "captured", "ground_truth_style.syx")

    # ============================================================
    # 1. Load template .syx
    # ============================================================
    with open(template_path, 'rb') as f:
        template_raw = f.read()

    # Split into messages
    template_msgs = []
    start = None
    for i, b in enumerate(template_raw):
        if b == 0xF0: start = i
        elif b == 0xF7 and start is not None:
            template_msgs.append(template_raw[start:i+1])
            start = None

    print(f"Template: {len(template_msgs)} messages, {len(template_raw)} bytes")

    # ============================================================
    # 2. Extract template data per track
    # ============================================================
    track_raw_data = {}  # AL → decoded bytes
    for m in template_msgs:
        if len(m) < 10 or m[2] != 0x00:
            continue
        al = m[8]
        payload_7bit = bytes(m[9:-2])
        decoded = decode_7bit(payload_7bit)
        if al not in track_raw_data:
            track_raw_data[al] = b''
        track_raw_data[al] += decoded

    print(f"Tracks found: {[f'0x{al:02X}' for al in sorted(track_raw_data.keys())]}")
    for al, d in sorted(track_raw_data.items()):
        print(f"  AL=0x{al:02X}: {len(d)} bytes")

    # ============================================================
    # 3. Build known RHY1 track data
    # ============================================================
    # Keep the original 28-byte preamble
    original_rhy1 = track_raw_data[0x00]
    preamble = original_rhy1[:28]
    print(f"\nRHY1 preamble (kept): {preamble.hex(' ')}")

    # Build a single bar with known events
    # Use the SAME bar header as the first bar in the original
    # (bytes 28-40 of original = first 13 bytes of event data)
    original_events = original_rhy1[28:]
    # First bar header = first 13 bytes
    bar_header = original_events[:13]
    print(f"Bar header (kept from original): {bar_header.hex(' ')}")

    # Known events (sorted by tick for monotonicity)
    known_pattern = [
        # (note, velocity, gate, tick, name)
        (36, 127, 412, 240, "Kick1"),      # Beat 1
        (49, 127,  74, 240, "Crash1"),      # Beat 1
        (44, 119,  30, 240, "HHpedal"),     # Beat 1
        (44,  95,  30, 720, "HHpedal"),     # Beat 2
        (38, 127, 200, 960, "Snare1"),      # Beat 3
        (44,  95,  30, 960, "HHpedal"),     # Beat 3
        (44,  95,  30, 1440, "HHpedal"),    # Beat 4
    ]

    # Encode events
    event_bytes = b''
    for i, (note, vel, gate, tick, name) in enumerate(known_pattern):
        enc = encode_event(note, vel, gate, tick, i)
        event_bytes += enc
        print(f"  e{i}: {name:>8} n={note} v={vel} g={gate} t={tick} → {enc.hex()}")

    # Build the track data: preamble + header + events (single bar, no delimiter)
    new_rhy1 = preamble + bar_header + event_bytes
    print(f"\nNew RHY1: {len(new_rhy1)} bytes (preamble={len(preamble)}"
          f" header={len(bar_header)} events={len(event_bytes)})")

    # ============================================================
    # 4. Build SysEx messages
    # ============================================================
    device_num = 0x10  # Match template

    # Split track data into chunks that fit in SysEx (max 128 decoded bytes per msg)
    MAX_DECODED = 128

    all_syx_msgs = []

    # Init message
    all_syx_msgs.append(build_init_msg(device_num))

    # RHY1 data (AL=0x00)
    for offset in range(0, len(new_rhy1), MAX_DECODED):
        chunk = new_rhy1[offset:offset + MAX_DECODED]
        msg = build_sysex_msg(device_num & 0x0F, 0x02, 0x7E, 0x00, chunk)
        all_syx_msgs.append(msg)
        print(f"  RHY1 msg: offset={offset} chunk={len(chunk)}B syx={len(msg)}B")

    # Copy other tracks from template (AL=0x01..0x06, 0x7F)
    # Re-emit the original messages for non-RHY1 tracks
    for m in template_msgs:
        if len(m) < 10 or m[2] != 0x00:
            continue
        al = m[8]
        if al != 0x00:  # Skip RHY1 (we replaced it)
            all_syx_msgs.append(bytes(m))

    # Close message
    all_syx_msgs.append(build_close_msg(device_num))

    # ============================================================
    # 5. Write .syx file
    # ============================================================
    output_path = os.path.join(base, "captured", "known_pattern.syx")
    with open(output_path, 'wb') as f:
        for msg in all_syx_msgs:
            f.write(msg)

    total_size = sum(len(m) for m in all_syx_msgs)
    print(f"\nOutput: {output_path}")
    print(f"  {len(all_syx_msgs)} messages, {total_size} bytes")

    # ============================================================
    # 6. Verify by re-parsing
    # ============================================================
    print(f"\n{'='*60}")
    print(f"  VERIFICATION: re-parse the generated .syx")
    print(f"{'='*60}")

    from qymanager.formats.qy70.sysex_parser import SysExParser
    parser = SysExParser()
    verify_msgs = parser.parse_file(output_path)

    rhy1_verify = b""
    for m in verify_msgs:
        if m.is_style_data and m.address_low == 0 and m.decoded_data:
            rhy1_verify += m.decoded_data

    print(f"  Re-parsed RHY1: {len(rhy1_verify)} bytes")
    print(f"  Preamble match: {rhy1_verify[:28] == preamble}")
    print(f"  Header match: {rhy1_verify[28:41] == bar_header}")

    # Decode events from re-parsed data
    evt_start = 28 + 13  # preamble + header
    print(f"\n  Decoded events from generated .syx:")

    from midi_tools.roundtrip_test import decode_event_raw
    GM_DRUMS = {36: "Kick1", 38: "Snare1", 44: "HHpedal", 49: "Crash1"}

    errors = 0
    for i in range(len(known_pattern)):
        evt = rhy1_verify[evt_start + i*7 : evt_start + (i+1)*7]
        note, vel, gate, tick, *_ = decode_event_raw(evt, i)
        exp_note, exp_vel, exp_gate, exp_tick, exp_name = known_pattern[i]

        # Velocity quantization
        exp_vc = max(0, min(15, round((127 - exp_vel) / 8)))
        exp_vel_q = max(1, 127 - exp_vc * 8)

        ok = note == exp_note and vel == exp_vel_q and gate == exp_gate and tick == exp_tick
        status = "✓" if ok else "✗"
        if not ok: errors += 1

        name = GM_DRUMS.get(note, f"n{note}")
        print(f"    e{i}: {status} {name:>8} n={note} v={vel} g={gate} t={tick}"
              f" (expected: n={exp_note} v={exp_vel_q} g={exp_gate} t={exp_tick})")

    if errors == 0:
        print(f"\n  ALL {len(known_pattern)} EVENTS VERIFIED ✓")
    else:
        print(f"\n  {errors} ERRORS!")

    # ============================================================
    # 7. Save the known pattern spec for later comparison
    # ============================================================
    spec_path = os.path.join(base, "captured", "known_pattern_spec.txt")
    with open(spec_path, 'w') as f:
        f.write("# Known pattern specification\n")
        f.write("# Format: event_index note velocity gate tick name\n")
        for i, (note, vel, gate, tick, name) in enumerate(known_pattern):
            vel_code = max(0, min(15, round((127 - vel) / 8)))
            vel_q = max(1, 127 - vel_code * 8)
            f.write(f"{i} {note} {vel_q} {gate} {tick} {name}\n")
    print(f"\n  Spec saved to: {spec_path}")


if __name__ == "__main__":
    main()
