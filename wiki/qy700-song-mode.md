# QY700 Song Mode

Ref: `manual/QY700/QY700_MANUAL/06_2_1SongMode.txt`

Song mode gestisce performance complete (linear sequences con accompaniment pattern).

## Capacità

- **20 songs** contemporaneamente in memoria interna (battery-backed)
- **35 tracks per song**:
  - **TR1-TR32**: sequence tracks (note MIDI)
  - **Pattern track**: seleziona quale style/section suona
  - **Chord track**: accordi per la Fingered Chord engine
  - **Tempo track**: cambi di tempo

## Chord track

Contiene 5 sub-event:
- **Chord Root**: C..B (12 valori)
- **Chord Type**: 28 tipi + THRU (vedi [qy700-pattern-mode.md](qy700-pattern-mode.md))
- **On Bass**: nota bass indipendente dal chord root
- **Original Bass**: chord completo
- **Syncopation**: flag per sincopa

## Record modes

| Mode | Description |
|------|-------------|
| Realtime | Registra in tempo reale mentre suoni |
| Punch | Registra solo in un range di misure/beat specificato |
| Step | Inserisci una nota alla volta, senza timing in tempo reale |

## Song Play settings

| Setting | Range / Options |
|---------|-----------------|
| Loop | LOC1..LOC2 (infinite loop tra due locate points) |
| Transposition | ±24 semitoni |
| Click mode | Off, Rec (solo in record), Ply (solo in play), All |
| Count | 1Ms..8Ms (misure di lead-in prima del rec/play) |

## Pattern Setup switch (ON/OFF)

**Critico** per il comportamento del tone generator:

- **ON**: il Pattern Mode usa i **Pattern Effects** del pattern corrente. Le voci cambiano ad ogni switch di pattern.
- **OFF**: il Pattern Mode usa gli **Effect Mode settings** del song (fissi per tutta la durata).

In pratica:
- **ON** = suono dinamico che cambia con pattern/section. Usa questo per demo-like performance.
- **OFF** = suono coerente per tutta la song. Usa questo se hai customizzato voice/effect nel Song ma vuoi pattern "muti" da lato voice.

## Song Jobs (25 totali)

| # | Job | Description |
|---|-----|-------------|
| 01 | Quantize | |
| 02 | Modify Velocity | |
| 03 | Modify Gate Time | |
| 04 | Crescendo | |
| 05 | Transpose | |
| 06 | Shift Note | |
| 07 | Shift Clock | |
| 08 | Chord Sort | |
| 09 | Chord Separate | |
| 10 | Shift Event | |
| 11 | Copy Event | |
| 12 | Erase Event | |
| 13 | Extract Event | |
| 14 | Thin Out | |
| 15 | Time Stretch | |
| 16 | Create Measure | Inserisce misure vuote |
| 17 | Delete Measure | |
| 18 | Copy Track | |
| 19 | Mix Track | |
| 20 | Clear Track | |
| **21** | **Expand Backing** | **Converte Pattern+Chord track in MIDI data su TR17-32** |
| 22 | Normalize Play Effect | Materializza play effect nelle note |
| 23 | Copy Song | |
| 24 | Clear Song | |
| 25 | Song Name | |

### Expand Backing (Job 21) — importante

Prende la Pattern track + Chord track del song e **materializza** tutto l'accompaniment come sequenza MIDI regolare sui tracks TR17..TR32. Dopo l'expand, non c'è più dipendenza dal Pattern Mode: il song può essere esportato come SMF standard e suonare identico su qualsiasi tone generator XG.

Utile per:
- Export SMF compatibile con DAW
- Rendering audio su synth esterni
- Backup "congelato" in cui il pattern originale non influenza più la riproduzione

### Normalize Play Effect (Job 22)

Stesso concept ma per i Play Effect (Groove Quantize, Clock Shift, Gate Time, Velocity). Le note vengono re-calcolate con gli effetti applicati, e i Play Effect vengono resettati a neutri.

## Rilevanza per qyconv

### Conversione SMF → Song QY700

Difficoltà: SMF non ha concetto di Pattern/Chord track. Conversione richiede:
1. Import SMF in TR1-16 as-is
2. Lasciare Pattern/Chord track vuote
3. User deve editare manualmente a song complete

### Song ESEQ (.ESQ) format

Legacy Yamaha, simile a SMF ma include tempo embedded e solo TR1-16. Compatibile con QY70 (ma QY70 ha limiti: max 8 tracks).

### File Q7S contenuto

Un file `.Q7S` contiene:
- 32 sequence tracks (TR1-32)
- Pattern/Chord/Tempo track
- **Voice settings** di quel song
- **Effect settings** di quel song

Non contiene pattern/style (quelli sono nel Q7P o Q7A).
