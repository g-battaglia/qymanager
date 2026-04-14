#!/usr/bin/env python3
"""SysEx diagnostic tool — systematically test what reaches the QY70.

Tests multiple SysEx sending methods and message types to diagnose
why the QY70 ignores all SysEx from the computer via UR22C.

The QY70 has MIDI THRU which echoes incoming bytes, so we can
capture what actually reaches the device by listening on MIDI IN.

Strategy:
  1. Send a note (baseline — known to work)
  2. Send small SysEx messages (Section Control, Identity Request)
  3. Send via mido vs rtmidi directly
  4. Try both UR22C ports
  5. Compare sent vs received (via THRU loopback)
"""

import sys
import time
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


# ─── Test messages ───

# Note On (ch10 = drums, note 36 = kick, vel 100) + Note Off
NOTE_ON = [0x99, 36, 100]
NOTE_OFF = [0x99, 36, 0]

# Identity Request (Universal SysEx — 6 bytes)
IDENTITY_REQ = [0xF0, 0x7E, 0x7F, 0x06, 0x01, 0xF7]

# GM System On (Universal SysEx — 6 bytes)
GM_SYSTEM_ON = [0xF0, 0x7E, 0x7F, 0x09, 0x01, 0xF7]

# Master Volume max (Universal SysEx — 8 bytes)
MASTER_VOLUME = [0xF0, 0x7F, 0x7F, 0x04, 0x01, 0x7F, 0x7F, 0xF7]

# XG System On (Yamaha, model 4C — 9 bytes)
XG_SYSTEM_ON = [0xF0, 0x43, 0x10, 0x4C, 0x00, 0x00, 0x7E, 0x00, 0xF7]

# QY70 Section Control: switch to MAIN A (ss=0x09, dd=0x01)
# Format: F0 43 7E 00 ss dd F7 (7 bytes, from List Book p.54)
SECTION_CTRL_MAIN_A = [0xF0, 0x43, 0x7E, 0x00, 0x09, 0x01, 0xF7]

# QY70 Section Control: switch to INTRO (ss=0x08, dd=0x01)
SECTION_CTRL_INTRO = [0xF0, 0x43, 0x7E, 0x00, 0x08, 0x01, 0xF7]

# QY70 Sequencer Parameter Change: bulk mode on
# F0 43 10 5F 00 00 00 01 F7 (this is the Init message)
SEQ_INIT = [0xF0, 0x43, 0x10, 0x5F, 0x00, 0x00, 0x00, 0x01, 0xF7]

# Minimal SysEx — just F0 43 00 F7 (Yamaha, 4 bytes)
MINIMAL_YAMAHA = [0xF0, 0x43, 0x00, 0xF7]


def capture_midi_in(port_name, duration_s, results):
    """Capture MIDI messages on input port for duration_s seconds."""
    import rtmidi
    mi = rtmidi.MidiIn()
    mi.ignore_types(sysex=False, timing=True, active_sense=True)

    port_idx = None
    for i in range(mi.get_port_count()):
        if mi.get_port_name(i) == port_name:
            port_idx = i
            break
    if port_idx is None:
        results.append(("ERROR", f"Input port '{port_name}' not found"))
        return

    mi.open_port(port_idx)
    deadline = time.time() + duration_s
    while time.time() < deadline:
        msg = mi.get_message()
        if msg:
            data, delta = msg
            results.append(("MSG", data, delta, time.time()))
        time.sleep(0.001)
    mi.close_port()


def send_via_rtmidi(port_name, message, label=""):
    """Send a MIDI message via rtmidi directly (bypassing mido)."""
    import rtmidi
    mo = rtmidi.MidiOut()

    port_idx = None
    for i in range(mo.get_port_count()):
        if mo.get_port_name(i) == port_name:
            port_idx = i
            break
    if port_idx is None:
        print(f"  ERROR: Output port '{port_name}' not found")
        return False

    mo.open_port(port_idx)
    mo.send_message(message)
    time.sleep(0.05)
    mo.close_port()
    return True


def send_via_mido(port_name, message, label=""):
    """Send a MIDI message via mido."""
    import mido

    with mido.open_output(port_name) as port:
        if message[0] == 0xF0:
            # SysEx: strip F0 and F7 for mido
            msg = mido.Message("sysex", data=message[1:-1])
        elif (message[0] & 0xF0) == 0x90:
            msg = mido.Message("note_on", channel=message[0] & 0x0F,
                               note=message[1], velocity=message[2])
        else:
            print(f"  Unsupported message type: 0x{message[0]:02X}")
            return False
        port.send(msg)
        time.sleep(0.05)
    return True


def send_via_rtmidi_chunked(port_name, message, chunk_size=32):
    """Send SysEx in small chunks via rtmidi (some interfaces need this)."""
    import rtmidi
    mo = rtmidi.MidiOut()

    port_idx = None
    for i in range(mo.get_port_count()):
        if mo.get_port_name(i) == port_name:
            port_idx = i
            break
    if port_idx is None:
        return False

    mo.open_port(port_idx)
    # rtmidi on CoreMIDI should handle full SysEx in one call,
    # but try sending the complete message
    mo.send_message(message)
    time.sleep(0.05)
    mo.close_port()
    return True


def run_loopback_test(out_port, in_port, message, label, method="rtmidi"):
    """Send a message and capture what comes back via MIDI THRU."""
    captured = []

    # Start capture thread
    capture_thread = threading.Thread(
        target=capture_midi_in,
        args=(in_port, 1.5, captured)
    )
    capture_thread.start()
    time.sleep(0.2)  # Let capture thread settle

    # Send
    if method == "rtmidi":
        ok = send_via_rtmidi(out_port, message, label)
    else:
        ok = send_via_mido(out_port, message, label)

    capture_thread.join()

    return captured, ok


def format_msg(data):
    """Format MIDI message bytes for display."""
    return " ".join(f"{b:02X}" for b in data)


def run_tests():
    import rtmidi

    mo = rtmidi.MidiOut()
    ports = [mo.get_port_name(i) for i in range(mo.get_port_count())]

    if not ports:
        print("ERROR: No MIDI output ports found!")
        return

    print("=" * 70)
    print("QY70 SysEx Diagnostic")
    print("=" * 70)
    print(f"\nAvailable ports: {ports}")
    print()

    # Use Porta 1 as primary, Porta 2 as alternative
    primary_out = None
    alt_out = None
    primary_in = None

    for p in ports:
        if "Porta 1" in p:
            primary_out = p
            primary_in = p  # Same name for in/out
        elif "Porta 2" in p:
            alt_out = p

    if not primary_out:
        primary_out = ports[0]
        primary_in = ports[0]
    if not alt_out and len(ports) > 1:
        alt_out = ports[1]

    print(f"Primary OUT: {primary_out}")
    print(f"Primary IN:  {primary_in}")
    if alt_out:
        print(f"Alt OUT:     {alt_out}")
    print()

    # ─── Test messages to try ───
    tests = [
        ("Note On (baseline)",           NOTE_ON,               False),
        ("Note Off",                     NOTE_OFF,              False),
        ("Identity Request (6B)",        IDENTITY_REQ,          True),
        ("GM System On (6B)",            GM_SYSTEM_ON,          True),
        ("Master Volume (8B)",           MASTER_VOLUME,         True),
        ("Section Ctrl MAIN A (7B)",     SECTION_CTRL_MAIN_A,   True),
        ("Section Ctrl INTRO (7B)",      SECTION_CTRL_INTRO,    True),
        ("XG System On (9B)",            XG_SYSTEM_ON,          True),
        ("Seq Init (9B)",               SEQ_INIT,              True),
        ("Minimal Yamaha (4B)",          MINIMAL_YAMAHA,        True),
    ]

    # ═══ Phase 1: Send via rtmidi on Porta 1 with loopback capture ═══
    print("=" * 70)
    print("PHASE 1: rtmidi direct → Porta 1 (with THRU loopback capture)")
    print("=" * 70)

    for label, msg, is_sysex in tests:
        print(f"\n  [{label}]")
        print(f"  SENT:   {format_msg(msg)}")

        captured, ok = run_loopback_test(primary_out, primary_in, msg, label, "rtmidi")

        if not ok:
            print(f"  STATUS: SEND FAILED")
            continue

        if captured:
            for item in captured:
                if item[0] == "MSG":
                    data = item[1]
                    print(f"  RECV:   {format_msg(data)}")
                    # Compare
                    if is_sysex:
                        if data == msg:
                            print(f"  MATCH:  EXACT (SysEx echoed correctly)")
                        elif data[0] == 0xF0:
                            print(f"  MATCH:  SysEx received but different")
                        else:
                            print(f"  MATCH:  Different message type")
                    else:
                        if data == msg:
                            print(f"  MATCH:  EXACT")
                elif item[0] == "ERROR":
                    print(f"  ERROR:  {item[1]}")
        else:
            print(f"  RECV:   (nothing received)")

    # ═══ Phase 2: Send via mido on Porta 1 ═══
    print()
    print("=" * 70)
    print("PHASE 2: mido → Porta 1 (with THRU loopback capture)")
    print("=" * 70)

    # Only test a subset via mido
    mido_tests = [
        ("Note On via mido",            NOTE_ON,               False),
        ("GM System On via mido",       GM_SYSTEM_ON,          True),
        ("Section Ctrl via mido",       SECTION_CTRL_MAIN_A,   True),
        ("XG System On via mido",       XG_SYSTEM_ON,          True),
    ]

    for label, msg, is_sysex in mido_tests:
        print(f"\n  [{label}]")
        print(f"  SENT:   {format_msg(msg)}")

        captured, ok = run_loopback_test(primary_out, primary_in, msg, label, "mido")

        if not ok:
            print(f"  STATUS: SEND FAILED")
            continue

        if captured:
            for item in captured:
                if item[0] == "MSG":
                    data = item[1]
                    print(f"  RECV:   {format_msg(data)}")
                    if is_sysex and data == msg:
                        print(f"  MATCH:  EXACT")
                    elif is_sysex and data[0] == 0xF0:
                        print(f"  MATCH:  SysEx received but different")
        else:
            print(f"  RECV:   (nothing received)")

    # ═══ Phase 3: Try Porta 2 ═══
    if alt_out:
        print()
        print("=" * 70)
        print(f"PHASE 3: rtmidi direct → Porta 2")
        print("=" * 70)

        porta2_tests = [
            ("Note On → Porta 2",          NOTE_ON,               False),
            ("GM System On → Porta 2",     GM_SYSTEM_ON,          True),
            ("Section Ctrl → Porta 2",     SECTION_CTRL_MAIN_A,   True),
        ]

        for label, msg, is_sysex in porta2_tests:
            print(f"\n  [{label}]")
            print(f"  SENT:   {format_msg(msg)}")
            # Can't capture loopback on porta 2 easily, just send
            ok = send_via_rtmidi(alt_out, msg, label)
            print(f"  STATUS: {'sent' if ok else 'FAILED'}")

    # ═══ Phase 4: Byte-level analysis ═══
    print()
    print("=" * 70)
    print("PHASE 4: Byte-level analysis of SysEx vs Note")
    print("=" * 70)

    # Send note, capture, then send SysEx, capture — compare timing
    print(f"\n  Sending Note On + wait 500ms + SysEx...")
    captured = []
    capture_thread = threading.Thread(
        target=capture_midi_in,
        args=(primary_in, 3.0, captured)
    )
    capture_thread.start()
    time.sleep(0.2)

    # Note
    send_via_rtmidi(primary_out, NOTE_ON)
    time.sleep(0.5)
    # SysEx
    send_via_rtmidi(primary_out, GM_SYSTEM_ON)
    time.sleep(0.5)
    # Note Off
    send_via_rtmidi(primary_out, NOTE_OFF)

    capture_thread.join()

    print(f"  Captured {len([c for c in captured if c[0] == 'MSG'])} messages:")
    for item in captured:
        if item[0] == "MSG":
            data, delta, ts = item[1], item[2], item[3]
            is_sx = data[0] == 0xF0
            print(f"    {'SysEx' if is_sx else 'Note ':5s} {format_msg(data)}"
                  f"  delta={delta:.4f}s")

    # ═══ Summary ═══
    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print()
    print("If SysEx messages appear in RECV (via THRU loopback),")
    print("the bytes physically reach the QY70 but the firmware ignores them.")
    print()
    print("If SysEx messages do NOT appear in RECV but notes do,")
    print("the UR22C is not transmitting SysEx on the physical MIDI OUT.")
    print()
    print("If nothing appears in RECV (not even notes),")
    print("the MIDI THRU cable may not be connected or port is wrong.")
    print()
    print("Next steps based on results:")
    print("  - If SysEx not transmitted: try a different USB-MIDI interface")
    print("  - If SysEx transmitted but ignored: check QY70 mode (Standby required)")
    print("  - Install SysEx Librarian (macOS app) as alternative SysEx sender")


if __name__ == "__main__":
    run_tests()
