# XG Default Values

Both the [QY70](qy70-device.md) and [QY700](qy700-device.md) follow the Yamaha XG specification.

## Standard Parameters

| Parameter | Default | Hex | Notes |
|-----------|---------|-----|-------|
| Volume | 100 | `0x64` | |
| Pan | 64 (Center) | `0x40` | 0=Random, 1-63=Left, 64=Center, 65-127=Right |
| Reverb Send | 40 | `0x28` | |
| Chorus Send | 0 | `0x00` | |
| Variation Send | 0 | `0x00` | |
| Bank MSB (Normal) | 0 | `0x00` | |
| Bank MSB (Drums) | 127 | `0x7F` | |

## MIDI Channel Conventions

- Channel 10 = Drums (always)
- Channels 1-9, 11-16 = Melodic instruments

## XG Model IDs

| Model ID | Purpose |
|----------|---------|
| `0x4C` | Tone Generator (voice/effect parameters) |
| `0x5F` | Sequencer (pattern/style/song data) |

## XG Voice Reference

- [Studio4All XG Reference](https://www.studio4all.de/htmle/main90.html)
- Bank Select MSB + Bank Select LSB + Program Change selects a voice
- Common voices: 0/0/0 = Acoustic Grand Piano, 0/0/33 = Finger Bass, 127/0/0 = Standard Kit
