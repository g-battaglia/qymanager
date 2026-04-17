# XG Parameter Reference — Hub

Tutti i comandi XG SysEx (Model ID `4C`) modificabili in tempo reale sul [QY70](qy70-device.md) **e sul [QY700](qy700-device.md)**. Entrambi espongono un tone generator XG-compatibile: ogni parametro del sound engine (voice, effetti, drum, system) è modificabile atomicamente via Parameter Change, senza passare per dump+edit del pattern.

> **Ricorda**: QY70 = macchina XG; QY700 = "XG- and GM-compatible AWM2 tone generator, 491 voci, 3 effect systems" (manuale QY700 pag 1, Introduction). Per modifiche real-time dei suoni usa questo protocollo, non il sequencer Model `5F`.

## Supporto per device

| Device | Tone generator | XG Param Change | XG event nel pattern | XG PARM OUT |
|--------|----------------|-----------------|----------------------|-------------|
| QY70 | XG + GM | Sì (runtime) | Sì (Event Edit: XG Exc System/Effect/Multi/Drum) | Sì (UTILITY → MIDI, pag 224) |
| QY700 | XG + GM | Sì (runtime) | Sì in Song mode (event type "XG Parameter", pag 948/1018). In Pattern/Phrase Edit disponibile solo "Excl" generico | Da verificare |

## Formato SysEx XG

```
F0 43 1n 4C [AH] [AM] [AL] [data...] F7
```

| Campo | Valore | Descrizione |
|-------|--------|-------------|
| `F0` | 0xF0 | SysEx Start |
| `43` | 0x43 | Yamaha Manufacturer ID |
| `1n` | 0x10-0x1F | Parameter Change, n=device number (0=default) |
| `4C` | 0x4C | XG Model ID |
| `AH AM AL` | — | Address High/Mid/Low (vedi tabelle) |
| `data` | 1-4 byte | Dato parametro (size da tabella) |
| `F7` | 0xF7 | SysEx End |

**Varianti**:
- Bulk Dump: `F0 43 0n 4C [BH] [BL] [AH AM AL] [data...] [CS] F7`
- Bulk Request: `F0 43 2n 4C [AH] [AM] [AL] F7`
- Parameter Request: `F0 43 3n 4C [AH] [AM] [AL] F7`

**Device number**: il QY70 risponde su `n=0` (OMNI) e sul device number configurato. Usare `10` (n=0) è sicuro.

## Variabili nelle tabelle

| Simbolo | Significato |
|---------|-------------|
| `NN` | Part Number (Parts 1-16 = 00h-0Fh) |
| `RR` | Drum Note Number (13-91 = 0Dh-5Bh) |
| `XX` | Data byte (00h-7Fh / 0-127 dec) |
| `0Y,0Z` | 2 nibble data (Part Detune) |
| `0W,0X,0Y,0Z` | 4 nibble data (Master Tune) |

## Pages dedicate

- **[xg-system.md](xg-system.md)** — Master Tune/Volume/Transpose, System reset, XG On, MIDI controller standard
- **[xg-multi-part.md](xg-multi-part.md)** — Multi Part setup per ognuna delle 16 parti (~70 parametri)
- **[xg-drum-setup.md](xg-drum-setup.md)** — Drum Setup 1/2 per-note (pitch, level, pan, EG, filter)
- **[xg-effects.md](xg-effects.md)** — Reverb, Chorus, Variation effects e loro type code

## Protocollo QY70: riferimenti manuale

Per il QY70 specifico, il manuale `QY70_LIST_BOOK.PDF` (pag. 56-62) elenca anche:
- Table 1-2 System
- Table 1-3 System Information (Model Name, XG Support Level)
- Table 1-4 Effect 1 (Reverb+Chorus+Variation)
- Table 1-5 Display Data (Message Window, Bitmap)
- Table 1-6 Multi Part
- Table 1-7 Drum Setup
- Table 1-8 Effect Type List (tutti i type code)

Le tabelle del QY70 coincidono con la specifica XG standard.

## Persistenza: XG Param Change vs Pattern Events

**Critico**: il QY70 tratta i comandi XG in due modi radicalmente diversi.

### Runtime (NON persistente)

Comandi XG Parameter Change inviati via MIDI IN dall'esterno (`F0 43 10 4C ... F7`):
- Modificano lo **stato runtime** del tone generator
- **Non vengono salvati** nel pattern
- **Non sono recuperabili** via Bulk Dump Request (Model 5F)
- Persi al power cycle o al caricamento di un altro pattern
- Reset da **XG System On**, **GM On**, **All Parameter Reset**, cambio pattern

Conseguenza: modificare un parametro via XG ed eseguire dump del pattern NON mostra la modifica, perché il pattern bitstream non contiene lo stato XG globale.

### Pattern-embedded (SALVATO)

Il QY70 permette di inserire eventi XG **come eventi del pattern** via Event Edit (manuale pag. 204-206):
- `XG Exc System` — reset globale, master volume/tune/transpose
- `XG Exc Effect` — Reverb/Chorus/Variation type + params
- `XG Exc Multi part` — part mode, bank, program, volume, pan, sends…
- `XG Exc Drum setup` — parametri per-nota dei Drum Setup 1/2

Questi eventi:
- Vengono **memorizzati nel pattern** (bitstream)
- Sono **trasmessi all'esecuzione** come normali eventi MIDI
- **Sopravvivono** al bulk dump / STORE / power cycle
- Possono essere riprodotti e ricavati via dump

### Setting "XG PARM OUT" (pag. 224)

Utility → MIDI → XG PARM OUT (on/off): determina se i parametri XG voice/effect vengono trasmessi fuori **quando cambiano** o quando si carica un nuovo song/pattern. Questo suggerisce che il QY70 mantiene uno stato XG globale ma NON necessariamente lo persiste nel pattern.

### Implicazioni per il reverse engineering

1. **Diff pattern via XG params** → NON funziona se applichi XG Param Change esterno: il bitstream del pattern non cambia.
2. **Diff pattern via XG events inseriti** → funziona, ma richiede editing manuale del pattern sul QY70.
3. **Dump SETUP** (`F0 43 20 5F 03 00 00 F7`, 32B) è potenzialmente la chiave: potrebbe contenere lo stato XG persistent per-song che XG PARM OUT trasmette al caricamento.

## Reverse engineering via XG

### Strategia A: SETUP dump diff (autonomous-friendly)

Target = **SETUP dump** (non pattern dump). Se i parametri XG globali sono lì:

1. **Baseline**: `F0 43 10 5F 00 00 00 01 F7` (Init) → `F0 43 20 5F 03 00 00 F7` (SETUP dump)
2. **Modifica XG**: `F0 43 10 4C AH AM AL DD F7` (un parametro alla volta)
3. **Ri-dump SETUP**: stesso comando
4. **Diff**: byte cambiato → mapping offset SETUP ↔ parametro XG

### Strategia B: Pattern dump con XG events inseriti (manuale)

Richiede input utente sul QY70:
1. Pattern vuoto → STORE → baseline dump
2. Event Edit → inserisci `XG Exc Effect Reverb Time = 20` → STORE → dump
3. Diff sul bitstream pattern → trova la sequenza di byte dell'evento XG

### Strategia C: All Bulk dump (`04 00 00`)

Cattura stato globale + all patterns. Se XG runtime state è qui, è l'unico modo per estrarlo senza edit manuale.

## Tool: `qymanager xg` (CLI) + `midi_tools/xg_param.py`

Dalla CLI principale:

```bash
qymanager xg summary capture.syx       # sommario per AH/Part/AL
qymanager xg parse capture.syx [-n 20] # decodifica ogni messaggio XG
qymanager xg diff a.syx b.syx          # parametri cambiati tra A e B
qymanager xg emit --ah 08 --am 00 --al 07 --data 01  # costruisci un messaggio
```

Oppure direttamente sul modulo:

## Tool: `midi_tools/xg_param.py`

Parser/emitter per XG Param Change. Sottocomandi:

```bash
# Parse e decodifica ogni messaggio XG in un .syx
uv run python3 midi_tools/xg_param.py parse <file.syx>

# Sommario per AH/NN/AL
uv run python3 midi_tools/xg_param.py summary <file.syx>

# Diff due stream XG
uv run python3 midi_tools/xg_param.py diff <a.syx> <b.syx>

# Costruisci un singolo messaggio XG (stamp su stdout)
uv run python3 midi_tools/xg_param.py emit --ah 08 --am 00 --al 07 --data 01
#  → F0 43 10 4C 08 00 07 01 F7  [Part 00 Part Mode=Drum]
```

## Osservazione chiave: XG PARM OUT è una fonte RE viabile

`ground_truth_preset.syx` (7337B, 812 messaggi) è una cattura del QY70 con XG PARM OUT attivo. Struttura tipica:

1. `F0 43 10 4C 00 00 7E 00 F7` — XG System On
2. Block di Variation: `5A` (Connection), `58` (Send→Reverb), `40 MSB LSB` (Type), `42..4A` (Params 1-5)
3. Per ogni Part: `07` (Part Mode), `11` (Dry Level), `23` (Bend Pitch)
4. `00 00 7D 01` — Drum Setup 2 Reset
5. Drum Setup 2 tuning: `31 <note> <AL> <data>` (Level, Variation Send, ecc)

Il QY70 emette questa sequenza **al cambio pattern/preset** se "UTILITY → MIDI → XG PARM OUT" = on (pag. 224 manuale). Questa è una fonte autonoma di stato XG per-pattern:

1. Attivare XG PARM OUT sul QY70
2. Catturare la trasmissione durante il cambio da pattern A a pattern B
3. Parse con `xg_param.py` → ottieni lo stato XG completo di ciascun pattern

**Confermato**: pattern dump (Model 5F) NON contiene messaggi XG (verificato su `ground_truth_C_kick.syx`). Lo stato XG per-pattern è emesso runtime, non incorporato nel bitstream pattern.

Vedi task #87.

### ⚠️ Limite critico: XG PARM OUT NON trasmette Bank/Program

Verificato empiricamente su `ground_truth_preset.syx` (812 msg, 33 snapshot): i soli `AL` del blocco **Multi Part** (`AH=0x08`) emessi sono

| AL | Nome | Conta |
|----|------|-------|
| `0x07` | Part Mode | 84 |
| `0x11` | Dry Level | 256 |
| `0x23` | Bend Pitch Control | 256 |

**Assenti**: `AL=0x01` (Bank MSB), `AL=0x02` (Bank LSB), `AL=0x03` (Program Number). Il QY70 non "mette" queste voci nello stream XG.

**Implicazione**: la selezione voice per-Part viaggia via **MIDI channel events** — `Bn 00 <MSB>` + `Bn 20 <LSB>` + `Cn <Program>` sul canale della Part — NON come XG Param Change. Per catturarli serve un listener che conservi anche 0x80..0xEF, non solo 0xF0:

```bash
# SysEx only (default) — perde PC/CC
python3 midi_tools/capture_xg_stream.py -o out.syx

# All events — cattura PC/CC e XG insieme
python3 midi_tools/capture_xg_stream.py --all -o out.syx
```

Il parser `xg_param.parse_all_events(path)` restituisce `(xg_msgs, channel_events)` per file misti. Usare questa via per scoprire a quale voce (dalla `XG Normal Voice List` / `XG Drum Voice List` in `manual/QY70/QY70_LIST_BOOK.PDF` pag 2-5) è assegnata ciascuna Part.

## Source

- [studio4all.de — Introduction](http://www.studio4all.de/htmle/main90.html)
- [studio4all.de — System + MIDI Control](http://www.studio4all.de/htmle/main91.html)
- [studio4all.de — Part Setup](http://www.studio4all.de/htmle/main92.html)
- [studio4all.de — Drum Setup](http://www.studio4all.de/htmle/main93.html)
- [studio4all.de — Reverb + Chorus](http://www.studio4all.de/htmle/main94.html)
- [studio4all.de — Variation Effect](http://www.studio4all.de/htmle/main95.html)
- `manual/QY70/QY70_LIST_BOOK.PDF` pag. 54-62

## Also See

- [SysEx Format](sysex-format.md) — Sequencer SysEx protocol (Model 5F)
- [QY70 Device](qy70-device.md) — General device info
