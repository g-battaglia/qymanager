# QYFiler.exe Reverse Engineering

Disassembly analysis of Yamaha QY Data Filer (Windows, MSVC 6.0 / MFC). Session 20 (binario) + Session 30g (HLP + deep strings/imports).

**Confidence: HIGH** -- findings from static disassembly of actual Yamaha binary and user manual (.HLP).

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

## MidiCtrl.dll — Deep RE (Session 30g)

**File**: `exe/extracted/Program_Dll_Files/MidiCtrl.dll` (122.880 byte, PE32 i386 DLL, MSVC 6.0 linker)
**Timestamp**: 27 Sep 2000
**Version metadata**: "**DLL Software for Card Filer**", v1.0.4, © 1999 YAMAHA CORPORATION

> Originariamente sviluppata per **Card Filer** (software PCMCIA Yamaha generico), riusata in QYFiler. Spiega perché la DLL è **device-agnostic**: nessuna stringa "QY70/QY700/Yamaha" nel codice, nessun error-table custom, nessun handshake hardcoded. Tutta la logica protocol-specific sta nell'exe parent.

### Singleton pattern

Tutte le 14 export functions sono thin C thunks che dispatchano via vtable verso un singleton `0x10017058` in `.data`. Offset interni noti:
- `+0x10`: last result (HRESULT-like)
- `+0x14`: callback utente (MIDI IN data)
- `+0xC0`: MIDI OUT subsystem base

### Import table — completa

**WINMM** (tutte le funzioni MIDI host):
```
midiInOpen/Close/Start/Stop/Reset
midiInAddBuffer/PrepareHeader/UnprepareHeader
midiInGetNumDevs/GetDevCapsA/GetErrorTextA
midiOutOpen/Close/Reset
midiOutShortMsg/LongMsg
midiOutPrepareHeader/UnprepareHeader
midiOutGetNumDevs/GetDevCapsA/GetErrorTextA
```

**Notevoli**:
- `Sleep` (ord.662), `CreateThread`, `SetThreadPriority`, 4× CriticalSection API
- 5× `Reg*` (HKCU read)
- `WritePrivateProfileStringA` (scrittura .ini in fallback)
- **NO `timeGetTime` / `timeBeginPeriod`**: la DLL non usa high-resolution timing, si appoggia solo ai callback WINMM

### Timing / buffer constants (DLL-interne)

| Valore | Significato |
|--------|-------------|
| `0x40` (64) | `sizeof(MIDIHDR)` — passato a Prepare/UnprepareHeader |
| `0x10` (16) | Slot pool buffer MIDIHDR (`shl $6` stride = 16 × 64 byte) |
| `0x400` (1024) | **Buffer stack SysEx IN** — limite per chunk MIM_LONGDATA |
| `0x30000` | Flag `CALLBACK_FUNCTION` passato a `midiOutOpen` |
| `0x32` (50 ms) | `Sleep(50)` tra iterazioni polling thread IN |
| `0x3E8` (1000) | Loop count / timeout ms |
| `0x143` | Custom WM_USER+0x43 per notifica inter-thread |
| `0x3C3` / `0x3C4` / `0x3C9` | MIM_DATA / MIM_LONGDATA / MOM_DONE |

### SysEx handling — flow dedotto

**`outWrite(buf, len)`**: se `buf[0] < 0xF0` e `len ≤ 3` → `midiOutShortMsg` (pack in DWORD). Altrimenti: alloca slot (GlobalAlloc+Lock), memcpy, `midiOutPrepareHeader(&hdr, 0x40)` + `midiOutLongMsg(&hdr, 0x40)`.

**`outDump`**: long-path di outWrite, scorre i 16 slot cercando uno libero. **Chunking**: una SysEx = una call `midiOutLongMsg`. **La DLL non segmenta SysEx grandi** — dipende dal driver/OS. Il chunking QY70 (128B blocks 7-bit + 147B dopo encoding) è deciso dall'eseguibile parent, NON dalla DLL.

**`inStart`/MIM_LONGDATA handler**: copia bytes in buffer stack da 1024, richiama callback utente via `*0x14(singleton)`, poi re-submits il buffer con `midiInPrepareHeader + midiInAddBuffer` (ring-buffer).

**Error propagation**: `comGetLastResult` legge `+0x10`; `comGetErrorText` wrappa `midi{In,Out}GetErrorTextA`. Nessun error-table custom → errori utente sono quelli standard Windows MME.

### Configuration

Device ID e port ID iniettati dal parent via `comSetDeviceID` e `ctrlSelectDevice`. **Nessun .ini embedded**. Legge `HKCU\Software\Microsoft\Windows\CurrentVersion\Multimedia\MIDIMap\CurrentInstrument` per il default MIDI mapper di sistema.

### Resource strings

UTF-16 dialog strings:
- "MIDI IN Port" / "MIDI OUT Port" — dialog invocato da `ctrlSelectDevice`
- `CMidiInThread` (class name) — thread dedicato con PeekMessage loop

### Take-away per qyconv

- **Limite SysEx IN = 1024 byte** per chunk MIM_LONGDATA. Compatibile con dump QY70 standard (~500B), ma dump > 1KB richiedono concatenazione applicativa.
- **Nessun timing custom**: i 500ms/150ms Init → Bulk → Bulk delay documentati in `quirks.md` sono imposti dal **firmware QY70**, non dalla DLL.
- **No handshake/flow-control**: la DLL dispatcha direttamente al driver. L'affidabilità della trasmissione dipende dall'OS + driver, non dalla DLL.
- Il protocollo QY70 reverse-engineered nel progetto **è compatibile** con come QYFiler chiamava questa DLL (outDump di buffer intero, inStart con callback).

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
| 0x434630 | `F0 7E 7F 09 01 F7` | **GM System On** (Universal Realtime) |
| 0x434638 | `F0 7F 7F 04 01 11 7F F7` | **Master Volume** (Universal Realtime, max) |
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
| 0x4346F8 | `F0 43 20 5F 04 00 00 F7` | **Dump Request AH=0x04 (BULK ALL)** |

**QY70 Identity**: Manufacturer 0x43 (Yamaha), Family 0x00 0x41, Member 0x02 0x55. FF bytes in the reply template are wildcards for matching.

**Implicazione GM On / Master Volume**: il Data Filer resetta lo stato GM e alza il volume prima di trasmettere gli .MID generati via **SMF Data Send**. Match col flusso descritto nel manuale HLP (SMF Data Conv → optional "Add XG header").

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

## QYFiler.HLP — User manual content (extracted)

Windows 3.0 Help file (18879 byte, signature `3F 5F 03 00`, © 1997 Yamaha). Testo topic-blocks in chiaro, dump con `strings`. **No decompression needed** su macOS.

### Target device

QYFiler è **solo per QY70**. Il manuale non menziona mai il QY700 — prodotto distinto (QY700 usa floppy disk + XG SysEx, non il Data Filer PC).

### Comandi principali (5 transfer operations)

| Comando | Direzione | Payload |
|---------|-----------|---------|
| QY Data Save | QY70 → PC | Bulk dump completo → .BLK |
| QY Data Send | PC → QY70 | .BLK → QY70, modi `All` / `One Song` / `One Pattern` |
| SMF Data Conv. | PC filesystem | Converte Song QY70 → .MID (opz. "Add XG header" prepende SysEx XG voice setup) |
| SMF Data Send | PC → QY70 | Invia .MID → slot Song, conversione SMF→QY al volo (proprietario, non documentato) |
| QY Control Ctrl | PC → QY70 | Name list view; CLEAR SONG / CLEAR ALL SONGS / CLEAR USER STYLE / CLEAR ALL USER STYLES |

### Slot ranges confermati

- **Song**: 01-20 (20 slot)
- **User Style / Pattern**: U01-U64 (64 slot)
- **"One Pattern" = "One User Style"** — sinonimi nel manuale

### Stato display requirements

Prima di ogni transfer verso QY70: il device **deve essere in SONG play display o PATTERN play display** (obbligatorio). Play/Record devono essere stoppati.

### Messaggi di stato UI (non error codes)

- "Ready for data transfer"
- "The QY70 bulk file has been created"
- "The Standard MIDI File has been created"
- "Transmission complete"

**Il manuale non espone error codes né SysEx protocol** all'utente. Il lavoro RE è completamente giustificato.

### Add XG Header option (SMF Data Conv)

Se attivata, il converter prepone un SysEx XG di voice setup **prima del primo tick** del file .MID generato, utile per riproduzione su expander XG esterni senza perdere lo stato voci.

### Technical residui

- Fonts: Helv, Symbol, Arial, MS Sans Serif, Times, Wingdings, Century
- Temp path residuo: `C:\WINDOWS\TEMP\~hc10`
- Macro: `BrowseButtons()` (Prev/Next WinHelp 3.0)
- Phrase-table HLP: 4 entries `R:Seq1..Seq4` offsets `0, 1F0, 8630, 108BC`

### Rilevanza per qyconv

Il filer **non documenta**: rotation, bitstream, dense encoding, pattern structure, SysEx format. Conferma memoria `project_qyfiler_re.md` ("barrel rotation is QY70 hardware-internal, BLK=raw SysEx"). Il .BLK è formato opaco by design.

## QYFiler.exe — Deep strings & resources (Session 30g)

### Full DLL imports (9 DLL)

| DLL | Ruolo |
|-----|-------|
| **MidiCtrl.DLL** | MIDI broker (vedi sezione dedicata sopra) |
| KERNEL32.DLL | File I/O, threading, GlobalAlloc |
| USER32.DLL | Window/dialog, messaggi UI |
| GDI32.DLL | Painting (bitmaps 1.1 MB in .rsrc) |
| ADVAPI32.DLL | Registry read/write |
| COMDLG32.DLL | File Open/Save common dialog |
| WINSPOOL.DRV | Print (probabilmente print Name List da QY Control) |
| SHELL32.DLL | ShellExecute per Help / SMF open |
| WINMM.DLL | Backup MIDI se MidiCtrl assente; multimedia timer |

**Fallback pattern**: USER32 MessageBox è usato direttamente per gli error dialog (non via MFC wrapper custom).

### Menu hierarchy (estratta da .rsrc UTF-16LE)

```
File
├── New                Ctrl+N
├── Open...            Ctrl+O
├── Close
├── Save               Ctrl+S
├── Save As...
├── (Recent file list)
└── Exit

QY Data
├── QY Data Save...         ← richiede Dump Request flow
├── QY Data Send...         ← modi All / One Song / One Pattern
├── SMF Data Conv...        ← opz. "Add XG header"
├── SMF Data Send...
└── QY Control...           ← Name list + CLEAR operations

Option
└── MIDI Setup...           ← ctrlSelectDevice (MidiCtrl.dll)

Help
├── Help Topics              ← apre QYFiler.HLP
└── About QY DATA FILER...
```

### Registry path

**Hive**: `HKCU\Software\Local AppWizard-Generated Applications\QY DATA FILER\Settings\`

Chiavi osservate (MFC standard profile):
- `Recent File List\File1..File4` — MRU dei .BLK aperti
- `Settings\MidiInID` (DWORD) — device ID iniettato in MidiCtrl via `comSetDeviceID`
- `Settings\MidiOutID` (DWORD)
- `Settings\AddXgHeader` (DWORD 0/1) — flag per SMF Data Conv
- `Settings\WorkDir` (SZ) — ultima dir I/O

Path tipico "Local AppWizard-Generated" indica che l'applicazione è stata generata dal wizard MFC AppWizard standard senza override del Registry path — consueto per progetti interni Yamaha.

### Error messages table (estratti stringhe UTF-16LE)

Message box mostrati all'utente (14+):

| Messaggio | Contesto |
|-----------|----------|
| "An error found in the bulk file." | Validazione BLK (size < 0x560 o header non-5F) |
| "This bulk file is not for QY70." | Byte[6] high nibble ≠ 0x0_ |
| "The QY70 is not ready for data transfer." | Device non in SONG/PATTERN play display |
| "Communication error with the QY70." | Timeout MIDI IN (3000ms) |
| "Please wait. The QY70 is in bulk transfer mode." | Init inviato ma close pendente |
| "Now Bulk Mode" | Stato blocking durante trasferimento |
| "Ready for data transfer" | Status-bar pre-transfer |
| "The QY70 bulk file has been created." | Dopo QY Data Save |
| "The Standard MIDI File has been created." | Dopo SMF Data Conv |
| "Transmission complete." | Dopo QY Data Send / SMF Data Send |
| "The file is not a QY70 format." | Loading file non-BLK |
| "Cannot open MIDI input/output device." | midiInOpen/midiOutOpen MMSYSERR |
| "Please set the device display to SONG or PATTERN play." | Pre-condition check fail |
| "The operation has been cancelled." | User cancel mid-transfer |

**Nota**: nessun codice numerico — sono tutte stringhe UI. Gli HRESULT sottostanti (da WINMM `midi{In,Out}GetErrorTextA`) non sono mai esposti direttamente.

### English vs Japanese build — confronto

Due build separati (`English_Files/` vs `Japanese_Files/`): **funzionalmente identici**. Differenze limitate a:
- `.rsrc` dialog/menu/string resources (traduzioni UTF-16LE)
- About box version string
- Help file path (stesso .HLP ma con topic-blocks tradotti)

Tutta la code section (`.text`), SysEx template table (0x434630), MidiCtrl.DLL, 7-bit encoder e flow protocol sono **byte-identici**. Conferma che la logica protocol-specific è isolata in codice C++ puro, indipendente dalla lingua UI.

### Timing magic numbers extended

Oltre ai valori già documentati:

| Valore | Hex | Significato |
|--------|-----|-------------|
| 208 | `0xD0` | Chunk read BLK file |
| 300 | `0x012C` | Pausa ms tra Send iterations (non confermato MIDI layer) |
| 400 | `0x0190` | Timeout ACK da QY70 (ms) |
| 1000 | `0x3E8` | Default operation timeout (ms) |

Combinati con 200ms inter-block + 3000ms timeout: finestra operativa totale ~3.5s per un trasferimento standard.

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
