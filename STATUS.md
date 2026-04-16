# Project Status — qyconv

> Single-source north-star del progetto QY70 ↔ QY700 reverse engineering.
> Aggiornato a ogni chiusura di sessione.

**Ultimo aggiornamento**: 2026-04-17 (Session 29e)
**Obiettivo finale**: Editor completo pattern + conversione bidirezionale QY700 ↔ QY70

---

## Valutazione generale

| Area | Stato | % completato |
|------|-------|---------------|
| Conversione QY70 → QY700 (Pipeline B capture-based) | **Production-ready** | 100% |
| Conversione QY70 → QY700 (Pipeline A SysEx decode) | Research-blocked | 10% |
| Conversione QY700 → QY70 (metadata only) | Parziale (musicalmente errato) | 30% |
| Editor completo pattern | Non iniziato | 0% |
| **Obiettivo finale complessivo** | In progress | **~30-40%** |

---

## Cosa funziona (alta confidenza)

- **Pipeline B**: capture QY70 → quantize → Q7P 5120/6144B. Roundtrip byte-valid verificato su hardware: 208/208 note SGT, 126/126 Summer, DECAY self-parse byte-identical
- **Metadata converter** (`qy70_to_qy700.py`): tempo, nome, volume, pan, chorus/reverb
- **Decoder sparse** (user patterns): 100% su 7/7 casi noti (rotation R=9×(i+1))
- **Q7P format**: read + write + validator con invariant phrase-stream (0 warnings)
- **Hardware I/O**: Init handshake, bulk dump, send style, capture playback tutti funzionanti
- **Test suite**: 31+ test regression verdi, tra cui hardware-capture

Dettagli: [wiki/conversion-roadmap.md](wiki/conversion-roadmap.md), [wiki/decoder-status.md](wiki/decoder-status.md)

---

## Cosa è bloccato (research)

- **Decoder dense** (factory styles): struttura parzialmente compresa (per-beat rotation, 42B super-cycle SGT, 692B shared prefix) ma **nessun output MIDI corretto** prodotto. Structural impossibility provata su velocity encoding (Session 20). Stima: 10-30 sessioni residue, non garantito (forse serve firmware dump)
- **Encoder dense** (Q7P → SysEx): dipende dal decoder, 0% fatto
- **Chord transposition layer**: non decodificato — bar headers memorizzano chord-relative templates
- **Voice writes al QY700**: offset reali sconosciuti (0x1E6/0x1F6/0x206 causavano bricking, ora disabilitati)

Dettagli: [wiki/open-questions.md](wiki/open-questions.md), [wiki/bitstream.md](wiki/bitstream.md)

---

## Cosa non è ancora iniziato

- **Editor UI**: nessuna interfaccia utente
- **Pattern editing**: modifica note/velocity/timing su pattern catturato
- **Batch conversion**: conversione multipli file
- **Conversione chord tracks completa** (QY70 → QY700)

---

## Raccomandazione strategica

**Costruire editor completo sopra Pipeline B** anziché attendere decoder dense.

Workflow proposto:
1. Utente suona/registra pattern sul QY70
2. Sistema cattura MIDI playback via `capture_playback.py`
3. Editor carica note quantizzate da JSON
4. Utente modifica (note, velocity, timing, tracce)
5. Output: Q7P per QY700 + SMF standard

Pro: consegna prodotto funzionante molto prima, bypassa decoder dense irrisolto.
Contro: meno "puro" — serve QY70 hardware connesso per catturare.

---

## Prossimi passi prioritari

Ordine suggerito (ciascuno = 1+ sessione):

1. **Hardware**: catturare ground truth patterns A/B/C/D (chord semplici) per validare chord decoder
2. **Software**: verificare decoder Pipeline B su più pattern utente (oltre SGT/Summer)
3. **Strategia**: decidere se investire in decoder dense (rischioso) o editor Pipeline B (pragmatico)
4. **Decoder dense** (se si sceglie rischio): mappare 42B super-cycle SGT → MIDI note, cross-validate con playback capture
5. **Editor UI** (se si sceglie pragmatismo): prototipo CLI che carica capture JSON, permette edit, rigenera Q7P

---

## Stime residue (sessioni simili alle recenti)

| Task | Stima | Confidenza |
|------|-------|------------|
| Decoder dense completo | 10-30 sessioni | Bassa |
| Encoder dense Q7P→SysEx | 5-10 sessioni | Media (post-decoder) |
| Editor CLI su Pipeline B | 10-20 sessioni | Alta |
| Editor GUI | +10-20 sessioni | Media |

---

## File di riferimento

- **[wiki/conversion-roadmap.md](wiki/conversion-roadmap.md)** — pipeline details, blocking issues
- **[wiki/decoder-status.md](wiki/decoder-status.md)** — per-encoding confidence, history sessioni
- **[wiki/bitstream.md](wiki/bitstream.md)** — dense encoding structure
- **[wiki/open-questions.md](wiki/open-questions.md)** — hypotheses aperte
- **[wiki/log.md](wiki/log.md)** — log cronologico sessione-per-sessione
- **[CLAUDE.md](CLAUDE.md)** — istruzioni di progetto per AI agents
