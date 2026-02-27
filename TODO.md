# TODO - qymanager

## Legenda

- `[ ]` Da fare
- `[~]` In corso / parziale
- `[x]` Completato
- `[—]` Cancellato / non più rilevante

---

## Reverse Engineering QY70 Bitstream

### Priorità CRITICA — Sbloccano la conversione eventi

- [ ] **Catturare pattern ground-truth dal QY70**
  - Pattern A: solo accordo C major, 1 beat/battuta, solo C2 attivo
  - Pattern B: accordo diverso (Am o G) per confronto
  - Pattern C: traccia D1 drum (solo kick su beat 1)
  - Pattern D: 2 sezioni con accordi diversi
  - Richiede QY70 collegato + bulk dump manuale (UTILITY → MIDI → Bulk Dump)

- [~] **Decodifica completa tracce chord (C1-C4)** — ~70%
  - [x] Struttura 7-byte group confermata reale
  - [x] R=9 rotazione barrel universale (tutti i tipi traccia)
  - [x] 6×9-bit fields: F0-F2 shift register, F3-F5 parametri
  - [x] F3 lo4 = beat counter one-hot (confermato C2, C1)
  - [~] F3 mid3 = tipo voce/traccia — ipotesi, serve validazione
  - [~] F3 hi2 = octave/register flag — ipotesi, serve validazione
  - [~] F4 = 5-bit chord-tone mask + 4-bit param — parzialmente validato
  - [~] F5 = timing/gate (+16/beat) — decomposizione top2|mid4|lo3 ipotizzata
  - [ ] Validare F4 mask con header values >127 (intervalli vs MIDI notes?)
  - [ ] Decodifica completa bar header 13 byte (F0-F4=chord notes, F5-F10=?)

- [ ] **Decodifica tracce drum** — ~15%
  - [~] D1: marker `28 0F` trovati (13 occorrenze), struttura interna ignota
  - [ ] D1: decodifica eventi tra marker `28 0F`
  - [ ] D2: nessun DC, sezioni quasi identiche — capire formato
  - [ ] PC: nessun DC, differenze S0 vs S2-S5 — capire formato

- [ ] **Decodifica traccia BASS** — ~40%
  - [x] DC delimiters a posizioni [70, 100, 139, 184]
  - [x] R=9 confermato (avg 16.5 bits)
  - [ ] Semantica campi F0-F5 per BASS (diversa da chord?)

- [ ] **Costruire decoder prototype**
  - [ ] `QY70EventDecoder`: header → chord notes → F4 mask → timing
  - [ ] Generare output MIDI verificabile a orecchio
  - [ ] Validare su dati SGT

### Priorità ALTA — Conversione funzionante

- [ ] **Implementare conversione eventi QY70 → QY700**
  - [ ] Tradurre 9-bit packed fields → byte-oriented commands (D0/E0/A0-A7/BE/F2)
  - [ ] Mappare chord-tone mask → note events espliciti
  - [ ] Gestire bar headers, DC delimiters, shift register

- [ ] **Implementare conversione eventi QY700 → QY70**
  - [ ] Tradurre byte commands → packed bitstream con R=9 rotation
  - [ ] Generare bar headers con chord notes
  - [ ] Generare F3 beat counter, F4 chord mask, F5 timing

- [ ] **Testare trasmissione SysEx al QY70**
  - [x] `send_style.py` migliorato (pre-validazione, timing, verify-only)
  - [ ] Test hardware: inviare SGT.syx e verificare che QY70 lo accetti
  - [ ] Test hardware: inviare NEONGROOVE.syx

---

## Formato Q7P (QY700)

### Priorità ALTA

- [ ] **Trovare offset Program Change** — ipotizzato 0x1F6, tutti zeri nei test file
- [ ] **Trovare offset Bank Select** — ipotizzato MSB=0x1E6, LSB=0x206, inconclusivo
- [ ] **Parsare phrase data** (0x360-0x677, 792 byte) — solo statistiche attualmente
- [ ] **Parsare sequence events** (0x678-0x86F, 504 byte) — solo statistiche
- [ ] **Decodificare F1 record** — 87 byte in T01 (0x129-0x17F), assente in TXX
- [ ] **Identificare area 0x236-0x245** — possibile CC#74 (default 0x40)

### Priorità MEDIA

- [ ] **Verificare time signature** — solo 4/4 (0x1C) confermato
  - Serve creare pattern 3/4, 6/8, 5/4 sul QY700
- [~] **Mappatura header QY70↔QY700** — parziale (32 campi, 9 mappati)

---

## Formato QY70 (SysEx)

### Completati

- [x] Header SysEx 640 byte — mappa strutturale completa (95%)
- [x] Track header 24 byte — formato decodificato (90%)
- [x] Preamble per tipo traccia (4 byte, stabile cross-section)
- [x] Empty-marker pattern: `BF DF EF F7 FB FD FE`
- [x] Style name NON in ASCII nel bulk dump
- [x] Mixer region 0x1B9-0x21B = template fisso (non dati per-style)
- [x] AL addressing: `section*8 + track`, header AL=0x7F

### Aperti

- [ ] **Volume/Reverb/Pan offset nel header QY70** — regione 0x1B9-0x21B identificata ma non decodificata
- [ ] **Decodificare sezioni header 0x0F-0x044** — section pointer/phrase table
- [ ] **Decodificare sezione 0x096-0x0B5** — track/voice configuration variabile
- [ ] **Decodificare sezione 0x0D3-0x136** — per-track parameters (misto)

---

## Bug Fix Completati (Sessioni 1-8)

- [x] Channel mapping errato in `_get_channels()` — q7p_analyzer.py
- [x] Pan=0 mostrava "L64" invece di "Rnd" — tables.py
- [x] Time signature solo 4/4 funzionava — q7p_analyzer.py
- [x] Schema AL errato (0x08+section*8) — 6 file corretti
- [x] D1 voice mostrava "Soprano Sax" — syx_analyzer.py (init/close inquinavano)
- [x] Checksum writer: BH BL mancanti — writer.py
- [x] Header generation: tempo encoding — qy700_to_qy70.py
- [x] Volume extraction leggeva eventi MIDI — qy70_to_qy700.py
- [x] Chorus send offset 0x296→0x246 — q7p_analyzer.py, converters
- [x] Section bar count hardcoded a 4 — q7p_analyzer.py (ora parsa C0 nn)
- [x] Display strings e AL calculation — info.py
- [x] Chorus send offset display — tracks.py

---

## Feature Completate

- [x] Voice transfer in entrambi i converter
- [x] Chorus send extraction (`_get_chorus_sends` a 0x246)
- [x] NEONGROOVE.syx — stile custom (16,450 byte, 128 BPM)
- [x] 28 script di analisi MIDI in `midi_tools/`
- [x] Cattura bulk dump QY70 (808 byte, 7 messaggi)
- [x] Dipendenza opzionale `[midi]` in pyproject.toml
- [x] Documentazione completa (4 file, 2000+ righe totali)

---

## Feature Software Future

### Priorità MEDIA

- [ ] **Export MIDI** — `qymanager export pattern.Q7P --midi output.mid`
- [ ] **Parsare eventi phrase** — estrarre note MIDI, velocity, timing
- [ ] **Batch processing** — `qymanager batch convert *.syx --output-dir ./converted/`

### Priorità BASSA

- [ ] **Audio preview** — `qymanager play pattern.Q7P` (FluidSynth)
- [ ] **GUI web** — visualizzazione pattern, editing tracce, drag-and-drop conversion

---

## Riferimenti Struttura Q7P

```
Offset    Size   Descrizione                     Stato
------    ----   -----------                     ------
0x000     16     Header "YQ7PAT     V1.00"       ✓ OK
0x010     1      Pattern number                  ✓ OK
0x011     1      Pattern flags                   ✓ OK
0x030     2      Size marker (0x0990)            ✓ OK
0x100     32     Section pointers                ✓ OK
0x120     96     Section encoded data            Parziale (C0 nn parsato)
0x180     8      Padding (spaces)                ✓ OK
0x188     2      Tempo (BE, /10 per BPM)         ✓ OK
0x18A     1      Time signature                  Solo 4/4 confermato
0x190     8      Channel assignments             ✓ Mappato
0x1DC     8      Track numbers (0-7)             ✓ OK
0x1E4     2      Track enable flags              ✓ OK
0x220     6      Volume header                   ✓ OK
0x226     16     Volume data                     ✓ OK
0x236     16     Sconosciuto (CC#74?)            Da investigare
0x246     16     Chorus Send                     ✓ RISOLTO Session 5
0x256     16     Reverb Send                     ✓ OK
0x266     16     Padding/separatore              ✓ OK
0x276     72     Pan data (multi-section)        ✓ CORRETTO
0x2C0     160    Table 3 (sconosciuta)           Da investigare
0x360     792    Phrase data                     Solo statistiche
0x678     504    Sequence events                 Solo statistiche
0x870     16     Template padding                ✓ OK
0x876     10     Pattern name                    ✓ OK
0x880     128    Template area                   ✓ OK
0x900     192    Pattern mapping                 Sconosciuto
0x9C0     336    Fill area (0xFE)                ✓ OK
0xB10     240    Pad area (0xF8)                 ✓ OK
```

## XG Default Values

| Parametro | Default | Hex |
|-----------|---------|-----|
| Volume | 100 | 0x64 |
| Pan | 64 (Center) | 0x40 |
| Reverb Send | 40 | 0x28 |
| Chorus Send | 0 | 0x00 |
| Variation Send | 0 | 0x00 |
| Bank MSB (Normal) | 0 | 0x00 |
| Bank MSB (Drums) | 127 | 0x7F |
| Bank LSB | 0 | 0x00 |
| Program | 0 | 0x00 |
