# QYConv

Bidirectional converter and analyzer for Yamaha QY70 and QY700 pattern files.

## Overview

QYConv is a Python library and CLI tool for converting, analyzing, and editing pattern/style data between Yamaha QY70 SysEx files (.syx) and QY700 binary pattern files (.Q7P).

## Features

- **Modern CLI** with Rich formatting and progress indicators
- **Complete pattern analysis** - view ALL configuration data
- **Bidirectional conversion** - QY70 ↔ QY700
- **Read/Write both formats** - Parse and generate valid files
- **Hex dump inspection** - Raw data analysis for reverse engineering
- **Programmatic editing** - Modify patterns via Python API

## Installation

```bash
# From source
git clone https://github.com/qyconv/qyconv.git
cd qyconv
pip install -e .

# With development dependencies
pip install -e ".[dev]"
```

## CLI Usage

QYConv provides a modern command-line interface powered by [Typer](https://typer.tiangolo.com/) and [Rich](https://rich.readthedocs.io/).

### Commands Overview

```bash
qyconv --help              # Show all commands
qyconv info --help         # Show info command options
qyconv convert --help      # Show convert command options
qyconv --version           # Show version
```

---

### `qyconv info` - Pattern Analysis

Display complete pattern information from Q7P or SysEx files.

```bash
# Basic info
qyconv info pattern.Q7P
qyconv info style.syx

# With hex dumps of data areas
qyconv info pattern.Q7P --hex

# Include unknown/reserved areas
qyconv info pattern.Q7P --raw

# Output as JSON
qyconv info pattern.Q7P --json

# Show individual SysEx messages (for .syx files)
qyconv info style.syx --messages
```

#### Options

| Option | Short | Description |
|--------|-------|-------------|
| `--hex` | `-x` | Show hex dumps of data areas |
| `--raw` | `-r` | Show unknown/reserved areas |
| `--messages` | `-m` | Show individual SysEx messages |
| `--sections/--no-sections` | `-s` | Show/hide section details |
| `--json` | `-j` | Output as JSON |

#### Example Output (Q7P)

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
│ Time Signature: 4/4               │
│ Flags: 0x00                       │
╰───────────────────────────────────╯

                    Sections
╭───┬────────────┬──────────┬──────────┬─────────────────╮
│ # │ Name       │ Status   │ Pointer  │ Config Preview  │
├───┼────────────┼──────────┼──────────┼─────────────────┤
│ 0 │ Intro      │ Active   │ 0020     │ F0 00 FB 00 ... │
│ 1 │ Main A     │ Empty    │ fefe     │ 64 41 64 64 ... │
│ 2 │ Main B     │ Empty    │ fefe     │ 40 40 40 40 ... │
│ 3 │ Fill AB    │ Empty    │ fefe     │ 00 00 00 00 ... │
│ 4 │ Fill BA    │ Empty    │ fefe     │ 28 00 28 28 ... │
│ 5 │ Ending     │ Empty    │ fefe     │ 00 32 00 00 ... │
╰───┴────────────┴──────────┴──────────┴─────────────────╯

              Track Configuration
╭─────┬──────┬──────┬───────┬───────┬────────╮
│ #   │ Name │ Ch   │ Vol   │ Pan   │ Status │
├─────┼──────┼──────┼───────┼───────┼────────┤
│ 1   │ RHY1 │ 10   │ 100   │ C     │ On     │
│ 2   │ RHY2 │ 10   │ 100   │ C     │ Off    │
│ 3   │ BASS │ 9    │ 100   │ C     │ Off    │
│ ... │      │      │       │       │        │
╰─────┴──────┴──────┴───────┴───────┴────────╯
```

---

### `qyconv convert` - Format Conversion

Convert between QY70 SysEx and QY700 Q7P formats.

```bash
# QY70 → QY700
qyconv convert style.syx -o pattern.Q7P

# QY700 → QY70
qyconv convert pattern.Q7P -o style.syx

# Use template for better Q7P structure preservation
qyconv convert style.syx -o pattern.Q7P -t template.Q7P

# Verbose output
qyconv convert style.syx -o pattern.Q7P -v
```

#### Options

| Option | Short | Description |
|--------|-------|-------------|
| `--output` | `-o` | Output file path |
| `--template` | `-t` | Template Q7P file for conversion |
| `--verbose` | `-v` | Show detailed progress |

#### Conversion Notes

- **QY70 → QY700**: Uses template-based approach to preserve unknown structure areas
- **QY700 → QY70**: Generates complete SysEx bulk dump with valid checksums
- Auto-detects format based on file extension

---

## Python API

### Reading Files

```python
from qyconv.formats.qy70.reader import QY70Reader
from qyconv.formats.qy700.reader import QY700Reader

# Read QY70 SysEx file
pattern = QY70Reader.read("style.syx")
print(f"Pattern: {pattern.name}, Tempo: {pattern.tempo}")

# Read QY700 Q7P file
pattern = QY700Reader.read("pattern.Q7P")
for section_type, section in pattern.sections.items():
    print(f"  {section_type.name}: {len(section.tracks)} tracks")
```

### Pattern Analysis

```python
from qyconv.analysis.q7p_analyzer import Q7PAnalyzer
from qyconv.analysis.syx_analyzer import SyxAnalyzer

# Analyze Q7P file
analyzer = Q7PAnalyzer()
analysis = analyzer.analyze_file("pattern.Q7P")

print(f"Pattern: {analysis.pattern_name}")
print(f"Tempo: {analysis.tempo} BPM")
print(f"Active sections: {analysis.active_section_count}")
print(f"Data density: {analysis.data_density:.1f}%")

# Access raw data areas
print(f"Header: {analysis.header_raw.hex()}")
print(f"Section pointers: {analysis.section_pointers_raw.hex()}")

# Analyze SysEx file
syx_analyzer = SyxAnalyzer()
syx_analysis = syx_analyzer.analyze_file("style.syx")

print(f"Messages: {syx_analysis.total_messages}")
print(f"Valid checksums: {syx_analysis.valid_checksums}")
```

### Converting Between Formats

```python
from qyconv.converters import convert_qy70_to_qy700, convert_qy700_to_qy70

# QY70 → QY700
convert_qy70_to_qy700(
    source_path="style.syx",
    output_path="pattern.Q7P",
    template_path="template.Q7P"  # Optional
)

# QY700 → QY70
convert_qy700_to_qy70(
    source_path="pattern.Q7P",
    output_path="style.syx"
)
```

### Programmatic Editing

```python
import struct

# Load and modify Q7P file directly
with open("pattern.Q7P", "rb") as f:
    data = bytearray(f.read())

# Change tempo (at 0x188, big-endian, value * 10)
new_tempo = 140  # BPM
struct.pack_into(">H", data, 0x188, new_tempo * 10)

# Change pattern name (at 0x876, 10 bytes ASCII)
name = "MY STYLE  ".encode('ascii')
data[0x876:0x886] = name

# Save modified file
with open("modified.Q7P", "wb") as f:
    f.write(data)
```

---

## Examples

The `examples/` directory contains demonstration scripts:

| Script | Description |
|--------|-------------|
| `basic_analysis.py` | Extract pattern info from Q7P files |
| `convert_patterns.py` | Bidirectional format conversion |
| `sysex_analysis.py` | QY70 SysEx structure breakdown |
| `compare_patterns.py` | Diff two pattern files |
| `hex_inspection.py` | Raw binary data inspection |
| `modify_pattern.py` | Programmatic pattern editing |

```bash
cd examples
python basic_analysis.py
```

---

## File Formats

### QY70 SysEx (.syx)

The QY70 uses System Exclusive (SysEx) messages for data transfer:

| Property | Value |
|----------|-------|
| Manufacturer ID | 0x43 (Yamaha) |
| Model ID | 0x5F (QY70) |
| Data encoding | 7-bit packed (8 bytes → 7 bytes) |
| Checksum | Per-message (BH BL AH AM AL + data) |

**Bulk Dump Format:**
```
F0 43 0n 5F BH BL AH AM AL [data...] CS F7
```

### QY700 Binary (.Q7P)

The QY700 uses a fixed-size binary format:

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
| 0x120 | 96 | Section config data |
| 0x188 | 2 | Tempo (BE, ÷10 for BPM) |
| 0x190 | 8 | Channel assignments |
| 0x1DC | 8 | Track numbers |
| 0x1E4 | 2 | Track enable flags |
| 0x220 | 80 | Volume table |
| 0x270 | 80 | Pan table |
| 0x360 | 792 | Phrase data |
| 0x876 | 10 | Pattern name |

---

## Pattern Structure

Both formats organize patterns similarly:

```
Pattern
├── Settings (tempo, volume, etc.)
├── Sections (6 types)
│   ├── Intro
│   ├── Main A / Main B
│   ├── Fill A→B / Fill B→A
│   └── Ending
└── Each Section has 8 Tracks
    ├── Track 1-2: Rhythm (drums)
    ├── Track 3: Bass
    └── Track 4-8: Chord accompaniment
```

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

# Run with coverage
pytest --cov=qyconv

# Format code
black qyconv cli tests

# Lint
ruff check qyconv cli
```

---

## Documentation

See the [docs](docs/) folder for detailed documentation:

- [QY70 Format](docs/QY70_FORMAT.md) - SysEx structure and encoding
- [QY700 Format](docs/QY700_FORMAT.md) - Binary file structure

---

## Limitations

- **Phrase data**: MIDI event extraction is simplified
- **Voice data**: XG voice parameters partially supported
- **Chord tables**: Basic support only
- **Testing**: Hardware validation recommended

---

## Roadmap

- [ ] `qyconv analyze` - Detailed MIDI event analysis
- [ ] `qyconv serve` - Web-based editor (FastAPI + HTMX)
- [ ] `qyconv diff` - Side-by-side pattern comparison
- [ ] Audio preview support

---

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Submit a pull request

---

## License

MIT License - see [LICENSE](LICENSE) for details.

---

## Acknowledgments

- Yamaha QY70/QY700 documentation and MIDI implementation charts
- The retro music hardware community
