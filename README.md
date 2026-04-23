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
qymanager info          # Pattern information (basic or --full)
qymanager audit         # Report data extraction completeness + suggestions
qymanager tracks        # Detailed track/channel info with bar graphics
qymanager sections      # Section configuration details
qymanager phrase        # Phrase/sequence data analysis
qymanager map           # Visual file structure map
qymanager dump          # Annotated hex dump
qymanager bulk-summary  # Slot inventory for BULK_ALL multi-pattern files
```

**XG (tone generator) Commands:**
```bash
qymanager xg summary    # Message-count statistics by AH/AM/AL
qymanager xg inspect    # Final parsed XG state (voices, effects, system, drum setup)
qymanager xg parse      # Raw XG Parameter Change decode (one per line)
qymanager xg voices     # Voice resolution timeline (MSB/LSB/PC per channel)
```

**Extraction / Workflow Commands:**
```bash
qymanager merge         # Combine pattern bulk .syx + XG capture JSON
qymanager convert       # Convert between .syx (QY70) and .Q7P (QY700)
qymanager udm-convert   # Format-agnostic convert via UDM + lossy policy
```

**Edit Commands:**
```bash
qymanager edit          # 21 sub-commands: export/new-empty/add-note/transpose/...
qymanager field-set     # UDM path-based field edit
qymanager field-get     # UDM path-based field read
qymanager field-emit-xg # Emit just the XG Parameter Change bytes
qymanager realtime      # Live XG Parameter Change (list-ports/emit/watch)
qymanager pattern-set   # Structured pattern editing
qymanager song-set      # Song metadata edit
qymanager chord-add     # Add chord event to pattern
qymanager phrase-list   # List user phrases
```

**Utility Commands:**
```bash
qymanager diff      # Compare two Q7P files
qymanager validate  # Validate file structure
qymanager version   # Show version
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

### `qymanager audit` - Extraction Completeness Report

Report tabulare di cosa è estraibile da un `.syx` e cosa manca, con actionable suggestions. Risponde direttamente alla domanda: *"Questo file mi dà tutti i dati che mi servono?"*

```bash
qymanager audit file.syx
```

#### Esempio output (file CON XG state)

```
Audit: SGT_backup.syx (13891 bytes)

                Data extraction completeness
╭─────────────────────────────┬───┬──────────────────────────╮
│ Category                    │   │ Details                  │
├─────────────────────────────┼───┼──────────────────────────┤
│ Pattern events (edit buffer)│ ✓ │ 5/8 tracks, 2/6 sections │
│ Tempo                       │ ✓ │ 151 BPM                  │
│ Time signature              │ ~ │ 4/4 (assumed)            │
│ Pattern name directory      │ ✗ │ AH=0x05 not in file      │
│ Voice Bank/LSB/Prog (XG)    │ ✓ │ 8/8 tracks exact         │
│ Mixer (Vol/Pan/Rev/Cho)     │ ✓ │ per-track from XG        │
│ Global effects types        │ ✓ │ 1 extracted              │
│ XG System params            │ ✓ │ 2 params                 │
│ XG Drum Setup overrides     │ ✓ │ 11 note customizations   │
╰─────────────────────────────┴───┴──────────────────────────╯
Legend: ✓ complete · ~ partial/assumed · ✗ missing · — n/a
```

#### Esempio output (pattern bulk ONLY)

```
│ Voice Bank/LSB/Prog (no XG) │ ~ │ 5 via DB, 3 via class   │
│ Mixer (Vol/Pan/Rev/Cho)     │ ✗ │ no XG data — defaults   │

Suggestions:
  • No XG state → voice Bank/LSB/Prog unreliable.
    Run capture_complete.py -o full.syx on the QY70,
    or qymanager merge bulk.syx capture.json -o full.syx.
```

Quando il file è un BULK_ALL multi-slot, audit auto-reindirizza a `qymanager bulk-summary`.

---

### `qymanager merge` - Combine Pattern Bulk + XG Capture

Unisce un pattern bulk `.syx` con una capture JSON (`{"t": float, "data": "hex"}` list) in un singolo `.syx` parsabile completamente da `qymanager info`.

```bash
qymanager merge pattern.syx capture.json -o complete.syx
qymanager info complete.syx   # Ora mostra voice info completa
```

La capture JSON viene flattenata a raw MIDI bytes (SysEx + channel events) e appesa al bulk. Il parser `_parse_xg_multi_part` estrae Bank/LSB/Prog/Vol/Pan/FX dai CC (0/32/7/10/91/93) e Program Change.

**Workflow use case**: hai capturato il pattern bulk separatamente (BULK OUT → Pattern) e il MIDI stream al momento del pattern load (via `midi_tools/capture_xg_stream.py --all`). Dopo il merge hai un file che rappresenta lo stato completo.

---

### `qymanager bulk-summary` - Slot Inventory for BULK_ALL

I file di QY70 "BULK OUT → All" contengono 64 slot pattern (AM=0x00-0x3F) invece di un singolo edit buffer. `qymanager info` è per pattern singoli; questo comando lista gli slot popolati.

```bash
qymanager bulk-summary bulk_all.syx
```

#### Esempio output

```
Pattern slots populated: 33 / 64
╭──────┬─────┬────────────────────┬──────────────┬──────────╮
│ Slot │ Hdr │ Tracks             │ Sections     │ Bytes    │
├──────┼─────┼────────────────────┼──────────────┼──────────┤
│ U01  │  H  │ 1,4,5,6            │ 1            │    1281  │
│ U10  │  H  │ 1,2,3,4,5,6,7,8    │ 1,2,3,4,5,6  │   12845  │
│ ...                                                        │
╰──────┴─────┴────────────────────┴──────────────┴──────────╯

  • Song data (AH=0x01): 859 bytes
  • System meta (AH=0x03): 32 bytes
  • XG Multi Part state (Model 4C): absent — voice info limited
```

---

### `qymanager xg inspect` - Parsed XG State

Mostra lo STATO FINALE parsato dall'analyzer (vs `xg summary` che conta messaggi). Utile per verifica rapida di cosa `qymanager info` estrarrà da un file.

```bash
qymanager xg inspect file.syx
```

Output include: XG System, XG Effects, XG Multi Part per part (17 params), XG Drum Setup overrides per note. Se il file non ha XG data, mostra un helpful error con puntatore al workflow capture_complete.

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

### Complete Capture (recommended for full RE info)

```bash
uv run python3 midi_tools/capture_complete.py -o complete.syx
```

Performs in ONE session:
1. Init handshake
2. Pattern bulk request (8 tracks + header, AM=0x7E by default)
3. Pattern name directory request (AH=0x05)
4. System meta request (AH=0x03)
5. XG Multi Part bulk requests × 16 parts
6. Close handshake

Output file is parseable by `qymanager info` to extract **every XG parameter the QY70 emits**: voices, mixer, effects, drum setup, master tune. Use `--dry-run` to print the 29-message sequence without touching MIDI.

---

## SysEx Extraction — What's Possible and What's Not

> For the impatient: see [wiki/quickstart-sysex-extraction.md](wiki/quickstart-sysex-extraction.md).

The QY70 exposes pattern data across **7 distinct address families**. Not all of them are included in every bulk dump. The following table summarizes what's extractable and how:

| Data | Source | How to capture | Extraction |
|------|--------|----------------|:---:|
| Pattern events (notes, timings, gates) | `AH=0x02 AM=0x7E AL=0x00..0x2F` | `BULK OUT → Pattern` OR live | ✓ dense decoder 95-100% |
| Pattern header (tempo, sections) | `AH=0x02 AM=0x7E AL=0x7F` | Same as above | ✓ tempo exact |
| User pattern slots | `AH=0x02 AM=0x00..0x3F` | `BULK OUT → All` | ✓ via `bulk-summary` |
| Song data | `AH=0x01` | `BULK OUT → All` | ✓ presence detected |
| System meta (Master Tune/Vol) | `AH=0x03 AM=0x00` | `BULK OUT → All` | ✓ 32B parsed |
| Pattern name directory | `AH=0x05 AM=0x00 AL=0x00` | Separate dump request | ✓ 20 slot names (raw ASCII) |
| Voice Edit Dump (custom voices) | `AH=0x00 AM=0x40` | `BULK OUT → Voice` | ✓ size + voice class |
| Voice Bank/LSB/Prog per track | **XG Parameter Change (Model 4C)** | Live XG query OR capture at pattern load | ✓ via XG, ⚠ via signature DB only |
| Volume/Pan/Rev/Cho per track | XG Multi Part | Live XG query | ✓ via XG only |
| Global FX (Reverb/Chorus/Var type) | XG Effect block | Live XG query | ✓ 6 type MSB/LSB params |
| XG Drum Setup (per-note customization) | `Model 4C AH=0x30/0x31` | Live XG query | ✓ 16 params × 128 notes × 2 setups |

### Critical structural finding

**The QY70 pattern bulk dump does NOT contain resolvable voice info (Bank MSB/LSB/Program)**. The 640-byte pattern header at `AL=0x7F` encodes voice identity via an **opaque ROM-internal index** that cannot be decoded to Bank/LSB/Prog without:
- A firmware ROM dump from the QY70 chip, or
- Yamaha proprietary documentation

This was verified via 7+ iterations of byte-level analysis on 3 reference patterns (SGT, AMB01, STYLE2) across all plausible encodings (direct byte search, permutation, 7-bit unpack, 9-bit field extraction, strided blocks, bit-level brute force at every offset/width). See [wiki/pattern-header-al7f.md](wiki/pattern-header-al7f.md) for the full attack list.

### Three workflows to get everything

**Workflow A — Live capture (recommended)**

```bash
uv run python3 midi_tools/capture_complete.py -o complete.syx
uv run qymanager info complete.syx
```

This sends **29 dump requests** in one session (Init + 9 pattern + name directory + system + 16 XG Multi Part + close). Output `.syx` contains everything the QY70 emits.

**Workflow B — Merge pre-existing captures**

```bash
uv run qymanager merge pattern.syx xg_capture.json -o complete.syx
uv run qymanager info complete.syx
```

If you already captured the pattern bulk and the MIDI stream during pattern load (via `midi_tools/capture_xg_stream.py --all`), merge them into one file.

**Workflow C — Fallback (pattern bulk only, partial)**

```bash
uv run qymanager info pattern.syx          # Partial info
uv run qymanager audit pattern.syx         # See exactly what's extractable
```

Without XG data:
- **Voice class** (drum/bass/chord): reliable via B17-B20 class signature
- **Bank MSB/LSB/Prog**: via `data/voice_signature_db.json` (23 trained signatures, 21 unambiguous from 3 reference patterns) — falls back to class default for unknown signatures
- **Vol/Pan/Rev/Cho**: not available — values default to XG init (100/center/40/0)
- **FX types, Drum Setup, System params**: not available

### SysEx encoding per address

A subtle but critical detail: **not all QY70 bulk addresses use Yamaha 7-bit MSB packing**.

| AH | Encoding | Parser must use |
|:---:|----------|-----------------|
| 0x00 AM=0x40, 0x01, 0x02, 0x03 | 7-bit packed | `msg.decoded_data` |
| **0x05** | **RAW** (direct ASCII) | **`msg.data`** |
| 0x08 | Single-byte marker | N/A |

This was discovered late — `AH=0x05` pattern name directory was incorrectly being decoded, producing garbled output. See [wiki/pattern-header-al7f.md](wiki/pattern-header-al7f.md) for the full table.

---

## What's NOT yet decoded (known gaps)

| Item | Status | Why |
|------|:---:|-----|
| Time signature | ⚠ hardcoded 4/4 | All 3 reference patterns are 4/4 — no 3/4 or 6/8 sample for differential RE |
| Pattern bar count per section | ⚠ not derived | Track sizes (128/256/768B) correlate with event density, not bar count |
| Pattern name in AL=0x7F | ✗ not present | Names only in AH=0x05 directory for user slots |
| Voice Bank/LSB/Prog in bulk alone | ✗ structurally opaque | ROM index lookup without firmware access |

These are **architectural limits**, not missing features of the tool. The workarounds documented above recover the missing data via XG live capture.

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

**Quickstart guides** (recommended starting points):
- [wiki/quickstart-sysex-extraction.md](wiki/quickstart-sysex-extraction.md) — Decision tree "how to get everything from a .syx"
- [wiki/voice-extraction-workflow.md](wiki/voice-extraction-workflow.md) — 3 workflows detailed
- [STATUS.md](STATUS.md) — Project north-star (completion %, blockers, recommendation)

**Format references**:
- [docs/QY70_FORMAT.md](docs/QY70_FORMAT.md) — SysEx structure and encoding
- [docs/QY700_FORMAT.md](docs/QY700_FORMAT.md) — Binary file structure
- [wiki/pattern-header-al7f.md](wiki/pattern-header-al7f.md) — **640B pattern header structural map + voice encoding opacity analysis**
- [wiki/sysex-format.md](wiki/sysex-format.md) — QY70 SysEx bulk dump format (Sequencer Model 0x5F)
- [wiki/xg-multi-part.md](wiki/xg-multi-part.md) — XG Multi Part parameter reference (Model 0x4C)

**Session log & history**:
- [wiki/log.md](wiki/log.md) — Chronological session record
- [wiki/index.md](wiki/index.md) — Full wiki index
- [wiki/decoder-status.md](wiki/decoder-status.md) — Per-component RE confidence
- [wiki/open-questions.md](wiki/open-questions.md) — Unresolved hypotheses

---

## License

MIT License - see [LICENSE](LICENSE) for details.
