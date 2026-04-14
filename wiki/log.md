# Log

Chronological record of sessions, discoveries, and wiki changes.

## [2026-04-14] wiki-create | Initial wiki from 12 sessions of knowledge

Created wiki from accumulated knowledge across docs/, midi_tools/, and session notes.
Major sources: QY70_FORMAT.md (41K), QY700_FORMAT.md (18K), SESSION_RECAP.md, event_decoder.py.

## [2026-04-14] session-12 | Delimiters, beat counter fix, R equivalence

- Discovered 0x9E sub-bar delimiter (chord changes within a bar)
- Fixed lo4=0 → beat 0 (was treated as invalid)
- Proved R=9 right-rotate = R=47 left-rotate (same operation on 56 bits)
- Chord confidence: 68% → 82%, beat accuracy: 48% → 90%
- Online search for .syx files: no free downloads found

## [2026-02-26] session-11 | Bricking diagnosis and safety fixes

- Identified bricking cause: voice writes to unconfirmed offsets 0x1E6/0x1F6/0x206
- Disabled _extract_and_apply_voices(), fixed pan bounds check
- Added post-conversion validation

## [2026-02-20] sessions-6-10 | Bitstream reverse engineering

- Discovered R=9 barrel rotation and 9-bit field structure
- Decoded F3 (beat counter), F4 (chord mask), F5 (timing)
- Confirmed preamble-based encoding: 1FA3=chord, 29CB=general, 2BE3=bass, 2543=drum
- Built event_decoder.py (900+ lines)

## [2026-02-10] sessions-3-5 | Core library bug fixes

- Fixed 16 bugs in core library (channel mapping, pan display, time sig, AL schema, checksum, etc.)
- Added voice transfer to both converters
- Created NEONGROOVE.syx custom style
- Documented QY70 empty-marker pattern BF DF EF F7 FB FD FE

## [2026-02-01] sessions-1-2 | Infrastructure and MIDI setup

- Established MIDI connection via Steinberg UR22C
- Captured first bulk dump from QY70 (808 bytes, 7 SysEx messages)
- Created 20+ analysis scripts in midi_tools/
