# QY Manager

Bidirectional converter and manager for Yamaha QY70 and QY700 pattern files.

## Overview

QY Manager (formerly QYConv) is a Python library and CLI tool for converting, analyzing, and editing pattern/style data between Yamaha QY70 SysEx files (.syx) and QY700 binary pattern files (.Q7P).

## Features

- **Modern CLI** with Rich formatting, bar graphics, and progress indicators
- **Complete pattern analysis** - view ALL configuration data with visual representations
- **Bidirectional conversion** - QY70 ↔ QY700
- **Read/Write both formats** - Parse and generate valid files
- **Hex dump inspection** - Raw data analysis with annotated regions
- **File structure visualization** - Visual maps and density analysis
- **Programmatic editing** - Modify patterns via Python API

## Installation

```bash
# From source
git clone https://github.com/qymanager/qymanager.git
cd qymanager
pip install -e .

# With development dependencies
pip install -e ".[dev]"
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
