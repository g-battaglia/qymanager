# QY700 Pattern Mode

Ref: `manual/QY700/QY700_MANUAL/10_5_1PatternMode.txt`, `11_5_2PatternMode.txt`

Il Pattern Mode gestisce **style** (accompagnamento + ritmo) ed è il core business del QY700 come workstation.

## Struttura generale

- **64 style** user-definibili (+ preset sul QY700)
- Ogni **style** contiene:
  - **8 section** (A, B, C, D, E, F, G, H) — tipicamente Intro/Main1/Main2/Fill1/Fill2/Ending/Break/End, ma user-definibili
  - **fino a 99 user phrases** (preset phrases: 3.876)
  - **Play Effect** settings per ogni traccia
  - **Pattern Voice** settings (voice assignment per le 16 track)
  - **Pattern Effect** settings (Reverb/Chorus/Variation type per lo style)
- **Section Connection**: indica a quale sezione andare dopo (A→B/C/.../H/END). Usato durante SONG playback (a meno di override via Pattern track).
- **Meter (time signature)**: per-style, **condiviso fra tutte le 8 sezioni**. Range: 1/16–16/16, 1/8–16/8, 1/4–8/4.

## Tracks (Pattern mode: 16)

TR1..TR16, ciascuna assegnabile a:
- **Phrase** (preset o user)
- **MIDI channel** (1-16)
- **Voice** (XG Normal/Drum)

### Phrase categories (19 + US = User)

| Code | Name | Meaning |
|------|------|---------|
| Da | Drum a | Kick/snare pattern |
| Db | Drum b | Percussion variant |
| Fa / Fb / Fc | Fill a/b/c | Drum fills |
| DP | Drum + Perc | — |
| PC | Percussion | — |
| PF | Perc fill | — |
| Ba / Bb | Bass a/b | Bass lines |
| GC | Guitar Chord | — |
| GA | Guitar Arpeggio | — |
| GR | Guitar Riff | — |
| KC | Keyboard Chord | — |
| KA | Keyboard Arpeggio | — |
| KR | Keyboard Riff | — |
| PD | Pad | Sustained |
| BR | Brass | — |
| SE | Sound Effect | — |
| US | User | User-recorded phrase |

### Beat field (subcategoria per categoria)

| Code | Meaning |
|------|---------|
| 16 | 16-beat |
| 08 | 8-beat |
| 34 | 3/4-beat (o 6/8) |

Phrase numbering: `<CAT><BEAT><NNN>`, es. `KA16030` = Keyboard Arpeggio 16-beat phrase #30.

Preset range: 001-256 per categoria (non tutte riempite). User: 001-099.

### Phrase Types (per chord conversion)

| Type | Conversion behavior |
|------|---------------------|
| Mldy1 | Melody, mappa su chord root + scale |
| Mldy2 | Melody, mappa su chord tones |
| Chrd1 | Chord, trasforma nelle note del chord |
| Chrd2 | Chord, variante |
| Bass | Bass, segue chord root/on-bass |
| Bypas | Bypass — nessuna conversion, suona come scritto |
| Para | Parallel — trasposta per intervallo relativo |

Usato internamente dall'engine del QY700 per trasporre una phrase in base al chord corrente della Chord track.

### Retrigger

| Setting | Behavior on chord change |
|---------|--------------------------|
| ON | Trasporrà in mid-phrase, suona senza interruzione |
| OFF | Stoppa la phrase e riparte dall'inizio (o silenzio se non si vuole) |

## Chord types & roots

### Roots (12)

`C, C♯, D, E♭, E, F, F♯, G, A♭, A, B♭, B`

### Types (28, incl. THRU)

| # | Name | Notes (example on C) |
|---|------|----------------------|
| 1 | M | 1, 3, 5 |
| 2 | M7 | 1, 3, 5, 7 |
| 3 | 6 | 1, 3, 5, 6 |
| 4 | 7 | 1, 3, 5, ♭7 |
| 5 | m | 1, ♭3, 5 |
| 6 | m7 | 1, ♭3, 5, ♭7 |
| 7 | m6 | 1, ♭3, 5, 6 |
| 8 | mM7 | 1, ♭3, 5, 7 |
| 9 | m7(♭5) | 1, ♭3, ♭5, ♭7 |
| 10 | dim | 1, ♭3, ♭5, 6 (bb7) |
| 11 | aug | 1, 3, ♯5 |
| 12 | sus4 | 1, 4, 5 |
| 13 | add9 | 1, 3, 5, 9 |
| 14 | M7(9) | 1, 3, 5, 7, 9 |
| 15 | 6(9) | 1, 3, 5, 6, 9 |
| 16 | 7(9) | 1, 3, 5, ♭7, 9 |
| 17 | madd9 | 1, ♭3, 5, 9 |
| 18 | M9 | 1, 3, 5, 7, 9 |
| 19 | m7(9) | 1, ♭3, 5, ♭7, 9 |
| 20 | m7(11) | 1, ♭3, 5, ♭7, 11 |
| 21 | 7(♭5) | 1, 3, ♭5, ♭7 |
| 22 | 7(♯5) | 1, 3, ♯5, ♭7 |
| 23 | 7(♭9) | 1, 3, 5, ♭7, ♭9 |
| 24 | 7(♯9) | 1, 3, 5, ♭7, ♯9 |
| 25 | 7(13) | 1, 3, 5, ♭7, 13 |
| 26 | 7(♭13) | 1, 3, 5, ♭7, ♭13 |
| 27 | 7sus4 | 1, 4, 5, ♭7 |
| 28 | 7(♯11) | 1, 3, 5, ♭7, ♯11 |
| (—) | THRU (`---`) | Bypass chord conversion, phrase suona senza trasposizione |

**On Bass** = nota singola premuta a sinistra della Fingered Chord Zone; sostituisce il bass del chord.
**Original Bass** = chord suonato per intero nella zone.

## Play Effects (per-track)

### Groove Quantize

100 preset templates (`32Quantize`, `24Quantize`, `16Quantize`, `16+24Quant`, `12Quantize`, `08Quantize`, `08+12Quant`, `06Quantize`, `04Quantize`, `32Swing`, `24>16+12`, `24Drunk`, `24Sambody`, `24Shfflin1/2`, `16AccntDwn/Up`, `16AcidJazz`, `16Baion`, `16BaionBmb`, `16Batucada`, `16beatRock`, `16Bomba`, `16Caixa`, `16Cuban`, `16Drunk`, `16Dun-Dun`, `16GetFunky`, `16Guaguanc`, `16HipHop`, `16House`, `16Jungle`, ..., `08WayBack`, `06>4+3`, `06>4+3 ofs`, `04Swing`).

Lista completa in `qy700-groove-templates.md`.

Params:
- **Strength**: 0-100% (quanto è forte la quantizzazione verso il template)
- **Groove Timing**: 0-200% (scala delle deviazioni temporali)
- **Groove GateTime**: 0-200% (scala la durata note)
- **Groove Velocity**: 0-200%

Oltre ai preset c'è un **User template** editabile (1 slot).

### Altri Play Effect

| Parameter | Range |
|-----------|-------|
| Clock Shift | ±999 clock (MIDI ticks) |
| Gate Time | 0-200% (estende/accorcia note) |
| Velocity Rate | 0-200% (scala velocity) |
| Velocity Offset | ±99 (aggiunge/sottrae) |
| Transpose | ±99 semi |
| Inversion Transpose | ±64 (nelle chord phrases) |
| Open Harmony | ±15 (sposta note al registro sopra/sotto) |

### Drum Tables (8 editabili)

Tabelle di mapping note → note (per sostituire strumenti drum non-XG/GM in phrases importate). Permettono di rimappare es. MT-32 drum numbers → XG drum numbers.

### Scale Time track

Valori discreti: 050, 066, 075, 100, 133, 150, 200%. Accorcia o allunga la durata totale di una phrase.

### Beat Shift track

Range: ±32 sixteenth notes. Sposta temporalmente la phrase.

## Pattern Jobs (30 totali)

| # | Job | Description |
|---|-----|-------------|
| 00 | Undo / Redo | |
| 01 | Quantize | Quantize note a sub-division |
| 02 | Modify Velocity | Scale/offset velocity |
| 03 | Modify Gate Time | Scale/offset note duration |
| 04 | Crescendo | Velocity crescendo/decrescendo |
| 05 | Transpose | ±semi |
| 06 | Shift Note | Cambia pitch di note selezionate |
| 07 | Shift Clock | Sposta temporalmente |
| 08 | Chord Sort | Ordina note dentro accordi per pitch |
| 09 | Chord Separate | Separa note simultanee (stacco temporale piccolo) |
| 10 | Shift Event | |
| 11 | Copy Event | |
| 12 | Erase Event | |
| 13 | Extract Event | Estrae eventi specifici in nuova area |
| 14 | Thin Out | Decima eventi (utile per CC densi) |
| 15 | Time Stretch | Allunga/accorcia durata |
| 16 | Copy Phrase | |
| 17 | Mix Phrase | Combina due phrase in una |
| 18 | Append Phrase | |
| 19 | Split Phrase | |
| 20 | Get Phrase | Estrai porzione da pattern → phrase |
| 21 | Put Phrase | Inserisci phrase → pattern track |
| 22 | Clear Phrase | |
| 23 | Phrase Name | |
| 24 | Clear Track | |
| 25 | Copy Pattern | |
| 26 | Append Pattern | |
| 27 | Split Pattern | |
| 28 | Clear Pattern | |
| 29 | Pattern Name | |
| 30 | Style Icon | Assegna icona alla categoria style |

## Rilevanza per qyconv

### Converter QY70 → QY700

- I phrase del QY70 non sono direttamente compatibili (encoding bitstream vs byte-oriented).
- Serve ricostruire **phrase + pattern structure** nel formato Q7P.
- **Play Effect** settings possono essere inizializzati a neutri (Strength=0, Gate=100%, Velocity=100%, Transpose=0).
- **Chord types** da mappare: QY70 usa lo stesso set di 28 types → mapping 1:1 possibile.
- **Phrase categories**: allineamento diretto tra QY70 e QY700.

### Struttura dati Q7P sul disco

File Q7P contiene SOLO lo style corrente (non tutto il contenuto QY700). Vedi [q7p-format.md](q7p-format.md).

### Chord Root/Type via MIDI

Il QY700 accetta Fingered Chord da MIDI IN (vedi [qy700-utility-mode.md](qy700-utility-mode.md) F6). Ma durante playback song, i chord provengono dalla **Chord track** interna del song — non c'è input MIDI di chord in modalità Song.
