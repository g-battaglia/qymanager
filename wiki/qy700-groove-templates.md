# QY700 Groove Templates (Play Effect)

Ref: `QY700_REFERENCE_LISTING.pdf` — Groove Quantize Template List

Il Play Effect **Groove Quantize** offre **100 preset template** + 1 slot User editable. Ogni template è una "griglia" di timing/gate/velocity che la phrase originale segue al %-strength impostato.

## Lista completa (100 preset)

### Quantize straight

| # | Name | Note |
|---|------|------|
| 1 | 32Quantize | Griglia 1/32 |
| 2 | 24Quantize | Griglia triplet di 16th (24 pulses/beat) |
| 3 | 16Quantize | Griglia 1/16 |
| 4 | 16+24Quant | 1/16 + triplet 16ths |
| 5 | 12Quantize | Griglia triplet di 8th (12 pulses/beat) |
| 6 | 08Quantize | Griglia 1/8 |
| 7 | 08+12Quant | 1/8 + triplet 8ths |
| 8 | 06Quantize | — |
| 9 | 04Quantize | Griglia 1/4 |

### Swing

| Name | Meaning |
|------|---------|
| 32Swing | 1/32 swing |
| 04Swing | 1/4 swing |
| 16Swing | 1/16 swing (implicito, spesso default) |
| 08Swing | 1/8 swing |

### 24 (triplet 16ths) templates

`24>16+12`, `24Drunk`, `24Sambody`, `24Shfflin1`, `24Shfflin2` ...

### 16 (16th) templates — oltre 50

`16AccntDwn`, `16AccntUp`, `16AcidJazz`, `16Baion`, `16BaionBmb`, `16Batucada`, `16beatRock`, `16Bomba`, `16Caixa`, `16Cuban`, `16Drunk`, `16Dun-Dun`, `16GetFunky`, `16Guaguanc`, `16HipHop`, `16House`, `16Jungle`, `16Merengue`, `16Plena`, `16Reggae`, `16Rumba`, `16Salsa`, `16Samba`, `16SFunk`, `16Shuffle1`, `16Shuffle2`, `16Ska`, `16SkaTogu`, `16Slow`, `16Songo`, `16Soukous`, `16Swing`, `16TwoStep`, `16WayBack`, ...

### 08 (8th) templates

`08AccntDwn`, `08AccntUp`, `08Beat`, `08Funk`, `08Hiphop`, `08Jazz`, `08Rock`, `08Shuffle`, `08Swing`, `08TwoStep`, `08WayBack`, ...

### 06 templates

`06Quantize`, `06>4+3`, `06>4+3 ofs`, ...

## Parameters per ciascun template

Quando applicato a una track, il Groove Quantize ha:

| Parameter | Range | Effect |
|-----------|-------|--------|
| Template | 1-100 (o User) | Seleziona quale template |
| Strength | 0-100% | Quanto forte è la quantizzazione (0=off, 100=full) |
| Groove Timing | 0-200% | Scala delle deviazioni temporali del template (100=originale) |
| Groove GateTime | 0-200% | Scala delle durate del template |
| Groove Velocity | 0-200% | Scala delle velocity del template |

## User template

Oltre ai 100 preset, c'è 1 slot editabile. Puoi:
- Registrare un pattern di reference e usarlo come template
- Editare manualmente timing/gate/velocity per ogni 16th/8th position

## Rilevanza per qyconv

### Portabilità tra QY70 e QY700

Il QY70 ha un **subset** di questi template. Mapping non 1:1 — alcuni template QY700-only (es. Caixa, Samba, Salsa) non esistono sul QY70.

Per la conversione:
- Se template QY70 presente in QY700 → mapping diretto
- Altrimenti → User template con dati ricostruiti, oppure default quantize

### Normalize Play Effect (Song Job 22)

Prima di export SMF, eseguire Normalize Play Effect: il Groove template viene "materializzato" nelle note (cambia timing/gate/velocity) e il Play Effect viene resettato. Dopo questo, la song suona identica su altri device senza dipendenza dal template QY700.

### Lista completa in Reference Listing

La lista stampata (100 nomi esatti con numero) è nel PDF `QY700_REFERENCE_LISTING.pdf`. Non tutti i nomi sono stati estratti qui — per catalogazione completa, OCR del PDF serve.
