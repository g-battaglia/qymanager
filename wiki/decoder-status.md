# Decoder Status

Current state of [QY70 bitstream](bitstream.md) decoding as of Session 16 (2026-04-14).

## Per-Encoding Confidence

| Encoding | Preamble | Tracks | Note Accuracy | Key Findings |
|----------|----------|--------|---------------|--------------|
| chord | `1FA3`, `2D2B`, `303B` | CHD1-2, PAD, PHR1-2 | **100%** | Cumulative R=9×(i+1), [beat counter](event-fields.md#f3-beat-counter), [chord mask](event-fields.md#f4-chord-tone-mask). 2D2B/303B = same encoding (Session 14) |
| general_29dc | `29DC` | CHD1 | **100%** | Same cumulative model works |
| general_294b | `294B` | RHY2 | **100%** | Cumulative + R=47 fallback |
| [drum_primary](2543-encoding.md) | `2543` | RHY1 (+ all Pattern mode) | **100%** (ground truth) | R=9×(i+1) PROVEN (7/7 known_pattern.syx), F0=note, F5=gate, velocity solved |
| general | `29CB` | PAD | **95%** | Same unified decoder |
| general | `29CB` | BASS | **78%** | 4 events still failing |

**Global: 342/342 = 100% valid notes** across all decoded note events (431 total: 342 note, 61 ctrl, 28 fail). Decode rate: 342/370 = **92%** of non-ctrl events.

## Unified Decoder (`decode_drum_event`) — Model G

All encoding types now use the same decoder with a 4-step cascade (Session 14):
1. **Cumulative R=(9×(event_index+1)) % 56** — PROVEN correct (7/7 known_pattern.syx)
2. **Control event detection** — lo7 > 87 at cumulative R → classify as structural marker
3. **Skip-ctrl R=(9×(note_index+1)) % 56** — for events after ctrl events where standard R gives invalid note. note_index counts only preceding note events (excludes ctrl).
4. **Constant R=47** fallback — catches remaining edge cases (RHY2/294b)

Event index is **per-segment** (resets to 0 at each DC delimiter).

| Track | Model A (std) | Model G (cascade) |
|-------|--------------|-------------------|
| USER-RHY1 | 84% | **96%** |
| SGT-RHY1 | 85% | **94%** |
| known_pattern | 100% | **100%** |

## What Works

- **Barrel rotation R=(9×(i+1))%56**: PROVEN correct — 7/7 perfect match on known_pattern.syx (all fields: note, velocity, tick, gate)
- **Beat counter (F3 lo4)**: 90%+ accuracy for chord and bass tracks
- **Bar delimiters**: DC (bar) and 9E (sub-bar chord change) both recognized
- **F4 chord mask**: 5-bit mask selects from 5 header notes (pattern consistent)
- **Track classification**: preamble-based encoding detection 100% reliable
- **Control events**: structural terminators at odd positions, lo7 > 87 at R=9, ALL end with byte 0x78, cross-track shared (RHY1=PAD)
- **F0 = note number**: lo7 gives valid GM drum notes (Kick=36, HH=44, etc.)
- **F1-F4 = position**: simultaneous events share identical F1-F4 values
- **F5 = gate time**: physically reasonable durations (kick=412 ticks, HH=30 ticks)
- **Velocity decoded**: 4-bit inverted code [F0_bit8:F0_bit7:rem], 0=fff(127), 15=pppp(7)
- **Round-trip encoder/decoder**: 100% on 47 events (ground_truth), 705/705 on SGT fixture (1219 total events, 711 in XG range, 6 control events excluded — clock overflow in terminators)

## What Doesn't Work Yet

- **BASS 29CB**: 4/18 note events fail all rotations (78% accuracy)
- **PAD 29CB**: 1 event fails (~5%)
- **Multi-segment residual failures**: Model G cascade (std→skip-ctrl→R=47) achieves 94-96% but ~3 events per track still fail (n=1, n=8). May be a different event type not yet classified
- ~~**New preambles 0x2D2B, 0x303B**~~: SOLVED — same chord encoding as 1FA3 (F4 masks and F5 timing identical). Preamble value is track-level metadata, not encoding type
- **Bar header chord notes**: 9-bit fields give valid MIDI notes for SGT but >127 values for other patterns
- **Chord transposition layer** (Session 17): Live playback of known_pattern produces C major [60,64,67] on ch13/CHD1, but the decoded bar header notes are completely different (F3, A4, E7, etc.). The QY70 applies real-time chord transposition — bitstream stores chord-relative patterns, not absolute MIDI notes. This is the key missing piece for chord decoding.
- **CHD1 uses 29DC encoding** (not 1FA3): In known_pattern, CHD1 (which outputs on ch13) uses general_29dc encoding. CHD2 and PHR1 use 1FA3 chord encoding but produce NO MIDI output on ch14/ch15.
- **Drum PATT OUT missing**: RHY1 drum data present in pattern but zero MIDI output via PATT OUT in Pattern mode (Session 17). Chord tracks work, drums don't.
- **Control event content**: F1-F5 fields carry structural commands, partially classified by F5 value
- **Trailing bytes**: segment metadata (2B most common), d878 = ctrl tail, CHD2/PHR1 share identical trails

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

See also: [2543 Encoding](2543-encoding.md), [Bitstream](bitstream.md), [Event Fields](event-fields.md), [Open Questions](open-questions.md)
