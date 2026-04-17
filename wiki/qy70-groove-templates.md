# QY70 Groove Templates

Template di quantizzazione/groove del QY70. Applicati a run-time o resi permanenti via Job "Normalize".

Riferimento: `manual/QY70/QY70_OWNERS_MANUAL.PDF` pag 96-98, 133.

## Panoramica

- **100 Groove Templates** disponibili (preset)
- Applicabili a qualsiasi track di song o pattern
- Modificano timing e velocity per creare "feel umano" (swing, push/pull, accenti)

## Parametri per-template

| Parametro | Range | Default | Effetto |
|-----------|-------|---------|---------|
| **TIMING** | 000-200 | 100 | 100 = originale; <100 = ritarda (relaxed); >100 = anticipa (pushed) |
| **VELOC** | 000-200 | 100 | 100 = originale; <100 = smorza; >100 = enfatizza |

Valori 000 = effetto massimo, 200 = effetto opposto massimo.

## Applicazione

Dal menu Job del QY70:
1. Seleziona la track da groove-quantizzare
2. Scegli template (001-100)
3. Imposta TIMING e VELOC
4. Press EXEC

**Preview temporanea**: il groove può essere attivo solo in playback (Play Effects). Per persistenza → Job "Normalize" converte Play Effects in eventi permanenti nella track.

## Drum Table Remapping

Feature separata ma correlata. Sostituisce drum instrument in playback senza toccare i dati track:
- Example: sostituire medium snare → rimshot su tutte le note 38 di una track
- Play Effect: applicato runtime, non persistente
- Persistenza via Job "Normalize"

Utile per provare kit alternativi senza rewrite della track.

## Implicazione RE

Groove template **non sono memorizzati** nel pattern data — sono config separata applicata a runtime. Un dump pattern SysEx non include il groove attivo: il playback MIDI capture può differire dal dump quando Groove è attivo.

Per ground truth deterministica durante RE:
- Disattivare Groove (TIMING=100, VELOC=100)
- Disattivare Drum Table Remapping
- Oppure applicare Job "Normalize" per bakare il groove prima del dump

## Cross-references

- [qy70-modes.md](qy70-modes.md) — JOB mode overview
- [bitstream.md](bitstream.md) — pattern data encoding
- `manual/QY70/QY70_OWNERS_MANUAL.PDF` pag 96-98, 133
