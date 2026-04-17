# QY70 Hardware Quirks

Raccolta dei comportamenti non-documentati del QY70 emersi durante il reverse engineering. Ognuno registra cosa succede, come si scopre, quale workaround è stato convalidato su hardware e cosa resta aperto.

## 1. "Primo-bulk-only" — il QY70 accetta un solo bulk send per power-cycle

### Sintomo

Dopo un `F0 43 00 5F [header] [data] F7` accettato correttamente (dump di ritorno contiene i nuovi valori), qualsiasi bulk send successivo viene **visto trasmesso** dal lato host (`105/105` byte OK) ma l'edit buffer del QY70 **resta al primo valore accettato**. Ripetuti dump request (`F0 43 20 5F 02 7E 7F F7`) durante la finestra bloccata rispondono con un buffer "freeze": gli stessi byte del primo send.

### Come si manifesta

Riprodotto con `midi_tools/tempo_cycle_v2.py` in session 30c (4 BPM consecutivi: 120 → 151 → 160 → 100). Solo il primo valore viene registrato; gli altri tre vengono silenziosamente ignorati anche se lo stack MIDI host li spedisce senza errori.

### Workaround confermato su hardware

**Un edit + un send per power-cycle**. Spegnere e riaccendere il QY70 sblocca lo stato. `syx_edit.py` su un singolo ciclo send→dump→verify in session 30b ha confermato `decoded[0]=0x3F → BPM=120` (commit `29cda88`).

### Cosa **non** funziona

- Power-cycle senza `utility reset` preliminare (testato session 30c).
- Sequenza di MIDI reset (`B0 79 00`, All-Sound-Off, ecc.).
- Secondo dump request tra i send — il QY70 risponde ma continua a ignorare gli send successivi.

### Ipotesi residue (non validate)

- Il QY70 entra in uno stato "receive-ready one-shot" e richiede un **Pattern↔Song mode switch** esplicito per rearmarsi.
- Qualche XG System On (`F0 43 10 4C 00 00 7E 00 F7`) tra un send e l'altro potrebbe resettare la receive state machine (non ancora testato perché servirebbe stress ripetuto sull'hardware).
- Firmware bug legato al fatto che `AM=0x7E` (solo edit buffer) non commitsma solo sovrascrive temporaneamente.

### Impatto pratico

Tool di edit atomico `syx_edit.py` è usabile in workflow singolo: edit → send → power-cycle. Non esiste (ancora) un percorso per batch di edit consecutivi automatici. I test in `tests/` usano sempre dump catturati, non re-send multipli.

### Log sorgenti

- [log.md §session-30b](log.md) — primo cattura del quirk
- [log.md §session-30c](log.md) — re-test, power-cycle non sufficiente

## 2. XG PARM OUT **NON** trasmette Bank/Program Change come XG Param Change

### Sintomo

Cattura di `ground_truth_preset.syx` con XG PARM OUT=on (812 XG messages, 33 snapshot preset): il blocco Multi Part (`AH=0x08`) contiene soltanto tre `AL` code: `0x07` Part Mode, `0x11` Dry Level, `0x23` Bend Pitch. Nessun `0x01/0x02/0x03` (Bank MSB/LSB, Program).

### Cosa succede davvero

La voce programma per ciascuna Part **non viaggia come XG Parameter Change**: viaggia come eventi canale MIDI standard sul canale MIDI della Part (`Bn 00 MSB`, `Bn 20 LSB`, `Cn PROG`). Quelli non sono SysEx, quindi un listener che filtra `raw[0] == 0xF0` li perde tutti — è esattamente cosa faceva `capture_xg_stream.py` pre-session-30f.

### Workaround

Usare il flag `--all` di `capture_xg_stream.py` (aggiunto session 30f). Parser: `midi_tools.xg_param.parse_all_events(path) → (xg_msgs, channel_events)`. Voice name lookup: `qymanager xg voices <file>`.

### Impatto pratico

Ogni RE che voglia associare "preset X" → "voce su canale N" deve usare la cattura mista. Pattern dump Model 5F non aiuta (0 XG messages; verificato su `ground_truth_C_kick.syx`). [xg-parameters.md](xg-parameters.md#⚠️-limite-critico-xg-parm-out-non-trasmette-bankprogram) documenta dettagli e comandi.

## 3. `AM=0x7E` è l'unico target stabile per edit runtime

Il QY70 risponde al Bulk Dump Request **solo** su `F0 43 2n 5F 02 7E AL F7` (edit buffer). Invii con slot User (`AM=0x00..0x1F`) risultano rifiutati senza errore: necessitano STORE manuale post-send.

Workaround: sempre edit-buffer (`AM=0x7E`), poi STORE con il tasto fisico sul QY70 se si vuole persistenza.

Cross-reference: [memoria `reference_qy70_sysex_protocol.md`](../../giacomo/.claude/projects/-Volumes-Data-DK-XG-T700-qyconv/memory/reference_qy70_sysex_protocol.md) (non nel repo — documentata nel wiki per readability).

## 4. Cattura SysEx su macOS richiede rtmidi diretto, non mido

`mido` su macOS CoreMIDI droppa silenziosamente i messaggi SysEx lunghi. Tutti gli script di cattura del progetto (`capture_playback.py`, `capture_xg_stream.py`, `request_dump.py`) usano `rtmidi.MidiIn` direttamente. `mi.ignore_types(sysex=False, timing=True, active_sense=True)` è il setting corretto.

## Aggiungere nuovi quirk

Formato: Sintomo → Come si manifesta → Workaround → Cosa non funziona → Ipotesi → Log sorgenti.

Non aggiungere un quirk al wiki finché non è **riprodotto almeno due volte** su hardware distinto / in momenti distinti, altrimenti rischia di essere un artefatto one-off.
