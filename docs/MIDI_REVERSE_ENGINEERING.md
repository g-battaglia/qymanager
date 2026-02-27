# MIDI Reverse Engineering - QY70 Live Access

## Stato Connessione

| Componente | Stato | Note |
|---|---|---|
| Interfaccia MIDI | **Steinberg UR22C** | Porta: "Steinberg UR22C Porta 1" (input + output) |
| CoreMIDI | Funzionante | Multipli input/output (filtrare porte Logic Pro) |
| mido + python-rtmidi | Installato | v1.3.3 + v1.5.8 |
| QY70 collegato | **FUNZIONANTE** | Note MIDI ricevute, bulk dump catturato con successo |

**Nota**: Il cavo USB-MIDI generico (VID:0x15CA) NON funziona per ricevere dati.
Usare Steinberg UR22C o interfaccia equivalente.

---

## Tool MIDI Disponibili

### `midi_tools/list_ports.py`
Mostra le porte MIDI disponibili sul sistema.
```bash
source .venv/bin/activate
python3 midi_tools/list_ports.py
```

### `midi_tools/probe_identity.py`
Invia un Identity Request (F0 7E 7F 06 01 F7) e aspetta la risposta del QY70.
Verifica che il QY70 sia acceso, collegato, e risponda via MIDI.
```bash
python3 midi_tools/probe_identity.py
python3 midi_tools/probe_identity.py --timeout 10
```

### `midi_tools/capture_dump.py`
Cattura un bulk dump SysEx dal QY70. L'utente deve avviare il dump manualmente
dal menu del QY70: `UTILITY -> MIDI -> Bulk Dump`.
```bash
python3 midi_tools/capture_dump.py                    # Default: 60s timeout
python3 midi_tools/capture_dump.py --timeout 120      # 2 min timeout
python3 midi_tools/capture_dump.py -o captured/my.syx # Output specifico
```

### `midi_tools/send_request.py`
Invia un Dump Request al QY70 per richiedere dati specifici senza intervento manuale.
```bash
python3 midi_tools/send_request.py --address 02 7E 7F    # Solo header
python3 midi_tools/send_request.py --address 02 7E 08    # Intro Track 1
python3 midi_tools/send_request.py --style                # Full style dump
```

---

## Piano di Reverse Engineering

### Sessione 1: Verifica Connessione
- [x] Installare mido + python-rtmidi
- [x] Verificare porte MIDI
- [x] Identity probe -> QY70 NON risponde a Identity Request ne' a Dump Request
- [x] Cattura bulk dump di test -> catturato pattern (808 bytes, 7 messaggi)
- [x] Interfaccia funzionante: Steinberg UR22C (il cavo generico USB-MIDI non funziona)

### Sessione 2: Mappatura Program Change / Bank Select
**Obiettivo**: Trovare gli offset nel formato Q7P per Program Change e Bank Select.

**Procedura**:
1. Sul QY70, creare un pattern/style con strumenti NOTI su ogni traccia:
   - D1: Standard Kit (Prg 0, Bank 127/0)
   - D2: Room Kit (Prg 8, Bank 127/0)
   - BA: Finger Bass (Prg 33, Bank 0/0)
   - C1: E.Piano 1 (Prg 4, Bank 0/0)
   - C2: Strings Ensemble (Prg 48, Bank 0/0)
   - C3: Brass Section (Prg 61, Bank 0/0)
   - C4: Flute (Prg 73, Bank 0/0)
2. Bulk dump -> cattura
3. Analisi hex: cercare i valori Program noti nei dati decodificati
4. Confronto con template vuoto per isolare gli offset

### Sessione 3: Parametri Mixer
**Obiettivo**: Trovare offset per Chorus Send, Variation Send, Expression.

**Procedura**:
1. Pattern con valori mixer distinti per traccia:
   - D1: Vol=100, Pan=C, Rev=40, Cho=0
   - BA: Vol=80, Pan=L30, Rev=20, Cho=50
   - C1: Vol=110, Pan=R40, Rev=60, Cho=80
2. Bulk dump -> confronto con default
3. Isolare offset Chorus Send (attualmente sconosciuto)

### Sessione 4: Time Signature e Section Length
**Obiettivo**: Decodificare time signature e lunghezza sezioni.

**Procedura**:
1. Pattern in 3/4 -> dump -> confronto con pattern in 4/4
2. Pattern in 6/8 -> dump -> confronto
3. Sezione con 8 battute vs 4 battute -> confronto

### Sessione 5: Phrase/Sequence Data
**Obiettivo**: Comprendere il formato dei dati MIDI nelle phrase.

**Procedura**:
1. Pattern con sequenza MIDI semplice nota (es. solo C4 quarter notes)
2. Dump -> analisi dei byte nella regione phrase
3. Confronto con il formato eventi gia' noto (D0/E0/A0/BE/F2)

---

## Formato SysEx QY70 - Riferimento

### Struttura messaggio Bulk Dump
```
F0 43 0n 5F BH BL AH AM AL [data...] CS F7
│  │  │  │  │  │  │  │  │   │         │  └─ End
│  │  │  │  │  │  │  │  │   │         └──── Checksum
│  │  │  │  │  │  │  │  │   └────────────── 7-bit encoded payload
│  │  │  │  │  │  │  │  └────────────────── Address Low (section/track)
│  │  │  │  │  │  │  └───────────────────── Address Mid (0x7E = user style)
│  │  │  │  │  │  └──────────────────────── Address High (0x02 = style data)
│  │  │  │  │  └─────────────────────────── Byte count low
│  │  │  │  └──────────────────────────────  Byte count high
│  │  │  └─────────────────────────────────  Model ID (0x5F = QY70)
│  │  └────────────────────────────────────  0n = bulk dump, 1n = param change, 2n = dump request
│  └───────────────────────────────────────  Yamaha manufacturer ID
└──────────────────────────────────────────  SysEx start
```

### Indirizzi AL (Address Low)

**CRITICO: Schema AL corretto (confermato da SGT dump, 2026-02-26)**

Lo schema precedente era SBAGLIATO. Non esiste una regione "phrase data" separata
ad AL 0x00-0x05. TUTTI gli AL 0x00-0x2F sono dati traccia:

```
AL = section_index * 8 + track_index

Section 0 (Intro):   AL 0x00-0x07  (8 tracks: D1,D2,PC,BA,C1,C2,C3,C4)
Section 1 (Main A):  AL 0x08-0x0F
Section 2 (Main B):  AL 0x10-0x17
Section 3 (Fill AB): AL 0x18-0x1F
Section 4 (Fill BA): AL 0x20-0x27
Section 5 (Ending):  AL 0x28-0x2F
Header/Config:       AL 0x7F       (640 bytes decoded, 5 messaggi)
```

| AL Range | Contenuto |
|---|---|
| 0x00-0x07 | Intro track data (8 tracks) |
| 0x08-0x0F | Main A track data (8 tracks) |
| 0x10-0x17 | Main B track data (8 tracks) |
| 0x18-0x1F | Fill AB track data (8 tracks) |
| 0x20-0x27 | Fill BA track data (8 tracks) |
| 0x28-0x2F | Ending track data (8 tracks) |
| 0x7F | Style header/config |

Per pattern (formato singolo): solo AL 0x00-0x07 + AL 0x7F.

### Messaggi di controllo
```
F0 43 1n 5F 00 00 00 01 F7   Init (prepara per bulk dump)
F0 43 1n 5F 00 00 00 00 F7   Close (fine bulk dump)
F0 43 2n 5F AH AM AL F7      Dump Request (richiedi dati)
F0 7E 7F 06 01 F7            Identity Request (standard MIDI)
```

---

## Log delle Sessioni

### Sessione 0 - Setup (2026-02-26)
- Installato mido 1.3.3 + python-rtmidi 1.5.8
- Interfaccia "USB Midi Cable" rilevata su CoreMIDI
- Porte: Input "USB Midi Cable", Output "USB Midi Cable"
- Creati 4 script in midi_tools/
- Aggiunto `mido` come dipendenza opzionale `[midi]` in pyproject.toml

### Sessione 1 - Live Connection + Bulk Dump (2026-02-26)
- Cavo USB-MIDI generico NON funziona per ricevere dati dal QY70
- Switchato a Steinberg UR22C -> ricezione immediata di 104 note MIDI
- QY70 NON risponde a Universal Identity Request (F0 7E 7F 06 01 F7)
- QY70 NON risponde a Yamaha Dump Request (F0 43 2n 5F ...) - dump solo manuale
- Catturato bulk dump pattern: `midi_tools/captured/qy70_dump_20260226_200743.syx`
  - 808 bytes, 7 messaggi SysEx
  - Formato PATTERN (header[0] = 0x2C), non style
  - Solo AL=0x00 (2 bytes) e AL=0x7F (640 bytes header)
- Creato `midi_tools/midi_monitor.py` per monitoraggio real-time

### Sessione 2 - Deep Analysis (2026-02-26)
- Analisi completa header SGT (AL=0x7F, 640 bytes decoded)
- Confronto byte-by-byte pattern vuoto vs SGT style:
  - 31 regioni differenti, 130 bytes identici nella zona strutturale (0x137-0x1B8)
  - Header[0] = 0x2C (pattern) vs 0x5E (style) -> confermato marker formato
- Mappatura track header (24 bytes per track):
  - bytes 0-11: Common prefix `08 04 82 01 00 40 20 08 04 82 01 00`
  - bytes 12-13: Constants `06 1C`
  - bytes 14-15: Voice encoding (0x40 0x80=drum, 0x00 0x04=bass, bank+prg per chord)
  - bytes 16-17: Note range (drums: 0x87 0xF8, melody: 0x07 0x78)
  - bytes 18-20: Track type flags (drums: 80 8E 83, bass: 00 07 12, chord: 00 0F 10)
  - bytes 21-22: Pan (0x41 0x40 = flag+value, 0x00 0x00 = use default)
- Confermato: track header identico in tutte le 6 sezioni per ogni track
- **Bug fix**: Canali MIDI TR5-TR12 tutti "Ch 4" -> risolto (0x03 era group marker)
- **Bug fix**: Pan=0 mostrava "L64" -> risolto (ora mostra "Rnd")
- **Bug fix**: Time signature 0x1C parsava come 1/4096 -> gia' risolto con lookup table
- Tempo encoding confermato: `tempo = (range * 95 - 133) + offset`

### Sessione 3 - AL Addressing Fix + NEONGROOVE + Regression Fix (2026-02-26)
- **SCOPERTA CRITICA**: Schema AL era SBAGLIATO in tutto il codebase
  - Vecchio (errato): AL = 0x08 + section*8 + track (con "phrase data" a 0x00-0x05)
  - Nuovo (corretto): AL = section*8 + track (confermato da SGT reference dump)
  - NON esiste regione "phrase data" separata — tutti AL 0x00-0x2F sono dati traccia
- Fix applicato in 6 file:
  - `syx_analyzer.py`: TRACK_SECTION_START=0x00, format detection, section building
  - `qy700_to_qy70.py`: base_al = section_idx * 8
  - `qy70_to_qy700.py`: al = section_idx * 8 + track_num
  - `reader.py`: SECTION_MAP usa indici 0-5, _parse_section raccoglie 8 tracce per sezione
  - `writer.py`: _write_section scrive ogni traccia al suo AL corretto
  - `cli/commands/info.py`: display strings e calcolo AL
- **NEONGROOVE custom style creato**: `tests/fixtures/NEONGROOVE.syx`
  - 16,450 bytes, 106 messaggi, 128 BPM
  - Tutti i checksum validi, struttura conforme a SGT
- **Bug fix D1 voice regression**:
  - Root cause: messaggi Init/Close (PARAMETER_CHANGE addr 00/00/00) condividevano
    AL=0x00 con Section 0 Track 0, iniettando 2 byte spuri nei dati traccia
  - Questo spostava tutti gli offset di 2 bytes, causando lettura voce errata
  - Fix: solo messaggi style data (AH=0x02, AM=0x7E) vengono accumulati per AL
  - Bonus: conteggio checksum ora corretto (103 valid, 0 invalid vs precedente 103+2 "invalid")
- **SCOPERTA**: Formato eventi traccia (bytes 24+) NON usa il formato D0/E0/BE/F2
  documentato per Q7P — e' una rappresentazione binaria packed interna non ancora decodificata

---

## Scoperte Formato SysEx QY70

### Header (AL=0x7F) - Decoded 640 bytes

| Offset | Size | Contenuto | Confermato |
|--------|------|-----------|------------|
| 0x000 | 1 | Format marker: 0x2C=pattern, 0x5E=style | Si |
| 0x001-0x005 | 5 | Sempre `00 00 00 00 80` | Si |
| 0x006-0x009 | 4 | Style data (varia tra formati) | Parziale |
| 0x00A-0x00B | 2 | Sempre `01 00` | Si |
| 0x010-0x044 | 53 | Repeating 7-byte groups (section config?) | No |
| 0x044-0x07F | 60 | Voice/mixer data (zeros in empty pattern) | Parziale |
| 0x080-0x087 | 8 | Common prefix `03 01 40 60 30` + timing | Si |
| 0x088-0x08D | 6 | Timing flags (differ between formats) | Parziale |
| 0x096-0x0B7 | 34 | Per-track config region | No |
| 0x0B8-0x0C5 | 14 | Common structure (identical) | Si |
| 0x137-0x1B8 | 130 | Structural template (always identical) | Si |
| 0x1B9-0x21B | 99 | **MIXER PARAMETERS** (vol/rev/cho bit-packed) | Si (sessione 4) |
| 0x21C-0x27F | 100 | Tail data (fill patterns + config) | Parziale |

### Track Data Header (per track, 24+ bytes)

| Byte | Contenuto | Note |
|------|-----------|------|
| 0-11 | `08 04 82 01 00 40 20 08 04 82 01 00` | Fixed common prefix |
| 12-13 | `06 1C` | Constants (timing?) |
| 14 | Voice byte 1 | 0x40=drum default, 0x00=bass/chord, N=bank_msb |
| 15 | Voice byte 2 | 0x80=drum, 0x04=bass marker, N=program |
| 16 | Note low | 0x87=drum, 0x07=C-2 (melody) |
| 17 | Note high | 0xF8=drum, 0x78=C8 (melody) |
| 18 | Flag byte 1 | 0x80=drum, 0x00=melody |
| 19 | Flag byte 2 | 0x8E=drum, 0x07=bass, 0x0F=chord |
| 20 | Flag byte 3 | 0x83=drum, 0x12=bass, 0x10=chord |
| 21 | Pan flag | 0x41=pan value valid, 0x00=use default |
| 22 | Pan value | 0x40=center, 0-127 |
| 23 | Unknown | Always 0x00 |
| 24+ | MIDI sequence data | Variable length |

### Event Data Structure (bytes 24+) - PARZIALMENTE DECODIFICATO

**Scoperta chiave (2026-02-26):** I dati evento NON usano il formato D0/E0/BE/F2 documentato
per Q7P. E' un formato packed interno.

**Struttura identificata per tracce chord (C1-C4):**

```
[4B sub-header][7B preamble][N barre di 41-42B ciascuna][DC 00 terminator]

Esempio C1 (104B totali):
  Bytes 0-3:   1F A3 60 00 (sub-header, costante per tipo traccia)
  Bytes 4-10:  DF 77 C0 8F CB F1 F8 (preamble)
  Bytes 11-17: A8 AE 8F C7 E3 71 78 (bar 1: 7 bytes)
  Bytes 18:    DC (bar delimiter)
  Bytes 19-59: Bar 2: 41 bytes (pattern completo)
  Bytes 60:    DC (bar delimiter)
  Bytes 61-101: Bar 3: 41 bytes (IDENTICO a Bar 2 = repeat!)
  Bytes 102:   DC (final delimiter)
  Bytes 103:   00 (terminator)
```

**Osservazioni strutturali:**
1. `DC` funge da delimitatore di barra
2. Le barre possono ripetersi identiche (C1 ha Bar 2 = Bar 3)
3. Il pattern 41-byte contenente `E3 71 78` ricorrente (5 volte)
4. Trigrammi comuni: `E3 71 78`, `71 78 BE`, `8F C7 E3`
5. I byte 0xC0-0xFF appaiono frequentemente (potrebbero essere command bytes)

**Ipotesi encoding eventi:**
- Ogni evento potrebbe essere 3 bytes (trigram pattern)
- Possibile struttura: [command][note][velocity] o [delta][note][gate]
- Non ancora decodificato completamente

**Tracce drum (D1/D2):**
- D1: 744 bytes, nessun pattern di ripetizione esatto trovato
- D2: 232 bytes, solo 12 bytes differiscono tra sezioni (ultimi 12 bytes)
- Frequenza byte 0xC0-0xFF molto alta (comandi?)

### Tempo Encoding (RAW payload of first 0x7F message)

```
tempo_bpm = (range_byte * 95 - 133) + offset_byte

range  = raw_payload[0]  (first byte after sub-address)
offset = raw_payload[1]

Examples:
  SGT 151 BPM:     range=2, offset=94  -> (2*95-133)+94  = 151
  Captured 101 BPM: range=2, offset=44  -> (2*95-133)+44  = 101
  MR.VAIN 133 BPM:  range=2, offset=76  -> (2*95-133)+76  = 133
  SUMMER 155 BPM:   range=3, offset=3   -> (3*95-133)+3   = 155
```

### Sessione 4 - Event Format Analysis + Converter Fixes + Send Improvements (2026-02-27)

**Analisi formato eventi QY70 (DEFINITIVA):**
- Scritto parser esaustivo (`midi_tools/parse_events.py`) che testa il command set Q7P
  (D0/E0/A0-A7/BE/F2) su TUTTI i track data QY70 (8 tracce × 5 offset di partenza)
- **Risultato: 16.8% coverage** — il command set Q7P NON funziona su dati QY70
- I match sono falsi positivi (0x00 come padding, A0-A7 che appaiono come dati)
- **CONCLUSIONE DEFINITIVA**: QY70 usa un **packed bitstream proprietario**:
  - 117 valori unici high-bit (vs ~15 comandi nel Q7P)
  - Shannon entropy: 4.8-6.65 bits/byte (alta, nessuna struttura comando)
  - Bit 7 frequency: 40-61% (uniforme, non ~25% come in formato a comandi)
  - Tutti gli 8 bit positions hanno frequenza 37-53% (hallmark di bitstream)
- DC (0xDC) in tracce chord crea barre di ~41 bytes; raro/assente in tracce drum
- Cross-section D1 data è byte-identical in tutte 6 sezioni (confermata validità)
- Track PC (offset 64+) mostra blocchi da 7 bytes con header `0x88`

**Analisi formato eventi Q7P (CONFERMATA):**
- Q7P eventi sono a 0x120-0x180 (section encoded data), NON nell'area "Phrase" (0x360+)
- L'area "Phrase" (0x360-0x678) è IDENTICA tra T01 e TXX = dati statici di configurazione
- Formato: `F0 00` (start) + `FB xx 00 xx` (section config) + `C0 04` (setup) + `F2` (end)
- 94 bytes totali differiscono tra T01 e TXX (su 3072)

**Bug fix checksum writer.py:**
- `writer.py:283` calcolava checksum su `AH AM AL + data` (3 bytes header)
- Corretto a `BH BL AH AM AL + data` (5 bytes header) — confermato da SGT reference
- `verify_sysex_checksum()` era già corretto (usa `message[4:-2]`)

**Bug fix converter qy700_to_qy70.py:**
- Header[0] veniva riempito con nome pattern — SBAGLIATO: byte 0 = tempo offset
- Tempo veniva scritto come singolo byte a offset 0x0A — SBAGLIATO: usa range/offset formula
- Corretto: decoded[0]=offset, MSBs di decoded[4:7] controllano range byte nell'encoded
- Docstring aggiornato: QY70 e QY700 hanno formati eventi DIVERSI

**Bug fix converter qy70_to_qy700.py:**
- Volume leggeva `track_data[24]` — SBAGLIATO: byte 24 = inizio MIDI events, non volume
- Volume rimosso (offset nel header QY70 non ancora mappato)
- Tempo extraction riscritta con formula corretta: re-encode + read group header
- AL range check corretto: 0x00-0x2F sono tutti track data (non 0x00-0x05 separati)

**Miglioramento send_style.py:**
- Pre-validazione completa prima di invio (checksums, struttura, device numbers)
- Timing migliorato: 100ms dopo Init, 30ms tra bulk dumps, 50ms prima di Close
- Device number override (--device N per matching QY70 setting)
- --verify-only mode per validazione senza invio
- Troubleshooting tips nell'output

**Analisi NEONGROOVE vs SGT:**
- NEONGROOVE strutturalmente valido: tutti checksum OK, init/close identici a SGT
- 1 messaggio extra (AL=0x16 ha 2 messaggi vs 1 nel SGT) — legittimo (più dati)
- Device numbers consistenti in entrambi i file

**Analisi Q7P vs QY70 mapping sistematico:**
- Scritto `midi_tools/map_fields.py` per confronto campo-per-campo
- 32 campi identificati: 6 mappati, 7 parziali, 3 incerti, 7 non mappati, 8 unilaterali
- Chorus send area (0x286-0x2BF) riempita con 0x40 = probabilmente padding, non chorus=64
- Voice transfer manca completamente da entrambi i converter

### Sessione 5 - Deep Q7P Analysis + Header Comparison (2026-02-27)

**Q7P Chorus Send localizzato:**
- Indagine sistematica su tutte le aree 0x220-0x2BF del Q7P
- Area 0x286-0x2BF è **Pan esteso** (tutto 0x40 = center), NON chorus send
- **Chorus Send confermato a 0x246-0x255** (16 bytes, uno per traccia, default XG = 0x00)
- Entrambi i file test (T01 e TXX) hanno tutti zeri a questo offset = corretto per XG default
- Layout rivisto delle tabelle parametri Q7P:
  ```
  0x226-0x235  Volume (16 tracks, default 0x64)
  0x236-0x245  Unknown CC#74? (16 tracks, default 0x40)
  0x246-0x255  Chorus Send (16 tracks, default 0x00) ← NUOVO
  0x256-0x265  Reverb Send (16 tracks, default 0x28)
  0x266-0x275  Padding/separator (zeros)
  0x276-0x2BF  Pan (multi-section × 16 tracks, default 0x40)
  ```

**Q7P Section bar count trovato:**
- Section config entries a 0x120+ hanno formato: `F0 00 FB pp 00 tt C0 bb F2` (9 bytes)
- `bb` dopo `C0` = bar count (entrambi i file test hanno `C0 04` = 4 battute)
- Aggiornato `_analyze_sections()` per estrarre bar count dal config data

**Q7P Section pointer mechanism:**
- Puntatori a 2 bytes big-endian relativi a 0x100
- Offset effettivo nel file = pointer_value + 0x100
- `0xFEFE` = sezione vuota

**Q7P F1 record scoperto:**
- In T01.Q7P, record F1 a 0x129-0x17F (87 bytes)
- Contiene override per-sezione di volume, reverb, pan
- Assente nel template vuoto TXX.Q7P

**Q7P Program/Bank offset inconclusivo:**
- Offsets 0x1E6, 0x1F6, 0x206 tutti zeri in entrambi i file
- Drums dovrebbe avere Bank MSB=0x7F ma mostra 0x00
- Questi offset potrebbero NON essere Bank/Program/LSB, oppure drums gestito implicitamente

**Header name encoding investigation:**
- Scritto `midi_tools/decode_header_name.py` per analisi esaustiva
- Testato ASCII diretto, 5-bit, 6-bit, BCD, nibble encoding su 3 file
- **NESSUN nome leggibile trovato** — il nome NON è nel bulk dump come testo ASCII
- Il nome è probabilmente solo nella memoria interna del QY70

**Deep SGT vs empty header comparison:**
- Confronto byte-per-byte di tutti 640 bytes header (AL=0x7F)
- 257 bytes fissi (40%), 383 bytes variabili (60%), 31 regioni di differenza contigue
- Mappa strutturale completa del header documentata in QY70_FORMAT.md

**Empty-marker pattern decodificato:**
- Pattern di 7 bytes: `BF DF EF F7 FB FD FE`
- Ogni byte è 0xFF con un bit (6→0) azzerato, discendente
- Equivalente QY70 del byte 0xFE di riempimento Q7P
- 29 occorrenze nel pattern vuoto, 11 nello style SGT
- Riempie ogni slot mixer non utilizzato

**Aggiornamenti codice (sessione 5 continuazione):**
- Aggiunto `CHORUS_DATA_START` a 0x246 (3072-byte) e 0xAC6 (5120-byte) in q7p_analyzer.py
- Aggiunto metodo `_get_chorus_sends()` e campo `global_chorus_sends` in Q7PAnalysis
- Estratzione bar count da `C0 nn` in section config in `_analyze_sections()`
- Corretto offset chorus da 0x296 a 0x246 in entrambi i converter
- Aggiornato display CLI tracks con offset chorus corretto
- Tutti 33 test passano dopo le modifiche

---

### Sessione 6: Bitstream Structure Cracking

**7-byte group alignment CONFERMATO:**
- DC delimiters allineati a gruppi da 7 bytes nel 100% dei casi in messaggi singoli
- Disallineamento in D1 MSG4 (DC@96, mod7=5) e C1 MSG1 (DC@39, mod7=4) causato da
  concatenazione multi-messaggio — ogni messaggio SysEx è codificato indipendentemente
- La periodicità a 7 bytes è struttura REALE, non artefatto dell'encoding
- 79 DC totali: 67 allineati (84.8%) nel dato concatenato, 100% nei messaggi singoli

**Struttura bar 41 bytes (tracce accordo):**
- Formato: [13-byte bar header] + 4 × [7-byte event]
- Header contiene configurazione timing/voicing per la battuta
- 4 eventi da 7 bytes ciascuno codificano le note/accordi
- Bar identiche: C2 Bar1 == Bar2, confermate byte-per-byte

**C2 vs C4 XOR analysis — nota che "si sposta":**
- Differenze di soli 2-4 bit per evento tra C2 e C4
- Posizioni XOR: E3@bits[9,14], E2@[18,23], E1@[26,31], E0@[35,36,41,42]
- Il campo nota si sposta di ~8 bit per slot evento
- Pattern XOR `0x21` (bit 5 e bit 0) consistente = trasposizione di una nota
- Bytes 5-6 degli eventi `1111100` quasi costanti: 0x61/0x71 + 0x78 (timing/gate)

**Bar headers 13-byte decodificati:**
- C2 default: `1F 8F 47 63 71 21 3E 9F 8F C7 62 42 70`
- C4 default: `1F 8F 47 63 71 23 3E 9F 8F 47 62 46 60` (4 bytes diversi)
- C3 S0: unico per ogni battuta (dati musicali)
- C3 S1-5: uguale al default C2 (pattern vuoto)

**Cross-section stability confermata:**
- C1: 100% identico tra tutte 6 sezioni (ogni byte, inclusi eventi)
- C3: Sezione 0 ha dati unici, sezioni 1-5 pattern default
- D1: Identico tra tutte 6 sezioni
- BASS: Bar 0 identica tra tutte 6 sezioni

**D1 drum track patterns:**
- 740 bytes eventi con solo 1 DC (bar 0: 580 bytes, bar 1: 159 bytes)
- `28 0F` appare 13 volte a intervalli 28-42 bytes (possibile beat marker)
- `40 78` appare 8 volte (altro pattern strutturale)
- Dopo `28 0F`: byte 0x8C/0x8D/0x8F (lo7=12/13/15, timing?)

**Analisi frequenza byte per traccia:**
- D1: byte più comune 0x08(26), 0x20(25) — distribuzione uniforme
- C2: byte più comune 0x8F(10), 0x71(9), 0x78(9) — alta concentrazione
- BASS: byte più comuni 0x00(8), 0x40(5), 0x10(5), 0x88(5)

**Bit-7 pattern distribution (447 eventi accordo):**
- `0100000`: 61 eventi (tutti i tracks) — header/preamble
- `1111001`: 52 eventi (C2,C3,C4) — variant chord event
- `1111100`: 27 eventi (C2,C3,C4) — standard chord event
- `1110001`: 37 eventi (tutti) — bar header fragment
- `1010000`: 30 eventi (tutti) — delimiter-adjacent
- Pattern `1111100` ha bytes 5-6 quasi costanti (timing fields)

**Script creati:**
- `midi_tools/encoding_boundary_analysis.py` — analisi DC vs encoding boundaries
- `midi_tools/per_message_analysis.py` — decomposizione per-messaggio e cross-section
- `midi_tools/d1_and_q7p_analysis.py` — analisi D1 drum e confronto Q7P
- `midi_tools/bitfield_cracking.py` — cracking bit-fields con XOR analysis

---

### Sessione 7: Deep Bitstream Decoding — 9-Bit Rotation & Shift Register (2026-02-27)

**9-bit barrel rotation CONFERMATO DEFINITIVAMENTE:**
- Ricerca esaustiva su tutte 55 rotazioni possibili (1-55 bit per eventi da 56 bit)
- R=9 è ottimale con score aggregato 35 (migliore di tutte le altre rotazioni)
- C2/C4: solo 10 bit differenti dopo rotazione (su 56)
- C3 S1 (default): 10 bit differenti
- C3 S0 (dati musicali unici): 11-18 bit (più variazione per note diverse)
- C1: 11-20 bit (pattern più complessi)

**Shift register model — parzialmente confermato:**
- De-rotazione con R=9 produce 6 campi da 9 bit (F0-F5) + 2 bit remainder
- **F1[i]==F0[i-1] e F2[i]==F1[i-1]: VERO per C2, C4** (primi 2 campi shiftano)
- **FALSO per C1 e C3 S0** (dati musicali diversi ad ogni beat)
- Conclusione: F0-F2 portano "storia" (valori beat precedenti), F3-F5 codificano parametri per-beat

**Bar header = note accordo (SCOPERTA CHIAVE):**
- Header 13 byte decodificato come campi da 9 bit produce note MIDI valide
- C2 bar1: F0-F4 = [63, 61, 59, 55, 36] = D#4, C#4, B3, G3, C2
- Intervalli dalla root: [0, 1, 3, 7, 11] semitoni = triade minore (0, 3, 7)
- **C4 ha header IDENTICO a C2** — differenza di registro codificata negli eventi, non nell'header
- C3 S0: header diversi per ogni battuta (progressione accordi)
- C1: valori >127 (encoding diverso)

**Differenza C2/C4 localizzata in F3/F4:**
- Dopo de-rotazione, la differenza nota è concentrata in F3 e F4 degli eventi
- F3 differisce di +1 (trasposizione di un semitono?)
- F4 ha salti grandi (+244, -16, +248, +248) — encoding diverso (nota+ottava packed?)
- F5 identico tra C2 e C4 (gate time o velocity?)

**Analisi cross-section valori F0:**
- C2 S0-S2: F0=[381, 376, 440, 504] (identici — pattern default)
- C2 S3-S4: F0=[407, 175, 111, 79] (variazione fill)
- C2 S5: F0=[431, 237, 27, 16] (variazione ending)
- C1 S0-S5: F0=[399, 253] (C1 mai cambia)

**Lo7 bitstream C2/C4:**
- Differenze in soli 13 bit su 287 bit totali (41 bytes × 7 bit)
- Coppie complementari +1/-1 a spaziatura regolare (~5 bit)
- Pattern bilanciato suggerisce codice simmetrico per le note

**Ground truth analysis:**
- Q7P T01 non ha eventi drum (pattern vuoto) — non utilizzabile come ground truth per D1
- D1 bitstream cercato per note drum a tutte le fasi — nessun pattern convincente
- C3 S0 vs S1: 84% bytes differiscono; header differiscono a 10/13 bytes

**Script creati (sessione 7):**
- `midi_tools/derotation_decoder.py` — ricerca rotazione esaustiva, de-rotazione, catalogo eventi
- `midi_tools/ground_truth_decoder.py` — decodifica eventi Q7P, ricerca note drum in bitstream
- `midi_tools/musical_content_isolator.py` — isolamento contenuto musicale C3 S0/S1
- `midi_tools/shift_register_decoder.py` — verifica modello shift register, analisi header chord

---

### Sessione 8 — Decomposizione Campi e Rotazione Universale

**Data:** 27 febbraio 2026
**Obiettivo:** Approfondire la decomposizione dei campi F3/F4/F5, confermare R=9 universale, analizzare tracce non-chord.

**Scoperte principali:**

1. **R=9 universale** — La rotazione a 9 bit è confermata anche per BASS (avg 16.5 bit diversi, R=10 → 24.6). È una costante del formato, non specifica per tipo di traccia.

2. **F3 decomposto in hi2|mid3|lo4:**
   - lo4 = contatore beat one-hot (1000→0100→0010→0001) confermato per C2, C1
   - mid3 = identificatore tipo voce/traccia (C2=5, fill=7, C4=5-6)
   - hi2 = flag ottava/registro (C2: 0 per beat 0-2, 2 per beat 3)

3. **F4 = maschera chord-tone 5-bit + parametro 4-bit:**
   - La maschera 5-bit seleziona quali note dell'accordo suonare su ogni beat
   - Cambia tra battute con accordi diversi nell'header
   - Validazione parziale — valori header >127 complicano interpretazione

4. **F5 = timing/gate:**
   - Spaziatura dominante +16 = un beat in 4/4
   - Decomposizione: top2|mid4|lo3 dove lo3=costante nella battuta, mid4 incrementa

5. **D2 non ha delimitatori DC** — DC è specifico per tracce chord e bass

6. **Confronto cross-sezione C2:** Quando l'accordo header cambia, TUTTI i 6 campi cambiano. Quando è lo stesso (S0=S1=S2), tutti i campi sono identici.

7. **Tabella eventi C2 completa** estratta per tutte e 6 le sezioni.

8. **Struttura PC:** 100 byte eventi, nessun DC, S0=S1, S2-S5 identiche tra loro.

**Script creati (sessione 8):**
- `midi_tools/comprehensive_decoder.py` — 10 analisi (BASS, F3/F4/F5, PC, D2, note decoder, rotazione, bitstream, cross-track, header decode)
- `midi_tools/hypothesis_tester.py` — 8 test ipotesi (F5 timing, F3 note/velocity, F4 decomposizione, C3 decode, correlazione header-evento)
- `midi_tools/note_cracker.py` — 8 analisi (cross-section chords, F3 one-hot, F4 chord-tone mask, XOR, F5 bits, full event table)

---

## Problemi Aperti da Risolvere

| # | Problema | File Coinvolto | Stato |
|---|---|---|---|
| 1 | Offset Program Change sconosciuto (Q7P) | q7p_analyzer.py | Offset ipotizzato a 0x1F6 — **INCONCLUSIVO** (tutti zeri) |
| 2 | Offset Bank Select sconosciuto (Q7P) | q7p_analyzer.py | Offset ipotizzato MSB=0x1E6, LSB=0x206 — **INCONCLUSIVO** |
| 3 | ~~Offset Chorus Send sconosciuto~~ | q7p_analyzer.py | **RISOLTO Session 5** (0x246-0x255, 16 bytes) |
| 4 | ~~Time signature solo 4/4 funziona~~ | q7p_analyzer.py | **RISOLTO** (lookup table) |
| 5 | ~~Section length hardcoded a 4~~ | q7p_analyzer.py | **RISOLTO Session 5** (C0 nn in section config) |
| 6 | ~~Pan=0 mostra "L64"~~ | tables.py | **RISOLTO** (ora mostra "Rnd") |
| 7 | ~~Canali MIDI TR5-TR12 tutti "Ch 4"~~ | q7p_analyzer.py | **RISOLTO** (0x03 = group marker) |
| 8 | Phrase data non parsata | q7p_analyzer.py | Aperto |
| 9 | Serve cattura STYLE dump dal QY70 | midi_tools | Richiede azione manuale |
| 10 | ~~Schema AL errato (0x08+section*8)~~ | syx_analyzer, reader, writer, converters | **RISOLTO** (AL=section*8+track) |
| 11 | ~~D1 voice mostra "Soprano Sax"~~ | syx_analyzer.py | **RISOLTO** (init/close msg inquinavano AL=0x00) |
| 12 | ~~Formato eventi QY70 (byte 24+)~~ | syx_analyzer.py | **CONFERMATO**: packed bitstream, NON D0/E0/BE |
| 13 | Mappatura header QY70↔QY700 incompleta | converters | Parziale (32 campi, 6+3 mappati con Session 5) |
| 14 | ~~Checksum writer.py errato~~ | writer.py | **RISOLTO** (BH BL AH AM AL + data) |
| 15 | ~~Header generation converter errata~~ | qy700_to_qy70.py | **RISOLTO** (tempo range/offset) |
| 16 | ~~Volume extraction converter errata~~ | qy70_to_qy700.py | **RISOLTO** (rimosso, offset sconosciuto) |
| 17 | Voice transfer mancante nei converter | qy700_to_qy70, qy70_to_qy700 | **AGGIUNTO Session 4** (basato su offset ipotetici) |
| 18 | Trasmissione SysEx al QY70 non funziona | midi_tools/send_style.py | Script migliorato, test hardware necessario |
| 19 | Volume/Reverb offset nel header QY70 | syx_analyzer.py | Parziale — mixer region 0x1B9-0x21B identificata Session 4 |
| 20 | Style name non nel bulk dump | QY70_FORMAT.md | **CONFERMATO Session 5** — nome non in ASCII nel dump |
| 21 | Area 0x236-0x245 funzione sconosciuta | q7p_analyzer.py | Nuovo — possibile CC#74 (default 0x40) |
| 22 | F1 record non parsato | q7p_analyzer.py | Nuovo — 87 bytes in T01, assente in TXX |
| 23 | ~~7-byte group alignment~~ | QY70_FORMAT.md | **CONFERMATO Session 6** — reale struttura, non artefatto encoding |
| 24 | Note field bit-packing QY70 | QY70_FORMAT.md | **IN PROGRESSO Session 8** — R=9 universale, F3/F4/F5 parzialmente decodificati |
| 25 | Bar header 13-byte format | QY70_FORMAT.md | **IN PROGRESSO Session 8** — F0-F4 = note accordo, chord-tone mask in F4 |
| 26 | D1 drum `28 0F` structural marker | QY70_FORMAT.md | Aperto — struttura interna sconosciuta |
| 27 | F3 mid3 semantica | QY70_FORMAT.md | Nuovo Session 8 — tipo voce/traccia? Serve più dati |
| 28 | F4 header valori >127 | QY70_FORMAT.md | Nuovo Session 8 — header potrebbe codificare intervalli, non MIDI notes |
| 29 | F5 lo3/mid4 semantica precisa | QY70_FORMAT.md | Nuovo Session 8 — lo3=gate? mid4=beat position? |
| 30 | Conversione dati evento QY70↔QY700 | converters | Aperto — richiede decodifica completa bitstream |
