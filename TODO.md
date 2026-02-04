# TODO - qyconv

## Completed

### v0.3.0 Features (Done)
- [x] `qyconv dump` - Annotated hex dump with region colors
- [x] `qyconv map` - Visual file structure map with density bars
- [x] `qyconv tracks` - Detailed track info with bar graphics
- [x] `qyconv sections` - Section configuration details
- [x] `qyconv phrase` - Phrase/sequence analysis with event detection
- [x] `qyconv info --full` - Complete extended analysis
- [x] Bar graphics for volume, pan, reverb
- [x] Centered pan bar visualization
- [x] Data density heatmaps
- [x] Removed duplicate tables from basic info output

### v0.2.0 Features (Done)
- [x] `qyconv diff` - Compare two Q7P files
- [x] `qyconv validate` - File structure validation
- [x] Phrase statistics (PhraseStats dataclass)
- [x] Fixed pan offset (0x276)
- [x] Fixed time signature lookup table
- [x] Added reverb send extraction (0x256)
- [x] XG voice name lookup (xg_voices.py)

---

## Hardware Verification Required

These items require testing on a physical QY700 to verify correct behavior.

### HIGH PRIORITY

#### 1. Find Program Change and Bank Select Offsets
**Status**: Not implemented - using defaults (Program=0, Bank=0/0)

**What's needed**:
1. Create a pattern on QY700 with specific instruments assigned:
   - RHY1: Standard Kit (Program 0, Bank 127/0)
   - BASS: Acoustic Bass (Program 32, Bank 0/0)
   - CHD1: Electric Piano 1 (Program 4, Bank 0/0)
2. Save as Q7P file
3. Compare hex dump with template to find Program/Bank offsets

**Suspected areas**:
- `0x120-0x17F`: Section encoded data
- `0x2C0-0x35F`: Table 3 area

#### 2. Verify Time Signature Encoding
**Status**: Implemented with lookup table, only 4/4 (0x1C) confirmed

**What's needed**:
1. Create patterns with different time signatures:
   - 3/4, 6/8, 5/4, 2/4, 12/8
2. Save each as Q7P
3. Check byte at offset 0x18A to build complete lookup table

**Current hypothesis**:
```
0x1C (28) = 4/4  (confirmed)
0x14 (20) = 3/4  (unconfirmed)
0x24 (36) = 6/8  (unconfirmed)
```

#### 3. Find Chorus Send Offset
**Status**: Not implemented

**Reverb Send found at 0x256** (values 0x28 = 40, matches XG default)

**Suspected Chorus location**: 
- Somewhere in 0x280-0x2BF area
- Default XG value is 0

#### 4. Decode Phrase Data Structure
**Status**: Statistical analysis only, no event parsing

**Phrase area (0x360-0x677)**: 792 bytes
**Sequence area (0x678-0x86F)**: 504 bytes

Need to understand:
- Event format (note on/off, timing)
- Delta time encoding
- Per-track data boundaries

---

## Software Implementation TODO

### Medium Priority

#### 5. Parse Phrase Data Events
Currently showing statistics only. Want to:
- Extract actual MIDI events
- Show note list per track
- Show velocity distribution

#### 6. Add MIDI Export
```bash
qyconv export pattern.Q7P --midi output.mid
```

#### 7. Add Audio Preview (optional)
```bash
qyconv play pattern.Q7P  # Play using FluidSynth or similar
```

### Low Priority

#### 8. Add Batch Processing
```bash
qyconv batch convert *.syx --output-dir ./converted/
qyconv batch validate *.Q7P
```

#### 9. Add GUI (optional)
Web-based editor with:
- Pattern visualization
- Track editing
- Drag-and-drop conversion

---

## Confirmed Q7P File Structure

```
Offset    Size   Description                    Status
------    ----   -----------                    ------
0x000     16     Header "YQ7PAT     V1.00"      ✓ OK
0x010     1      Pattern number                 ✓ OK
0x011     1      Pattern flags                  ✓ OK
0x030     2      Size marker (0x0990)           ✓ OK
0x100     32     Section pointers               ✓ OK
0x120     96     Section encoded data           Partial
0x180     8      Padding (spaces)               ✓ OK
0x188     2      Tempo (BE, /10 for BPM)        ✓ OK
0x18A     1      Time signature                 Lookup table
0x190     8      Channel assignments            ✓ Mapped
0x1DC     8      Track numbers (0-7)            ✓ OK
0x1E4     2      Track enable flags             ✓ OK
0x220     6      Volume header                  ✓ OK
0x226     8      Volume data                    ✓ OK
0x250     6      Reverb header                  ✓ OK
0x256     8      Reverb send data               ✓ OK
0x270     6      Pan header                     ✓ OK
0x276     8      Pan data                       ✓ FIXED
0x2C0     160    Table 3 (unknown)              Needs research
0x360     792    Phrase data                    Statistics only
0x678     504    Sequence events                Statistics only
0x870     16     Template padding               ✓ OK
0x880     128    Template area                  ✓ OK
0x876     10     Pattern name                   ✓ OK
0x900     192    Pattern mapping                Unknown
0x9C0     336    Fill area (0xFE)               ✓ OK
0xB10     240    Pad area (0xF8)                ✓ OK
```

---

## XG Documentation Reference

Based on analysis of https://www.studio4all.de/htmle/main92.html

### XG Default Values (confirmed)
| Parameter | Default | Hex |
|-----------|---------|-----|
| Volume | 100 | 0x64 |
| Pan | 64 (Center) | 0x40 |
| Reverb Send | 40 | 0x28 |
| Chorus Send | 0 | 0x00 |
| Variation Send | 0 | 0x00 |
| Bank MSB (Normal) | 0 | 0x00 |
| Bank MSB (Drums) | 127 | 0x7F |
| Bank LSB | 0 | 0x00 |
| Program | 0 | 0x00 |

### XG Pan Encoding
- 0 = Random
- 1-63 = Left (L63-L1)
- 64 = Center
- 65-127 = Right (R1-R63)
