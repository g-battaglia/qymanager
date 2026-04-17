# MIDI Setup

Hardware setup for communicating with [QY70](qy70-device.md) and [QY700](qy700-device.md).

## Hardware

- **Interface**: Steinberg UR22C (USB-MIDI)
- **Cabling**: QY70 MIDI OUT → UR22C MIDI IN, UR22C MIDI OUT → QY70 MIDI IN
- **Port names**: "Steinberg UR22C Porta 1" (may vary by OS)
- **Virtual env**: always use `.venv/bin/python3` (system python3 lacks `mido`)

## TO HOST direct connection (alternativa UR22C)

Il QY70 ha anche una porta **TO HOST** (MINI DIN 8-pin) per connessione diretta al PC senza MIDI interface. Dal manuale QY70 pag 16-20:

| Host Select | Device | Rate | Driver |
|-------------|--------|------|--------|
| MIDI | MIDI DIN only | 31250 bps MIDI | standard |
| PC-2 | IBM RS-232C | 38400 bps | Yamaha CBX / CBX-T3 |
| PC-1 | NEC PC-9801 | 31250 bps | Yamaha CBX / CBX-T3 |
| Mac | Mac serial modem/printer | 31250 bps | OMS / Yamaha CBX |

Cavo IBM: 8-pin MINI DIN → 9-pin D-SUB cross. Con TO HOST + MIDI controller esterno collegato, l'echo back software **deve essere ON**.

Non testato nel progetto (usiamo UR22C USB-MIDI direct).

## UTILITY → MIDI — tutte le opzioni (OM pag 222-224)

| Setting | Values | Use |
|---------|--------|-----|
| MIDI SYNC | Internal / External | **External** per ricevere MIDI Start/Clock dal computer |
| MIDI CONTROL | Off / In / Out / In+Out | **In** o **In+Out** per accept MIDI Start/Stop remoti |
| ECHO BACK | Off / Thru / RecMontr | **Off** (no loop); Thru = pass-through input → output; RecMontr = monitor record |
| LOCAL | On / Off | Controlla se la micro-keyboard pilota il tone generator interno |
| MIDI FILTER | Off / PB / CC / AT / Exc | Blocca un tipo di evento in ricezione/record |
| PATT OUT CH | Off / 1~8 / 9~16 | Canali MIDI su cui trasmettere le 8 tracce pattern |
| XG PARM OUT | Off / On | Trasmette XG parameters al cambio song/pattern |
| DEVICE NO | 1-16 / Off | Device number per SysEx (default 1 = 0x00) |
| RECEIVE CH | 1-16 / Omni | Canale ricezione per modo Voice/Song |

**SYSTEM EXCLUSIVE INTERVAL TIME** (UTILITY → System, pag 221): `0*100..9*100 ms` — delay tra blocchi SysEx in transmission. Questo è la **fonte ufficiale** del 150-200ms empirico documentato nei nostri script `send_style.py`. Il QY70 inserisce automaticamente questo delay quando invia bulk dump, e si aspetta che il mittente faccia altrettanto.

## MIDI Validation (Session 16)

Bidirectional MIDI confirmed:
- **Computer → QY70**: SysEx bulk data sent and received. Notes sent from computer are heard on QY70 speakers.
- **QY70 → Computer**: Keyboard notes received. Manual bulk dump captured. CC reset messages on MIDI Stop confirmed.
- **Identity Request**: QY70 **responds correctly** to `F0 7E 7F 06 01 F7` with Identity Reply `F0 7E 7F 06 02 43 00 41 02 55 00 00 00 01 F7` (Yamaha, XG Family 0x4100, Model 0x5502). Previous "no response" finding was caused by mido SysEx bug.
- **Style playback MIDI output**: requires [PATT OUT CH](qy70-device.md#midi-output-for-patternstyle-playback) to be set (default is Off).

**CRITICAL**: use `rtmidi` directly for all SysEx — `mido` silently drops SysEx on macOS CoreMIDI.

## Identity Check

```bash
.venv/bin/python3 midi_tools/sysex_diag.py
```

Sends Identity Request and various SysEx via rtmidi loopback test. The QY70 responds with Identity Reply confirming Family 0x4100 (XG), Model 0x5502.

**Do NOT use mido for SysEx** — it silently drops all SysEx messages on macOS CoreMIDI (confirmed Session 16).

## Capturing a Bulk Dump

The QY70 **supports Dump Request** for user pattern slots (AM=0x00-0x3F). Previous "unsupported" claims were wrong -- Session 16 received `F0 F7` from AM=0x00 which was a valid empty-pattern response (the slot was simply empty at the time). The [QYFiler.exe](qyfiler-reverse-engineering.md) binary confirms Dump Request templates are used by Yamaha's official tool.

**Important**: Dump Request does NOT work for the edit buffer (AM=0x7E). Only stored user pattern slots. The `request_dump.py` script defaulted to AM=0x7E which is why most tests appeared to fail.

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

**All SysEx must use rtmidi directly** (not mido). The `send_style.py` script has been fixed (Session 16).

**Critical timing** (Session 17): QY70 requires **500ms** after Init and **150ms** between bulk messages. Default timing in `send_style.py` has been updated. With correct timing, QY70 responds with ~160 messages (XG params, CC resets, Program Changes) confirming successful load.

```bash
# Send a .syx style file to QY70 (defaults: 500ms init, 150ms between msgs)
.venv/bin/python3 midi_tools/send_style.py tests/fixtures/QY70_SGT.syx

# Send + capture playback (combined workflow)
.venv/bin/python3 midi_tools/send_and_capture.py tests/fixtures/QY70_SGT.syx -d 10

# Request bulk dump from QY70
.venv/bin/python3 midi_tools/request_dump.py --ah 02 --am 00 --al 00

# Diagnostic: test SysEx loopback
.venv/bin/python3 midi_tools/sysex_diag.py
```

**Dump Request**: Works for user pattern slots (AM=0x00-0x3F). Use `request_dump.py --am 00` to request User Pattern 1. Edit buffer (AM=0x7E) does NOT support dump request. QYFiler also uses AM=0xFF (untested). Manual dump via UTILITY menu is always available as fallback.

## Analysis Scripts

| Script | Purpose |
|--------|---------|
| `sysex_diag.py` | SysEx loopback diagnostic (rtmidi vs mido comparison) |
| `send_style.py` | Send .syx style files to QY70 (rtmidi direct, 500ms/150ms timing) |
| `send_and_capture.py` | Combined send + playback capture workflow |
| `capture_playback.py` | Capture MIDI playback output (rtmidi, replaces mido version) |
| `request_dump.py` | Request bulk dump from QY70 (rtmidi direct) |
| `capture_dump.py` | Capture bulk dump to .syx file |
| `event_decoder.py` | Decode [bitstream](bitstream.md) events from .syx files |
| `build_claude_test.py` | Build test pattern .syx with known drum events |

## Enabling Pattern Playback Output

To capture style/pattern playback via MIDI, you must enable PATT OUT CH:

1. Press **[MENU]** → select **Utility**
2. Press **[MENU]** → select **MIDI**
3. Set **PATT OUT CH** to **"9~16"** (recommended: drums on ch 9-10, bass on ch 12, chords on ch 13-16)
4. Optionally set **MIDI CONTROL** to **"In"** or **"In/Out"** to accept MIDI Start/Stop

Then use `capture_playback.py` to capture notes during style playback:
```bash
.venv/bin/python3 midi_tools/capture_playback.py -d 10
```

See [QY70 MIDI Output](qy70-device.md#midi-output-for-patternstyle-playback) for full channel mapping.

## Captured Files

| File | Size | Content |
|------|------|---------|
| `ground_truth_A.syx` | 808B | Empty style (header only) |
| `ground_truth_preset.syx` | 7337B | 812 XG Parameter Change msgs (not bulk dump) |
| `ground_truth_style.syx` | 3211B | Real pattern: 133 BPM, 7 tracks, 6 bars |
| `known_pattern.syx` | 2542B | 7 known drum events, 100% round-trip verified |
| `claude_test.syx` | 2388B | 8-beat rock pattern: Kick+HH on 1,3, Snare+HH on 2,4 |
