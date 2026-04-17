# QY Data Filer (Windows Software)

Software utente Yamaha per backup/restore dati QY70 via MIDI su PC Windows. **Solo QY70** — il QY700 usa floppy disk e non è supportato.

Riferimento: estratto da `QYFiler.HLP` (Windows 3.0 Help, 1997 Yamaha). La reverse engineering dell'eseguibile è in [qyfiler-reverse-engineering.md](qyfiler-reverse-engineering.md).

## Installazione

- **OS**: Windows 9x/NT/2000/XP (MFC 6.0 runtime)
- **Binario**: `QYFiler.exe` (1.4 MB, 2000-10-05)
- **DLL**: `MidiCtrl.dll` (122 KB, 2000-09-27)
- **Driver MIDI**: Windows MME (Multimedia Extensions) — nessun ASIO, no MIDI high-resolution
- **MIDI interface**: qualunque con driver MME funzionante

Su macOS/Linux moderni: non gira nativamente, richiede Wine o VM Windows.

## Menu principale

```
File             — file management Windows (New/Open/Save)
QY Data          — 5 comandi di trasferimento
  ├── QY Data Save           QY70 → PC (.BLK)
  ├── QY Data Send           PC (.BLK) → QY70
  ├── SMF Data Conv          Song QY70 → .MID
  ├── SMF Data Send          PC (.MID) → QY70
  └── QY Control             Remote commands
Option
  └── MIDI Setup             Selezione porte MIDI IN/OUT
Help
  ├── Help Topics            Apre QYFiler.HLP
  └── About
```

## 5 comandi transfer — dettaglio

### QY Data Save (QY70 → PC)

Crea un file `.BLK` contenente il bulk dump completo del QY70.

**Prerequisite**: QY70 deve essere in **SONG play display** o **PATTERN play display**, play/record stoppato.

**Flow**:
1. Invia Identity Request `F0 7E 7F 06 01 F7`
2. QY70 risponde con Identity Reply → verifica match
3. Invia Init `F0 43 10 5F 00 00 00 01 F7`
4. Invia Dump Request per ogni tipo (song, pattern, setup)
5. Riceve tutti i bulk dump chunks
6. Invia Close `F0 43 10 5F 00 00 00 00 F7`
7. Scrive i bytes raw in `.BLK`

**Status messages**:
- "Ready for data transfer"
- "The QY70 bulk file has been created."

### QY Data Send (PC → QY70)

Carica un `.BLK` sul QY70.

**Modi** (radio button):
- **All**: tutto il contenuto .BLK → sovrascrive tutto
- **One Song**: seleziona 1 song (01-20) → singolo slot
- **One Pattern**: sinonimo "One User Style" (U01-U64)

**Flow**:
1. Valida header .BLK (`F0 43 xx 5F`, byte[6] high nibble = `0x0_` per QY70)
2. Se size < 0x560 byte → "An error found in the bulk file."
3. Se byte[6] ≠ QY70 → "This bulk file is not for QY70."
4. Init → chunked send (128 B decoded / 147 B encoded per msg) → Close
5. "Transmission complete."

### SMF Data Conv (local conversion)

Converte `.Q7S` song proprietario → **Standard MIDI File** (.MID).

**Opzione "Add XG header"**:
- **OFF**: solo note/CC
- **ON**: prepone SysEx XG (voice setup + effect reset) prima del primo tick

Utile per:
- Riproduzione su DAW
- Archiviazione in formato standard
- Import in altro sequencer XG (PSR/MU serie)

Il converter SMF→QY è **proprietario** (non documentato): riverse engineering non completata.

### SMF Data Send (PC → QY70)

Invia un `.MID` al QY70 slot Song, convertendo SMF → formato QY on-the-fly.

**Prerequisito**: come Data Send, QY70 in SONG display.

**Flow interno** (dedotto da [RE](qyfiler-reverse-engineering.md)):
1. GM System On `F0 7E 7F 09 01 F7` (reset voci)
2. Master Volume max `F0 7F 7F 04 01 11 7F F7`
3. Converti SMF → bulk dump QY
4. Send come Data Send mode "One Song"

### QY Control

Name list view + comandi CLEAR remoti:

| Comando | Effetto |
|---------|---------|
| CLEAR SONG | Azzera 1 song slot |
| CLEAR ALL SONGS | Azzera tutti i song |
| CLEAR USER STYLE | Azzera 1 pattern slot |
| CLEAR ALL USER STYLES | Azzera tutti i pattern |

Invia direttamente i comandi SysEx CLEAR al QY70.

## Slot ranges

- **Song**: 01-20 (20 slot)
- **User Style / Pattern**: U01-U64 (64 slot)
- **User Phrases**: non esposti dal Data Filer (accessibili solo via QY70 UI o bulk ALL)

## Error messages utente

Vedi [qyfiler-reverse-engineering.md](qyfiler-reverse-engineering.md#error-messages-table-estratti-stringhe-utf-16le) per la tabella completa. Principali:

| Msg | Causa |
|-----|-------|
| "An error found in the bulk file." | File corrotto |
| "This bulk file is not for QY70." | File per altro modello |
| "The QY70 is not ready for data transfer." | Device non in SONG/PATTERN display |
| "Communication error with the QY70." | Timeout MIDI (3s) |
| "Please wait. The QY70 is in bulk transfer mode." | Transfer in corso |

## File format

`.BLK` = **raw SysEx** in formato binario. Contiene la sequenza di messaggi SysEx esattamente come trasmessi dal QY70. Vedi [blk-format.md](blk-format.md).

**NO compressione, NO encryption, NO scrambling** — il file è direttamente parsabile come stream SysEx.

## Build English vs Japanese

Due distribuzioni ufficiali: `English_Files/` e `Japanese_Files/`. Funzionalmente identici, differiscono solo in UI strings (dialog/menu/help). Tutta la logica protocol è byte-identica. Vedi [qyfiler-reverse-engineering.md](qyfiler-reverse-engineering.md#english-vs-japanese-build--confronto).

## Relazione con qyconv

`qyconv` replica e supera le funzioni del Data Filer:

| Data Filer | qyconv equivalent |
|------------|-------------------|
| QY Data Save | `midi_tools/request_dump.py`, `midi_tools/capture_dump.py` |
| QY Data Send | `midi_tools/send_style.py`, `midi_tools/restore_pattern.py` |
| SMF Data Conv | `midi_tools/capture_playback.py` (QY70 → MIDI via live capture) |
| SMF Data Send | *non supportato* (funzione proprietaria SMF→QY) |
| QY Control CLEAR | `midi_tools/send_sysex.py` (SysEx manuali) |

**Vantaggi qyconv**: nativo macOS/Linux, scripting, cross-platform, integrazione con analisi/RE. **Limite**: nessun SMF→QY converter (feature proprietaria non documentata).

## Cross-references

- [qyfiler-reverse-engineering.md](qyfiler-reverse-engineering.md) — deep RE del binario
- [blk-format.md](blk-format.md) — formato .BLK
- [qy70-bulk-dump.md](qy70-bulk-dump.md) — procedura bulk dump lato QY70
- [sysex-format.md](sysex-format.md) — struttura SysEx QY70
- `exe/extracted/English_Files/QYFiler.exe` — binario
- `QYFiler.HLP` — manuale user (Win 3.0 Help format)
