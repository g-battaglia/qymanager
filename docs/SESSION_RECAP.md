# QYConv — Recap Sessioni 1-11

## Panoramica del Progetto

**qyconv** converte pattern/style tra Yamaha QY70 (SysEx .syx) e QY700 (binario .Q7P).
In 11 sessioni abbiamo: stabilito la connessione MIDI, corretto 16 bug nel core library,
creato uno stile custom, condotto un reverse engineering profondo del formato bitstream QY70,
e diagnosticato/fixato la causa del bricking QY700.

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
| Preamble slot-based (non voice-based) | Alta | 10 |
| D1 msgs 0-4 identici, solo msg 5 differisce | Alta | 10 |
| General encoding (29CB) usa R=47 left = R=9 right | Alta | 10,12 |
| SGT vs NEONGROOVE dati traccia 100% identici | Alta | 10 |
| DC delimiter solo in chord/bass tracks | Alta | 6-8 |
| Empty-marker pattern: BF DF EF F7 FB FD FE | Alta | 5 |
| Style name NON in ASCII nel dump | Alta | 5 |

#### Stato decodifica per tipo traccia

| Traccia | Encoding | Decodifica | Note |
|---------|----------|-----------|------|
| Chord (CHD2,PHR1,PHR2) | chord (1FA3) | ~82% | Beat counter 90%, 9E sub-bar delimiter, chord mask confermato |
| General (RHY2,CHD1,PAD) | general (29CB) | ~38% | R=9 right funziona! Beat counter confermato, stessa rotazione di chord |
| Bass slot (BASS) | bass_slot (2BE3) o general (29CB) | ~38% | BASS può usare 29CB, beat counter 100% |
| Drum primary (RHY1) | drum_primary (2543) | ~61% | 9E sub-bar, beat accuracy 51% |

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
midi_tools/event_decoder.py             — Chord track decoder (893 lines), slot-based naming fix
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
- **Pattern A**: Un solo accordo C major, un beat per battuta, solo CHD2 attivo
- **Pattern B**: Come A ma con accordo diverso (Am o G)
- **Pattern C**: Come A ma con traccia RHY1 drum (solo kick su beat 1)
- **Pattern D**: Come A ma 2 sezioni con accordi diversi

Ogni cattura valida/smentisce le ipotesi su F3, F4, F5 in modo definitivo.
Questo è il singolo passo con il miglior rapporto effort/risultato.

### 2. Decode General Encoding (29CB)
L'encoding general (preamble 29CB) è usato da RHY2, CHD1, PAD:
- R=47 (inverso del chord R=9) è ottimale
- Shift register non funziona — struttura campi completamente diversa
- DC potrebbe non essere delimitatore in questo encoding
- Serve analisi a livello di bit con pattern noti

### 3. Drum Track Decoding (RHY1)
- Analizzare marker `28 0F` di RHY1 con pattern drum noti (kick/snare/hi-hat)
- Msgs 0-4 identici tra sezioni, solo msg 5 differisce — concentrare analisi su msg 5
- Cercare correlazione tra posizione nel bitstream e note MIDI percussive

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

## Sessione 11: Diagnosi Bricking e Analisi Profonda

### Causa del bricking QY700 (RISOLTA)

Il converter `qy70_to_qy700.py` scriveva a 3 offset **non confermati** nel file Q7P:
- `0x1E6`: presunto Bank MSB → scriveva **0x7F** per drum tracks
- `0x1F6`: presunto Program Change
- `0x206`: presunto Bank LSB

**Conferma**: deep diff T01.Q7P vs TXX.Q7P mostra che **tutte e 3 le aree sono ZERO** in entrambi i file. L'ipotesi voice era sbagliata — scrivere valori non-zero in un'area che deve essere zero ha corrotto il file.

### Fix applicati

1. **Disabilitata `_extract_and_apply_voices()`** — non scrive piu' a offset non confermati
2. **Fixato bounds check pan**: `< 0x246` → `< 0x2C0` (era un no-op totale)
3. **Aggiunto `_validate_critical_areas()`** — verifica post-conversione che aree critiche siano intatte

### Nuove scoperte formato Q7P

| Scoperta | Confidenza |
|----------|-----------|
| Voice offsets 0x1E6/0x1F6/0x206 = tutti ZERO (NON sono voice data) | Alta |
| Track enable flags (0x1E5): bitmask sezioni attive (0x01=1, 0x1F=5) | Alta |
| Section config usa record F0/F1/F2: F0=section header, F1=data block, F2=end | Alta |
| Section pointers (0x100+): 16-bit BE offsets, 0xFEFE=inattivo | Alta |
| Phrase data (0x360-0x677) in Q7P 3072B: NON usa formato D0/E0 commands | Alta |
| Phrase data contiene valori 0x2D-0x7F senza command bytes → formato diverso | Alta |

### Nuove scoperte formato QY70 SysEx

| Scoperta | Confidenza |
|----------|-----------|
| Track header byte14/15 = indicatore TIPO traccia, non Bank MSB/Program | Alta |
| 0x40/0x80 = famiglia drum/auto (D1, D2, BASS) | Alta |
| 0x00/0x04 = modo chord-following (CHD1) | Alta |
| 0x00/0x00 = default melodia (CHD2, PHR1, PHR2) | Alta |
| Flags 80/8E/83 = tracce auto (drum/bass), 00/0F/10 = melodia | Alta |

### Script creati

- `midi_tools/safe_q7p_tester.py` — genera 10 file Q7P diagnostici per test incrementale
- `midi_tools/ground_truth_analyzer.py` — valida decoder chord su dati con contenuto noto
- `midi_tools/q7p_test_files/` — 10 file test + DIFF_SUMMARY.txt

---

---

## Sessione 12: Scoperta Delimitatori e Miglioramento Decoder

### Scoperte chiave

| Scoperta | Confidenza |
|----------|-----------|
| **0x9E = sub-bar delimiter** (chord change within bar) | Alta |
| **lo4=0000 = beat 0** (non "invalid") | Alta |
| **R=9 right = R=47 left** (stessa operazione su 56 bit) | Alta |
| **General encoding (29CB) usa R=9** (come chord) | Alta |
| **BASS slot può usare preamble 29CB** (non solo 2BE3) | Alta |
| **Nessun .syx QY70 free disponibile online** | Alta |
| **QY70 non supporta Dump Request remoto** | Alta |
| **QY70 Identity Reply: Family=0x4100 Member=0x5502** | Alta |
| **Bar headers con campi >127 = encoding non-lineare** | Media |

### Miglioramenti al decoder

| Metrica | Prima | Dopo |
|---------|-------|------|
| Chord confidence | 68% | **82%** |
| Beat accuracy | 48% | **90%** |
| Bars decodificate (CHD2) | 4 | **6** (sub-bars) |
| BASS beat accuracy | 60% | **100%** |
| General tracks confidence | 15% | **38%** (con sub-bars) |

### Fix applicati

1. **`extract_bars()` aggiornato** — ora riconosce 0x9E come sub-bar delimiter
2. **`lo4_to_beat()` fixato** — lo4=0000 mappa a beat 0 (prima era -1/invalid)
3. **`send_request.py`** — fixato bug AL addressing (sec*8+trk, non 0x08+sec*8+trk)
4. **`midi_status.py`** — aggiunta identificazione dispositivi Yamaha da Identity Reply
5. **`qy700_to_qy70.py`** — fixato commento stale sull'AL addressing

### File catturati

- `ground_truth_A.syx` — 808B, stile vuoto (solo header)
- `ground_truth_preset.syx` — 7337B, 812 XG Parameter Change (non usabile)
- `ground_truth_style.syx` — 3211B, pattern reale 133 BPM, 7 tracce attive

### Stato ricerca .syx online

- qy100.doffu.net: stili QY70-compatibili ma a **pagamento** (Patreon)
- groups.io/YamahaQY70AndQY100: probabilmente ha file, **richiede iscrizione**
- GitHub, KVR, forum vari: nessun file scaricabile trovato

---

## Numeri

- **12 sessioni** di lavoro
- **16 bug** corretti nel core library + **3 fix** converter sicurezza + **4 fix** decoder/tools
- **33 test** tutti verdi
- **30+ script** di analisi creati
- **1 stile custom** (NEONGROOVE) generato
- **4 file .syx** analizzati (SGT, NEONGROOVE, captured dump, ground_truth_style)
- **2 file .Q7P** analizzati (T01, TXX)
- **~82%** decodifica tracce chord QY70
- **~38%** decodifica tracce general (29CB)
- **0%** conversione dati evento implementata
