# QY Manager

Bidirectional converter and manager for Yamaha QY70 and QY700 pattern files.

## Overview

QY Manager (formerly QYConv) is a Python library and CLI tool for converting, analyzing, and editing pattern/style data between Yamaha QY70 SysEx files (.syx) and QY700 binary pattern files (.Q7P).

## Features

- **Modern CLI** with Rich formatting, bar graphics, and progress indicators
- **Complete pattern analysis** - view ALL configuration data with visual representations
- **Bidirectional conversion** - QY70 ↔ QY700 with granular lossy policy (`--keep/--drop`)
- **Unified Data Model** (UDM) — single format-agnostic schema for all parsers/emitters
- **Read/Write formats** - `.syx` (sparse + XG bulk), `.q7p`, `.blk`, `.mid` (SMF out)
- **Complete offline editor** - System, Multi Part, Drum Setup, Effect, Song, Pattern, Chord via CLI + Python API
- **Realtime XG editor** - every UDM edit can be emitted live over MIDI via `--realtime`
- **Hex dump + file structure visualization** - annotated maps and density analysis
- **Property tests** - Hypothesis-based invariants on UDM/XG roundtrip
- **Hardware-in-the-loop markers** - opt-in `QY_HARDWARE=1` device tests

## Installation

Project uses [uv](https://docs.astral.sh/uv/) (Astral) for environment / dependency management.

```bash
# From source
git clone https://github.com/qymanager/qymanager.git
cd qymanager

# Install uv if not already: https://docs.astral.sh/uv/getting-started/install/

# Sync deps (runtime + MIDI extras + dev tools)
uv sync --all-extras --group dev

# Run CLI
uv run qymanager --help

# Run tests
uv run pytest
```

If installing on an external volume / filesystem without hardlink support (APFS → exFAT/NTFS), export `UV_LINK_MODE=copy` first.

Legacy pip workflow still works:
```bash
pip install -e ".[midi]"
```

## CLI Usage

QY Manager provides a modern command-line interface powered by [Typer](https://typer.tiangolo.com/) and [Rich](https://rich.readthedocs.io/).

### Commands Overview

```bash
qymanager --help              # Show all commands
qymanager --version           # Show version (v0.4.0)
```

**Analysis Commands:**
```bash
qymanager info      # Pattern information (basic or --full)
qymanager tracks    # Detailed track/channel info with bar graphics
qymanager sections  # Section configuration details
qymanager phrase    # Phrase/sequence data analysis
qymanager map       # Visual file structure map
qymanager dump      # Annotated hex dump
```

**Utility Commands:**
```bash
qymanager diff      # Compare two Q7P files
qymanager validate  # Validate file structure
qymanager convert   # Convert between formats
```

---

### `qymanager info` - Pattern Analysis

Display pattern information from Q7P or SysEx files.

```bash
# Basic info
qymanager info pattern.Q7P

# Full extended analysis (all details)
qymanager info pattern.Q7P --full

# With hex dumps
qymanager info pattern.Q7P --hex

# Output as JSON
qymanager info pattern.Q7P --json
```

#### Options

| Option | Short | Description |
|--------|-------|-------------|
| `--full` | `-f` | Show complete extended analysis |
| `--hex` | `-x` | Show hex dumps of data areas |
| `--raw` | `-r` | Show unknown/reserved areas |
| `--messages` | `-m` | Show individual SysEx messages |
| `--json` | `-j` | Output as JSON |

#### Example Output (Basic)

```
╭──── Q7P Pattern Info ────╮
│ Pattern: USER TMPL       │
│ Number: 2                │
│ Format: YQ7PAT     V1.00 │
│ Status: Valid            │
│ File Size: 3072 bytes    │
│ Data Density: 28.0%      │
╰──────────────────────────╯

╭───────────── Timing ──────────────╮
│ Tempo: 120.0 BPM (raw: 0x04 0xB0) │
│ Time Signature: 4/4 (raw: 0x1C)   │
│ Flags: 0x00                       │
╰───────────────────────────────────╯

                            Voice Settings
╭───────┬────┬──────┬───────┬──────────────────────┬─────┬────┬─────╮
│ Track │ Ch │ Prog │ Bank  │ Instrument           │ Vol │ Pan│ Rev │
├───────┼────┼──────┼───────┼──────────────────────┼─────┼────┼─────┤
│ RHY1  │ 10 │ 0    │ 127/0 │ Standard Kit         │ 91  │ C  │ 40  │
│ RHY2  │ 10 │ 0    │ 127/0 │ Standard Kit         │ 100 │ C  │ 40  │
│ BASS  │ 2  │ 0    │ 0/0   │ Acoustic Grand Piano │ 100 │ C  │ 40  │
│ ...   │    │      │       │                      │     │    │     │
╰───────┴────┴──────┴───────┴──────────────────────┴─────┴────┴─────╯
```

---

### `qymanager tracks` - Track Information

Display detailed track/channel information with bar graphics.

```bash
# All tracks
qymanager tracks pattern.Q7P

# Specific track (1-8)
qymanager tracks pattern.Q7P --track 1

# Summary table only
qymanager tracks pattern.Q7P --summary
```

#### Example Output

```
╭────────── Track 1 ──────────╮
│ RHY1 - Rhythm 1 (Drums)     │
│ Status: ENABLED  Type: DRUM │
╰─────────────────────────────╯

   MIDI Channel       Ch 10                                     0x190
   Voice              Program   0  Bank 127/0                   TBD
                      Standard Kit
   Volume              91 [████████░░░░]  71%  [≠100]           0x226
   Pan                  C [──────●──────]  50%                  0x276
   Reverb Send         40 [███░░░░░░░░░]  31%                   0x256
   Chorus Send          0 [░░░░░░░░░░░░]   0%                   TBD
```

---

### `qymanager sections` - Section Details

Display detailed section information.

```bash
# All sections
qymanager sections pattern.Q7P

# Specific section (0-5)
qymanager sections pattern.Q7P --section 0

# Active sections only
qymanager sections pattern.Q7P --active

# Summary table
qymanager sections pattern.Q7P --summary
```

---

### `qymanager phrase` - Phrase/Sequence Analysis

Analyze phrase and sequence data areas with event detection.

```bash
# Full analysis
qymanager phrase pattern.Q7P

# Sequence area only
qymanager phrase pattern.Q7P --area sequence

# With data density heatmap
qymanager phrase pattern.Q7P --heatmap

# Without hex dump
qymanager phrase pattern.Q7P --no-hex
```

#### Features

- Byte frequency analysis
- Potential MIDI event detection (notes, velocities, delta times)
- Data density visualization
- Top value histogram

---

### `qymanager map` - File Structure Map

Visual map of Q7P file structure and data density.

```bash
# Basic map
qymanager map pattern.Q7P

# With hex preview of each region
qymanager map pattern.Q7P --detailed
```

#### Example Output

```
File Overview (each char = ~48 bytes, █=data, ░=empty)
0x000 ▓▒░░░░▓▓▓▒▒▓▓░░░░░███▓▓▒▓░░░░░░░░░▓▒█▒█████▒▓▒░░▓█▓░▒░░░░░░░░░░░ 0xBFF

                              File Regions
╭─────────────┬───────────────┬───────┬─────────────────────┬──────╮
│ Offset      │ Region        │ Size  │ Density             │ %    │
├─────────────┼───────────────┼───────┼─────────────────────┼──────┤
│ 0x000-0x00F │ Header        │ 16    │ ███████████░░░░░    │  68% │
│ 0x360-0x677 │ Phrase Data   │ 792   │ ██░░░░░░░░░░░░░░    │  18% │
│ 0x678-0x86F │ Sequence Data │ 504   │ ████████░░░░░░░░    │  53% │
│ ...         │               │       │                     │      │
╰─────────────┴───────────────┴───────┴─────────────────────┴──────╯

Overall Data Density: 19.8% (607/3072 bytes)
```

---

### `qymanager dump` - Annotated Hex Dump

Color-coded hex dump with region annotations.

```bash
# Full file dump
qymanager dump pattern.Q7P

# Specific region
qymanager dump pattern.Q7P --region PHRASE
qymanager dump pattern.Q7P --region TEMPO
qymanager dump pattern.Q7P --region VOLUMES

# Byte range
qymanager dump pattern.Q7P --start 0x360 --length 128

# Only lines with non-filler data
qymanager dump pattern.Q7P --non-zero

# Without legend
qymanager dump pattern.Q7P --no-legend
```

#### Available Regions

`HEADER`, `PAT_INFO`, `SECT_PTR`, `SECT_DATA`, `TEMPO`, `CHANNELS`,
`TRK_CFG`, `VOLUMES`, `REVERB`, `PAN`, `PHRASE`, `SEQUENCE`, `TMPL_NAME`,
`PAT_MAP`, `FILL`, `PAD`

---

### `qymanager diff` - Compare Files

Compare two Q7P pattern files and show differences.

```bash
qymanager diff pattern1.Q7P pattern2.Q7P
qymanager diff pattern1.Q7P pattern2.Q7P --verbose
```

#### Example Output

```
╭───────────────────────────── Differences Found ──────────────────╮
│ File A: T01.Q7P                                                  │
│ File B: TXX.Q7P                                                  │
│                                                                  │
│ 94 byte(s) differ across 7 region(s)                             │
╰──────────────────────────────────────────────────────────────────╯

                         Structural Differences
╭────────┬────────────┬─────────────────┬─────────────┬────────────╮
│ Offset │ Area       │ Description     │ File A      │ File B     │
├────────┼────────────┼─────────────────┼─────────────┼────────────┤
│ 0x010  │ Pattern    │ Pattern number  │ 2           │ 1          │
│        │ Number     │ differs         │             │            │
│ 0x100  │ Section    │ 8 byte(s)       │ FE FE FE FE │ 00 29 00   │
│        │ Pointers   │ differ          │ ...         │ 32 ...     │
╰────────┴────────────┴─────────────────┴─────────────┴────────────╯
```

---

### `qymanager validate` - File Validation

Validate Q7P file structure and content.

```bash
qymanager validate pattern.Q7P
qymanager validate pattern.Q7P --strict  # Warnings as errors
qymanager validate pattern.Q7P --verbose
```

#### Checks Performed

- File size (3072 bytes)
- Header magic (`YQ7PAT     V1.00`)
- Tempo range (20-300 BPM)
- Time signature encoding
- MIDI parameter ranges (channels, volumes, pans)
- Section pointer consistency
- Filler/padding area integrity

---

### `qymanager convert` - Format Conversion

Convert between QY70 SysEx and QY700 Q7P formats.

```bash
# QY70 → QY700
qymanager convert style.syx -o pattern.Q7P

# QY700 → QY70
qymanager convert pattern.Q7P -o style.syx

# With template
qymanager convert style.syx -o pattern.Q7P -t template.Q7P
```

---

## Unified Data Model (UDM) & Editor

The v0.4 series introduces a **format-agnostic Device model** in `qymanager.model`.
All parsers (Q7P, QY70 `.syx` sparse, XG bulk, SMF) decode into the same `Device` schema;
all emitters consume it. The editor CLI and realtime XG wrapper operate on the model,
not on raw bytes — so you can edit any parameter without caring whether the source file
is a `.syx` or a `.q7p`.

```
Device
├── system            # master_tune, master_volume, transpose, midi_sync, ...
├── multi_part[16]    # voice (bank_msb/lsb/program), volume, pan, send levels, EG, ...
├── drum_setup[2]     # per-note pitch, level, pan, send, alt-group, note-off mode
├── effects           # reverb / chorus / variation (type + 11-43 params)
├── songs[]           # tracks, chord track, tempo changes
├── patterns[]        # sections, chord track, groove ref, phrase references
└── phrases[]         # user phrases (events, category, type)
```

### Offline editing (path-based DSL)

```bash
# Edit a single field and save UDM as JSON
qymanager field-set multi_part[0].voice.program=12 --in pattern.q7p --out pattern.json

# Read a single field
qymanager field-get multi_part[0].volume --in pattern.q7p

# Emit just the XG Parameter Change bytes (no MIDI I/O)
qymanager field-emit-xg system.master_volume --value 100

# Structured commands for patterns/songs/chords
qymanager pattern-list pattern.q7p
qymanager pattern-set pattern.q7p --idx 0 --name NEW --tempo 128 --out out.q7p
qymanager chord-add pattern.q7p --measure 1 --beat 1 --root C --type MAJ --out out.q7p
qymanager song-list song.mid
```

### Realtime editing (live XG Parameter Change)

```bash
# List available MIDI ports
qymanager realtime list-ports

# Watch XG Parameter Changes coming out of the device
qymanager realtime watch --port "UR22C Port 1"

# Send one or more UDM edits as live XG
qymanager realtime emit --port "UR22C Port 1" \
    --set system.master_volume=100 \
    --set multi_part[0].volume=115
```

Under the hood the CLI composes `qymanager.editor.ops.make_xg_messages(device, edits)`
which validates against `qymanager.editor.schema`, resolves the XG `(AH, AM, AL)` triple
via `qymanager.editor.address_map`, and sends raw SysEx via `python-rtmidi`
(we avoid `mido` on macOS because of a known SysEx-drop bug — see
`memory/feedback_mido_sysex_bug.md`).

### Converter lossy policy

```bash
# Convert QY70 sparse → QY700 UDM JSON, warning only on fill CC/DD
qymanager udm-convert SGT.syx -o SGT.udm.json --target-model QY700 \
    --drop sections.Fill_CC,sections.Fill_DD --warn-file SGT.warnings.json
```

The policy distinguishes **structural normalization** (always applied when switching
target model — e.g., parts 17-32 stripped when going to QY70) from **warning emission**
(controlled by `--keep/--drop`). Every warning lists the UDM path that was lost or adapted,
so a future round-trip tool can recover.

---

## Python API

### Pattern Analysis

```python
from qymanager.analysis.q7p_analyzer import Q7PAnalyzer

analyzer = Q7PAnalyzer()
analysis = analyzer.analyze_file("pattern.Q7P")

print(f"Pattern: {analysis.pattern_name}")
print(f"Tempo: {analysis.tempo} BPM")
print(f"Active sections: {analysis.active_section_count}")
print(f"Data density: {analysis.data_density:.1f}%")

# Phrase statistics
if analysis.phrase_stats:
    stats = analysis.phrase_stats
    print(f"Phrase density: {stats.phrase_density:.1f}%")
    print(f"Potential notes: {stats.potential_note_events}")
```

### Reading Files

```python
from qymanager.formats.qy70.reader import QY70Reader
from qymanager.formats.qy700.reader import QY700Reader

# Read QY70 SysEx file
pattern = QY70Reader.read("style.syx")

# Read QY700 Q7P file
pattern = QY700Reader.read("pattern.Q7P")
```

### Converting Between Formats

```python
from qymanager.converters import convert_qy70_to_qy700, convert_qy700_to_qy70

# QY70 → QY700
convert_qy70_to_qy700(
    source_path="style.syx",
    output_path="pattern.Q7P",
    template_path="template.Q7P"
)

# QY700 → QY70
convert_qy700_to_qy70(
    source_path="pattern.Q7P",
    output_path="style.syx"
)
```

---

## MIDI Communication with QY70

### CRITICAL: Init Handshake Required for Dump Request

The QY70 **requires an Init handshake message** before it will respond to Bulk Dump Requests. Without the Init, all dump requests are silently ignored.

```
Step 1: Send Init       F0 43 10 5F 00 00 00 01 F7
Step 2: Wait 500ms
Step 3: Send Request     F0 43 20 5F 02 7E AL F7    (AL = track 0x00-0x07, or 0x7F = header)
Step 4: Receive dump data
Step 5: Send Close       F0 43 10 5F 00 00 00 00 F7
```

This was discovered in Session 22 (2026-04-16). All previous documentation incorrectly stated "QY70 does not support remote Dump Request".

### XG Parameter Request (no handshake needed)

```
F0 43 30 4C 08 pp xx F7    (pp = part 0-15, xx = parameter offset)
```

Returns current XG tone generator parameters (voice, volume, pan, effects).

### QY70 MIDI Settings for Reverse Engineering

| Setting | Value | Purpose |
|---------|-------|---------|
| PATT OUT CH | 9~16 | Output pattern tracks on MIDI channels 9-16 |
| MIDI SYNC | External | Sync to external MIDI clock |
| ECHO BACK | Off | Prevent MIDI echo loops |

### Pipeline B: Capture-Based Conversion

```
Send .syx → QY70 → MIDI Start+Clock → Capture Notes → Quantize → SMF/Q7P
```

Uses `auto_capture_pipeline.py` for one-shot automated conversion.

---

## File Formats

### QY70 SysEx (.syx)

| Property | Value |
|----------|-------|
| Manufacturer ID | 0x43 (Yamaha) |
| Model ID | 0x5F (QY70) |
| Data encoding | 7-bit packed |
| Checksum | Per-message |

### QY700 Binary (.Q7P)

| Property | Value |
|----------|-------|
| File size | 3072 bytes (fixed) |
| Header | `YQ7PAT     V1.00` |
| Data encoding | Raw 8-bit |

**Key Offsets:**

| Offset | Size | Description |
|--------|------|-------------|
| 0x000 | 16 | Header magic |
| 0x010 | 1 | Pattern number |
| 0x100 | 32 | Section pointers |
| 0x188 | 2 | Tempo (BE, ÷10) |
| 0x190 | 8 | Channel assignments |
| 0x226 | 8 | Volume table |
| 0x256 | 8 | Reverb send table |
| 0x276 | 8 | Pan table |
| 0x360 | 792 | Phrase data |
| 0x678 | 504 | Sequence data |
| 0x876 | 10 | Pattern name |

---

## Development

```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run CLI from source
PYTHONPATH=. python3 cli/app.py info tests/fixtures/T01.Q7P
```

---

## Documentation

See the [docs](docs/) folder for detailed documentation:

- [QY70 Format](docs/QY70_FORMAT.md) - SysEx structure and encoding
- [QY700 Format](docs/QY700_FORMAT.md) - Binary file structure

---

## License

MIT License - see [LICENSE](LICENSE) for details.
