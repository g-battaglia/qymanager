# Decoder Status

Current state of [QY70 bitstream](bitstream.md) decoding as of Session 20 (2026-04-15).

> **CRITICAL (Session 19)**: All confidence percentages below were measured by **self-consistency** (valid note range, beat counter monotonicity, etc.), NOT against ground truth MIDI output. Session 19 validated against actual QY70 playback capture and found **~0% accuracy on complex styles**. The rotation model is proven ONLY for simple simple patterns.

## Per-Encoding Confidence

| Encoding | Preamble | Tracks | User Pattern | Complex Style (SGT) | Key Findings |
|----------|----------|--------|-------------|---------------------|--------------|
| [drum_primary](2543-encoding.md) | `2543` | RHY1 | **100%** (7/7 known_pattern) | **~9% precision** | R=9×(i+1) PROVEN for simple patterns. FAILS on factory dense data |
| chord | `1FA3`, `2D2B`, `303B` | CHD1-2, PAD, PHR1-2 | Untested | **0% precision** | Self-consistency was 100%, real accuracy 0% |
| general_29dc | `29DC` | CHD1 | Untested | **~0%** | Same failure |
| general_294b | `294B` | RHY2 | Untested | **~0%** | Same failure |
| general | `29CB` | PAD, BASS | Untested | **15% precision** (BASS) | Self-consistency was 78-95%, real accuracy near random |

**Session 19 ground truth validation**: Decoded notes from `QY70_SGT.syx` compared against 2570 MIDI messages captured from QY70 hardware playback (`sgt_full_capture.json`). ALL decoders produce essentially random output for complex styles.

**User patterns (known_pattern.syx)**: R=9×(i+1) remains PROVEN correct — 7/7 events match perfectly. The model works for sparse data (33% zero bytes) but not for dense dense/complex data (0-2% zeros).

## Unified Decoder (`decode_drum_event`) — Model G

All encoding types now use the same decoder with a 4-step cascade (Session 14):
1. **Cumulative R=(9×(event_index+1)) % 56** — PROVEN correct (7/7 known_pattern.syx)
2. **Control event detection** — lo7 > 87 at cumulative R → classify as structural marker
3. **Skip-ctrl R=(9×(note_index+1)) % 56** — for events after ctrl events where standard R gives invalid note. note_index counts only preceding note events (excludes ctrl).
4. **Constant R=47** fallback — catches remaining edge cases (RHY2/294b)

Event index is **per-segment** (resets to 0 at each DC delimiter).

| Track | Model A (std) | Model G (cascade) | vs Ground Truth (Session 19) |
|-------|--------------|-------------------|------|
| USER-RHY1 | 84% | **96%** | not tested |
| SGT-RHY1 | 85% | **94%** | **~9% precision** (random chance) |
| known_pattern | 100% | **100%** | **100%** (7/7 PROVEN) |

> **Note**: the 85-96% figures for SGT-RHY1 measure self-consistency (note in XG range 13-87), NOT correctness against actual MIDI output. Ground truth shows these "valid" notes are the WRONG notes.

## What Works

### Confirmed by ground truth (high confidence)
- **Barrel rotation R=(9×(i+1))%56**: PROVEN on simple patterns — 7/7 perfect match on known_pattern.syx (all fields: note, velocity, tick, gate)
- **Rotation is hardware-side (Session 20)**: [QYFiler.exe disassembly](qyfiler-reverse-engineering.md) proves the rotation happens INSIDE the QY70 hardware, not in host software. QYFiler contains NO rotation/XOR/scrambling. The .syx files contain data exactly as the QY70 stores it internally.
- **Track classification**: preamble-based encoding detection 100% reliable
- **Bar delimiters**: DC (bar) and 9E (sub-bar chord change) both recognized
- **Round-trip encoder/decoder**: 100% on 47 events (ground_truth), 705/705 on SGT fixture — proves encoding/decoding is INTERNALLY consistent, even though decoded notes are wrong for complex styles

### Self-consistency only (unverified for complex styles)
- **Beat counter (F3 lo4)**: 90%+ accuracy — but only tested against internal consistency, not playback
- **F4 chord mask**: 5-bit mask selects from 5 header notes — pattern consistent but selected notes are WRONG for complex styles
- **Control events**: structural terminators at odd positions, lo7 > 87 at R=9, ALL end with byte 0x78
- **F0 = note number**: correct for simple patterns, wrong for complex styles
- **Velocity decoded**: 4-bit inverted code — correct for simple patterns, unverified for factory

## What Doesn't Work — CRITICAL (Session 19)

### Factory style decoding FAILS completely

**Session 19 ground truth validation** (`validate_sgt_capture.py`): compared decoded events from `QY70_SGT.syx` against 2570 captured MIDI notes from hardware playback:

| Track | Captured Notes | Decoder Precision | Decoder Recall | Verdict |
|-------|---------------|------------------|----------------|---------|
| RHY1 (drum) | 680 (6 unique) | 8.9% | ~random | FAIL |
| CHD2 (chord) | 114 (8 unique) | 0% | 0% | FAIL |
| PHR1 (phrase) | 151 (8 unique) | 0% | 0% | FAIL |
| BASS | 131 (4 unique) | 15.4% | ~random | FAIL |
| RHY2 | 170 (1 unique) | ~random | ~random | FAIL |
| PAD | — | — | — | untested |

**Root cause**: the R=9×(i+1) rotation model works for **sparse simple patterns** (known_pattern: 33% zero bytes) but NOT for **dense data** (SGT: 0-2% zero bytes). ALL rotation models tested produce random-chance results on dense data (Session 20 exhaustive analysis on correct file `tests/fixtures/QY70_SGT.syx`).

**Velocity impossibility (Session 20)**: n42 v32 (the most common note in the ground truth — 16 per bar) requires F0=426 (9-bit field). Exhaustive search finds ZERO events that produce this F0 at ANY rotation. The model is structurally incapable of encoding the required data, not just misconfigured.

**Why brute-force R search was misleading**: with 6 target drum notes out of 128 possible × 56 rotations, P(at least one hit) ≈ 93%. All brute-force "matches" were noise.

**Section duplication (CORRECTED Session 20)**: sections are NOT identical — different byte counts per track across sections. Session 19 claim was wrong.

### Other known issues
- **Chord transposition layer** (Session 17): bar headers store chord-relative templates, not absolute MIDI notes
- **CHD1 uses 29DC encoding** (not 1FA3) in Pattern mode
- **Drum PATT OUT missing**: zero MIDI output in Pattern mode (works in Style mode)
- **Control event content**: F1-F5 fields not fully decoded
- **Trailing bytes**: segment metadata purpose unknown

## Improvement History

| Session | Change | Impact |
|---------|--------|--------|
| 6 | R=9 rotation discovered | Core breakthrough |
| 7 | Shift register F0-F2 identified | Structural understanding |
| 8 | F3 beat counter decoded | +40% beat accuracy |
| 10 | Preamble-based classification | 100% track typing |
| 12 | lo4=0 → beat 0, 9E delimiter | 48%→90% beat accuracy |
| 12c | 2543: constant R, F0=note, F5=gate, velocity, beat | Drum encoding ~80% decoded |
| 12d | 2543: cumulative R=9×(i+1), XG drum range | 66%→77% valid notes |
| 12e | Event type classification (Note/Control/Null) | 77%→94% (note events) |
| 12f | Unified decoder, correct ctrl detection (lo7>87), R=47 fallback | 94%→96% global, 5 tracks at 100% |
| 13 | First live playback capture (330 notes), PATT OUT CH discovery | Hardware validation path established |
| **14** | **R=9×(i+1) PROVEN (7/7), per-segment index, 2D2B/303B = chord variants of 1FA3** | **2543 rotation solved, preamble classification expanded** |
| **15-16** | **BC formula fixed, mido SysEx bug found, rtmidi fix, round-trip 705/705 on SGT** | **SysEx sending works, encoder/decoder 100% on note events** |
| **17** | **Bulk dump timing (500ms/150ms), MIDI SYNC=External, chord playback capture** | **End-to-end: send→load→play→capture WORKS for chord tracks. Chord transposition layer discovered** |
| **18** | **PATT OUT 1~8 fails, Q7P 3072 sequence events breakthrough** | **Q7P actual data at 0x678-0x870, not Phrase Data area** |
| **19** | **Ground truth validation: ALL decoders FAIL on complex styles** | **R=9×(i+1) only works for simple patterns. Strategic pivot to capture-based conversion** |
| **20** | **Exhaustive analysis on correct file, velocity impossibility proven** | **All rotation models definitively disproven. Velocity encoding cannot produce required values. Sparse vs dense = fundamentally different encodings** |
| **20b** | **QYFiler.exe disassembly: NO rotation in host software** | **Barrel rotation is QY70 hardware-internal. BLK format = raw SysEx. Dump Request definitively unsupported** |

## Strategic Pivot: Capture-Based Conversion (Session 19)

Since the SysEx bitstream decoder CANNOT decode complex styles, an alternative pipeline bypasses it entirely:

```
QY70 Hardware → MIDI Playback Capture → Abstract Events → Q7P
```

This captures the ACTUAL notes the QY70 produces (after all transposition, groove templates, etc.) and writes them directly to Q7P format. See [Conversion Roadmap](conversion-roadmap.md#capture-based-pipeline-session-19).

See also: [2543 Encoding](2543-encoding.md), [Bitstream](bitstream.md), [Event Fields](event-fields.md), [Open Questions](open-questions.md)
