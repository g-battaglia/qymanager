# QY Manager Examples

This directory contains example scripts demonstrating how to use the `qymanager` library.

## Examples

### basic_analysis.py
Basic pattern analysis showing how to extract pattern information from Q7P files.

```bash
cd examples
python basic_analysis.py
```

### convert_patterns.py
Demonstrates bidirectional conversion between QY70 SysEx and QY700 Q7P formats.

```bash
python convert_patterns.py
```

### sysex_analysis.py
Detailed analysis of QY70 SysEx file structure, showing message statistics and section breakdown.

```bash
python sysex_analysis.py
```

### compare_patterns.py
Compare two Q7P pattern files and show differences in configuration.

```bash
python compare_patterns.py
```

### hex_inspection.py
Raw hex dump and binary data inspection for reverse engineering.

```bash
python hex_inspection.py
```

### modify_pattern.py
Programmatically modify pattern settings (tempo, name, volume).

```bash
python modify_pattern.py
```

## Requirements

Make sure you're in the project root directory or have `qymanager` installed:

```bash
# From project root
cd /path/to/qymanager
pip install -e .

# Or run with PYTHONPATH
PYTHONPATH=.. python examples/basic_analysis.py
```

## Test Files

The examples use test files from `tests/fixtures/`:
- `T01.Q7P` - QY700 pattern with data
- `TXX.Q7P` - QY700 empty template
- `QY70_SGT.syx` - QY70 style file
