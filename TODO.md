# TODO - qyconv

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
- `0x120-0x17F`: Section encoded data (contains variable values)
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

#### 3. Verify Channel Assignment Encoding
**Status**: Implemented with default channel mapping

**Observations from T01.Q7P**:
- Offset 0x190: `00 00 00 00 03 03 03 03`
- RHY1/RHY2 have value 0x00
- CHD1-CHD5 have value 0x03

**Current interpretation**:
- 0x00 = Channel 10 (drums) for RHY tracks
- Other values = channel number + 1

**Needs verification**: Play pattern on QY700 with MIDI monitor to see actual channel output.

#### 4. Find Chorus Send and Variation Send Offsets
**Status**: Not implemented

**Reverb Send found at 0x256** (values 0x28 = 40, matches XG default)

**Suspected Chorus location**: 
- Somewhere in 0x250-0x2BF area
- Default XG value is 0

---

## Software Implementation TODO

### Medium Priority

#### 5. Add Section-specific Settings Display
Each section can have different:
- Length in measures
- Time signature (per section)
- Track enable flags

Currently only showing global values.

#### 6. Parse Phrase Data (0x360-0x677)
Extract:
- Number of MIDI events
- Note range (min/max)
- Velocity statistics
- Event density per beat

#### 7. Parse Sequence Events (0x678-0x86F)
This area contains:
- Tempo changes
- Program changes (possibly)
- Other automation data

### Low Priority

#### 8. Add `qyconv analyze` Command
Detailed MIDI event analysis with:
- `--events` flag for event list
- `--piano-roll` flag for ASCII visualization

#### 9. Add `qyconv diff` Command
Side-by-side comparison of two Q7P files showing:
- Setting differences
- Hex diff of data areas

#### 10. Add `qyconv validate` Command
Structural validation:
- Header check
- Size marker verification
- Section pointer validation
- Checksum (if any)

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

---

## Confirmed Q7P File Structure

```
Offset    Size   Description                    Status
------    ----   -----------                    ------
0x000     16     Header "YQ7PAT     V1.00"      OK
0x010     1      Pattern number                 OK
0x011     1      Pattern flags                  OK
0x030     2      Size marker (0x0990)           OK
0x100     32     Section pointers               OK
0x120     96     Section encoded data           Partial
0x180     8      Padding (spaces)               OK
0x188     2      Tempo (BE, /10 for BPM)        OK
0x18A     1      Time signature                 Lookup table
0x190     8      Channel assignments            Mapped to defaults
0x1DC     8      Track numbers (0-7)            OK
0x1E4     2      Track enable flags             OK
0x220     6+16   Volume header + data           OK (offset 0x226)
0x256     16     Reverb Send                    NEW
0x270     6+48   Pan header + data              FIXED (offset 0x276)
0x2C0     160    Table 3 (unknown)              Needs research
0x360     792    Phrase data                    Not parsed
0x678     504    Sequence events                Not parsed
0x876     10     Pattern name                   OK
```
