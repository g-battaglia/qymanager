#!/usr/bin/env python3
"""Build a test .syx with a recognizable 8-beat rock drum pattern.

Pattern "CLAUDE_TEST" — 1 bar, 4/4:
  Beat 1: Kick(36) fff + HH closed(42) f
  Beat 2: Snare(38) ff  + HH closed(42) f
  Beat 3: Kick(36) ff  + HH closed(42) f
  Beat 4: Snare(38) ff  + HH closed(42) f

All events encoded with PROVEN R=9*(i+1) barrel rotation.
Uses user_style_live.syx as structural template (no corrupted messages).

Key format rules discovered from real QY70 captures:
  - Every bulk dump message MUST be exactly 158 bytes
  - Decoded data per message MUST be padded to exactly 128 bytes
  - BC = len(encoded_data) = 147 (always, since 128 decoded → 147 encoded)
  - Checksum covers BH BL AH AM AL + encoded_data
"""

import sys, os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from qymanager.utils.yamaha_7bit import encode_7bit, decode_7bit
from qymanager.utils.checksum import calculate_yamaha_checksum
from midi_tools.roundtrip_test import encode_event, decode_event_raw


CHUNK_SIZE = 128  # Decoded bytes per message (fixed, always padded)


def build_sysex_msg(device_num, ah, am, al, raw_data):
    """Build a QY70 bulk dump SysEx message.

    raw_data MUST be exactly 128 bytes (pad with zeros if shorter).
    BC = len(encoded) = 147 for 128 decoded bytes.
    Checksum covers BH BL AH AM AL + encoded.
    """
    assert len(raw_data) == CHUNK_SIZE, f"raw_data must be {CHUNK_SIZE}B, got {len(raw_data)}"
    encoded = encode_7bit(raw_data)
    assert len(encoded) == 147, f"encoded must be 147B, got {len(encoded)}"
    bc = len(encoded)  # = 147 always
    bh = (bc >> 7) & 0x7F
    bl = bc & 0x7F
    cs_region = bytes([bh, bl, ah, am, al]) + encoded
    cs = calculate_yamaha_checksum(cs_region)
    msg = bytes([0xF0, 0x43, device_num, 0x5F, bh, bl, ah, am, al]) + encoded + bytes([cs, 0xF7])
    assert len(msg) == 158, f"message must be 158B, got {len(msg)}"
    return msg


def build_init_msg(device_num=0x00):
    return bytes([0xF0, 0x43, 0x10 | device_num, 0x5F, 0x00, 0x00, 0x00, 0x01, 0xF7])


def build_close_msg(device_num=0x00):
    return bytes([0xF0, 0x43, 0x10 | device_num, 0x5F, 0x00, 0x00, 0x00, 0x00, 0xF7])


def split_and_pad(data, chunk_size=CHUNK_SIZE):
    """Split data into chunk_size blocks, zero-padding the last one."""
    chunks = []
    for offset in range(0, len(data), chunk_size):
        chunk = data[offset:offset + chunk_size]
        if len(chunk) < chunk_size:
            chunk = chunk + bytes(chunk_size - len(chunk))
        chunks.append(chunk)
    return chunks


def main():
    base = os.path.dirname(os.path.abspath(__file__))

    # Try user_style_live.syx first (no corrupted messages), fall back to ground_truth
    for template_name in ["user_style_live.syx", "ground_truth_style.syx"]:
        template_path = os.path.join(base, "captured", template_name)
        if os.path.exists(template_path):
            break

    # ============================================================
    # 1. Load template and decode ALL track data
    # ============================================================
    with open(template_path, 'rb') as f:
        template_raw = f.read()

    template_msgs = []
    start = None
    for i, b in enumerate(template_raw):
        if b == 0xF0: start = i
        elif b == 0xF7 and start is not None:
            template_msgs.append(template_raw[start:i+1])
            start = None

    # Decode track data per AL, preserving AL order
    track_raw_data = {}
    al_order = []
    for m in template_msgs:
        if len(m) < 10 or m[1] != 0x43:
            continue
        if (m[2] >> 4) != 0:  # Not a bulk dump
            continue
        al = m[8]
        payload_7bit = bytes(m[9:-2])
        decoded = decode_7bit(payload_7bit)
        if al not in track_raw_data:
            track_raw_data[al] = b''
            al_order.append(al)
        track_raw_data[al] += decoded

    print(f"Template: {template_name}, {len(template_msgs)} msgs")
    print(f"Tracks: {[f'AL=0x{al:02X} ({len(track_raw_data[al])}B)' for al in al_order]}")

    # ============================================================
    # 2. Define the test pattern
    # ============================================================
    test_pattern = [
        # (note, velocity, gate, tick, name)
        (36, 127, 200,  240, "Kick1"),       # Beat 1
        (42, 100,  30,  240, "HHclosed"),    # Beat 1
        (38, 110, 150,  720, "Snare1"),      # Beat 2
        (42, 100,  30,  720, "HHclosed"),    # Beat 2
        (36,  95, 200, 1200, "Kick1"),       # Beat 3
        (42, 100,  30, 1200, "HHclosed"),    # Beat 3
        (38, 110, 150, 1680, "Snare1"),      # Beat 4
        (42, 100,  30, 1680, "HHclosed"),    # Beat 4
    ]

    print(f"\nPattern: 8-beat rock, {len(test_pattern)} events")

    # ============================================================
    # 3. Encode events
    # ============================================================
    event_bytes = b''
    print(f"\nEncoding:")
    for i, (note, vel, gate, tick, name) in enumerate(test_pattern):
        enc = encode_event(note, vel, gate, tick, i)
        event_bytes += enc
        dn, dv, dg, dt, *_ = decode_event_raw(enc, i)
        vel_q = max(1, 127 - max(0, min(15, round((127 - vel) / 8))) * 8)
        ok = dn == note and dv == vel_q and dg == gate and dt == tick
        print(f"  e{i}: {name:>9} n={note:2d} v={vel:3d}(q={vel_q:3d}) g={gate:3d} t={tick:4d}"
              f"  {enc.hex()}  {'OK' if ok else 'FAIL'}")

    # ============================================================
    # 4. Build RHY1 track data
    # ============================================================
    original_rhy1 = track_raw_data[0x00]
    preamble = original_rhy1[:28]
    bar_header = original_rhy1[28:41]

    new_rhy1 = preamble + bar_header + event_bytes
    print(f"\nRHY1: {len(new_rhy1)}B (preamble=28 + header=13 + events={len(event_bytes)})")

    # Replace RHY1 in track data
    track_raw_data[0x00] = new_rhy1

    # ============================================================
    # 5. Rebuild ALL SysEx messages from decoded data
    # ============================================================
    device_num = 0x00
    all_msgs = [build_init_msg(device_num)]

    for al in al_order:
        data = track_raw_data[al]
        chunks = split_and_pad(data)
        for chunk in chunks:
            msg = build_sysex_msg(device_num, 0x02, 0x7E, al, chunk)
            all_msgs.append(msg)
        print(f"  AL=0x{al:02X}: {len(data)}B → {len(chunks)} msgs (128B each, padded)")

    all_msgs.append(build_close_msg(device_num))

    # ============================================================
    # 6. Write .syx
    # ============================================================
    output_path = os.path.join(base, "captured", "claude_test.syx")
    with open(output_path, 'wb') as f:
        for msg in all_msgs:
            f.write(msg)

    total_size = sum(len(m) for m in all_msgs)
    bulk_count = len(all_msgs) - 2
    print(f"\nOutput: {output_path}")
    print(f"  {len(all_msgs)} messages ({bulk_count} bulk), {total_size} bytes")
    print(f"  All bulk msgs 158B: {all(len(m)==158 for m in all_msgs[1:-1])}")

    # ============================================================
    # 7. Verify checksums
    # ============================================================
    print(f"\n{'='*60}")
    print(f"  VERIFICATION")
    print(f"{'='*60}")

    from qymanager.utils.checksum import verify_sysex_checksum
    cs_ok = sum(1 for m in all_msgs[1:-1] if verify_sysex_checksum(m))
    print(f"  Checksums: {cs_ok}/{bulk_count} OK")

    # Verify RHY1 events
    from qymanager.formats.qy70.sysex_parser import SysExParser
    parser = SysExParser()
    verify_msgs = parser.parse_file(output_path)

    rhy1_verify = b""
    for m in verify_msgs:
        if m.is_style_data and m.address_low == 0 and m.decoded_data:
            rhy1_verify += m.decoded_data

    print(f"  Re-parsed RHY1: {len(rhy1_verify)} bytes")
    print(f"  Preamble match: {rhy1_verify[:28] == preamble}")
    print(f"  Header match:   {rhy1_verify[28:41] == bar_header}")

    evt_start = 41
    errors = 0
    GM_DRUMS = {36: "Kick1", 38: "Snare1", 42: "HHclosed", 49: "Crash1"}

    for i, (exp_note, exp_vel, exp_gate, exp_tick, exp_name) in enumerate(test_pattern):
        evt = rhy1_verify[evt_start + i*7 : evt_start + (i+1)*7]
        note, vel, gate, tick, *_ = decode_event_raw(evt, i)
        exp_vc = max(0, min(15, round((127 - exp_vel) / 8)))
        exp_vel_q = max(1, 127 - exp_vc * 8)
        ok = note == exp_note and vel == exp_vel_q and gate == exp_gate and tick == exp_tick
        if not ok: errors += 1
        name = GM_DRUMS.get(note, f"n{note}")
        print(f"  e{i}: {'OK' if ok else 'FAIL'} {name:>9} n={note} v={vel} g={gate} t={tick}")

    if errors == 0:
        print(f"\n  ALL {len(test_pattern)} EVENTS VERIFIED OK")
    else:
        print(f"\n  {errors} ERRORS!")

    # Save spec
    spec_path = os.path.join(base, "captured", "claude_test_spec.txt")
    with open(spec_path, 'w') as f:
        f.write("# Claude test pattern: 8-beat rock\n")
        f.write("# Format: event_index note velocity_quantized gate tick name\n")
        for i, (note, vel, gate, tick, name) in enumerate(test_pattern):
            vel_q = max(1, 127 - max(0, min(15, round((127 - vel) / 8))) * 8)
            f.write(f"{i} {note} {vel_q} {gate} {tick} {name}\n")
    print(f"  Spec: {spec_path}")

    return output_path


if __name__ == "__main__":
    main()
