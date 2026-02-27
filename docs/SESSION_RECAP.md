# QYConv — Recap Sessioni 1-8

## Panoramica del Progetto

**qyconv** converte pattern/style tra Yamaha QY70 (SysEx .syx) e QY700 (binario .Q7P).
In 8 sessioni abbiamo: stabilito la connessione MIDI, corretto 16 bug nel core library,
creato uno stile custom, e condotto un reverse engineering profondo del formato bitstream QY70.

---

## Cosa abbiamo fatto

### Infrastruttura e MIDI (Sessioni 1-2)
- Connessione MIDI stabilita con QY70 via **Steinberg UR22C**
- Cattura bulk dump dal QY70 (808 bytes, 7 messaggi SysEx)
- Creati 20+ script di analisi in `midi_tools/`
- Interfaccia USB generica scartata (non funzionante)

### Bug Fix nel Core Library (Sessioni 3-5) — 16 correzioni
| Bug | File | Sessione |
|-----|------|----------|
| Channel mapping errato | q7p_analyzer.py | 3 |
| Pan=0 mostrava "L64" | tables.py | 3 |
| Time signature solo 4/4 | q7p_analyzer.py | 3 |
| Schema AL errato | 6 file | 4 |
| D1 voice "Soprano Sax" | syx_analyzer.py | 4 |
| Checksum writer errato | writer.py | 4 |
| Header generation errata | qy700_to_qy70.py | 4 |
| Volume extraction errata | qy70_to_qy700.py | 4 |
| Chorus offset errato (0x296→0x246) | q7p_analyzer.py, converters | 5 |
| Section bar count hardcoded | q7p_analyzer.py | 5 |

- **Voice transfer** aggiunto a entrambi i converter
- **33 test** tutti verdi

### Stile Custom (Sessione 4)
- **NEONGROOVE.syx** — 16,450 bytes, 106 messaggi, 128 BPM
- Validato strutturalmente identico a SGT di riferimento
- `send_style.py` migliorato (pre-validazione, timing corretto) ma non testato su hardware

### Reverse Engineering Bitstream QY70 (Sessioni 6-8)

Scoperta fondamentale: **QY70 e QY700 usano formati evento completamente diversi.**
- QY700: comandi byte-oriented (D0/E0/A0-A7/BE/F2)
- QY70: **packed bitstream** con campi da 9 bit e rotazione barrel

#### Scoperte confermate

| Scoperta | Confidenza | Sessione |
|----------|-----------|----------|
| 7-byte group = struttura reale | Alta | 6 |
| R=9 rotazione universale (tutti i tipi traccia) | Alta | 6-8 |
| 6 campi × 9 bit + 2 bit remainder per evento | Alta | 6 |
| F0-F2 = shift register (2 beat di storia) | Alta (C2/C4) | 7 |
| F3 lo4 = beat counter one-hot | Alta (C2, C1) | 8 |
| F3 mid3 = tipo voce/traccia | Media | 8 |
| F4 = 5-bit chord-tone mask + 4-bit param | Media | 8 |
| F5 = timing/gate (+16 per beat) | Media | 8 |
| Bar header 13 byte → note accordo (MIDI) | Alta | 7 |
| DC delimiter solo in chord/bass tracks | Alta | 6-8 |
| Empty-marker pattern: BF DF EF F7 FB FD FE | Alta | 5 |
| Style name NON in ASCII nel dump | Alta | 5 |

#### Stato decodifica per tipo traccia

| Traccia | Decodifica | Note |
|---------|-----------|------|
| Chord (C1-C4) | ~70% | Struttura eventi, beat counter, chord mask |
| Bass | ~40% | DC delimiters, R=9, struttura nota |
| Drum D1 | ~15% | Marker `28 0F`, nessun DC, struttura interna ignota |
| Drum D2 | ~10% | Nessun DC, sezioni quasi identiche |
| Percussion PC | ~10% | Nessun DC, differenze S0 vs S2-S5 |

---

## File principali modificati

```
qymanager/analysis/q7p_analyzer.py      — Chorus send, bar count, channel fix
qymanager/analysis/syx_analyzer.py      — AL addressing, D1 regression fix
qymanager/converters/qy700_to_qy70.py   — Header, chorus, voice transfer
qymanager/converters/qy70_to_qy700.py   — Chorus, volume, voice transfer
qymanager/formats/qy70/reader.py        — Section map fix
qymanager/formats/qy70/writer.py        — Checksum fix
cli/commands/info.py                     — Display fix
cli/commands/tracks.py                   — Chorus offset display
cli/display/tables.py                    — Pan display fix
```

## Documentazione

| File | Contenuto | Righe |
|------|-----------|-------|
| `docs/QY70_FORMAT.md` | Formato SysEx completo + bitstream | ~1000 |
| `docs/QY700_FORMAT.md` | Formato binario Q7P | ~200 |
| `docs/QY70_QY700_MAPPING.md` | Mappatura tra formati | ~275 |
| `docs/MIDI_REVERSE_ENGINEERING.md` | Log sessioni + 30 problemi aperti | ~630 |

---

## Prossimi Passi

### 1. Ground Truth (PRIORITA MASSIMA)
Catturare 3-4 pattern .syx dal QY70 con contenuto noto e semplice:
- **Pattern A**: Un solo accordo C major, un beat per battuta, solo C2 attivo
- **Pattern B**: Come A ma con accordo diverso (Am o G)
- **Pattern C**: Come A ma con traccia D1 drum (solo kick su beat 1)
- **Pattern D**: Come A ma 2 sezioni con accordi diversi

Ogni cattura valida/smentisce le ipotesi su F3, F4, F5 in modo definitivo.
Questo e il singolo passo con il miglior rapporto effort/risultato.

### 2. Decoder Prototype per Chord Tracks
Costruire `QY70EventDecoder` che:
1. Estrae bar header → decodifica note accordo
2. De-ruota eventi (R=9) → estrae 6 campi da 9 bit
3. Applica F4 chord-tone mask → determina note suonate
4. Calcola timing da F5 → posiziona nel tempo
5. Genera output MIDI verificabile a orecchio

### 3. Drum Track Decoding
- Analizzare marker `28 0F` di D1 con pattern drum noti (kick/snare/hi-hat)
- Cercare correlazione tra posizione nel bitstream e note MIDI percussive
- D2 e PC: confrontare differenze S0 vs S2-S5 per isolare contenuto musicale

### 4. Conversione Eventi QY70 ↔ QY700
Una volta decodificato il bitstream:
- Implementare traduzione da 9-bit packed fields a byte-oriented commands (e viceversa)
- Mappare chord-tone mask QY70 → note events espliciti QY700
- Gestire le differenze strutturali (bar headers, DC delimiters, shift register)

### 5. Test Hardware
- Testare `send_style.py` per trasmissione SysEx al QY70
- Verificare che il QY70 accetti e riproduca stili ricevuti via MIDI
- Se funziona: validare NEONGROOVE su hardware reale

---

## Numeri

- **8 sessioni** di lavoro
- **16 bug** corretti nel core library
- **33 test** tutti verdi
- **20+ script** di analisi creati
- **1 stile custom** (NEONGROOVE) generato
- **3 file .syx** analizzati (SGT, NEONGROOVE, captured dump)
- **2 file .Q7P** analizzati (T01, TXX)
- **~70%** decodifica tracce chord QY70
- **0%** conversione dati evento implementata
