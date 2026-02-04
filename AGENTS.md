# AGENTS.md - Coding Agent Instructions for qyconv

## Project Overview

QYConv is a Python library and CLI for converting pattern/style data between
Yamaha QY70 SysEx (.syx) and QY700 binary (.Q7P) formats. Both use Yamaha XG.

**Key domains**: MIDI, SysEx, binary file parsing, Yamaha XG synthesizers.

**Version**: 0.3.0

---

## Build and Run Commands

```bash
# Setup (REQUIRED first)
cd /Volumes/Data/DK/XG/T700/qyconv
source .venv/bin/activate
pip install -e ".[dev]"

# Run CLI
PYTHONPATH=. python3 cli/app.py info tests/fixtures/T01.Q7P
PYTHONPATH=. python3 cli/app.py info tests/fixtures/T01.Q7P --full
PYTHONPATH=. python3 cli/app.py convert input.syx -o output.Q7P
```

## Available CLI Commands

| Command | Description | Example |
|---------|-------------|---------|
| `info` | Pattern info (basic or --full) | `info T01.Q7P --full` |
| `tracks` | Track details with bar graphics | `tracks T01.Q7P --track 1` |
| `sections` | Section configuration | `sections T01.Q7P --active` |
| `phrase` | Phrase/sequence analysis | `phrase T01.Q7P --heatmap` |
| `map` | Visual file structure map | `map T01.Q7P --detailed` |
| `dump` | Annotated hex dump | `dump T01.Q7P --region PHRASE` |
| `diff` | Compare two files | `diff T01.Q7P TXX.Q7P` |
| `validate` | Validate file structure | `validate T01.Q7P --strict` |
| `convert` | Format conversion | `convert in.syx -o out.Q7P` |

## Test Commands

```bash
pytest                                              # All tests
pytest tests/test_7bit_codec.py                     # Single file
pytest tests/test_7bit_codec.py::TestYamaha7BitCodec::test_roundtrip  # Single test
pytest -v                                           # Verbose
pytest --cov=qyconv                                 # With coverage
pytest -k "codec"                                   # Pattern match
```

## Linting and Formatting

```bash
black qyconv cli tests          # Format (line-length 100)
ruff check qyconv cli           # Lint
ruff check --fix qyconv cli     # Lint + autofix
mypy qyconv cli                 # Type check
```

---

## Code Style Guidelines

### Formatting
- **Line length**: 100 chars | **Formatter**: Black | **Linter**: Ruff
- **Python**: 3.9+ | **Quotes**: Double | **Indent**: 4 spaces

### Import Order
```python
# 1. Standard library
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# 2. Third-party
from rich.console import Console

# 3. Local
from qyconv.models.pattern import Pattern
```

### Naming Conventions
| Type | Style | Example |
|------|-------|---------|
| Classes | PascalCase | `Q7PAnalyzer`, `TrackInfo` |
| Functions | snake_case | `parse_tempo`, `get_channels` |
| Constants | UPPER_SNAKE | `FILE_SIZE`, `HEADER_MAGIC` |
| Private | _prefix | `_get_byte`, `_analyze` |

### Type Hints (Required)
```python
def parse_tempo(data: bytes, offset: int = 0x188) -> Tuple[float, Tuple[int, int]]:
    """Parse tempo from Q7P data."""
```

### Docstrings
```python
def decode_7bit(encoded_data: Union[bytes, List[int]]) -> bytes:
    """Decode Yamaha 7-bit packed data to 8-bit raw data.

    Args:
        encoded_data: The 7-bit encoded data from SysEx

    Returns:
        Decoded 8-bit raw data
    """
```

### Error Handling
- Use `ValueError` for invalid input
- Early returns for validation
- Document exceptions in docstrings

### Dataclasses
```python
@dataclass
class TrackInfo:
    number: int
    name: str
    channel: int
    program: int = 0  # Defaults for optional fields
```

---

## Project Structure

```
qyconv/
├── cli/                    # CLI (Typer + Rich)
│   ├── app.py             # Entry point, command registration
│   ├── commands/          # Command implementations
│   │   ├── info.py        # info command (+ --full)
│   │   ├── convert.py     # convert command
│   │   ├── diff.py        # diff command
│   │   ├── validate.py    # validate command
│   │   ├── dump.py        # dump command (hex)
│   │   ├── map.py         # map command (visual)
│   │   ├── tracks.py      # tracks command
│   │   ├── sections.py    # sections command
│   │   └── phrase.py      # phrase command
│   └── display/           # Rich formatting
│       ├── tables.py      # Table displays
│       └── formatters.py  # Bar graphics, formatting utils
├── qyconv/                # Core library
│   ├── analysis/          # q7p_analyzer, syx_analyzer
│   ├── converters/        # qy70_to_qy700, qy700_to_qy70
│   ├── formats/qy70/      # SysEx parser
│   ├── formats/qy700/     # Binary parser
│   ├── models/            # Pattern, Section, Track
│   └── utils/             # 7-bit codec, checksum, xg_voices
├── tests/fixtures/        # T01.Q7P, TXX.Q7P, QY70_SGT.syx
└── docs/                  # QY70_FORMAT.md, QY700_FORMAT.md
```

---

## Domain Knowledge

### Q7P File (QY700)
- Fixed 3072 bytes, header "YQ7PAT     V1.00"
- Big-endian multi-byte values
- Key offsets: 0x188=tempo, 0x190=channels, 0x226=volume, 0x256=reverb, 0x276=pan, 0x876=name
- Empty sections: 0xFEFE pointer | Fill: 0xFE | Padding: 0xF8

### SysEx (QY70)
- Manufacturer: 0x43 (Yamaha), Model: 0x5F
- 7-bit packing: 8 encoded bytes = 7 data bytes
- Checksum: sum of address + data, 2's complement

### XG Reference
- https://www.studio4all.de/htmle/main90.html
- 16 MIDI channels, channel 10 = drums
- Bank Select MSB/LSB + Program Change for voices

### XG Default Values
| Parameter | Default | Hex |
|-----------|---------|-----|
| Volume | 100 | 0x64 |
| Pan | 64 (Center) | 0x40 |
| Reverb Send | 40 | 0x28 |
| Chorus Send | 0 | 0x00 |
| Bank MSB (Drums) | 127 | 0x7F |

---

## Test Fixtures

| File | Description |
|------|-------------|
| `T01.Q7P` | Pattern with data (tempo 120, 1 section active) |
| `TXX.Q7P` | Empty template (5 sections active) |
| `QY70_SGT.syx` | QY70 style (16KB, 105 messages) |

```python
def test_example(q7p_data):  # Fixture from conftest.py
    analyzer = Q7PAnalyzer()
    analysis = analyzer.analyze_bytes(q7p_data)
    assert analysis.tempo == 120.0
```

---

## Common Gotchas

1. **PYTHONPATH**: Set `PYTHONPATH=.` when running from source
2. **Virtual env**: Always activate `.venv` before commands
3. **Byte order**: Q7P uses big-endian for 16-bit values
4. **7-bit encoding**: SysEx data must be decoded before use
5. **Pan values**: 0 = Random (not L64), 64 = center
6. **Channel 0**: Raw value 0x00 = Channel 10 (drums) for RHY tracks
7. **Volume offset**: Data at 0x226 (not 0x220, which is header)
8. **Pan offset**: Data at 0x276 (not 0x270, which is header)
9. **Reverb offset**: Data at 0x256

---

## Display Formatting

### Bar Graphics (from formatters.py)

```python
from cli.display.formatters import value_bar, pan_bar

# Volume bar
value_bar(91)  # "91 [████████░░░░] 71%"

# Pan bar (centered)
pan_bar(64)    # " C [─────●─────] 50%"
pan_bar(32)    # "L32 [◀◀◀──●─────] 25%"
```

### Color Scheme
- **cyan**: Region names, parameter labels
- **green**: Active/enabled, notes in range
- **yellow**: Non-default values, warnings
- **red**: Errors, disabled
- **dim**: Filler bytes, empty areas
