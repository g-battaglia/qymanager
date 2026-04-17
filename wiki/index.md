# QYConv Wiki

Knowledge base for the QY70/QY700 reverse engineering and conversion project.

## Devices

### QY70
- [QY70 Device](qy70-device.md) — Yamaha QY70 portable sequencer/style player
- [QY70 Modes](qy70-modes.md) — 7 mode overview (Song/Pattern/Voice/Effect/Utility/Job/Edit)
- [QY70 Menu Tree](qy70-menu-tree.md) — Mappa navigazione completa (modi, sotto-menu, F-key, parametri range/default)
- [QY70 Voice List](qy70-voice-list.md) — 519 XG Normal + 20 Drum Kits architecture
- [QY70 Drum Kits](qy70-drum-kits.md) — Note mapping per-kit (13-91 range)
- [QY70 Preset Phrases](qy70-preset-phrases.md) — 4167 preset + 384 user, 12 categorie
- [QY70 Groove Templates](qy70-groove-templates.md) — 100 templates (TIMING/VELOC 0-200)

### QY700
- [QY700 Device](qy700-device.md) — Yamaha QY700 workstation sequencer
- [QY700 Menu Tree](qy700-menu-tree.md) — Mappa navigazione completa (mode/submode/pagina/parametri)
- [QY700 Song Mode](qy700-song-mode.md) — Song/sequence structure (20 songs, 32 tracks)
- [QY700 Pattern Mode](qy700-pattern-mode.md) — 64 styles, 8 sections, phrase categories
- [QY700 Voice Mode](qy700-voice-mode.md) — Voice/volume/pan assignment per-part
- [QY700 Effect Mode](qy700-effect-mode.md) — Reverb/Chorus/Variation configuration
- [QY700 Utility Mode](qy700-utility-mode.md) — System/MIDI/Filter/Sequencer/Click/Fingered Zone
- [QY700 Disk Mode](qy700-disk-mode.md) — Floppy disk file I/O (Q7A/Q7P/Q7S/ESQ/MID)
- [QY700 Phrase Lists](qy700-phrase-lists.md) — Preset phrase numbering conventions (3,876 preset)
- [QY700 Chord Types](qy700-chord-types.md) — 28 chord types + THRU, root notes, intervals
- [QY700 Groove Templates](qy700-groove-templates.md) — 100 Play Effect preset templates
- [QY700 Troubleshooting](qy700-troubleshooting.md) — Error messages, common problems, fixes
- [QY700 MIDI Protocol](qy700-midi-protocol.md) — XG SysEx protocol, dump request, parameter tables

### Identity
- [Identity Reply Codes](identity-reply.md) — MIDI Identity Reply device identification

## File Formats

- [SysEx Format](sysex-format.md) — QY70 System Exclusive bulk dump format (Sequencer Model 5F)
- [BLK Format](blk-format.md) — QY Data Filer bulk file format (.blk = raw SysEx)
- [Q7P Format](q7p-format.md) — QY700 binary pattern file format
- [7-Bit Encoding](7bit-encoding.md) — Yamaha 7-bit MIDI data packing scheme
- [Format Mapping](format-mapping.md) — Cross-format field mapping QY70 ↔ QY700
- [QYFiler Reverse Engineering](qyfiler-reverse-engineering.md) — Disassembly of Yamaha QY Data Filer (Windows)
- [QY Data Filer (User)](qy-data-filer.md) — User-facing Data Filer software documentation
- [QY70 Bulk Dump](qy70-bulk-dump.md) — Hardware bulk dump procedure QY70 ↔ PC

## XG Protocol (Model 4C)

- **[XG Parameters — Hub](xg-parameters.md)** — **SysEx format, persistenza Param Change vs Pattern Events, strategie di RE**
- [XG System](xg-system.md) — Master Tune/Volume/Transpose, System reset, XG On, standard MIDI CC
- [XG Multi Part](xg-multi-part.md) — Part setup per le 16 parti (~70 parametri)
- [XG Drum Setup](xg-drum-setup.md) — Drum Setup 1/2 per-note (pitch, level, pan, EG, filter)
- [XG Effects](xg-effects.md) — Reverb, Chorus, Variation type code e parametri

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
- [Pattern Backup & Restore](pattern-restore.md) — Capture QY70 patterns to .syx, restore via MIDI
- [Pattern Directory](pattern-directory.md) — AH=0x05 user pattern name list (20 × 16B)
- [Pattern Editor](pattern-editor.md) — Pipeline B CLI editor: export/edit/build (Session 29f)

## Status & History

- **[../STATUS.md](../STATUS.md)** — **Project north-star: % completion, cosa funziona, raccomandazione strategica (single-source recap)**
- [Conversion Roadmap](conversion-roadmap.md) — End-to-end conversion status and blocking issues
- [Decoder Status](decoder-status.md) — Current decoding confidence per track type
- [Bricking Diagnosis](bricking.md) — QY700 bricking cause, fix, and safety rules
- [Hardware Quirks](quirks.md) — Non-documented QY70 behaviour (primo-bulk-only, XG PARM OUT gap, ...)
- [Open Questions](open-questions.md) — Unresolved hypotheses and next steps
- [Log](log.md) — Chronological record of sessions and discoveries
