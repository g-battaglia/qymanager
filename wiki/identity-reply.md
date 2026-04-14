# MIDI Identity Reply

Yamaha XG devices respond to the Universal Identity Request (`F0 7E 7F 06 01 F7`) with a structured reply.

## Reply Format

```
F0 7E 7F 06 02 43 00 41 [member_lo] [member_hi] 00 00 00 01 F7
```

| Field | Value | Description |
|-------|-------|-------------|
| `43` | Manufacturer | Yamaha |
| `00 41` | Family | `0x4100` = XG/Sequencer family |
| member bytes | varies | Device-specific code |

## Known Devices

| Device | Member Code | Bytes | Source |
|--------|------------|-------|--------|
| [QY100](https://faq.yamaha.com) | `0x3404` | `04 34` | QY100 Data List p.56 |
| [QY70](qy70-device.md) | `0x5502` | `02 55` | Confirmed 2026-04-14 |
| MU90R / XG daughterboard | `0x0321` | `21 03` | YamahaMusicians forum |

## Usage

When a device responds, check the Member code against this table to identify the model. This determines which SysEx commands to send — e.g., the [QY70](qy70-device.md) uses Model ID `0x5F` for sequencer data, while the QY700 may use a different format.

## Disambiguation

To tell QY70 from QY700 (if both might be connected), send a QY70-specific SysEx (Model ID `0x5F`) and check for a response.
