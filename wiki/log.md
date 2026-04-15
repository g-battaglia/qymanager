# Log

Chronological record of sessions, discoveries, and wiki changes.

## [2026-04-15] session-19 | Ground truth validation: ALL decoders FAIL on factory styles

### CRITICAL FINDING: Decoder accuracy ~0% on factory styles

Validated all decoders against `sgt_full_capture.json` (2570 MIDI messages captured from QY70 hardware playback of SGT style):

| Track | Captured | Decoder Precision | Verdict |
|-------|---------|------------------|---------|
| RHY1 (2543 drum) | 680 notes, 6 unique [36,38,42,44,54,68] | 8.9% | FAIL |
| CHD2 (1FA3 chord) | 114 notes, 8 unique [65-77] | 0% | FAIL |
| PHR1 (1FA3 chord) | 151 notes, 8 unique [65-77] | 0% | FAIL |
| BASS (2BE3) | 131 notes, 4 unique [29,31,33,38] | 15.4% | FAIL |
| RHY2 (29CB general) | 170 notes, 1 unique [37] | ~random | FAIL |

### Root cause analysis

- **R=9×(i+1) works ONLY for user-created patterns** (known_pattern: 33% zero bytes, sparse). Factory styles have dense data (0-2% zeros) and the rotation model produces random output.
- **All alternative rotation models tested** (R=7*(i+1), R=11*(i+1), R=constant, R=0, etc.) — ALL at random-chance level.
- **Brute-force R search misleading**: P(random hit) ≈ 93% for drum targets, all "matches" were noise.
- **Section data duplication**: ALL 6 style sections have IDENTICAL track data per slot.
- **Previous confidence metrics were false**: 82-100% accuracy was self-consistency (valid note range), NOT ground truth.

### Strategic pivot: capture-based conversion

Since SysEx decoding fails for factory styles, alternative pipeline bypasses decoder:
```
QY70 Hardware → MIDI Playback Capture → Quantize → Q7P
```
This captures actual notes after all transposition/groove processing.

### Scripts created
- `validate_sgt_capture.py` — ground truth validation framework
- `sgt_deep_diagnosis.py` — exhaustive R-value brute force analysis
- `sgt_raw_hex_analysis.py` — hex dump with delimiter marking, multi-encoding search
- `sgt_section0_focused.py` — local vs global R comparison, capture timing
- `sgt_message_structure.py` — SysEx message structure, section duplication discovery
- `sgt_no_delimiters_test.py` — tests 0x9E/0xDC as data bytes hypothesis (rejected)

### Wiki updated
- `decoder-status.md` — downgraded factory style confidence, added ground truth results
- `conversion-roadmap.md` — added Pipeline B (capture-based), reorganized priorities
- `open-questions.md` — added factory encoding as top priority

## [2026-04-15] session-18 | PATT OUT 1~8 test, Q7P sequence events breakthrough

### PATT OUT CH = 1~8 Test
- **PATT OUT 1~8 produces ZERO output** when ECHO BACK = Thru. With Thru enabled, the MIDI OUT port passes through incoming data and the QY70 suppresses PATT OUT note data.
- Clock pass-through works (187/192 expected clocks echoed back), confirming QY70 receives external clock and is running.
- Tested with both known_pattern.syx (19 msgs) and QY70_SGT.syx (105 msgs) — both loaded successfully but zero notes captured on any channel.
- **Solution**: PATT OUT must be **9~16** with **ECHO BACK = Off** (the Session 17 configuration).

### Chord Transposition Analysis
- Decoded CHD1 (29DC encoding) from known_pattern.syx: 3 bars, 11 events. Bar header 9-bit fields do NOT contain [60,64,67] directly.
- CHD2 and PHR1 (1FA3 chord encoding) have **identical data** in known_pattern — same headers, same events.
- Bar header analysis across CHD2 bars 1-5: field 1 (=53) and field 5 (=484) are CONSTANT, fields 2-4 change per bar. These don't form recognizable chords as MIDI notes.
- **Hypothesis**: Bar headers encode chord-RELATIVE templates (voicing patterns), not absolute notes. The QY70 applies real-time substitution based on the user's chord input.
- Created `capture_chord_test.py` for systematic multi-chord comparison (CM, Dm, G7, etc.) when PATT OUT is fixed.

### Q7P 3072-byte Sequence Events — BREAKTHROUGH
- **Actual musical data is at 0x678-0x870** (Sequence Events area), NOT at 0x360-0x677 (Phrase Data).
- 5120-byte D0/E0 command format does NOT apply to 3072-byte files.
- Structure decoded: config header (48B) → 3 velocity LUT blocks (32+64+64 bytes of 0x64=vel100) → event data (128B) → track flags
- Event data = 16 × 8-byte groups: Groups 0-7 = sequence pattern, Groups 8-15 = note table
- Command bytes: `0x83` = note group, `0x84` = timing, `0x88` = section end (distinct from 5120-byte D0/E0)
- Note table (G8-15): 8 instrument slots with per-beat note variants. Primary note repeated with 1-3 alternates per slot.
- Sequence area (G0-7): 7 core drum notes (BD2, SideStk, Snare1, Snare2, HHclose, HHpedal, HHopen)
- Note table has 20 unique notes incl. rides, congas, maracas, shaker — used for fills/variations
- T01.Q7P vs TXX.Q7P: **identical** in phrase data + sequence events. Differ only in section pointers (T01=1 section, TXX=4 sections)
- Created `q7p_sequence_analyzer.py` for structural analysis

### BASS Decoder
- BASS with 2BE3 (SGT): 12 events, confidence 0.25, chaotic field values
- BASS with 29CB (known_pattern): 20 events, confidence 0.31, consistent F4 masks but selected notes in wrong range
- Both encodings remain poorly understood (38% confidence)

### Scripts
- `capture_chord_test.py`: NEW — systematic chord transposition test
- `q7p_sequence_analyzer.py`: NEW — Q7P sequence events structural analysis
- Updated channel maps in `capture_playback.py` and `send_and_capture.py` for both 1~8 and 9~16 PATT OUT

## [2026-04-14] session-17 | End-to-end playback capture, chord transposition discovered

### Bulk Dump Protocol
- **Timing SOLVED**: Init needs **500ms**, bulk messages need **150ms** between each. Wrong timing → QY70 silently ignores everything.
- **All bulk dumps write to AM=0x7E (edit buffer)**: Writing to AM=0x00 (User Pattern 1) is rejected. Edit buffer data IS playable in Pattern mode.
- **Load confirmation**: QY70 responds with ~160 messages (XG params, CCs, Program Changes) on first load. Subsequent loads to same buffer get fewer responses.
- `send_style.py` defaults updated: init_delay 100→500ms, delay 30→150ms.

### Playback Discovery
- **MIDI SYNC must be External**: Without external MIDI Clock, QY70 produces ZERO notes on PATT OUT despite receiving MIDI Start. With external clock (Start + 24ppqn), chord tracks output correctly.
- **Chord playback CAPTURED**: known_pattern CHD1 → ch13: C major [60,64,67], vel=127, ~1070 tick duration, every 5 bars. Same pattern confirmed with SGT and claude_test styles.
- **Drum tracks DO NOT output** via PATT OUT in Pattern mode. All 3 test patterns (known_pattern, claude_test, SGT) show only CHD1 on ch13. No notes on ch9-12 or ch14-16.

### Chord Transposition Discovery
- **Playback notes ≠ decoded bitstream notes**: QY70 outputs [60,64,67] (C major) but decoder extracts [F3, A4, E7, etc.] from the bar headers. The QY70 applies **real-time chord transposition** — the bitstream stores chord-relative patterns, not absolute MIDI notes.
- **CHD1 uses 29DC encoding** in known_pattern (not 1FA3). CHD2/PHR1 have 1FA3 encoding but produce zero output on ch14/ch15.

### Scripts
- `send_style.py`: timing defaults fixed
- `capture_playback.py`: rewritten to use rtmidi (was mido)
- `send_and_capture.py`: NEW — combined send + clock + capture workflow
- Saved: `known_pattern_playback.json` — first chord capture ground truth

## [2026-04-14] session-16 | mido SysEx bug found, rtmidi fix, Identity Reply confirmed

- **ROOT CAUSE FOUND: mido drops SysEx on macOS CoreMIDI**. `sysex_diag.py` loopback test: rtmidi direct sends SysEx correctly (QY70 echoes all messages AND responds to Identity Request), mido sends **nothing** (zero SysEx received on MIDI IN for all message types). Notes work via both methods. The bug is in mido's SysEx serialization on CoreMIDI backend.
- **Identity Request WORKS** (contradicts Session 12f): QY70 responds with `F0 7E 7F 06 02 43 00 41 02 55 00 00 00 01 F7` (Yamaha, Family 0x4100=XG, Model 0x5502). Previous test used mido which silently dropped the SysEx.
- **send_style.py rewritten to use rtmidi directly**: all SysEx now sent via `rtmidi.MidiOut.send_message()` instead of `mido.Message("sysex")`. SGT fixture (105 msgs) and claude_test.syx (17 msgs) both transmitted successfully.
- **Bulk Dump Request limited**: QY70 echoes dump requests on MIDI OUT but only responds to AM=0x00 (User Pattern 1) with `F0 F7` (empty pattern). Other addresses (AM=0x7E, 0x7F, Setup, Song) are echoed without response. Likely requires Pattern mode Standby.
- **List Book analysis complete** (pp.51-64): Sequencer RECEIVE FLOW confirms format `F0 43 00 5F BH BL AH AM AL [data] CS F7`. Table 1-9 SEQUENCER PARAMETER ADDRESS maps all valid addresses. BC=147 confirmed in spec ("data size is fixed at 147 bytes").
- Created: `sysex_diag.py` (loopback SysEx tester), `request_dump.py` (bulk dump requester via rtmidi)
- Updated: `send_style.py` (rtmidi direct), `midi-setup.md`, `open-questions.md`

## [2026-04-14] session-15 | SysEx BC formula discovery, bulk dump transmission

- **SysEx BC formula CORRECTED**: `BC = len(encoded_data)` = 147, NOT `3 + len(encoded)`. Verified against 3 independent QY70 captures (126/126 checksums match). The wrong formula (`bc = 3 + len(encoded)`) in `build_ground_truth_syx.py` caused wrong BH/BL → wrong checksum → QY70 silently discards all messages.
- **Fixed message format**: All QY70 bulk dump messages MUST be exactly 158 bytes (128 decoded → 147 encoded → 158 total). Decoded blocks must be zero-padded to 128 bytes.
- **Fixed builders**: `build_ground_truth_syx.py` corrected. `create_custom_style.py` and `writer.py` already had the correct formula.
- **Corrupted capture detected**: `ground_truth_style.syx` has 2 messages with dropped bytes (140B and 29B instead of 147B). `user_style_live.syx` clean (17/17).
- **Bulk dump transmission investigation**: QY70 receives notes but ignores SysEx bulk dumps from computer via UR22C. Testing: mido, rtmidi direct, alternative ports, different delays, GM/XG parameter SysEx, original captures. Investigation ongoing.
- **Wiki updated**: bitstream.md SysEx format section, checksum.py documentation.

## [2026-04-14] session-14 | R=9×(i+1) PROVEN, per-segment index, new preambles

- **R=9×(i+1) DEFINITIVELY PROVEN**: known_pattern.syx ground truth test — 7/7 events match perfectly on ALL 4 fields (note, velocity, tick, gate). No other rotation model achieves this. This is the definitive proof for 2543 drum encoding rotation.
- **Event index is PER-SEGMENT**: resets to 0 at each DC delimiter. Global index gives 1/36 expected hits vs 6/36 for per-segment. Confirmed on both known_pattern (single segment) and USER-RHY1 (multi-segment).
- **Multi-segment control event interference**: control events at odd positions within segments disrupt cumulative index. Position-specific R {e0:9, e1:22, e2:12, e3:53} gives 100% on USER-RHY1 bars 3-4, but no linear formula exists and SGT-RHY1 needs completely different R values.
- **2D2B/303B = chord encoding variants of 1FA3**: USER style has 0x2D2B (CHD1) and 0x303B (CHD2/PAD/PHR1/PHR2). Deep analysis proved these use IDENTICAL encoding to 1FA3: F4 chord-tone masks `[11101,11101,11101,01101]` and F5 timing `[172,180,188,186]` match exactly between USER-CHD1(2D2B) and SGT-CHD2(1FA3). Preamble value is track-level metadata, not encoding type selector.
- **Extended preamble identified**: first 14 bytes of event_data (before first DC delimiter) are identical between USER and SGT styles — this is extended preamble metadata, not a real bar segment.
- **Playback capture improved**: created capture_playback_json.py (proper JSON with channel mapping, velocity stats). Previous capture_diag.py only printed to terminal.
- **event_decoder.py updated**: removed R=9 constant fallback, added mod 56 to cumulative R, reordered decoder priority chain. Control event detection now uses cumulative R.
- **Model G cascade decoder**: std→skip-ctrl→R=47 achieves 96% USER-RHY1, 94% SGT-RHY1 (vs 84%/85% baseline). After ctrl events, skip-ctrl R correctly decodes Crash1(49), Ride1(51) where std gives garbage.
- **event_decoder.py updated**: decode_drum_event() now accepts note_index parameter for Model G cascade. classify_encoding() recognizes 2D2B/303B as chord encoding.
- Created: analyze_known_pattern.py, analyze_rhy1_*.py (6 scripts), analyze_sgt_rhy1_crossbar.py, validate_rhy1_decoder.py, capture_playback_json.py, analyze_new_preambles.py, analyze_new_preambles_deep.py, analyze_ctrl_skip_index.py, analyze_ctrl_skip_combined.py
- Updated: event_decoder.py, 2543-encoding.md, decoder-status.md, open-questions.md, bitstream.md, log.md

## [2026-04-14] session-13 | First live playback capture, PATT OUT CH

- **PATT OUT CH discovery** (Owner's Manual p.224): UTILITY → MIDI parameter, default Off. Set to "9~16" for D1=ch9..C4=ch16
- **First successful playback capture**: 330 note events on 4 channels (ch9=D1, ch12=BA, ch13=C1, ch14=C2)
- **Track mapping confirmed**: RHY1→D1(ch9), BASS→BA(ch12), CHD1→C1(ch13), CHD2→C2(ch14)
- **External sync works**: MIDI SYNC=External + Start+Clock from computer drives QY70 playback at 120 BPM
- **Captured chord progression**: G→C→Em→D (4 bars, 8s loop). CHD1 plays voice-led triads, BASS plays root, CHD2 plays single-note phrase
- **Drum pattern**: 8-beat (HH42 on every 8th, Kick36 on beats 1/5, Snare38 on beats 3/7). Velocities vary (groove template): HH=112-122, Kick=111-127, Snare=115-123
- **Groove quantization confirmed**: velocity variation in drums matches QY70's groove template feature
- **Silent tracks**: ch10(D2/RHY2), ch11(PC/PAD), ch15(C3/PHR1), ch16(C4/PHR2) — not present in this style
- Created: capture_diag.py (comprehensive MIDI diagnostic), capture_and_save.py (JSON capture)
- Updated: qy70-device.md, midi-setup.md, open-questions.md, log.md

## [2026-04-14] session-12g | PATT OUT CH discovery, wiki audit

- **PATT OUT CH found** (Owner's Manual p.224): UTILITY → MIDI → PATT OUT CH controls style/pattern MIDI output. Default is "Off" (no output). Set to "9~16" to transmit D1=ch9, D2=ch10, PC=ch11, BA=ch12, C1-C4=ch13-16
- **QY70 does NOT use INT/EXT/BOTH**: unlike other Yamaha synths, QY70 has a single PATT OUT parameter (Off/1~8/9~16)
- **MIDI CONTROL parameter**: Off/In/Out/In/Out — must be set to "In" or "In/Out" to accept MIDI Start/Stop from computer
- **Identity Request confirmed NOT supported**: QY70 ignores Universal Identity Request. MIDI bidirectional works (notes, SysEx), just not Identity.
- **Wiki audit completed**: fixed midi-setup.md (added bidirectional validation, PATT OUT setup), qy70-device.md (added MIDI output section, Identity limitation), open-questions.md (marked off-by-one resolved, updated dump request status)
- Updated: qy70-device.md, midi-setup.md, open-questions.md, log.md

## [2026-04-14] session-12f | Unified decoder, 96% global accuracy

- **Unified decoder `decode_drum_event()`**: single decoder for ALL encoding types (2543, 29CB, 29DC, 294B, 1FA3) using priority chain: cumulative R=9×(i+1) → R=9 fallback → ctrl detection → R=47 fallback
- **96% global note accuracy**: 143/149 note events across all 7 tracks. 5 tracks at 100% (RHY2, CHD1, CHD2, PHR1, PAD nearly)
- **Correct control event detection**: lo7 > 87 at R=9 (not F0=0x078 as previously documented — F0 is actually 0x1E0=480)
- **Control events are sub-sequence terminators**: 11/16 are last in segment, ALL at odd positions, F5 encodes type (0x120=intermediate, 0x06C=final, 0x036=BASS-specific)
- **ALL control events end with byte 0x78**: universal marker across all tracks/encodings
- **Trailing bytes analysis**: d878 = last 2 bytes of most common ctrl event; CHD2/PHR1 share identical trails; BASS has zero-padding
- **MIDI connectivity**: QY70 bidirectional confirmed (heard kick sent from computer), but dump request not supported, style playback output blocked by INT track mode
- **known_pattern.syx**: built and sent to QY70, 7 events with 100% round-trip verification
- Updated: decoder-status.md, 2543-encoding.md, event_decoder.py

## [2026-04-14] session-12e | Event type classification, cross-encoding analysis

- **Event types discovered**: 3 types — Note (85%), Control (15%, F0=0x078 at R=9), Null (BASS only, F0=0x000)
- **Control events are structural markers**: byte-identical patterns appear across RHY1 AND PAD tracks. Pattern `280f8d83b0d878` in 4 locations, `3486f2e3e24078` in 2 locations.
- **True accuracy 94%**: mixed model (cumulative + constant R=9 fallback) gives 49/52 valid on NOTE events only. Only 3 note events (~6%) remain unexplained.
- **1FA3 has 0% control events**: chord encoding is purely note-based. 29CB has 11%, 2BE3 has 15% control + 20% null.
- **6-byte header hypothesis REJECTED**: 41% valid vs 85% for 13-byte header. Header bytes 6-12 decode to note=105 (invalid) at R=0 for most segments.
- **R=9×(i+1) confirmed for 1FA3**: 95% valid for CHD2/PHR1 vs 70% with R=9×i (event_decoder.py formula is off-by-one!)
- **Trailing bytes are cross-encoding**: BASS, CHD2, PHR1 share identical trail patterns [1,0,2,0,0,2] and segment sizes [28,41,29,41,41,43]. Format-level feature, not encoding-specific.
- **CHD2 and PHR1 share identical event data**: same raw bytes at same positions, confirming style copies data across tracks
- **Global cumulative index doesn't work**: per-segment index reset confirmed (global gives much worse results)
- Created 4 new analysis scripts: 6byte_header, continuous_stream, failing_events, cross_encoding_failures, event_types

## [2026-04-14] session-12d | 2543 cumulative rotation hypothesis, segment alignment

- **Cumulative rotation R=9×(i+1) gives 77% valid notes** vs 66% for constant R=9 — original "constant rotation proof" was inconclusive (all identical events at e0 position)
- **Segment misalignment discovered**: 50% of segments have (length-13)%7 ≠ 0, with 1-3 trailing bytes before delimiter. Pattern `d878` appears twice.
- **XG drum note range confirmed**: Standard Kit maps notes 13-87 only. Notes 82-87: Shaker, JnglBell, BellTree, Castanets, MuSurdo, OpSurdo. Notes >87 are NOT valid drum sounds.
- **Pattern mode padding**: AL=127 track filled with empty marker `BF DF EF F7 FB FD FE` repeated, confirming padding pattern
- **14 remaining invalid events**: mostly at higher event indices (e4+) where cumulative R exceeds 56 and wraps around. May be non-note events or rotation artifacts.
- Created 5 analysis scripts: anomalies, alignment, event_types, rotation_model, r_sweep_cumulative
- Updated wiki: 2543-encoding.md (rotation model, segment alignment, XG range), decoder-status.md, open-questions.md, bitstream.md

## [2026-04-14] session-12c | 2543 drum encoding decoded, Dump Request corrected

- **2543 uses CONSTANT rotation** (not cumulative like 1FA3): proven by 9 byte-identical events at different positions all decoding identically at R=9
- **F0 = note number** (lo7 = MIDI note): Kick1=36, HHpedal=44, HHopen=46, Ride=51, Crash=57 confirmed from repeated events
- **F1-F4 = position encoding**: simultaneous events share identical F1-F4 (e.g., Kick+HH at beat 1 all have F1=60,F2=82,F3=58,F4=108)
- **F5 = gate time in ticks**: physically reasonable (Kick=412≈332ms, HH=30≈24ms at 155BPM)
- **F0 bits 7-8 = flags**: possibly velocity level (2-bit), not yet confirmed
- **Dump Request IS supported**: List Book section 3-6-3-4, `F0 43 20 5F AH AM AL F7`, AM=00-3F for individual patterns. Previous test used wrong address AM=7E (edit buffer)
- **Pattern mode ALL tracks use 2543**: not just drums — chord tracks (C1-C4) also use this encoding in Pattern mode
- Created wiki page [2543-encoding.md](wiki/2543-encoding.md), updated 6 existing pages
- Joint R optimization: R=34 best for combined drum+beat (35.5%), but R=9 gives best drum note identification (61%) — 2543 doesn't use one-hot beat counter like 1FA3
- **Velocity SOLVED**: 4-bit inverted code `[F0_bit8:F0_bit7:rem]`, 0=fff(127), 15=pppp(7). Same note at different velocities confirmed (MuTriang v2/v8, OpTriang v12-v15)
- **Beat number extracted**: F1 top 2 bits = beat (0-3). Tick 240 = primary beat position in 6/10 segments
- Clock encoding: `((F1 & 0x7F) << 2) | (F2 >> 7)` gives 9-bit clock, 59% monotonicity within segments

## [2026-04-14] wiki-create | Initial wiki from 12 sessions of knowledge

Created wiki from accumulated knowledge across docs/, midi_tools/, and session notes.
Major sources: QY70_FORMAT.md (41K), QY700_FORMAT.md (18K), SESSION_RECAP.md, event_decoder.py.

## [2026-04-14] session-12b | List Book MIDI Data Format analysis

- Analyzed full QY70E2.PDF (QY70 List Book, 64 pages)
- **Table 1-9**: Sequencer addresses — patterns at AH=02, AM=00-3F, songs at AH=01
- **Bulk Dump Request supported**: substatus=0x20 (F0 43 20 5F AH AM AL F7)
- **AM=0x7E = edit buffer** in dump DATA messages (not a pattern slot number)
- **Section Control**: F0 43 7E 00 ss dd F7 — can switch sections via MIDI
- Captured C major pattern on C1 track (AL=0x04) — preamble is 2543 (not 1FA3!)
- Pattern mode uses different preamble encoding than Style mode
- 99 Chord Templates, 100 Groove Templates, 128 Preset Styles documented

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
