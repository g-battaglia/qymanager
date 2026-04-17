# QY70 Preset Phrases

Phrase library preinstallata nel QY70. Fondamentale per capire come i pattern vengono assemblati: un pattern è una combinazione di phrase sulle 8 track × 6 sezioni.

Riferimento: `manual/QY70/QY70_OWNERS_MANUAL.PDF` pag 137-143, `QY70_LIST_BOOK.PDF` pag 14-39.

## Numeri

- **4167 preset phrases** fisse (factory)
- **384 user phrase slots** (64 user styles × 6 sections × 1 phrase = slot allocabili)
- Slot notation: `Us--001` .. `Us--048` (48 phrase slot per user style, 6 sezioni × 8 track)

## Categorie (12 tipi)

Le phrase sono classificate per ruolo musicale. Letter code visibile sul display QY70:

| Code | Descrizione | Track tipico |
|------|-------------|--------------|
| `Da` | Drum-a (Pop & Rock) | D1 |
| `Db` | Drum-b (Specific) | D2 |
| `Fa` | Drum Fill-a (Pop & Rock) | D1/D2 FILL |
| `Fb` | Drum Fill-b (Specific) | D1/D2 FILL |
| `PC` | Percussion | PC |
| `Ba` | Bass-a (Pop & Rock) | BA |
| `Bb` | Bass-b (Specific) | BA |
| `Ga` | Guitar Chord-a | C1/C2 |
| `Gb` | Guitar Chord-b | C1/C2 |
| `GR` | Guitar Riff | C3/C4 |
| `KC` | Keyboard Chord | C1/C2 |
| `KR` | Keyboard Riff | C3/C4 |
| `PD` | Pad | C2/C3 |
| `BR` | Brass | C3/C4 |
| `SE` | Sound Effects | C4 |

## Beat types

Classificazione ritmica:
- **16 Beat** — sixteen-note groove
- **8 Beat** — eight-note groove
- **3/4 Beat** — waltz / triple meter

## Phrase Types (OM pag 147)

Ogni phrase ha un **type** che determina come viene re-armonizzata con i chord changes:

| Type | Behavior |
|------|----------|
| **Bypass** | Note fisse, no transposition con chord |
| **Bass** | Segue root/bass del chord |
| **Chord 1** | Mappata su chord voicing primario |
| **Chord 2** | Mappata su chord voicing secondario |
| **Parallel** | Trasposta parallelamente con root change |

Questo è critico per il reverse engineering: le note memorizzate nelle phrase **non sono quelle suonate** — sono relative al chord C major di default e vengono trasposte a run-time secondo il chord event.

## Assemblaggio pattern

Un pattern QY70 è l'aggregato di 48 phrase (8 track × 6 section). Ogni slot pattern:
1. Header con chord principale, tempo, time signature, voci
2. Per ciascuna delle 8 track × 6 section: reference a una phrase (preset o user) con type/key shift

## Implicazione RE

Il bitstream dense encoding (2543 per drum, 29CB per general, 2BE3 per bass) contiene **note trasposte a run-time**, non le note originali della phrase. Questo spiega la difficoltà nel matchare la playback capture byte-per-byte col contenuto dumpato: servirebbe decodificare contestualmente le chord changes e applicarle.

Vedi [bitstream.md](bitstream.md) e [2543-encoding.md](2543-encoding.md).

## Cross-references

- [bar-structure.md](bar-structure.md) — chord events per-bar
- [track-structure.md](track-structure.md) — track layout
- [qy70-modes.md](qy70-modes.md) — Pattern vs Song mode
- `manual/QY70/QY70_OWNERS_MANUAL.PDF` pag 137-147
