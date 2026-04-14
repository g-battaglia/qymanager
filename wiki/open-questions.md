# Open Questions

Unresolved hypotheses and next steps for the [QY70](qy70-device.md)/[QY700](qy700-device.md) reverse engineering.

## Priority 1: Ground Truth Capture

**The single most impactful next step.** Program simple patterns on the QY70 with known content and capture via bulk dump.

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

## Priority 4: Q7P Phrase Data Format

The phrase data at 0x360-0x677 in Q7P files does NOT use the expected D0/E0 byte-oriented commands. Values 0x2D-0x7F appear without command bytes, suggesting a different encoding. This blocks [event conversion](format-mapping.md#event-data--not-yet-mapped) in both directions.

## Priority 5: Voice Offset Discovery

The real voice offsets in Q7P are unknown (0x1E6/0x1F6/0x206 are all zero). To find them:
1. On QY700 hardware, create a pattern with known voices
2. Save as Q7P and hex-dump
3. Search for Bank MSB 0x7F (drums) and program numbers

## Other Open Questions

- **Style name encoding**: how does the QY70 encode the style name in the [header](header-section.md)?
- **F0-F2 shift register**: can we exploit the history pattern for decoding?
- **Drum track marker `28 0F`**: what does it mean in RHY1?
- **PHR2 preamble switching**: why does PHR2 change from 1FA3 to 29CB in fill sections?
- **QY100 .syx compatibility**: checksum modification needed — what exactly changes?

## External Resources

| Source | URL | Access |
|--------|-----|--------|
| QY100 Explorer | qy100.doffu.net | Paid (Patreon) |
| Groups.io community | groups.io/g/YamahaQY70AndQY100 | Free membership required |
| XG Reference | studio4all.de/htmle/main90.html | Free |
