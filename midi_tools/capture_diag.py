#!/usr/bin/env python3
"""Diagnostic MIDI capture — verifies connectivity, sends Start+Clock, logs everything.

Usage: .venv/bin/python3 midi_tools/capture_diag.py [--bpm 120] [--duration 10]
"""
import sys
import time
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def find_midi_ports():
    import mido
    out_ports = mido.get_output_names()
    in_ports = mido.get_input_names()
    out = next((p for p in out_ports if "steinberg" in p.lower() or "ur22" in p.lower()), None)
    inp = next((p for p in in_ports if "steinberg" in p.lower() or "ur22" in p.lower()), None)
    return inp, out


def main():
    import mido

    parser = argparse.ArgumentParser(description="Diagnostic MIDI capture for QY70")
    parser.add_argument("--bpm", type=int, default=120)
    parser.add_argument("--duration", "-d", type=float, default=10.0)
    args = parser.parse_args()

    in_name, out_name = find_midi_ports()
    print(f"MIDI OUT: {out_name}")
    print(f"MIDI IN:  {in_name}")
    if not in_name or not out_name:
        print("ERROR: ports not found")
        return

    bpm = args.bpm
    clock_interval = 60.0 / (bpm * 24)

    with mido.open_input(in_name) as midi_in, mido.open_output(out_name) as midi_out:
        # Flush pending
        for _ in midi_in.iter_pending():
            pass

        # === Step 1: connectivity test ===
        print(f"\n{'='*60}")
        print("  STEP 1: Connectivity test (sending kick on ch10)")
        print(f"{'='*60}")
        midi_out.send(mido.Message('note_on', channel=9, note=36, velocity=100))
        time.sleep(0.15)
        midi_out.send(mido.Message('note_off', channel=9, note=36, velocity=0))
        time.sleep(0.5)

        step1_msgs = []
        for msg in midi_in.iter_pending():
            step1_msgs.append(msg)
            print(f"  Received: {msg}")
        if not step1_msgs:
            print("  (no response — this is normal if ECHO BACK=Off)")
        print("  → Did you hear the kick on the QY70?")

        # === Step 2: passive listen (what does QY70 send on its own?) ===
        print(f"\n{'='*60}")
        print("  STEP 2: Passive listen (2s, no commands sent)")
        print(f"{'='*60}")
        t0 = time.time()
        passive_counts = {}
        while time.time() - t0 < 2.0:
            for msg in midi_in.iter_pending():
                passive_counts[msg.type] = passive_counts.get(msg.type, 0) + 1
            time.sleep(0.001)
        if passive_counts:
            print(f"  QY70 sending: {dict(sorted(passive_counts.items()))}")
        else:
            print("  QY70 silent (no messages) — expected in External sync mode")

        # === Step 3: Start + Clock ===
        print(f"\n{'='*60}")
        print(f"  STEP 3: Start + Clock at {bpm} BPM for {args.duration}s")
        print(f"  Clock interval: {clock_interval*1000:.1f}ms")
        print(f"{'='*60}")

        # Flush again
        for _ in midi_in.iter_pending():
            pass

        midi_out.send(mido.Message('start'))
        t0 = time.time()
        next_clock = t0
        clock_sent = 0
        msg_counts = {}
        all_msgs = []
        last_report = t0

        while time.time() - t0 < args.duration:
            now = time.time()

            # Send clocks
            while now >= next_clock:
                midi_out.send(mido.Message('clock'))
                next_clock += clock_interval
                clock_sent += 1

            # Read incoming
            for msg in midi_in.iter_pending():
                t = now - t0
                mtype = msg.type
                msg_counts[mtype] = msg_counts.get(mtype, 0) + 1
                all_msgs.append((t, msg))

                # Print interesting messages immediately
                if mtype == 'note_on':
                    ch = msg.channel + 1
                    print(f"  {t:6.2f}s NOTE_ON  ch{ch:2d} note={msg.note:3d} vel={msg.velocity:3d}")
                elif mtype == 'note_off':
                    ch = msg.channel + 1
                    print(f"  {t:6.2f}s NOTE_OFF ch{ch:2d} note={msg.note:3d}")
                elif mtype == 'control_change':
                    ch = msg.channel + 1
                    print(f"  {t:6.2f}s CC       ch{ch:2d} cc={msg.control:3d} val={msg.value:3d}")
                elif mtype == 'program_change':
                    ch = msg.channel + 1
                    print(f"  {t:6.2f}s PC       ch{ch:2d} prg={msg.program:3d}")
                elif mtype == 'sysex':
                    data = msg.data
                    hx = ' '.join(f'{b:02X}' for b in data[:16])
                    print(f"  {t:6.2f}s SYSEX    [{len(data)}B] F0 {hx} ...")

            # Progress every 2s
            if now - last_report >= 2.0:
                elapsed = now - t0
                total_rx = sum(msg_counts.values())
                print(f"  --- {elapsed:.0f}s elapsed | clocks sent: {clock_sent} | msgs received: {total_rx} ---")
                last_report = now

            time.sleep(0.0004)

        # Stop
        midi_out.send(mido.Message('stop'))
        time.sleep(0.3)

        # Capture remaining after stop
        for msg in midi_in.iter_pending():
            t = time.time() - t0
            mtype = msg.type
            msg_counts[mtype] = msg_counts.get(mtype, 0) + 1
            all_msgs.append((t, msg))
            if mtype not in ('clock',):
                ch_str = f" ch{msg.channel+1}" if hasattr(msg, 'channel') else ""
                print(f"  {t:6.2f}s {mtype}{ch_str} {msg}")

        # === Summary ===
        print(f"\n{'='*60}")
        print(f"  SUMMARY")
        print(f"{'='*60}")
        print(f"  Clocks sent:      {clock_sent}")
        print(f"  Messages received: {sum(msg_counts.values())}")
        print(f"  By type: {dict(sorted(msg_counts.items()))}")

        non_clock = [(t, m) for t, m in all_msgs if m.type != 'clock']
        if non_clock:
            print(f"\n  Non-clock messages ({len(non_clock)}):")
            for t, m in non_clock[:50]:
                print(f"    {t:6.3f}s  {m}")
            if len(non_clock) > 50:
                print(f"    ... and {len(non_clock)-50} more")
        else:
            print("\n  *** NO non-clock messages received! ***")

        # Diagnosis
        note_msgs = [m for _, m in all_msgs if m.type == 'note_on']
        cc_msgs = [m for _, m in all_msgs if m.type == 'control_change']
        pc_msgs = [m for _, m in all_msgs if m.type == 'program_change']
        syx_msgs = [m for _, m in all_msgs if m.type == 'sysex']

        print(f"\n  Diagnosis:")
        if note_msgs:
            channels = set(m.channel + 1 for m in note_msgs)
            print(f"  ✓ Notes received on channels: {sorted(channels)}")
        else:
            print(f"  ✗ No note events — possible causes:")
            if not cc_msgs and not pc_msgs:
                print(f"    → QY70 may not be playing (no CC/PC either)")
                print(f"    → Check: is a style selected in SONG mode?")
                print(f"    → Check: does the display show the style playing?")
                print(f"    → Try: press [►] on QY70 during capture")
            else:
                print(f"    → QY70 is sending CC/PC but no notes")
                print(f"    → PATT OUT CH might be Off or wrong range")

        if syx_msgs:
            print(f"  ℹ {len(syx_msgs)} SysEx message(s) received")

        # Check if QY70 was visibly playing
        print(f"\n  Quick checks:")
        print(f"    1. Was the beat/measure counter moving on QY70 display?")
        print(f"    2. Could you hear the style playing internally?")
        print(f"    3. What mode is shown? (SONG/PATT)")
        print(f"    4. What style number is selected?")


if __name__ == "__main__":
    main()
