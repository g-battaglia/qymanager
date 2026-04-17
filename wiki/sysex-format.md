# QY70 SysEx Format

The [QY70](qy70-device.md) uses MIDI System Exclusive messages for bulk data transfer.

## Message Structure

```
F0 43 0n 5F BH BL AH AM AL [data...] CS F7
```

| Field | Size | Description |
|-------|------|-------------|
| `F0` | 1 | SysEx Start |
| `43` | 1 | Yamaha Manufacturer ID |
| `0n` | 1 | Message type + device number (n=0-15) |
| `5F` | 1 | QY70 Sequencer Model ID |
| `BH BL` | 2 | Byte count: `(BH << 7) \| BL` |
| `AH AM AL` | 3 | Address (AH=0x02, AM=0x7E for style data) |
| data | var | [7-bit encoded](7bit-encoding.md) payload |
| `CS` | 1 | Checksum |
| `F7` | 1 | SysEx End |

## Message Types

| Device Byte | Type | Description |
|-------------|------|-------------|
| `0x0n` | Bulk Dump | Data transfer block |
| `0x1n` | Parameter Change | Single parameter (no checksum) |
| `0x2n` | Dump Request | Request data from QY70 |
| `0x3n` | Dump Acknowledgment | ACK from QY70 (found in [QYFiler templates](qyfiler-reverse-engineering.md#sysex-command-template-table-at-va-0x434630)) |

**Dump Request** works for user pattern slots (AM=0x00-0x3F). Format: `F0 43 20 5F AH AM AL F7`. Does NOT work for edit buffer (AM=0x7E). Session 16 received `F0 F7` from AM=0x00 (valid empty-pattern response). [QYFiler.exe](qyfiler-reverse-engineering.md) also uses AM=0xFF in templates (possibly "all slots" wildcard). See [MIDI Setup](midi-setup.md).

## Checksum

```python
def calculate_checksum(address_and_data: bytes) -> int:
    return (128 - (sum(address_and_data) & 0x7F)) & 0x7F
```

## Address Map (AH=0x02, AM=0x7E)

| AL Range | Description |
|----------|-------------|
| `0x00-0x07` | Section 0 tracks 0-7 |
| `0x08-0x0F` | Section 1 tracks 0-7 |
| ... | ... |
| `0x28-0x2F` | Section 5 tracks 0-7 |
| `0x7F` | [Header/config](header-section.md) (640 decoded bytes) |

**Addressing**: `AL = section_index * 8 + track_index`

See [Track Structure](track-structure.md) for section/track layout.

## Top-level AH Map (Session 28)

AH value sweep against live QY70 revealed multiple top-level dumpable areas:

| AH | Purpose | Size | Msg count |
|----|---------|------|-----------|
| `0x00` | Pattern body (slot N via AM) | 16274 B | 103 |
| `0x01` | Song slot (per QYFiler template) | — | — |
| `0x02` | Style/pattern tracks (AL addressing) | — | — |
| `0x03` | System meta trailer | 48 B | 1 |
| `0x04` | Full dump = `AH=0x00` + `AH=0x03` | 16322 B | 104 |
| `0x05` | [Pattern name directory](pattern-directory.md) | 331 B | 1 |

AL appears to be ignored by the QY70 for `AH=0x00/0x04/0x05` — the device returns the full fixed-size area regardless. AM selects the pattern slot for `AH=0x00`.

## Complete Transfer Sequence

1. **Init**: `F0 43 10 5F 00 00 00 01 F7` (Parameter Change)
2. **Track data**: Bulk Dump messages for each active track (AL 0x00-0x2F)
3. **Header**: Bulk Dump messages at AL=0x7F (5 × 128 decoded bytes)
4. **Close**: `F0 43 10 5F 00 00 00 00 F7` (Parameter Change)

## Track Data Sizes (decoded bytes)

| Track | Size | Messages |
|-------|------|----------|
| RHY1 (D1) | 768 | 6 × 128 |
| RHY2 (D2) | 256 | 2 × 128 |
| BASS (PC) | 128 | 1 × 128 |
| CHD1-PHR2 | 128-256 | 1-2 × 128 |

Each message carries up to 128 decoded bytes (147 encoded bytes after [7-bit packing](7bit-encoding.md)).

## QYFiler Command Templates (Session 20 + 30g)

[QYFiler.exe disassembly](qyfiler-reverse-engineering.md) revealed a complete template table at VA 0x434630:

| Template | Purpose |
|----------|---------|
| `F0 7E 7F 09 01 F7` | **GM System On** (Universal Realtime) |
| `F0 7F 7F 04 01 11 7F F7` | **Master Volume max** (Universal Realtime) |
| `F0 7E 7F 06 01 F7` | Identity Request |
| `F0 7E 7F 06 02 43 00 41 02 55 FF FF FF FF F7` | Identity Reply match (FF=wildcards) |
| `F0 43 10 5F 00 00 00 01 F7` | Init (start transfer) |
| `F0 43 10 5F 00 00 00 00 F7` | Close (end transfer) |
| `F0 43 30 5F 00 00 00 F7` | Dump acknowledgment |
| `F0 43 20 5F 01 FF 00 F7` | Dump Request song slot |
| `F0 43 20 5F 02 FF 00 F7` | Dump Request style slot |
| `F0 43 20 5F 03 00 00 F7` | Dump Request system data |
| `F0 43 20 5F 04 00 00 F7` | Dump Request BULK ALL (AH=0x04) |

**Send protocol**: 20 tracks in a loop, each chunked into 128-byte blocks, 7-bit encoded, SysEx wrapped, then a 654-byte system block at track=0x7F.

**Receive protocol**: 512-byte block alignment in destination buffer (128 decoded bytes placed 512 apart). 200ms inter-block delay. 3000ms timeout.

**No data transformation**: [QYFiler performs NO rotation or scrambling](qyfiler-reverse-engineering.md#critical-finding-no-rotation-or-scrambling) -- the barrel rotation is applied by the QY70 hardware internally.

## Official Protocol (QY70 Manual Table 1-9, pag. 63)

Il manuale elenca il protocollo ufficiale Sequencer (Model ID `5F`). Questi formati e indirizzi sono la reference documentata (vs. scoperte empiriche sopra).

### Formati ufficiali

| Operazione | Formato | Note |
|------------|---------|------|
| Bulk Dump data | `F0 43 0n 5F BH BL H M L [data...] CS F7` | 147B max, split per files lunghi |
| Parameter Change | `F0 43 1n 5F H M L data F7` | Solo per bulk mode / clear |
| Dump Request | `F0 43 2n 5F H M L F7` | Nessun payload |
| Parameter Request | `F0 43 3n 5F H M L F7` | Return Parameter Change |

### Address Table (Sequencer Parameter Address)

| Area | `H M L` | Size | Recv | Trans | Req |
|------|---------|------|------|-------|-----|
| SYSTEM bulk mode on/off | `00 00 00` | 1 | ✓ | ✓ | ✓ |
| SONG slot 1..20 | `01 00 00` .. `01 13 00` | 147 | ✓ | ✓ | ✓ |
| SONG all | `01 7F 00` | 147 | ✓ | ✓ | ✗ |
| PATTERN slot 1..64 | `02 00 00` .. `02 3F 00` | 147 | ✓ | ✓ | ✓ |
| PATTERN all | `02 7F 00` | 147 | ✓ | ✓ | ✗ |
| SETUP | `03 00 00` | 32 | ✓ | ✓ | ✓ |
| BULK ALL | `04 00 00` | 147 | ✓ | ✓ | ✗ |
| INFO song | `05 00 00` | 320 | ✗ | ✓ | ✓ |
| INFO pattern 1-32 | `05 01 00` | 512 | ✗ | ✓ | ✓ |
| INFO pattern 33-64 | `05 01 01` | 512 | ✗ | ✓ | ✓ |
| COMMAND clear song/pattern | `08 00 00` | 1 | ✓ | ✗ | ✓ |

### Implicazione chiave

**Parameter Change NON supporta modifica atomica di tempo/nome/tracce** — gli unici indirizzi Parameter Change documentati sono `00 00 00` (bulk mode) e `08 00 00` (clear). Il pattern è un blob monolitico di 147B (multipli se lungo). Per editare tempo va usato il ciclo `dump → edit blob → send`.

### Discrepanza con nostro protocollo

Il nostro empirico `F0 43 20 5F 02 7E 7F F7` (session 22+) **non è documentato** nella Table 1-9:
- Manuale: pattern all = `02 7F 00` (M=0x7F, L=0x00)
- Nostro: `02 7E 7F` (M=0x7E, L=0x7F) → probabilmente edit buffer undocumented

Entrambi funzionano sul QY70 reale ma restituiscono formati diversi (edit buffer ha header `AL=0x7F`, request ufficiale probabilmente no). Scoperto session 30c: `F0 43 20 5F 02 7F 00 F7` restituisce dump senza header AL=0x7F. Da indagare.

### Tone generator XG (Model ID 4C) — protocollo separato

Oltre al sequencer (5F), il QY70 espone il tone generator XG come sistema SysEx separato (Model `4C`) con Parameter Change **granulari**:
- MULTI PART (voice, volume, pan, filter, EG per ogni part)
- EFFECT 1 (reverb/chorus/variation)
- DRUM SETUP
- SYSTEM (master tune, master volume, transpose)

Formato: `F0 43 1n 4C AH AM AL data F7`.

Non è parte del pattern data ma utile per controllo in tempo reale del sound engine. Ref: manual pag. 56-62 tables 1-2..1-7.

## Realtime & System Common Messages (Sequencer sync)

Il QY70 come sequencer trasmette/riceve anche MIDI Realtime e System Common per sync con device esterni (da QY70_LIST_BOOK pag 50-51):

| Status | Type | Direction | Use |
|--------|------|-----------|-----|
| `F8` | Timing Clock | TX (MIDI SYNC=Internal) / RX (MIDI SYNC=External) | 24 ppq clock |
| `FA` | Start | TX/RX | Avvia playback da bar 1 |
| `FB` | Continue | TX/RX | Resume da posizione corrente |
| `FC` | Stop | TX/RX | Stop playback |
| `F2 lsb msb` | Song Position Pointer | TX/RX | Posizione in 6-tick MIDI beats |
| `F3 song#` | Song Select | RX | Seleziona song 0-19 (slot) |
| `FE` | Active Sensing | RX | Ignored (può essere filtrato) |
| `FF` | Reset | RX | System reset |

**Transmission flow** (QY70 → PC): Timing Clock trasmesso quando `MIDI SYNC = Internal`, non trasmesso quando External (il QY70 segue il master esterno).

**Receive flow**: il QY70 riceve tutto il Realtime/Common per permettere sync remoto quando configurato come slave.

## Also See

- [BLK Format](blk-format.md) — QY Data Filer file format (.blk = raw SysEx)
- [QYFiler RE](qyfiler-reverse-engineering.md) — Full disassembly analysis
- [xg-parameters.md](xg-parameters.md) — Model 4C XG Parameter Change (atomic tone-gen edit)
- [quirks.md](quirks.md) — Documented non-standard behaviour (primo-bulk-only, ecc.)
