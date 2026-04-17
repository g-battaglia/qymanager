# Project Overview

**qyconv** converts pattern/style data between Yamaha [QY70](qy70-device.md) (SysEx `.syx`) and [QY700](qy700-device.md) (binary `.Q7P`) formats.

## Architecture

```
qymanager/           Core library
├── analysis/        q7p_analyzer.py, syx_analyzer.py
├── converters/      qy70_to_qy700.py, qy700_to_qy70.py
├── formats/qy70/    SysEx parser (sysex_parser.py)
├── formats/qy700/   Binary parser
├── models/          Pattern, Section, Track dataclasses
└── utils/           7-bit codec, checksum, xg_voices

cli/                 CLI (Typer + Rich)
├── app.py           Entry point
├── commands/        info, convert, diff, validate, dump, map, tracks, sections, phrase, edit
└── display/         Rich tables and formatters

midi_tools/          Reverse engineering scripts
├── event_decoder.py Chord/general track bitstream decoder
├── midi_status.py   MIDI diagnostics + device identification
├── send_request.py  SysEx dump request sender
├── capture_dump.py  Bulk dump capture
└── captured/        Captured .syx files
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `info` | Pattern info (basic or `--full`) |
| `tracks` | Track details with bar graphics |
| `sections` | Section configuration |
| `phrase` | Phrase/sequence analysis |
| `map` | Visual file structure map |
| `dump` | Annotated hex dump |
| `diff` | Compare two files |
| `validate` | Validate file structure |
| `convert` | Format conversion |

## Test Fixtures

| File | Description |
|------|-------------|
| `T01.Q7P` | Pattern with data (120 BPM, 1 section active) |
| `TXX.Q7P` | Empty template (5 sections active, all default) |
| `QY70_SGT.syx` | QY70 style (~16KB, 105 messages, 155 BPM) |

## Build & Test

```bash
cd /Volumes/Data/DK/XG/T700/qyconv
source .venv/bin/activate
pip install -e ".[dev]"
pytest                    # 33 tests, all green
PYTHONPATH=. python3 cli/app.py info tests/fixtures/T01.Q7P
```
