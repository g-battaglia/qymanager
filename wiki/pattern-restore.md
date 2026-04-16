# Pattern Backup & Restore

How to capture a QY70 User Pattern to disk and restore it later. Useful insurance against:
- QY70 memory loss (battery failure, factory reset)
- Accidental overwrites during editing
- Moving patterns between devices
- Preserving [ground truth captures](open-questions.md#priority-1b-ground-truth-capture-critical-for-dense-encoding)

## Workflow

```
QY70 (U01)  →  [request_dump.py]  →  captured.syx  →  [restore_pattern.py]  →  captured_restore.syx  →  [send_style.py]  →  QY70 (U01)
   hardware       MIDI dump req        9× redundant         dedup + Init/Close            single send           hardware
```

## Step 1: Capture the pattern

Required QY70 state:
- Power on, at main screen (not in menus)
- `UTILITY → MIDI → SYNC = External` (default)
- `UTILITY → MIDI → Device Number = 1` (default, device byte = 0)

```bash
.venv/bin/python3 midi_tools/request_dump.py \
    --ah 02 --am 00 --all-tracks \
    -o midi_tools/captured/my_pattern.syx
```

**Notes**:
- `--ah 02` = pattern data
- `--am 00` = User Pattern slot 0 (U01). Change for other slots: `--am 01` = U02, etc.
- `--all-tracks` sends 9 dump requests (AL=0..7 and 0x7F). The QY70 ignores AL and
  returns the full pattern each time — you end up with 9 redundant copies of the same
  14 messages. The restore tool deduplicates this.
- The script automatically sends the required [Init handshake](../CLAUDE.md#critical-qy70-init-handshake-for-dump-request)
  before each request.

## Step 2: Build restore-ready file

```bash
.venv/bin/python3 midi_tools/restore_pattern.py \
    midi_tools/captured/my_pattern.syx
# → writes my_pattern_restore.syx
```

The restore tool:
- Deduplicates bulk dumps (keeps one copy of each unique message)
- Sorts into canonical order (tracks 0..7 first, header 0x7F last)
- Prepends the Init handshake (`F0 43 10 5F 00 00 00 01 F7`)
- Appends the Close message (`F0 43 10 5F 00 00 00 00 F7`)
- Validates all checksums before writing

**Optional flags**:
- `--slot N` — Remap to a different User Pattern slot (0-63). Rewrites the AM byte
  in every bulk dump and recalculates checksums.
- `--send` — Build AND immediately transmit to the QY70 (one-shot restore).
- `-o PATH` — Custom output path.

## Step 3: Restore to QY70

```bash
.venv/bin/python3 midi_tools/send_style.py \
    midi_tools/captured/my_pattern_restore.syx
```

QY70 will receive the pattern into User Pattern slot U01 (or whatever slot was encoded).
No audible confirmation — the QY70 silently absorbs the data. Press PATTERN and verify
U01 contains the expected content.

## Format expectations

The restore file contains:

| Position | Message | AL | Purpose |
|----------|---------|----|---------|
| 1 | `F0 43 10 5F 00 00 00 01 F7` | — | Init handshake (required) |
| 2..N-1 | Bulk dumps in AL order | 0x00..0x07, 0x7F | Pattern data |
| N | `F0 43 10 5F 00 00 00 00 F7` | — | Close (required) |

Each bulk dump has format `F0 43 0n 5F BH BL AH AM AL [data] CS F7` where:
- `n` = device number (0 = device 1)
- `BH BL` = byte count of encoded data (147 for full 128-byte blocks)
- `AH = 0x02` = pattern data
- `AM` = User Pattern slot (0x00 = U01)
- `AL` = track index (0x00=RHY1..0x07=PHR3, 0x7F=header)
- `CS` = Yamaha checksum over BH BL AH AM AL + data

See [SysEx Format](sysex-format.md) for full details.

## Safety

- **No bricking risk**: these are Pattern writes (AM=0x00..0x3F), not the dangerous
  Voice writes (see [Bricking Diagnosis](bricking.md) for the QY700 Voice offsets that
  caused the prior brick).
- **Round-trip verified**: the captured `ground_truth_C_kick.syx` decodes to a consistent
  structure; re-sending should reproduce the same pattern on the QY70.
- **Not an ACK protocol**: the QY70 silently discards messages with bad checksums.
  The restore tool validates checksums before writing to avoid sending broken files.

## Related Tools

- `midi_tools/request_dump.py` — Low-level dump request (with Init handshake)
- `midi_tools/restore_pattern.py` — Dedup + framing (this page's tool)
- `midi_tools/send_style.py` — General-purpose .syx sender (rtmidi direct)
- `midi_tools/capture_dump.py` — Listens for bulk dumps triggered from QY70 menu
