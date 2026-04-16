# Open Questions

Unresolved hypotheses and next steps for the [QY70](qy70-device.md)/[QY700](qy700-device.md) reverse engineering.

## Priority 1: Complex Style Encoding (Session 19 — CRITICAL)

**Session 19 proved that ALL decoders FAIL on complex styles** (~0% accuracy against ground truth). The R=9×(i+1) rotation works for user-created patterns (sparse, 33% zeros) but NOT for factory preset styles (dense, 0-2% zeros). See [Decoder Status](decoder-status.md#what-doesnt-work--critical-session-19).

**Session 20: exhaustive elimination of hypotheses** (analysis on correct file `tests/fixtures/QY70_SGT.syx`):

| Hypothesis | Test | Result | Status |
|-----------|------|--------|--------|
| Different rotation key | All a*(i+c) mod 56 | Best 13% (81 events) | **ELIMINATED** |
| XOR with bar header | 5 variants tested | Max 7% | **ELIMINATED** |
| XOR with header difference (KP⊕SGT) | Tested | 3-5/81 | **ELIMINATED** |
| Different header size | Sizes 0-20 tested | Best 20% on 30 events | **ELIMINATED** |
| Message boundary reset | Per-message indexing | No improvement | **ELIMINATED** |
| Reversed 7-bit decoding | Compared with parser | Doesn't match | **ELIMINATED** |
| Drum map indices | Notes 0-5 vs MIDI | Random chance | **ELIMINATED** |
| Note-index skip | R by note count | 5/81 | **ELIMINATED** |

**KEY FINDING — velocity impossibility**: n42 v32 (16 per bar in ground truth) requires F0=426. No SGT event produces this at ANY rotation. The barrel rotation model is **structurally incapable** of encoding the required data.

### QYFiler.exe Disassembly Finding (Session 20)

[QYFiler.exe reverse engineering](qyfiler-reverse-engineering.md) proves that the barrel rotation is performed **inside the QY70 hardware**, NOT by the host software. QYFiler contains NO rotation, XOR, or scrambling -- only [7-bit encoding](7bit-encoding.md). The .syx/.blk files contain data exactly as the QY70 stores it internally.

This means:
1. The rotation IS the QY70's internal storage format
2. Simple and complex patterns are both stored rotated
3. The failure on dense data is a problem of understanding the QY70's internal encoding, not a host-side transformation we're missing

**Remaining hypotheses** (not yet tested):
- Completely different encoding scheme (not barrel rotation at all) for dense data
- Compression or delta-encoding on top of events
- Lookup table / codebook approach (events index into a table, not self-contained)
- Different field layout for dense events (not 6x9-bit + 2-bit remainder)
- The 13-byte bar header participates in decoding (not just metadata)

**Session 25d: ALL rotation models exhaustively eliminated for dense encoding**:
- **Structural impossibility**: note 38 (snare) UNREACHABLE from Seg 2 events at ANY rotation
- **Instrument reordering**: "stable core" bytes (e.g., `ae8d81`=snare) move between event slots per bar
- **7 models tested**: cumulative (global/per-bar/offset), header-derived, XOR, 8×7-bit beat, free R
- **Best score**: 5/20 events (25%) — no better than chance
- **8×7-bit velocity model**: shape correlation up to r=0.979 but wrong absolute values
- **Barrel rotation model is WRONG for dense patterns** — not a matter of finding correct R
- **Next step**: create SIMPLE hardware test patterns to isolate the encoding from scratch

**Evidence**:
- User sparse: known_pattern (33% zeros), R=9×(i+1) gives 100% (7/7)
- User dense: Summer (0% zeros), **ALL rotation models give ≤25%** (max 5/20 events)
- Factory: SGT (0-2% zeros), ALL models give random-chance results
- Three distinct encoding regimes: sparse user (solved) → dense user (unsolved) → factory style (unsolved)
- Dense and factory may use the **same** encoding (both show structural impossibility)

**Approach**: This is now a research problem, not a blocking issue for conversion. Pipeline B (capture-based) bypasses decoding entirely.

## ~~Priority 1a: Dump Request~~ — CORRECTED (Session 20)

**Dump Request IS supported** for user pattern slots (AM=0x00-0x3F). Previous "unsupported" claim was wrong:
- Session 16: AM=0x00 returned `F0 F7` = valid empty-pattern response (slot was empty)
- Session 20: AM=0x7E (edit buffer) got no response — edit buffer doesn't support dump request
- QYFiler.exe uses AM=0xFF in templates (possibly "all slots" wildcard) — not yet tested

**To test**: load data into a User Pattern slot on QY70, then `request_dump.py --am 00`.

**Previous hardware dumps are consistent**: Feb 26 and Apr 14 header captures differ by only 6/640 bytes, confirming faithful reproduction.

## Priority 1b: Ground Truth Capture (critical for dense encoding)

Program simple patterns on the QY70 with known content and capture via bulk dump.

| Pattern | Content | Purpose |
|---------|---------|---------|
| A | Solo CHD2, C major chord, 4 bars, 120 BPM | Validate [bar header](bar-structure.md) chord encoding |
| B | Same as A but Am chord | Which bytes change for different root/type |
| C | Solo RHY1, kick (note 36) on beat 1 ONLY | Isolate single-instrument dense encoding |
| D | Solo RHY1, HH on beats 1+3 only | Isolate beat pattern encoding |
| E | Solo RHY1, HH all 8 eighth notes, no groove | Test whether no-groove gives exact vel_code |
| F | Main A: C major, Main B: G major on CHD2 | Cross-section chord changes |

Patterns C-E are CRITICAL for understanding the [instrument lane model](2543-encoding.md#instrument-lane-model--dense-patterns-session-25b) and [groove template](2543-encoding.md#groove-template-session-25b).

This validates or invalidates all hypotheses about [event fields](event-fields.md) and [bar headers](bar-structure.md).

## Priority 1c: Groove Template Location

**Session 25b**: Per-beat velocity humanization is applied by the QY70 playback engine. The groove parameters are NOT in the track-level data (384 bytes for RHY1). Possible locations:

1. **Header track (AL=0x7F)**: 640 decoded bytes, contains global pattern settings
2. **Pattern-level setting**: a global "groove type" parameter (like "16Beat" or "Shuffle")
3. **Hardcoded per-style**: the groove is baked into the QY70 firmware for each style template

**Test**: capture a pattern with groove OFF (if possible) and compare velocities with groove ON. If velocities become exact vel_code multiples (127, 119, 95...) with groove off, the groove is a separable parameter.

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
- **Chord transposition formula** (Session 18/25b/25c): **8 combinatorial approaches all FAILED** (single field+offset, field pairs, root extraction, intervals, scale factors, nibbles, raw bytes). Header lo7 notes do NOT map to GT notes by any simple formula. **Session 25c discovery**: F0 and F5 are ALWAYS shared between CHD1 and PHR1 (same bar), likely encoding chord info. But F0 is CONSTANT (=53) for bars 1-3 despite different chords (C/Em/D). Raw headers: bars 1-2 share 9/13 bytes, only 4 bytes encode C→Em difference. The QY70 likely uses a runtime voice-leading algorithm with chord table lookup, not a simple transposition formula.
- ~~**Tempo encoding**~~: SOLVED (Session 25c) — `BPM = raw_data[0] × 95 - 133 + raw_data[1]` from first header SysEx message. Summer=155 BPM (not 110 as assumed), MR. Vain=133 BPM ✓.
- **Auto-generated bass** (Session 25b): BASS track (AL=0x02) absent from Summer SysEx, yet GT ch12 plays 100 notes (chord roots: G1,C2,E1,D1 matching G-C-Em-D). QY70 auto-generates bass voice from chord progression. Where is the bass pattern template stored? Header track (AL=0x7F)? Built-in style engine?
- **Groove template scope** (Session 25b): Groove velocity humanization applies ONLY to drum tracks (RHY1 vel=112-127 varies). Chord/phrase tracks play at fixed vel=127. Groove parameters likely in header track or pattern-level settings.

## External Resources

| Source | URL | Access |
|--------|-----|--------|
| QY100 Explorer | qy100.doffu.net | Paid (Patreon) |
| Groups.io community | groups.io/g/YamahaQY70AndQY100 | Free membership required |
| XG Reference | studio4all.de/htmle/main90.html | Free |
