# QY700 Bricking Diagnosis

The `qy70_to_qy700.py` converter caused the [QY700](qy700-device.md) to hang when loading converted patterns.

## Root Cause

`_extract_and_apply_voices()` wrote to 3 **unconfirmed** offsets in the [Q7P file](q7p-format.md):

| Offset | Hypothesized As | Written Value | Actual Content |
|--------|----------------|---------------|----------------|
| `0x1E6 + track` | Bank MSB | `0x7F` (for drums) | ALL ZERO in both test files |
| `0x1F6 + track` | Program Change | voice program | ALL ZERO in both test files |
| `0x206 + track` | Bank LSB | bank LSB | ALL ZERO in both test files |

**Confirmation**: deep diff of T01.Q7P vs TXX.Q7P showed all 3 areas are identically zero. The "Bank MSB/Program/LSB" hypothesis was wrong.

Writing `0x7F` into an area that must be zero corrupted the file structure.

## Fixes Applied (Session 11)

1. **Disabled `_extract_and_apply_voices()`** — the method still exists but is not called. No writes to unconfirmed offsets.
2. **Fixed pan bounds check**: `< 0x246` → `< 0x2C0` (the old check was a total no-op since pan starts at 0x276).
3. **Added `_validate_critical_areas()`** — post-conversion check that reserved areas match the template.

## Safety Rules

1. **Never write to unconfirmed offsets** in Q7P files — use a whitelist approach.
2. **Always validate** converted files against the template before use.
3. **Test incrementally**: modify one field at a time and verify on hardware.
4. The `safe_q7p_tester.py` script generates diagnostic Q7P files for incremental testing.

## Recovery

The "brick" is a software hang, not hardware damage:
- Power cycle usually recovers the device
- Loading a clean Q7P (TXX.Q7P template) restores normal operation
- Factory reset is available from the QY700 menu

## Confirmed Safe Offsets

| Offset | Field | Write Safety |
|--------|-------|-------------|
| `0x876` | Pattern name (10 bytes ASCII) | Safe |
| `0x188` | Tempo (2 bytes BE) | Safe |
| `0x226` | Volume (16 bytes) | Safe |
| `0x276` | Pan (within bounds) | Safe |
| `0x246` | Chorus Send (16 bytes) | Safe |
| `0x256` | Reverb Send (16 bytes) | Safe |
| `0x1E6/0x1F6/0x206` | RESERVED | **DANGEROUS** |
