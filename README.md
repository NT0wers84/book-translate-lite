# book-translate-lite

Una skill per **Claude Code** e **Codex** che traduce un libro intero (EPUB, PDF, DOCX o Markdown) **dall'inizio alla fine**, con **revisione finale** e libro pronto in EPUB, DOCX e PDF. È progettata per consumare pochi token.

*An agent skill (Claude Code / Codex) that translates a whole book end to end — chunking, parallel translation, automatic checks, a final review pass and EPUB/DOCX/PDF output — with an orchestrator that is a script, not a model. Docs are in Italian.*

```
libro.epub ─ init ─▶ parti ─▶ traduzione a gruppi ─▶ controlli ─▶ revisione ─▶ EPUB · DOCX · PDF
                              (motore in parallelo)   (script)    (motore)     + RAPPORTO_FINALE.md
```

## Perché

Con le skill di traduzione classiche, il costo lo fa soprattutto l'**orchestratore**: una conversazione lunga che a ogni chiamata rimanda centinaia di migliaia di token. Qui ci sono tre accorgimenti:

1. **L'orchestratore è uno script** (`auto.py`). Ogni gruppo di 3 parti è *una* chiamata non interattiva al modello (`codex exec` o `claude -p`) con un task autosufficiente. Il modello non deve usare strumenti: risponde con i blocchi tradotti, e lo script li salva e li verifica.
2. **Task minimi.** Ogni task contiene solo le regole, i termini del glossario presenti in quelle parti, i nomi ricorrenti ancora senza resa e la coda della parte precedente per la continuità.
3. **I controlli e le correzioni meccaniche li fanno gli script**, non il modello. Gli script verificano paragrafi, Markdown, termini e regole vietate, e correggono apostrofi, virgolette, `...`→`…` e altre sostituzioni di progetto.

Se non c'è una CLI, la **modalità in chat** (`passo.py`) usa i sotto-agenti dell'app: l'orchestratore lancia solo un comando che gli dice cosa fare dopo.

## Installazione

```bash
git clone https://github.com/NT0wers84/book-translate-lite.git
cd book-translate-lite && ./install.sh
```

`install.sh` crea i link simbolici in `~/.claude/skills/` e `~/.codex/skills/`.

Requisiti:

- Python 3.9+, [pandoc](https://pandoc.org) 3.x e [Calibre](https://calibre-ebook.com), per la conversione e per il PDF;
- per la modalità automatica, la CLI di [Codex](https://github.com/openai/codex) oppure quella di [Claude Code](https://docs.anthropic.com/claude-code).

## Uso rapido

```bash
S=~/.claude/skills/book-translate-lite/scripts
python3 $S/init.py "Il mio libro.epub" --lang it
cd "Il mio libro_temp"
# facoltativo: titolo tradotto in progetto.json, nomi fissi in glossario.json, stile in regole.md
python3 $S/auto.py --sfondo            # parte e va avanti da solo fino al libro finito
python3 $S/auto.py --stato             # a che punto è
```

Il risultato finisce in `libro/<titolo>.epub|docx|pdf`. Il resoconto è in `revisione/RAPPORTO_FINALE.md`.

### Prompt di avvio per un agente (Codex o Claude)

> Usa la skill book-translate-lite per tradurre `<percorso>/libro.epub` in italiano. Prepara il progetto con `init.py`, imposta il titolo tradotto, poi avvia la modalità automatica in background e dimmi come seguirla. Se la CLI non c'è, usa la modalità in chat e vai avanti fino a «FINITO».

Per riprendere un lavoro già avviato:

> Usa la skill book-translate-lite in `<percorso>/<libro>_temp` e porta la traduzione fino alla fine.

## Le fasi

| fase | cosa succede | file |
|---|---|---|
| preparazione | conversione con Calibre in Markdown diviso in parti da circa 6.000 caratteri, pre-glossario dei nomi ricorrenti | `chunkNNNN.md`, `progetto.json`, `regole.md`, `glossario.json`, `preglossario.json` |
| traduzione | gruppi di `gruppo` parti, `paralleli` alla volta. Ogni risposta è verificata; le parti respinte vengono ritradotte con l'elenco degli errori, fino a `tentativi` volte, poi accettate e segnalate | `output_chunkNNNN.md`, `.meta.json`, `stato.json`, `auto.log` |
| glossario | dopo ogni gruppo, i termini nuovi proposti dal modello entrano come **P** (proposta). Un conflitto su un termine P cambia la resa; uno su un termine **V** (vincolante) viene solo annotato | `glossario.json`, `stato.json → conflitti_v` |
| analisi | scansione di tutto il libro: errori di struttura, termini resi in modo diverso nelle varie parti, frasi rimaste in lingua originale, virgolette, parole ripetute | `revisione/segnalazioni.json`, `revisione/rapporto.md` |
| revisione | il motore di revisione (anche diverso, per esempio Claude) rilegge originale e traduzione e risponde con correzioni puntuali `@@VECCHIO@@/@@NUOVO@@`. Le correzioni che non trovano il testo o che rompono la verifica vengono scartate | `revisione/modifiche.md`, `revisione/backup/` |
| libro | pandoc (EPUB e DOCX) e Calibre (PDF): `lang` corretto, sommario con tutti i capitoli, riquadro per i messaggi di sistema | `libro/` |
| rapporto | che cosa resta da guardare a mano e quali termini vincolanti qualcuno vorrebbe cambiare | `revisione/RAPPORTO_FINALE.md` |

Il valore `revisione` in `progetto.json` decide quanto rivedere: `completa` (default), `segnalate` (solo le parti con problemi) oppure `nessuna`.

## Configurazione: `progetto.json`

| chiave | default | significato |
|---|---|---|
| `lingua`, `lingua_nome` | `it`, `italiano` | lingua di arrivo |
| `titolo`, `autore` | dal libro | metadati del libro finale |
| `gruppo`, `paralleli` | 3, 3 | parti per chiamata e chiamate in parallelo |
| `tentativi` | 2 | ritraduzioni di una parte respinta |
| `motore`, `modello`, `ragionamento` | `codex`, —, `low` | motore di traduzione |
| `motore_revisione`, `modello_revisione`, `ragionamento_revisione` | come traduzione, —, `medium` | motore di revisione |
| `comando_motore` | — | con `motore: "comando"`, il comando da lanciare: riceve il task su stdin e restituisce la risposta su stdout |
| `revisione`, `gruppo_revisione` | `completa`, 3 | |
| `virgolette`, `apostrofo_tipografico`, `punto_fuori` | `«»`, sì, sì | correzioni tipografiche automatiche |
| `sostituzioni` | `Okay→Ok`, `...→…` | `[{"re", "con"}]`, applicate a ogni salvataggio |
| `vietate` | — | `[{"re", "msg"}]`: forme che bloccano la parte |
| `maiuscolo_chat` | — | nomi le cui righe `Nome: …` devono essere TUTTE MAIUSCOLE |
| `rapporto_min`, `rapporto_max` | 0,6 / 1,9 | soglie per i paragrafi troppo corti o troppo lunghi |
| `formati`, `timeout_minuti` | `epub,docx,pdf`, 20 | |

## Comandi

| script | uso |
|---|---|
| `init.py libro --lang it [--chunk-size 6000]` | crea `<libro>_temp/` accanto al libro |
| `auto.py [--sfondo] [--stato] [--motore …] [--fino N] [--revisione …]` | modalità automatica, si può riprendere |
| `passo.py` | modalità in chat: stampa la prossima azione fino a «FINITO» |
| `prep.py [A B] [--rev]` · `save.py` · `patch.py` · `finish.py [A B]` | i passi singoli, a mano |
| `check.py A [B] \| --tutte [--breve] [--fix]` | verifica, in sola lettura salvo `--fix` |
| `revisione.py analizza \| da-fare \| finale` | analisi del libro, parti da rivedere, chiusura con build e rapporto |
| `build.py [--titolo] [--formati] [--parziale] [--out]` | costruzione del libro |
| `migra.py <cartella>_temp` | importa un progetto [translate-book](https://github.com/deusyu/translate-book) senza toccare le parti fatte |

Formati dei blocchi e dei file: [docs/FORMATI.md](docs/FORMATI.md). Architettura e scelte: [docs/ARCHITETTURA.md](docs/ARCHITETTURA.md).

## Test

```bash
python3 tests/test_completo.py
```

I test usano un libro di prova scritto apposta (`tests/libro_prova.md`) e un motore finto, quindi non chiamano nessun modello. Provano:

- la modalità automatica, compreso un errore da ritentare, la revisione e il libro in EPUB, DOCX e PDF;
- la modalità in chat con sotto-agenti simulati;
- il rifiuto delle parti incomplete;
- la migrazione senza modifiche ai file esistenti.

## Note

- La traduzione è per uso personale. Rispetta i diritti d'autore dei libri che traduci.
- Ogni libro sta nella sua cartella `<libro>_temp/`, e la skill non scrive mai fuori da lì.

## Licenza

MIT. `scripts/vendor/convert.py` e `scripts/vendor/manifest.py`, che convertono l'input in Markdown e lo dividono in parti, vengono senza modifiche da **translate-book** © 2025 Rainman, con licenza MIT ([scripts/vendor/LICENSE-translate-book](scripts/vendor/LICENSE-translate-book)). Il resto è scritto da zero.
