# Architettura e scelte

## Da dove viene il consumo

Su un libro reale di 291 parti, tradotto con un orchestratore LLM e sotto-agenti, i log hanno mostrato tre cose:

- **Sotto-agenti:** ogni chiamata di strumento costa circa 25–30k token di contesto fisso (prompt di sistema, strumenti, storia), mentre una parte tradotta ne produce circa 2,5k. Il costo segue il **numero di chiamate**, non la lunghezza del testo.
- **Orchestratore:** una conversazione tenuta aperta per giorni arrivava a circa 400k token per chiamata e faceva circa il **90%** della spesa totale.
- **Skill originale:** un `SKILL.md` di circa 7k token, caricato in ogni contesto.

## Risposte

| problema | soluzione |
|---|---|
| orchestratore LLM costoso | `auto.py`: l'orchestratore è uno script. In chat, `passo.py` riduce ogni passo a un comando con un output di poche righe |
| troppe chiamate per parte | **un gruppo di 3 parti = 1 chiamata** in modalità automatica, senza strumenti; 2 chiamate (`cat` del task + `save.py`) in chat |
| contesto superfluo | ogni task contiene solo i termini presenti, le regole e 600 caratteri di continuità |
| il modello controlla e corregge | `check.py` e `correggi()`: controlli e tipografia sono deterministici |
| «da ritradurre» dopo ogni modifica al glossario | stato senza hash |
| EPUB marcato con la lingua sbagliata, sommario di una sola voce | `build.py` usa pandoc con `lang` da `progetto.json` e `--split-level=1`: un capitolo per ogni `#` |
| il lavoro si ferma a metà | le parti respinte vengono ritentate con l'elenco degli errori e poi accettate con segnalazione; i giri senza progresso fermano tutto con un messaggio chiaro; tutto si può riprendere |

## Revisione

La revisione è separata dalla traduzione, per tre motivi:

1. Le **segnalazioni** sono calcolate su tutto il libro, con il glossario finale. Dicono, per esempio, «questo termine è reso in un altro modo in 12 parti», cosa che un singolo sotto-agente non può vedere.
2. Il **motore di revisione** può essere più forte, per esempio Claude per la revisione e Codex con ragionamento basso per la traduzione.
3. Il revisore restituisce solo **correzioni puntuali**, quindi l'output costa poco. Una correzione che non trova il testo o che rompe la struttura viene scartata.

## Riuso

Da translate-book (MIT) vengono, senza modifiche, `convert.py` e `manifest.py`: la conversione Calibre → HTML → Markdown, la gestione di note e immagini e la divisione in parti. Il formato delle parti (`chunkNNNN.md` / `output_chunkNNNN.md` / `.meta.json`) è compatibile, perciò `migra.py` può importare progetti avviati con translate-book.
