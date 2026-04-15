# 7-Bit Encoding

Yamaha's standard scheme for packing 8-bit data into MIDI SysEx (which requires all bytes ≤ 127).

## Principle

For every 7 bytes of raw data:
1. Extract bit 7 from each byte
2. Pack those 7 high bits into a "header" byte
3. Clear bit 7 in the original bytes
4. Output: 1 header + 7 data = **8 encoded bytes**

Ratio: 7 raw → 8 encoded (14% overhead).

## Header Byte Layout

```
Header: [b6 b5 b4 b3 b2 b1 b0 0]
         │  │  │  │  │  │  │
         │  │  │  │  │  │  └── Bit 7 of byte 6
         │  │  │  │  │  └───── Bit 7 of byte 5
         │  │  │  │  └──────── Bit 7 of byte 4
         │  │  │  └─────────── Bit 7 of byte 3
         │  │  └────────────── Bit 7 of byte 2
         │  └───────────────── Bit 7 of byte 1
         └──────────────────── Bit 7 of byte 0
```

## Example

Raw: `80 40 20 10 08 04 02` (7 bytes)
High bits: `1 0 0 0 0 0 0` → Header: `0x40`
Encoded: `40 00 40 20 10 08 04 02` (8 bytes)

## Code

```python
def decode_7bit(encoded: bytes) -> bytes:
    result = bytearray()
    for i in range(0, len(encoded), 8):
        header = encoded[i]
        for j in range(1, min(8, len(encoded) - i)):
            high_bit = (header >> (7 - j)) & 1
            result.append(encoded[i + j] | (high_bit << 7))
    return bytes(result)
```

## Usage in QY70

All [SysEx bulk dump](sysex-format.md) data payloads use this encoding. The byte count in the message header refers to the **encoded** size. After decoding:
- 128 encoded bytes → 112 decoded bytes (but QY70 uses 147 → 128)
- Track data and [header section](header-section.md) data are always decoded before analysis

The [QY700](q7p-format.md) does NOT use 7-bit encoding — its `.Q7P` files are raw 8-bit binary.

## QYFiler.exe Confirmation (Session 20)

[Disassembly of QYFiler.exe](qyfiler-reverse-engineering.md#7-bit-encoder-at-va-0x411d70) at VA 0x411D70 confirmed the encoder implementation. It uses a different bit-packing layout (shift-and-merge per 7-byte group) but produces identical results to the header-byte approach above.

**Encoder algorithm** (from disassembly):
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

Main loop: 18 iterations x 7 bytes = 126 bytes, plus 2-byte tail = **128 input -> 147 output**.

### Round-Trip Validation

Testing all 103 SGT messages through decode->re-encode:
- **92 messages**: 1-byte mismatch at byte 144 (unused low bits of final group header)
- **11 messages**: byte-for-byte identical
- **All 103**: identical decoded data -- mismatch is in padding bits, irrelevant for data integrity

**CRITICAL**: the 7-bit encoding is the ONLY transformation in QYFiler. There is [no rotation or scrambling](qyfiler-reverse-engineering.md#critical-finding-no-rotation-or-scrambling) -- barrel rotation happens inside QY70 hardware.
