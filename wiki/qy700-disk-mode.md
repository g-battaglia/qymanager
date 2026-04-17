# QY700 Disk Mode

Ref: `manual/QY700/QY700_MANUAL/13_7DiskMode.txt`

Sub-mode DISK permette di salvare/caricare dati su floppy disk 3.5".

## Media supportati

| Formato fisico | Capacità | File system |
|----------------|----------|-------------|
| 2HD (MF2HD) | 1.44 MB, 18 settori/traccia | MS-DOS FAT12 |
| 2DD (MF2DD) | 720 KB, 9 settori/traccia | MS-DOS FAT12 |

File system **MS-DOS** → i dischi QY700 sono leggibili/scrivibili da PC (Mac via `hdiutil`/`dd`). Nomi file **8.3** MS-DOS (no `*`, no `?`, max 8 char base + estensione).

## Tipi di file (selezionabili con direct key D1..D5)

| Direct key | Tipo | Estensione | Contenuto |
|------------|------|------------|-----------|
| D1 | All Data | `.Q7A` | 20 songs + 64 styles + System Setup (tutto il contenuto) |
| D2 | Style | `.Q7P` | 1 style: 8 pattern + 99 user phrases + Play Effect + Pattern Voice + Pattern Effect |
| D3 | Song | `.Q7S` | 1 song: 32 sequence tracks + pattern/chord/tempo + voice/effect settings |
| D4 | Song ESEQ | `.ESQ` | Solo TR1-16 + tempo (Yamaha ESEQ format, compatibile QY70/MD serie) |
| D5 | Song SMF | `.MID` | Standard MIDI File Format 0 o 1 (tutte le track, fino a TR32 in Format 1) |

## Operazioni (function keys)

| Key | Function |
|-----|----------|
| F1 | Save |
| F2 | Load |
| F4 | Rename |
| F5 | Delete |
| F6 | Format |

### F1 Save

Seleziona il tipo (D1..D5), il song/style da salvare, inserisci filename (8 char + estensione auto).

Opzione **DeflName** (F6 da filename entry): copia automaticamente il nome del song/style come filename.

Opzione **XG Header** (solo per SMF/ESEQ):
- **ON**: aggiunge 1-2 setup measure all'inizio del file con SysEx Voice/Effect/Part setup. Utile per rendering su qualunque tone generator XG. Causa piccolo lag tempo nelle prime misure.
- **OFF**: il file contiene solo note/CC.

### F2 Load

Seleziona il file dalla lista; il QY700 carica nello slot corrispondente al tipo. Conferma sovrascrittura se slot non vuoto.

### F4 Rename

Nuovo filename. Se già esiste un file con lo stesso nome, errore "Can't Change File Name".

### F5 Delete

Conferma "Are you sure?" prima della cancellazione.

### F6 Format

Formatta il disco in formato QY700-compatibile (MS-DOS FAT12). **Distrugge tutti i dati sul disco**.

Due modalità:
- 2HD: 1.44 MB
- 2DD: 720 KB

Seleziona in base al tipo fisico del media.

## Rilevanza per qyconv

### Accesso diretto ai file Q7P/Q7S/Q7A via floppy

I file sono leggibili/scrivibili da PC. Pipeline possibile:
1. Creare file Q7P su PC tramite converter
2. Copiare su disco floppy (o immagine montata)
3. Caricare sul QY700 via DISK mode

Questo bypass il problema di **non poter caricare pattern via MIDI bulk** (vedi Open Question in `qy700-midi-protocol.md`).

### Formati esportabili

- **SMF Format 0/1**: l'export SMF è compatibile con qualunque DAW. Utile per backup e interoperabilità.
- **ESEQ**: legacy Yamaha format, compatibile con QY70/QY300/MD/PSR serie. 
- **Expand Backing (Song Job 21)** prima di Save SMF: espande pattern+chord track → MIDI data su TR17-32, così il SMF contiene anche le parti ritmiche/accompagnamento (non solo le tracce sequence).

### Incompatibilità note

- **QY300/QS300** patterns/phrases **NON caricabili** (strutture diverse).
- **Mac floppy drive**: richiede SuperDrive USB o emulatore (gli attuali Mac non hanno floppy).
- Q7P loaded from disk NON include i dati voice/effect della modalità Effect — quelli sono nel Q7A o nei singoli Q7S.

## Error messages (vedi [qy700-troubleshooting.md](qy700-troubleshooting.md))

- **No Disk** / **Unformat** / **Bad Disk**
- **Illegal Format** — formato non QY700 (es. esa floppy formattato DD ma inserito in slot HD o viceversa)
- **Write Protected** — cursore floppy in write-protect
- **File Not Found** / **Bad File** / **Illegal File**
- **Disk Full**
- **Disk Changed** — hai cambiato disco durante un'operazione multi-step
- **Can't Change File Name** — filename già esistente in rename
