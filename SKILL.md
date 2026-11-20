---
name: book-translate-lite
description: Traduce un libro intero (EPUB/PDF/DOCX/MD) dall'inizio alla fine con revisione finale e libro pronto, consumando pochi token - orchestratore a script, gruppi di parti per sotto-agente, controlli e correzioni automatiche. Usare per tradurre un libro o riprendere una traduzione (cartella <libro>_temp con progetto.json).
---

# book-translate-lite

`S=<cartella di questa skill>/scripts`. Tutti i comandi si lanciano **dentro `<libro>_temp/`**. Il lavoro va avanti **fino alla fine del libro**: traduzione → revisione → EPUB/DOCX/PDF + `revisione/RAPPORTO_FINALE.md`.

## 1. Preparazione (una volta)

- Libro nuovo: `python3 $S/init.py libro.epub --lang it`, poi `cd <libro>_temp`.
- Progetto translate-book esistente: `python3 $S/migra.py <libro>_temp` (le parti fatte non vengono toccate).
- In `progetto.json` imposta `titolo` (tradotto). Se l'utente ha preferenze di stile, aggiungile a `regole.md`. Se vuole fissare i nomi principali, mettili in `glossario.json` (tipo V); i candidati sono in `preglossario.json`.

## 2A. Modalità automatica (consigliata: zero token di orchestrazione)

Serve la CLI `codex` o `claude` sul computer.

```
python3 $S/auto.py --sfondo [--motore codex|claude] [--motore-revisione claude]
python3 $S/auto.py --stato        # quando l'utente chiede a che punto è
```

Lo script traduce a gruppi in parallelo, ritenta le parti respinte, fa la revisione e costruisce il libro. Si può rilanciare: riprende da dove era. Se è bloccato, leggi le ultime righe di `auto.log`.

## 2B. Modalità in chat (sotto-agenti di questa app)

Ripeti fino a «FINITO», senza fermarti:

1. `python3 $S/passo.py`
2. Se stampa «AVVIA ADESSO»: avvia **tutti** i sotto-agenti elencati **in una sola chiamata**, ciascuno con il suo prompt esatto e niente altro, poi aspettali **in una sola attesa**. Poi torna a 1.
3. Se stampa «BLOCCATE»: riferiscilo all'utente e prosegui con le altre parti.
4. Se stampa «FINITO»: riferisci all'utente il riepilogo di `revisione/RAPPORTO_FINALE.md`.

`passo.py` chiude i task, verifica, aggiorna il glossario, rimette in coda le parti respinte, passa da solo alla revisione e alla costruzione del libro.

Regole: **non leggere traduzioni, task o glossario**; leggi solo l'output di `passo.py` e le risposte brevi dei sotto-agenti. Non correggere a mano. Non ritradurre le parti fatte. Ogni tuo messaggio intermedio: al massimo una riga. Per l'orchestratore basta un modello economico con ragionamento basso.

## 3. Ultima lettura (Claude)

Al termine, se richiesto, rivedi solo le parti elencate in `revisione/RAPPORTO_FINALE.md`: correzioni con `patch.py` (formato `@@PARTE NNNN@@ @@VECCHIO@@ … @@NUOVO@@ …`), poi `python3 $S/build.py`.

## Comandi utili

`check.py --tutte --breve` · `finish.py` (stato) · `revisione.py analizza` · `build.py [--parziale]`
