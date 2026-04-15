# QYFiler.exe Reverse Engineering

Disassembly analysis of Yamaha QY Data Filer (Windows, MSVC 6.0 / MFC). Session 20.

**Confidence: HIGH** -- findings from static disassembly of actual Yamaha binary.

See also: [SysEx Format](sysex-format.md), [7-Bit Encoding](7bit-encoding.md), [BLK Format](blk-format.md)

## Binary Overview

| Property | Value |
|----------|-------|
| File | `exe/extracted/English_Files/QYFiler.exe` |
| Format | PE32 (x86) |
| Size | 1.4 MB (1.1 MB is GUI bitmaps in .rsrc) |
| Compiler | MSVC 6.0, MFC-based (CDocument/CView) |
| Date | 2000-10-05 |
| Main classes | `CQy70Doc`, `CQy70View` |
| DLL | `MidiCtrl.dll` (122 KB, 2000-09-27) |

## CRITICAL FINDING: No Rotation or Scrambling

**There is NO barrel rotation, XOR, encryption, or data scrambling anywhere in QYFiler.exe or MidiCtrl.dll.**

- Zero ROL/ROR instructions in meaningful code sections
- No `imul` by 9 or any rotation-factor arithmetic
- No XOR operations on data buffers
- The [7-bit encoding](7bit-encoding.md) is the **ONLY** data transformation

**Implication**: the barrel rotation `R=9*(i+1)` discovered on pattern data is performed **inside the QY70 hardware itself**. The QYFiler receives already-rotated data from the QY70 and stores it as-is. When sending, the QY70 accepts rotated data directly.

This means:
1. The QY70 stores events in rotated form in its internal memory
2. When playing back, it de-rotates internally
3. When dumping via SysEx, it sends rotated data as-is
4. The `.syx` / `.blk` files contain hardware-rotated data

## MidiCtrl.dll Export Table

14 exported functions for MIDI I/O:

| Ordinal | Name | Purpose |
|---------|------|---------|
| 1 | `_ENTRYcomGetDeviceID` | Get MIDI device ID |
| 2 | `_ENTRYcomGetErrorText` | Error text |
| 3 | `_ENTRYcomGetLastResult` | Last result code |
| 4 | `_ENTRYcomSetDeviceID` | Set MIDI device ID |
| 5 | `_ENTRYctrlGetSysCurInstrument` | Get current instrument |
| 6 | `_ENTRYctrlSelectDevice` | Select MIDI device dialog |
| 7 | `_ENTRYinClose` | Close MIDI input |
| 8 | `_ENTRYinOpen` | Open MIDI input |
| 9 | `_ENTRYinStart` | Start MIDI input |
| 10 | `_ENTRYinStop` | Stop MIDI input |
| 11 | `_ENTRYoutClose` | Close MIDI output |
| **12** | **`_ENTRYoutDump`** | **Send SysEx bulk dump** |
| 13 | `_ENTRYoutOpen` | Open MIDI output |
| 14 | `_ENTRYoutWrite` | Write short/SysEx MIDI msg |

`_ENTRYoutDump` and `_ENTRYoutWrite` are thin wrappers around Windows `midiOutLongMsg` / `midiOutShortMsg`. They load a singleton object at address `0x10017058`, add offset `0xC0` for the MIDI output subsystem.

## 7-Bit Encoder (at VA 0x411D70)

Standard Yamaha 8-to-7-bit packer, **confirmed identical to our `yamaha_7bit.py`**.

**Algorithm** (decoded from disassembly):
- Main loop: **18 iterations** (0x12), each processing **7 input bytes** into **8 output bytes**
- 18 x 7 = 126 input bytes in main loop
- Tail section: remaining 2 bytes -> 3 output bytes
- Total: **128 input bytes -> 147 output bytes**

Per 7-byte group:
```
out[0] = in[0] >> 1
out[1] = (in[0] & 0x01) << 6 | (in[1] >> 2)
out[2] = (in[1] & 0x03) << 5 | (in[2] >> 3)
out[3] = (in[2] & 0x07) << 4 | (in[3] >> 4)
out[4] = (in[3] & 0x0F) << 3 | (in[4] >> 5)
out[5] = (in[4] & 0x1F) << 2 | (in[5] >> 6)
out[6] = (in[5] & 0x3F) << 1 | (in[6] >> 7)
out[7] = in[6] & 0x7F
```

**Note**: this is a different bit-packing layout than the header-byte approach documented in [7bit-encoding.md](7bit-encoding.md). Both produce the same decoded result but the encoder uses shift-and-merge rather than extract-MSB-to-header. The decoder in `yamaha_7bit.py` (header-byte approach) is the inverse and produces identical output -- confirmed by round-trip test on all 103 SGT messages.

### 7-Bit Round-Trip Mismatch (cosmetic)

Testing all 103 bulk messages in `QY70_SGT.syx` through decode-then-re-encode:
- **92 messages**: 1-byte mismatch at byte 144 (last 7-bit header byte)
- **11 messages**: byte-for-byte identical
- **All 103 messages**: produce **identical decoded data** after round-trip

The mismatch is in **unused low bits** (bits 4-0) of the final 7-bit group header. The last group only has 2 data bytes, so bits 4-0 of the header are never read during decoding. The QY70 hardware sets them to non-zero values; our encoder sets them to zero. This is harmless -- the decoded payload is bit-for-bit identical.

## SysEx Envelope Builder (at VA 0x411E70)

Builds complete SysEx messages:

```
Byte 0:    F0          SysEx start
Byte 1:    43          Yamaha manufacturer ID
Byte 2:    0n          Device number (typically 0x00)
Byte 3:    5F          Model ID (QY70 family)
Byte 4:    01          Fixed
Byte 5:    13          Fixed (bulk data type)
Byte 6:    01          Fixed
Byte 7:    TT          Track number
Byte 8:    SS          Sub-address / block counter
Bytes 9-155: 147 bytes of 7-bit encoded data
Byte 156:  CS          Checksum
Byte 157:  F7          SysEx end
```

**Total: 158 bytes (0x9E)**

**Track number remapping**: tracks 0x10-0x13 get +9 added to sub-address byte (maps to 0x19-0x1C).

## Checksum Algorithm

```
checksum = (-sum_of_bytes_4_through_155) & 0x7F
```

Covers 152 bytes (0x98): from byte[4] through byte[155]. Standard Yamaha two's complement with 7-bit mask. Equivalent to `(128 - (sum & 0x7F)) & 0x7F`.

## SysEx Command Template Table (at VA 0x434630)

Complete embedded SysEx templates found in the binary:

| VA Address | Template (hex) | Purpose |
|-----------|----------------|---------|
| 0x434644 | `F0 7E 7F 06 01 F7` | Identity Request (Universal) |
| 0x43464C | `F0 7E 7F 06 02 43 00 41 02 55 FF FF FF FF F7` | Identity Reply match (QY70, FF=wildcards) |
| 0x43465C | `F0 43 10 5F 00 00 00 01 F7` | Init (start bulk transfer) |
| 0x434668 | `F0 43 10 5F 00 00 00 00 F7` | Close (end bulk transfer) |
| 0x434674 | `F0 43 30 5F 00 00 00 F7` | Dump acknowledgment |
| 0x434680 | `F0 43 10 5F 08 00 00 FF F7` | Parameter request block 0 |
| 0x434688 | `F0 43 10 5F 08 01 00 FF F7` | Parameter request block 1 |
| 0x434694 | `F0 43 10 5F 08 02 00 00 F7` | Parameter request block 2 |
| 0x4346A0 | `F0 43 00 5F 01 13 01 ...` (275B) | Bulk dump Song type 1 |
| 0x4346B0 | `F0 43 00 5F 01 13 02 ...` (275B) | Bulk dump Song type 2 |
| 0x4346C0 | `F0 43 00 5F 00 25 03 ...` (37B) | Bulk dump type 3 (system setup?) |
| 0x4346E0 | `F0 43 00 5F 02 40 05 ...` (576B) | Bulk dump Style |
| 0x4346F0 | `F0 43 00 5F 04 00 05 01` | Receive matching template |

**QY70 Identity**: Manufacturer 0x43 (Yamaha), Family 0x00 0x41, Member 0x02 0x55. FF bytes in the reply template are wildcards for matching.

### Dump Request Templates

| Template | Purpose |
|----------|---------|
| `F0 43 20 5F 01 FF 00 F7` | Dump Request per song slot |
| `F0 43 20 5F 02 FF 00 F7` | Dump Request per style slot |
| `F0 43 20 5F 03 00 00 F7` | Dump Request system data |

Note: substatus `0x20` = Dump Request, `0x30` = Dump Acknowledgment.

## Bulk Dump Send Protocol (at VA 0x40B44D)

**Send path** (from disassembly):

1. Outer loop: **20 tracks** (0x14 iterations)
2. Per track: data size read from `obj+0x442[track*4]` (4 bytes per track = size)
3. Data chunked into **128-byte blocks** (capped at 0x80)
4. Each block: 7-bit encoded (0x411D70) -> SysEx wrapped (0x411E70) -> sent (0x403F80)
5. After 20-track loop: **654-byte (0x28E) system/global block** sent with track=0x7F

**Track count = 20** breaks down as: 8 tracks x (up to) 6 sections in some mapping. The exact section-track mapping is not fully decoded from the disassembly but matches the [address map](sysex-format.md#address-map-ah0x02-am0x7e).

## Bulk Dump Receive Protocol (at VA 0x40E0BF)

**Receive path**:

1. `bl` register = block counter (starts at 0)
2. Receives 0x410 (1040) bytes per MIDI read buffer
3. Matches received header against template at 0x4346F0 (8 bytes: `F0 43 00 5F 04 00 05 01`)
4. Data placement: `destination = buffer_base + bl * 512` (`shl $0x9`)
5. Each received message provides 128 bytes of decoded data
6. After block 0 (bl becomes 1): sends ACK and waits **200ms** (0xC8)
7. After block 1 (bl becomes 2): sets completion flag
8. Timeout: **3000ms** (0xBB8)

**CRITICAL**: the `shl $0x9` (multiply by 512) means each 128-byte decoded block is placed **512 bytes apart** in the destination buffer, leaving 384 bytes gap. This suggests the QY70's internal memory layout has **512-byte block alignment**.

## Byte-Swap Utility (at VA 0x408C10)

Small utility for Yamaha's 14-bit parameter encoding:
```
input:  16-bit value (low byte, high byte)
output: (low_byte & 0x7F) << 7 | (high_byte >> 8) & 0x7F
```
Converts between standard 16-bit and Yamaha's two-7-bit-bytes encoding.

## BLK File Validation

When loading a `.blk` file, QYFiler checks:
1. File size > 0x560 (1376 bytes) -- error: "An error found in the bulk file"
2. SysEx start: `F0 43 xx 5F` (Yamaha, QY70 model)
3. Byte[6] high nibble: `0x0_` = QY70 (valid), `0x1_` = wrong model: "This bulk file is not for QY70"

See [BLK Format](blk-format.md) for file structure details.

## Key Constants Summary

| Value | Hex | Meaning |
|-------|-----|---------|
| 158 | 0x9E | Total SysEx message size |
| 128 | 0x80 | Decoded payload per message |
| 147 | 0x93 | 7-bit encoded payload per message |
| 152 | 0x98 | Bytes included in checksum (bytes 4-155) |
| 18 | 0x12 | Main loop iterations in 7-bit encoder |
| 20 | 0x14 | Number of tracks in send loop |
| 512 | 0x200 | Block alignment in receive buffer |
| 1376 | 0x560 | Minimum valid BLK file size / header skip offset |
| 208 | 0xD0 | BLK file read chunk size |
| 654 | 0x28E | System/global data block size (track 0x7F) |
| 3000 | 0xBB8 | MIDI receive timeout (ms) |
| 200 | 0xC8 | Inter-block delay (ms) |
