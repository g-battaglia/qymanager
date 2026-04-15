# QYConv Wiki

Knowledge base for the QY70/QY700 reverse engineering and conversion project.

## Devices

- [QY70](qy70-device.md) — Yamaha QY70 portable sequencer/style player
- [QY700](qy700-device.md) — Yamaha QY700 workstation sequencer
- [Identity Reply Codes](identity-reply.md) — MIDI Identity Reply device identification

## File Formats

- [SysEx Format](sysex-format.md) — QY70 System Exclusive bulk dump format
- [BLK Format](blk-format.md) — QY Data Filer bulk file format (.blk = raw SysEx)
- [Q7P Format](q7p-format.md) — QY700 binary pattern file format
- [7-Bit Encoding](7bit-encoding.md) — Yamaha 7-bit MIDI data packing scheme
- [Format Mapping](format-mapping.md) — Cross-format field mapping QY70 ↔ QY700
- [QYFiler Reverse Engineering](qyfiler-reverse-engineering.md) — Disassembly of Yamaha QY Data Filer (Windows)

## Track & Event Data

- [Track Structure](track-structure.md) — Track layout, slot names, AL addressing
- [Header Section](header-section.md) — Global pattern/style header (AL=0x7F, 640 bytes)
- [Bitstream Encoding](bitstream.md) — R=9 rotation, 9-bit field packing, preambles
- [Bar Structure](bar-structure.md) — 13-byte bar headers, DC/9E delimiters
- [Event Fields](event-fields.md) — F0-F5 field decomposition, beat counter, chord mask (1FA3)
- [2543 Encoding](2543-encoding.md) — Drum/pattern encoding: R=9×(i+1) PROVEN, F0=note, F5=gate
- [XG Defaults](xg-defaults.md) — Yamaha XG default parameter values

## Infrastructure

- [MIDI Setup](midi-setup.md) — Hardware connection, Steinberg UR22C, bulk dump procedure
- [Project Overview](overview.md) — Goals, architecture, CLI commands, test fixtures

## Status & History

- [Conversion Roadmap](conversion-roadmap.md) — End-to-end conversion status and blocking issues
- [Decoder Status](decoder-status.md) — Current decoding confidence per track type
- [Bricking Diagnosis](bricking.md) — QY700 bricking cause, fix, and safety rules
- [Open Questions](open-questions.md) — Unresolved hypotheses and next steps
- [Log](log.md) — Chronological record of sessions and discoveries
