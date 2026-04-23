#!/usr/bin/env python3
"""
Chain-run all probes P00-P13 sequentially with inter-probe wait.

Workflow per probe:
  1. Build SysEx from spec
  2. Send Init + Bulk + Close
  3. Capture XG+channel response (5s window)
  4. Save to data/probes/{probe_id}/{sent.syx, response.bin, diff.json}
  5. Wait 2s before next probe

No power cycle between probes — tests empirically if QY70 recovers.
"""

import argparse
import json
import sys
import time
import threading
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from midi_tools.probe_runner import (
    PROBES, Probe, build_probe_syx, find_port,
    save_probe_artifacts,
)

PROBES_DIR = Path(__file__).parent.parent / "data" / "probes"


def send_and_capture(sent_syx: bytes, capture_window: float = 4.0) -> bytes:
    """Send a SysEx blob and capture response for capture_window seconds."""
    import rtmidi

    in_idx = find_port("in")
    out_idx = find_port("out")
    if in_idx is None or out_idx is None:
        raise RuntimeError("MIDI ports not found")

    mi = rtmidi.MidiIn()
    mi.ignore_types(sysex=False, timing=True, active_sense=True)

    collected: list[bytes] = []
    stop = [False]

    def listener():
        mi.open_port(in_idx)
        deadline = time.time() + capture_window
        while time.time() < deadline and not stop[0]:
            m = mi.get_message()
            if m:
                data, _ = m
                if data:
                    collected.append(bytes(data))
            else:
                time.sleep(0.001)
        mi.close_port()

    t = threading.Thread(target=listener, daemon=True)
    t.start()
    time.sleep(0.3)

    # Parse sent_syx into messages
    msgs = []
    i = 0
    while i < len(sent_syx):
        if sent_syx[i] != 0xF0:
            i += 1
            continue
        j = i + 1
        while j < len(sent_syx) and sent_syx[j] != 0xF7:
            j += 1
        msgs.append(sent_syx[i:j + 1])
        i = j + 1

    mo = rtmidi.MidiOut()
    mo.open_port(out_idx)
    for msg in msgs:
        mo.send_message(list(msg))
        is_init = len(msg) == 9 and msg[7] == 0x01
        is_close = len(msg) == 9 and msg[7] == 0x00
        if is_init:
            time.sleep(0.5)
        elif is_close:
            time.sleep(0.1)
        else:
            time.sleep(0.15)
    mo.close_port()

    # Wait for capture to complete
    remaining = capture_window - 1.0
    if remaining > 0:
        time.sleep(remaining)
    stop[0] = True
    t.join(timeout=1)

    return b"".join(collected)


def classify_response(blob: bytes) -> dict:
    """Parse response blob, return summary dict."""
    i = 0
    msgs = []
    while i < len(blob):
        if blob[i] == 0xF0:
            j = i + 1
            while j < len(blob) and blob[j] != 0xF7:
                j += 1
            msgs.append(("sysex", blob[i:j + 1]))
            i = j + 1
        elif 0x80 <= blob[i] <= 0xEF:
            status = blob[i]
            kind = status & 0xF0
            n_data = 2 if kind in (0x80, 0x90, 0xA0, 0xB0, 0xE0) else 1
            msg = blob[i:i + 1 + n_data]
            if len(msg) == 1 + n_data:
                msgs.append(("chan", msg))
            i += 1 + n_data
        else:
            i += 1

    xg_params = []
    voice_per_chan = {}
    note_events = []

    for kind, m in msgs:
        if kind == "sysex" and len(m) >= 4 and m[1] == 0x43 and m[3] == 0x4C:
            if (m[2] & 0xF0) == 0x10 and len(m) >= 8:
                xg_params.append({"ah": m[4], "am": m[5], "al": m[6], "dd": m[7]})
        elif kind == "chan":
            ch = (m[0] & 0x0F) + 1
            kind_val = m[0] & 0xF0
            voice_per_chan.setdefault(ch, {})
            if kind_val == 0xB0 and len(m) == 3:  # CC
                cc_num = m[1]
                voice_per_chan[ch].setdefault("cc", {})[cc_num] = m[2]
            elif kind_val == 0xC0:  # Pgm Chg
                voice_per_chan[ch]["program"] = m[1]
            elif kind_val == 0x90:  # Note on
                note_events.append({"ch": ch, "note": m[1], "vel": m[2]})
            elif kind_val == 0x80:  # Note off
                note_events.append({"ch": ch, "note": m[1], "vel": m[2], "off": True})

    return {
        "total_msgs": len(msgs),
        "xg_param_count": len(xg_params),
        "channel_msg_count": sum(len(v.get("cc", {})) + (1 if "program" in v else 0)
                                 for v in voice_per_chan.values()),
        "note_event_count": len(note_events),
        "xg_params": xg_params[:10],
        "voice_per_chan": voice_per_chan,
        "note_events": note_events[:20],
    }


def run_probe(probe_id: str, capture_window: float = 4.0) -> dict:
    """Run a single probe, save artifacts, return result summary."""
    probe = PROBES.get(probe_id)
    if probe is None:
        return {"error": f"probe {probe_id} not defined"}

    d = PROBES_DIR / probe_id
    d.mkdir(parents=True, exist_ok=True)

    sent_syx = build_probe_syx(probe)
    (d / "sent.syx").write_bytes(sent_syx)
    (d / "spec.json").write_text(json.dumps(probe.to_dict(), indent=2, default=str))

    print(f"  ─── Sending ({len(sent_syx)}B) ───")
    t0 = time.time()
    response = send_and_capture(sent_syx, capture_window)
    dt = time.time() - t0
    print(f"  Received {len(response)}B in {dt:.2f}s")

    (d / "response.bin").write_bytes(response)

    summary = classify_response(response)
    summary["sent_bytes"] = len(sent_syx)
    summary["received_bytes"] = len(response)
    summary["capture_seconds"] = dt
    (d / "summary.json").write_text(json.dumps(summary, indent=2))
    return summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("probes", nargs="*", default=None,
                    help="probe IDs to run (default: all in order)")
    ap.add_argument("--interprobe-wait", type=float, default=2.5,
                    help="seconds to wait between probes")
    ap.add_argument("--capture-window", type=float, default=4.0,
                    help="seconds to capture response per probe")
    args = ap.parse_args()

    if not args.probes:
        args.probes = list(PROBES.keys())

    print(f"═══ Chain-running {len(args.probes)} probes ═══")
    print(f"  Inter-probe wait: {args.interprobe_wait}s")
    print(f"  Capture window: {args.capture_window}s")

    all_results = {}
    for i, pid in enumerate(args.probes):
        print(f"\n[{i+1}/{len(args.probes)}] {pid}")
        try:
            result = run_probe(pid, capture_window=args.capture_window)
            all_results[pid] = result
            print(f"  total_msgs: {result.get('total_msgs', 0)}")
            print(f"  xg_params: {result.get('xg_param_count', 0)}")
            print(f"  channel_msgs: {result.get('channel_msg_count', 0)}")
            print(f"  note_events: {result.get('note_event_count', 0)}")
        except Exception as e:
            all_results[pid] = {"error": str(e)}
            print(f"  ERROR: {e}")

        if i < len(args.probes) - 1:
            print(f"  Waiting {args.interprobe_wait}s before next probe...")
            time.sleep(args.interprobe_wait)

    # Write aggregate
    out = PROBES_DIR / "_chain_results.json"
    out.write_text(json.dumps(all_results, indent=2))
    print(f"\n═══ Aggregate saved to {out} ═══")

    # Print comparison
    print(f"\n═══ Summary ═══")
    print(f"{'Probe':30s} {'Recv':>6} {'XG':>4} {'Chan':>5} {'Notes':>5}")
    for pid in args.probes:
        r = all_results.get(pid, {})
        print(f"{pid:30s} {r.get('received_bytes', 0):>6} "
              f"{r.get('xg_param_count', 0):>4} {r.get('channel_msg_count', 0):>5} "
              f"{r.get('note_event_count', 0):>5}")


if __name__ == "__main__":
    main()
