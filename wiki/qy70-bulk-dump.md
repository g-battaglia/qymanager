# QY70 Bulk Dump Procedure

Procedura hardware per inviare/ricevere dati dal QY70 via MIDI SysEx. Riferimento: `manual/QY70/QY70_OWNERS_MANUAL.PDF` pag. 120-123.

## Cosa può essere dumpato

Dal menu UTILITY → MIDI → Bulk Dump (F2):

| Target | Contenuto | Dimensione tipica |
|--------|-----------|-------------------|
| **ALL** | All songs + all user styles + system setup | ~2 MB raw, ~2.3 MB 7-bit encoded |
| **SONG** | Un singolo song (slot 01-20) | 30-500 KB |
| **STYLE** | Un singolo user style (U01-U64) | ~16 KB (103 messaggi × 158 B) |
| **SETUP** | System parameters (UTILITY settings) | ~50 B |

## Procedura TX (QY70 → PC)

1. Connettere QY70 MIDI OUT → PC MIDI IN (vedi [midi-setup.md](midi-setup.md))
2. Sul PC: avvia capture SysEx (es. `python3 midi_tools/capture_dump.py`)
3. Sul QY70:
   - Premi **UTILITY**
   - Premi **F2** (MIDI)
   - Seleziona **Bulk Dump** (F2 sub-menu)
   - Scegli target (ALL / SONG / STYLE / SETUP)
   - Se SONG/STYLE: seleziona slot
   - Premi **EXEC** → `Now Sending...`
4. Il display mostra progress. Alla fine → `Complete`.

**Timing**: ~150ms interval tra 1KB blocks (da UTILITY → SYS EXCLUSIVE INTERVAL TIME).

## Procedura RX (PC → QY70)

1. Connettere PC MIDI OUT → QY70 MIDI IN
2. Sul QY70:
   - Premi **UTILITY** → **F2** → **MIDI Receive** ON (o equivalente)
   - QY70 mostra "Waiting..."
3. Sul PC: invia il .syx/.blk file
4. QY70 riceve, mostra progress, alla fine → `Complete`

**CRITICAL**: il QY70 richiede l'Init message (vedi [sysex-format.md](sysex-format.md)) PRIMA del bulk data:
```
F0 43 10 5F 00 00 00 01 F7   ← Init
[bulk data messages]
F0 43 10 5F 00 00 00 00 F7   ← Close
```

## Dump Request remoto (senza UI QY70)

Dal PC, richiede dump singolo via SysEx:

```
F0 43 20 5F AH AM AL F7
```

| AH | AM | AL | Target |
|----|----|----|--------|
| 01 | 00..13 | 00 | Song slot 1..20 |
| 02 | 00..3F | 00 | Pattern slot U01..U64 |
| 03 | 00 | 00 | Setup |
| 04 | 00 | 00 | ALL |

**Prerequisito**: Init message `F0 43 10 5F 00 00 00 01 F7` **DEVE** essere inviato prima. Senza Init, il QY70 ignora il Dump Request (scoperto Session 22).

## Responses per slot vuoto

- Song/Pattern slot vuoto → `F0 F7` (empty response valid)
- Slot valido → bulk dump multi-messaggio

## Esempio pratico

`midi_tools/request_dump.py` implementa il flow completo:
```python
def dump_pattern(slot: int) -> bytes:
    send(b'\xF0\x43\x10\x5F\x00\x00\x00\x01\xF7')  # Init
    time.sleep(0.150)
    send(bytes([0xF0, 0x43, 0x20, 0x5F, 0x02, slot, 0x00, 0xF7]))
    data = capture_until_idle(timeout=3.0)
    send(b'\xF0\x43\x10\x5F\x00\x00\x00\x00\xF7')  # Close
    return data
```

## QYFiler alternative

Il software Windows [QYFiler.exe](qyfiler-reverse-engineering.md) offre UI:
- **QY Data Save**: equivalente a Bulk Dump ALL → .BLK file
- **QY Data Send**: equivalente a RX procedure → manda .BLK al QY70

.BLK e .syx sono formati equivalenti (raw SysEx). Vedi [blk-format.md](blk-format.md).

## Troubleshooting

| Sintomo | Causa probabile |
|---------|-----------------|
| QY70 non risponde a Dump Request | Manca Init message |
| Dump incompleto / corrotto | Interval Time troppo basso (aumentare UTILITY → SYS EXCLUSIVE) |
| QY70 freeze durante RX | SysEx non valido / checksum errato — power cycle |
| "Now Bulk Mode" persistente | Close message non inviato |

## Cross-references

- [sysex-format.md](sysex-format.md) — struttura messaggi SysEx
- [midi-setup.md](midi-setup.md) — cablaggio hardware
- [blk-format.md](blk-format.md) — formato file .BLK
- [quirks.md](quirks.md) — quirk Init handshake
- `midi_tools/request_dump.py`, `midi_tools/send_style.py` — script operativi
