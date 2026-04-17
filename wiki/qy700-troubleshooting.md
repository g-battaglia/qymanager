# QY700 Troubleshooting & Error Messages

Ref: `manual/QY700/QY700_MANUAL/15_Troubleshooting.txt`

## Error messages — categorizzate

### Monitor (input errors)

| Message | Cause | Fix |
|---------|-------|-----|
| Illegal Input | Input inappropriato | Check input method, try again |
| Preset Phrase | Attempted edit of preset phrase | Copy to User phrase first |
| No Data | Selected track/area empty | Re-select area |
| Time Sig. Mismatch | Phrase time sig ≠ pattern time sig | Change pattern time sig |
| Exceed Pat Meas | Phrase longer than pattern measures | Extend pattern length |

### MIDI

| Message | Cause | Fix |
|---------|-------|-----|
| XG Data Error | Invalid SysEx data received | Check MIDI cables, retransmit |
| XG Adrs Error | Invalid address in SysEx | Check AH/AM/AL |
| XG Size Error | Data size mismatch | Check ByteCountH/L |
| XG Checksum Error | Checksum mismatch | Recalc `(0 - sum) & 0x7F` |
| MIDI Buffer Full | RX buffer overflow | Reduce TX rate, add pause between chunks (Interval Time ≥ 3 in UTILITY F4) |

### Disk

| Message | Cause | Fix |
|---------|-------|-----|
| No Data | Save operation, song/style empty | Select different item |
| No Disk | Floppy not inserted | Insert floppy |
| Illegal Format | Floppy format unsupported | Format floppy or use different disk |
| Unformat | Floppy not formatted | Format in DISK mode F6 |
| Bad Disk | Physical failure | Use different floppy |
| Bad File | File corrupted | — |
| File Not Found | Specified file doesn't exist | Re-select, reinsert disk |
| Write Protected | Write-protect slider in prohibit pos | Close write-protect slider |
| Disk Full | No space for save | Delete files or use new disk |
| Disk Changed | Disk swapped during operation | Restart operation |
| Illegal File | File type unsupported | Check file contents |
| Can't Change File Name | Target filename already exists | Use different filename |

### System

| Message | Cause | Fix |
|---------|-------|-----|
| Memory Full | Internal memory full | Delete unused songs/patterns/phrases |
| Battery Low | Backup battery depleted | Contact Yamaha service center |

## Confirmations (non-errors)

| Message | When | Response |
|---------|------|----------|
| Can't Undo. Ok? (Y/N) | Job would fill memory, undo unavailable | [Inc]=execute, [Dec]=cancel |
| Executing... | Job in progress | Wait |
| Completed | Job finished | Press any key |
| Are you sure? (Y/N) | Before destructive op | [Inc]=yes, [Dec]=no |

## Common problems

### No sound

- Volume / track volume raised?
- Effect settings wrong?
- Fingered Chord on?
- Tracks muted? / TO TG channel off?
- Speaker disconnected?
- Playback data contains inappropriate Volume or Expression?

### Distorted sound

- Unneeded effects active? (Reverb return + Variation return too high → clipping)

### Volume low

- MIDI Volume (CC 7) or Expression (CC 11) lowered?

### Pitch wrong

- Note Shift ≠ 0?
- Detune ≠ 0?
- Transpose ≠ 0?

### Notes sputter/stutter

- Polyphony exceeded (max 32 voices)? Use Element Reserve or reduce note density.

### Playback doesn't start

- Song/pattern/phrase empty?
- MIDI Sync ≠ Internal? (Se esterno aspetta MIDI Clock)

### Song stops mid-play

- Pattern track contains style 65 "end"? (style 65 = stop)
- Pattern track contains Section Connection to END?

### Mute has low effect

- UTILITY F4 Mute Track Level = 0 vs percentuale

### No sound on chord change mid-measure

- Retrigger Off for that phrase?

### Groove different from recording

- Play Effect settings active? (disable per confronto)

### Fingered Chord not working

- Fingered Chord off (Utility F6)?
- Keys pressed outside Fingered Chord Zone?

### Can't load QY300 disk

- Must be MF2DD disk (720 KB)
- **QY300/QS300 patterns/phrases NOT compatible** (struttura diversa) — solo dati generici caricabili

### No click

- Song Play Click turned off?
- UTILITY F5 Click TG Channel off?
- Voice Mixer click part volume = 0?

### Voice/effect settings disappear when song starts

- Song beginning contains **tone generator reset** SysEx (XG System On / All Parameter Reset)?
- Data saved with XG Header was reloaded & resaved → XG Header re-applied ogni save
- Pattern track present → voice settings change with pattern
- Song Pattern Setup ON → voice/effect change with pattern

### Memory full with unused songs

- Large song/phrase uses much memory (shared pool 110,000 notes total)

## Tips preventivi

1. **Backup regolare**: save su floppy come Q7A (tutto). Battery low → perdita totale.
2. **Interval Time in UTILITY F4** = 3-5 per evitare "MIDI Buffer Full" quando ricevi bulk da PC/QY70.
3. **Echo Back Off**: sempre, per evitare MIDI loop.
4. **Write-protect floppy** di backup: slider in "aperto" (protetto).
5. **XG Header Off** quando fai Save as SMF, SE il song non deve girare su altri XG (risparmio 1-2 misure di setup data).
6. Battery originale dura ~5-10 anni. Se il display mostra "Battery Low", contatta service ENTRO pochi giorni (perdita dati se batteria muore completamente).
