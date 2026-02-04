# AGENTS.md - Coding Agent Instructions for qyconv

## Project Overview

QYConv is a Python library and CLI for converting pattern/style data between
Yamaha QY70 SysEx (.syx) and QY700 binary (.Q7P) formats. Both use Yamaha XG.

**Key domains**: MIDI, SysEx, binary file parsing, Yamaha XG synthesizers.

---

## Build and Run Commands

```bash
# Setup (REQUIRED first)
cd /Volumes/Data/DK/XG/T700/qyconv
source .venv/bin/activate
pip install -e ".[dev]"

# Run CLI
PYTHONPATH=. python3 cli/app.py info tests/fixtures/T01.Q7P
PYTHONPATH=. python3 cli/app.py convert input.syx -o output.Q7P
```

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
│   ├── app.py             # Entry point
│   ├── commands/          # info, convert
│   └── display/           # Rich tables
├── qyconv/                # Core library
│   ├── analysis/          # q7p_analyzer, syx_analyzer
│   ├── converters/        # qy70_to_qy700, qy700_to_qy70
│   ├── formats/qy70/      # SysEx parser
│   ├── formats/qy700/     # Binary parser
│   ├── models/            # Pattern, Section, Track
│   └── utils/             # 7-bit codec, checksum
├── tests/fixtures/        # T01.Q7P, TXX.Q7P, QY70_SGT.syx
└── docs/                  # QY70_FORMAT.md, QY700_FORMAT.md
```

---

## Domain Knowledge

### Q7P File (QY700)
- Fixed 3072 bytes, header "YQ7PAT     V1.00"
- Big-endian multi-byte values
- Key offsets: 0x188=tempo, 0x190=channels, 0x876=name
- Empty sections: 0xFEFE pointer | Fill: 0xFE | Padding: 0xF8

### SysEx (QY70)
- Manufacturer: 0x43 (Yamaha), Model: 0x5F
- 7-bit packing: 8 encoded bytes = 7 data bytes
- Checksum: sum of address + data, 2's complement

### XG Reference
- https://www.studio4all.de/htmle/main90.html
- 16 MIDI channels, channel 10 = drums
- Bank Select MSB/LSB + Program Change for voices

---

## Test Fixtures

| File | Description |
|------|-------------|
| `T01.Q7P` | Pattern with data (tempo 120, 1 section) |
| `TXX.Q7P` | Empty template |
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
5. **Pan values**: 0 = "not set" (not L64), 64 = center
6. **Channel 0**: Raw value 0x00 might mean channel 10 (drums)
