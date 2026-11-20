# Changelog

## 1.0.0 — 2026-11-20

- Modalità automatica `auto.py`: l'orchestratore è uno script, i motori sono `codex exec`, `claude -p` o un comando qualsiasi; esecuzione in background, stato e ripresa.
- Modalità in chat `passo.py`: macchina a stati che porta fino a «FINITO».
- Revisione finale: analisi di tutto il libro, correzioni puntuali `@@VECCHIO@@/@@NUOVO@@` con verifica e backup, rapporto finale.
- Ritentativi automatici delle parti respinte, con l'elenco degli errori.
- `build.py` con pandoc e Calibre: lingua corretta, sommario completo, CSS per i messaggi di sistema.
- `migra.py` per i progetti translate-book.
- Test end-to-end senza modelli.
