# CLAUDE.md

## STATUS.md (north-star)

Il file `STATUS.md` nella root è il **recap generale unico** del progetto: % completamento, cosa funziona, cosa manca, raccomandazione strategica, prossimi passi. **Aggiornalo a ogni chiusura di sessione** — in particolare:
- Data "Ultimo aggiornamento"
- Tabella "Valutazione generale" (% completato)
- Cosa è passato da "research" a "production-ready" o viceversa
- Cosa è passato da "non iniziato" a "in progress"

`STATUS.md` deve rimanere conciso (< 150 righe). I dettagli vanno in `wiki/`, linkati dal file.

## Wiki Maintenance

This project has a persistent knowledge base in `/wiki/`. The wiki is the single source of truth for all reverse-engineered knowledge about QY70/QY700 formats.

### Structure

- `wiki/index.md` — Master index of all pages (update on every page add/remove)
- `wiki/log.md` — Chronological log (append on every session with date prefix)
- Topic pages: interlinked markdown files covering formats, encodings, devices, status

### Rules

1. **After every discovery**: update the relevant wiki page AND the `log.md`
2. **After creating/removing a page**: update `index.md`
3. **Cross-link liberally**: use `[text](other-page.md)` links between pages
4. **Keep pages focused**: one topic per page, split if a page exceeds ~200 lines
5. **Confidence levels**: always note confidence (High/Medium/Low) for reverse-engineered findings
6. **Never duplicate**: if information exists in a wiki page, don't repeat it in docs/ — link to the wiki instead
7. **Session boundary**: at the end of each session, append a dated entry to `log.md` summarizing what was learned

### Key Pages

- [decoder-status.md](wiki/decoder-status.md) — Current decoding confidence per track type
- [open-questions.md](wiki/open-questions.md) — What to work on next
- [bricking.md](wiki/bricking.md) — Safety rules for Q7P writes

### Relationship to docs/

The `/docs/` directory contains the original detailed format documentation (QY70_FORMAT.md, QY700_FORMAT.md, etc.). The wiki synthesizes and organizes this knowledge. The docs/ files are the raw source material; the wiki is the compiled knowledge base.

## CRITICAL: QY70 Init Handshake for Dump Request

The QY70 REQUIRES an Init message before accepting Dump Requests:
```
F0 43 10 5F 00 00 00 01 F7   ← MUST send this first!
F0 43 20 5F 02 7E AL F7      ← Then dump request works
F0 43 10 5F 00 00 00 00 F7   ← Close when done
```
Without the Init, all dump requests return NOTHING. Discovered Session 22.

## Language

The user communicates in Italian. Respond in Italian. Code comments and technical terms remain in English.

## Environment

Il progetto usa **uv** (Astral). Su questo volume esterno serve `UV_LINK_MODE=copy` (il filesystem non supporta hardlink).

```bash
cd /Volumes/Data/DK/XG/T700/qyconv
export UV_LINK_MODE=copy

# Sync deps (prima volta o dopo modifiche a pyproject.toml)
uv sync --all-extras --group dev

# Test
uv run pytest

# Tool MIDI (richiedono extra `midi`, installato con --all-extras)
uv run python3 -m midi_tools.pattern_editor <cmd>
uv run python3 midi_tools/capture_playback.py ...

# CLI principale
uv run qymanager <cmd>
```
