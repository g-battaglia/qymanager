# MIDI Setup

Hardware setup for communicating with [QY70](qy70-device.md) and [QY700](qy700-device.md).

## Hardware

- **Interface**: Steinberg UR22C (USB-MIDI)
- **Cabling**: QY70 MIDI OUT → UR22C MIDI IN, UR22C MIDI OUT → QY70 MIDI IN
- **Port names**: "Steinberg UR22C Porta 1" (may vary by OS)
- **Virtual env**: always use `.venv/bin/python3` (system python3 lacks `mido`)

## Identity Check

```bash
.venv/bin/python3 midi_tools/midi_status.py
```

Sends `F0 7E 7F 06 01 F7` (Universal Identity Request) and displays the response. The QY70 replies with Family `0x4100`, Member `0x5502`. See [Identity Reply](identity-reply.md).

**Note**: Identity Request sometimes fails on first attempt — the script retries up to 10 times.

## Capturing a Bulk Dump

The [QY70 does NOT support remote Dump Request](qy70-device.md#known-limitations). The dump must be triggered manually.

### Procedure

1. Start the capture script:
   ```bash
   .venv/bin/python3 midi_tools/capture_dump.py -o midi_tools/captured/my_pattern.syx
   ```
2. On the QY70: **UTILITY → MIDI → Bulk Dump → Style** (or Pattern)
3. Wait for "Completed" on the QY70 display
4. The script saves the captured SysEx data

### Capture Tips

- Select a style/pattern **with content** before dumping (empty slots produce only header data)
- Preset styles must be copied to a user slot before dumping
- The captured .syx includes init, track data, header, and close messages

## Sending SysEx to QY70

```bash
.venv/bin/python3 midi_tools/send_request.py --address 02 7E 7F  # Request header
.venv/bin/python3 midi_tools/send_request.py --style             # Full style (NOT SUPPORTED)
```

**Dump Request does not work** — the QY70 does not respond. Use manual bulk dump instead.

## Analysis Scripts

| Script | Purpose |
|--------|---------|
| `midi_status.py` | Port listing, passive listen, Identity Request, dump test |
| `capture_dump.py` | Capture bulk dump to .syx file |
| `send_request.py` | Send SysEx dump requests (note: QY70 ignores these) |
| `event_decoder.py` | Decode [bitstream](bitstream.md) events from .syx files |
| `ground_truth_analyzer.py` | Validate decoder against known content |

## Captured Files

| File | Size | Content |
|------|------|---------|
| `ground_truth_A.syx` | 808B | Empty style (header only) |
| `ground_truth_preset.syx` | 7337B | 812 XG Parameter Change msgs (not bulk dump) |
| `ground_truth_style.syx` | 3211B | Real pattern: 133 BPM, 7 tracks, 6 bars |
