# QY700 Utility Mode

Ref: `manual/QY700/QY700_MANUAL/12_6UtilityMode.txt`

La mode UTILITY ha 6 sub-mode accessibili da `F1..F6`. Tutti i parametri sono battery-backed (SRAM interno).

**IMPORTANTE**: il QY700 NON ha Memory Protect né Device Number user-editable (simile al nostro QY70). Il device number SysEx è hardcoded a 0 e non modificabile.

## F1 — System

| Parameter | Range / Options |
|-----------|-----------------|
| Master Tune | -102.4 ÷ +102.3 cents (passo 0.1) |
| Backlite saver | Off, 1, 2, 4, 8 hours |
| Footswitch function | Start/Stop, Section Change, Sustain, Sostenuto |
| PITCH wheel assign | OFF, P.B., Ctrl#001-119 (escluso 32, CAT, VEL, TMP) |
| ASSIGNABLE wheel assign | stesso range di PITCH wheel |

Note: PITCH wheel = return-to-center; ASSIGNABLE wheel = detented (resta dove lo metti).

## F2 — MIDI

| Parameter | Options |
|-----------|---------|
| MIDI Sync | Internal, MIDI-A, MIDI-B, MTC:MIDI-A, MTC:MIDI-B |
| MIDI Control In | Off, In-A, In-B, In-A,B |
| MIDI Control Out | Off, Out-A, Out-B, Out-A,B |
| XG Parameter Out | Off, Out-A, Out-B, Out-A,B |
| Echo Back In-A | Off, Thru A, Thru B, Thru A,B, RecMonitor |
| Echo Back In-B | Off, Thru A, Thru B, Thru A,B, RecMonitor |
| MTC start offset | hh:mm:ss:ff (00-23, 00-59, 00-59, 00-29) |

**SysEx > 128 byte NON è echoed back** — hardcoded, non dipende dai settings.

**RecMonitor**: echoa il MIDI IN al MIDI OUT solo sul canale selezionato per la traccia in REC (utile per cuffia monitor live durante registrazione).

## F3 — MIDI Filter

Due colonne (TX e RX), stessi parametri:

| Filter | Affects |
|--------|---------|
| Note | Note On/Off |
| Pitch Bend | En messages |
| Control Change | Bn (inclusi MW, Expression, ecc.) |
| Program Change | Cn + Bank Select MSB (CC 0) + LSB (CC 32) |
| Poly Aftertouch | An |
| Channel Aftertouch | Dn |
| System Exclusive | F0..F7 |

Ogni filter può essere Off (=blocca) o On (=passa).

## F4 — Sequencer

| Parameter | Range |
|-----------|-------|
| Mute Track Level | Off (=0), 01-99% |
| Event Chase | Off, PC, PC+PB+Ctrl, ALL |
| Interval Time | 0-9 × 100ms |

**Mute Track Level**: quando una traccia viene MUTE, il suo volume viene ridotto di questa percentuale (non necessariamente portato a 0 — utile per mute gradual).

**Event Chase**: quando fai jump/locate a metà song, il QY700 decide quali eventi "passati" re-applicare (PC=program change, PB=pitch bend, Ctrl=CC, ALL=tutto).

**Interval Time**: pausa tra blocchi di 1KB durante playback SysEx da track (controllata di solito solo per bulk dump a tone generator esterni lenti).

## F5 — Click

Metronomo interno. Può suonare:
- Sul tone generator interno (TG)
- Via MIDI (OUT-A / OUT-B)
- O entrambi

| Parameter | Range |
|-----------|-------|
| Channel TG | Off, 01-32 |
| Channel MIDI A | Off, 01-16 |
| Channel MIDI B | Off, 01-16 |
| Accent Note | C-2 .. G8 |
| Accent Level | 0..127 |
| Normal Note | C-2 .. G8 |
| Normal Level | 0..127 |

L'accent suona sul primo beat di ogni misura; normal sui beat restanti.

## F6 — Fingered Chord Zone

Area della microkeyboard (o di una tastiera MIDI esterna) dedicata al chord input in Pattern Mode.

| Parameter | Range |
|-----------|-------|
| Switch | On / Off |
| Zone Low | C-2 .. G8 |
| Zone High | C-2 .. G8 |
| MIDI Port | In-A, In-B |
| MIDI Channel | ALL, 01-16 |

**Convention microkeyboard**: shift E2-D♯3 sono chord root; E3-F4 sono chord type (i simboli M/M7/6/7/m/... sono stampati sopra la tastiera).

## Rilevanza per qyconv

- **Echo Back Off** è essenziale per evitare loop MIDI durante cattura stream.
- **Interval Time** controlla la granularità della pausa inter-chunk SysEx in TX: se il QY700 invia dati troppo velocemente a un ricevitore lento, aumentare a 5-9.
- **MIDI Sync = Internal** è necessario perché [Recording] funzioni; se è esterno, il sequencer aspetta MIDI Clock.
- **Event Chase = ALL** è raccomandato se si fa locate su pattern/song con XG setup all'inizio (altrimenti i parametri delle parti restano quelli pre-locate).
