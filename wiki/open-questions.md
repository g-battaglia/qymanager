# Open Questions

Unresolved hypotheses and next steps for the [QY70](qy70-device.md)/[QY700](qy700-device.md) reverse engineering.

## Priority 1: Factory Style Encoding (Session 19 — CRITICAL)

**Session 19 proved that ALL decoders FAIL on factory styles** (~0% accuracy against ground truth). The R=9×(i+1) rotation works for user-created patterns (sparse, 33% zeros) but NOT for factory preset styles (dense, 0-2% zeros). See [Decoder Status](decoder-status.md#what-doesnt-work--critical-session-19).

**Hypotheses to investigate**:
- Factory styles use a different rotation key (not R=9)
- Factory styles use additional encryption/obfuscation on top of rotation
- The data structure is fundamentally different (not 7-byte events with 13-byte headers)
- Factory styles store compressed/delta-encoded data
- The preamble encodes a per-style key that modifies the rotation

**Evidence**:
- User patterns: sparse data (33% zero bytes), R=9×(i+1) gives 100% (7/7)
- Factory SGT: dense data (0-2% zeros), ALL rotation models give random-chance results
- ALL 6 sections in SGT have IDENTICAL track data per slot
- Brute-force R search unreliable (P(random hit) ≈ 93% for 6-target drum set)

**Approach**: This is now a research problem, not a blocking issue for conversion. Pipeline B (capture-based) bypasses decoding entirely.

## Priority 1b: Ground Truth Capture (still needed for Pipeline B validation)

Program simple patterns on the QY70 with known content and capture via bulk dump.

| Pattern | Content | Purpose |
|---------|---------|---------|
| A | Solo CHD2, C major chord, 4 bars, 120 BPM | Validate [bar header](bar-structure.md) chord encoding |
| B | Same as A but Am chord | Which bytes change for different root/type |
| C | Solo RHY1, kick (note 36) on beat 1 | Decode drum encoding |
| D | Main A: C major, Main B: G major on CHD2 | Cross-section chord changes |

This validates or invalidates all hypotheses about [event fields](event-fields.md) and [bar headers](bar-structure.md).

## Priority 2: Bar Header 9-Bit Fields > 127

For the SGT style, the first 5 fields of the [13-byte bar header](bar-structure.md) are valid MIDI notes (all ≤ 127). For the captured pattern (`ground_truth_style.syx`), fields 3-4 are > 127 (bit 8 set).

**Hypotheses**:
- Bit 8 is a voicing/register flag (the lo7 is still the MIDI note)
- Different patterns use a different header sub-encoding
- The header structure varies between Pattern and Style formats
- Fields 3-4 encode intervals or chord type, not absolute notes

**Test**: capture Pattern A above (known C major = notes 60, 64, 67). Check if bar header fields match.

## Priority 3: F4 param4 and F5 Timing

- **F4 param4** (4 bits): likely velocity, gate length, or articulation. Not decoded.
- **F5**: approximate timing (+8 per 8th note?) but values are not monotonically increasing within a bar. The decomposition top2/mid4/lo3 shows lo3 is consistently 4 in normal events.

**Test**: capture patterns with different velocities and note lengths. Compare param4 and F5 across captures.

## Priority 4: Q7P 3072-byte Musical Data — PARTIALLY SOLVED (Session 18)

**Session 18 breakthrough**: the actual musical data is in the **Sequence Events** area (0x678-0x870), NOT in the Phrase Data area (0x360-0x677). The 5120-byte D0/E0 format does NOT apply to 3072-byte files.

**Solved**:
- Structure map: config header (0x678) → velocity LUTs → event data (0x756, 128 bytes) → note table
- Event data = 16 × 8-byte groups. Groups 0-7 = sequence pattern, Groups 8-15 = note table
- Note table (G8-15): per-instrument note palette with primary note + beat variations
- Command bytes: `0x83` = note group, `0x84` = timing, `0x88` = section end
- Phrase area (0x360-0x677) contains velocity/parameter tables, not note sequences

**Still open**:
- Exact semantics of `0x84` parameter (timing step? beat index? velocity?)
- How sequence area (G0-7) maps to temporal beats
- Cross-reference between sequence and note table (partial overlap, 7 shared notes)
- How to WRITE events (needed for QY70→QY700 converter)

See [Q7P Format](q7p-format.md#sequence-events-0x678-0x870--session-18) for full details.

## Priority 5: Voice Offset Discovery

The real voice offsets in Q7P are unknown (0x1E6/0x1F6/0x206 are all zero). To find them:
1. On QY700 hardware, create a pattern with known voices
2. Save as Q7P and hex-dump
3. Search for Bank MSB 0x7F (drums) and program numbers

## ~~Priority 6: 2543 Velocity Encoding~~ — SOLVED

Velocity = `[F0_bit8 : F0_bit7 : rem]`, 4-bit inverted code (0=fff, 15=pppp). See [2543 Encoding](2543-encoding.md#velocity-encoding--solved).

## ~~Priority 6: 2543 Rotation Model~~ — SOLVED (Session 14)

**R=(9×(i+1)) % 56 PROVEN** with known_pattern.syx ground truth: 7/7 events match perfectly on all 4 fields (note, velocity, tick, gate). Event index resets per segment (at DC delimiter). No fallback models needed for single-segment tracks.

**Multi-segment open problem**: in tracks with control events at odd positions, the cumulative index is disrupted. Position-specific R values work empirically per style but have no universal formula. See [2543 Encoding — Multi-segment](2543-encoding.md#multi-segment-control-event-interference-open).

## ~~Priority 6a: New Preambles 0x2D2B and 0x303B~~ — SOLVED (Session 14)

**2D2B and 303B use the same chord encoding as 1FA3.** Proven by:
- F4 chord-tone masks are **identical** between USER-CHD1(2D2B) seg1 and SGT-CHD2(1FA3) seg1: `[11101, 11101, 11101, 01101]`
- F5 timing values are **identical**: `[172, 180, 188, 186]`
- Event byte similarity pattern matches 1FA3 (2-5 bits differ across bars)
- R_base=9 cumulative gives best results (same as 1FA3)

The preamble value at bytes 24-25 encodes **track-level metadata** (possibly chord template, voice parameters, or section type), NOT the data format. The `classify_encoding()` function now recognizes all three as chord encoding.

## Priority 6b: 2543 Segment Trailing Bytes

~50% of segments have 1-3 extra bytes between the last 7-byte event and the delimiter (0x9E). The pattern `d878` appears twice. These could be CRC, footer metadata, or segment-level parameters.

## Priority 6c: 2543 F3-F4 Position Structure

F1 top 2 bits = beat (confirmed), lower F1 + F2 top bits = clock (59% monotonicity). But F3 and F4 roles within position encoding still unknown — they're shared by simultaneous events. Possibly encode groove template parameters or sub-beat resolution.

## ~~Priority 7: Correct Dump Request Test~~ — RESOLVED (Session 17)

**Session 17 findings**:
- **Bulk dump SEND works end-to-end**: with correct timing (500ms init, 150ms between msgs), QY70 loads the style/pattern and responds with ~160 XG parameter messages. All bulk dumps write to AM=0x7E (edit buffer). Writing to AM=0x00-0x3F is rejected.
- **Playback via MIDI Start+Clock works**: QY70 MIDI SYNC must be **External**. With external clock, chord tracks output correctly on PATT OUT CH channels (CHD1→ch13 confirmed). Pattern loops at the correct bar count.
- **Drum track output issue**: RHY1 drum data does NOT output via PATT OUT in Pattern mode despite having valid data. All 3 test patterns (known_pattern, claude_test, SGT) show only CHD1 notes. May work in Style mode (Session 13 confirmed in Style mode).

**Playback capture workflow**: `send_and_capture.py` → send style → MIDI Start + Clock → capture on PATT OUT channels.

## Other Open Questions

- **Style name encoding**: how does the QY70 encode the style name in the [header](header-section.md)?
- **F0-F2 shift register** (chord encoding): can we exploit the history pattern for decoding?
- **PHR2 preamble switching**: why does PHR2 change from 1FA3 to 29CB in fill sections?
- **QY100 .syx compatibility**: checksum modification needed — what exactly changes?
- **2543 F1-F4 position structure**: 36-bit combined value, not simple chronological ordering — what's the bit layout?
- **2543 in Pattern mode**: do chord tracks (C1-C4) store absolute or chord-relative notes?
- ~~**2543 rotation model**~~: SOLVED (Session 14) — R=9×(i+1) PROVEN via known_pattern.syx 7/7
- ~~**Multi-segment cumulative index**~~: PARTIALLY SOLVED — Model G cascade (std→skip-ctrl→R=47) achieves 94-96%. ~3 events per track still fail (n=1, n=8 patterns)
- ~~**XG drum notes >87**~~: RESOLVED — these are [control events](2543-encoding.md#event-types) (F0=0x078 at R=9), not note events
- **Control event content**: F1-F5 fields of control events not decoded. They carry structural commands (bar repeat? section link? fill?). Cross-track identical bytes suggest format-level structure.
- ~~**event_decoder.py off-by-one**~~: RESOLVED (Session 12e) — confirmed R=9×(i+1) is correct, decoder updated.
- **Trailing bytes cross-encoding**: 54% of segments across ALL encoding types have trailing bytes. BASS/CHD2/PHR1 share identical patterns. Format-level feature, not encoding-specific. Purpose still unknown.
- **Drum PATT OUT in Pattern mode** (Session 17): RHY1/RHY2 drum tracks produce ZERO MIDI output via PATT OUT CH in Pattern mode + External sync. Chord tracks (CHD1) work correctly. Is this a QY70 firmware limitation? Does Style mode handle drums differently? Does a specific MIDI setting enable drum output?
- **PATT OUT 1~8 + ECHO BACK=Thru** (Session 18): This combination produces ZERO output on ALL channels. ECHO BACK=Thru monopolizes MIDI OUT for pass-through. Must use PATT OUT 9~16 + ECHO BACK=Off.
- **Chord transposition formula** (Session 18): Bar headers store chord-relative templates, not absolute MIDI notes. Fields 1 and 5 are constant across bars, fields 2-4 change. Need multi-chord capture comparison (CM vs Dm vs G7) to derive the transformation formula.

## External Resources

| Source | URL | Access |
|--------|-----|--------|
| QY100 Explorer | qy100.doffu.net | Paid (Patreon) |
| Groups.io community | groups.io/g/YamahaQY70AndQY100 | Free membership required |
| XG Reference | studio4all.de/htmle/main90.html | Free |
