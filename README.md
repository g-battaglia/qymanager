# QYConv

Bidirectional converter for Yamaha QY70 and QY700 pattern files.

## Overview

QYConv is a Python library and CLI tool for converting pattern/style data between Yamaha QY70 SysEx files (.syx) and QY700 binary pattern files (.Q7P).

## Features

- **Read QY70 SysEx files**: Parse bulk dump messages with 7-bit decoding
- **Read QY700 Q7P files**: Parse binary pattern structure
- **Write to both formats**: Generate valid files for each device
- **Bidirectional conversion**: QY70 ↔ QY700
- **Common data model**: Unified representation of patterns, sections, and tracks

## Installation

```bash
# From source
git clone https://github.com/qyconv/qyconv.git
cd qyconv
pip install -e .

# With development dependencies
pip install -e ".[dev]"
```

## Quick Start

### Reading Files

```python
from qyconv import QY70Reader, QY700Reader

# Read QY70 SysEx file
pattern = QY70Reader.read("style.syx")
print(f"Pattern: {pattern.name}, Tempo: {pattern.tempo}")

# Read QY700 Q7P file
pattern = QY700Reader.read("pattern.Q7P")
for section_type, section in pattern.sections.items():
    print(f"  {section_type.name}: {len(section.tracks)} tracks")
```

### Writing Files

```python
from qyconv import QY70Writer, QY700Writer, Pattern

# Create a new pattern
pattern = Pattern.create_empty("MY STYLE", tempo=120)

# Write to QY70 SysEx format
QY70Writer.write(pattern, "output.syx")

# Write to QY700 Q7P format
QY700Writer.write(pattern, "output.Q7P")
```

### Converting Between Formats

```python
from qyconv import QY70Reader, QY700Writer

# QY70 → QY700
pattern = QY70Reader.read("source.syx")
QY700Writer.write(pattern, "converted.Q7P")

# QY700 → QY70
from qyconv import QY700Reader, QY70Writer
pattern = QY700Reader.read("source.Q7P")
QY70Writer.write(pattern, "converted.syx")
```

## CLI Usage

```bash
# Convert QY70 to QY700
qyconv style.syx --output pattern.Q7P

# Convert QY700 to QY70
qyconv pattern.Q7P --output style.syx

# Get file info
qyconv --info pattern.Q7P
```

## File Formats

### QY70 SysEx (.syx)

The QY70 uses System Exclusive (SysEx) messages for data transfer:
- Manufacturer ID: 0x43 (Yamaha)
- Model ID: 0x5F (QY70)
- Data encoding: 7-bit packed (8 bytes encode 7 bytes of data)
- Checksum: Per-message validation

### QY700 Binary (.Q7P)

The QY700 uses a fixed-size binary format:
- File size: 3072 bytes (fixed)
- Header: "YQ7PAT     V1.00"
- Data: Raw 8-bit, no compression
- Structure: Header + sections + tracks + phrases

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

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run with coverage
pytest --cov=qyconv

# Format code
black qyconv tests

# Lint
ruff check qyconv
```

## Documentation

See the [docs](docs/) folder for detailed documentation:
- [QY70 Format](docs/QY70_FORMAT.md) - SysEx structure and encoding
- [QY700 Format](docs/QY700_FORMAT.md) - Binary file structure
- [Conversion Notes](docs/CONVERSION_NOTES.md) - Format differences and mapping

## Limitations

- **Phrase data**: Full phrase/event extraction is in progress
- **Voice data**: XG voice parameters partially supported
- **Chord tables**: Basic support only
- **Testing**: Requires validation on actual hardware

## Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Submit a pull request

## License

MIT License - see [LICENSE](LICENSE) for details.

## Acknowledgments

- Yamaha QY70/QY700 documentation and MIDI implementation charts
- The retro music hardware community
