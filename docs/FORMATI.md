# Formati

## Risposta di traduzione (`save.py`, modalità automatica)

```
@@PARTE 0012@@
…testo tradotto, stesso Markdown e stessi paragrafi dell'originale…
@@META@@
{"new_entities": [{"source": "Salt Market", "target_proposal": "Mercato del Sale", "category": "luogo", "evidence": "…"}],
 "conflicts":    [{"source": "Copper Gull", "current_target": "Gabbiano di Rame", "proposed_target": "Gabbiano Ramato", "reason": "…"}]}
@@PARTE 0013@@
…
```

- `@@META@@` è facoltativo.
- Con `save.py` un META non valido blocca tutto il salvataggio. In modalità automatica viene scartata solo la parte con il META non valido, che poi viene ritentata.

## Risposta di revisione (`patch.py`)

```
@@PARTE 0012@@
@@VECCHIO@@
testo esatto copiato dalla traduzione (unico nella parte)
@@NUOVO@@
testo corretto
@@VECCHIO@@
…
@@NUOVO@@
…
@@PARTE 0013@@
@@OK@@
```

Ogni correzione:

- si applica solo se `VECCHIO` compare esattamente una volta nella parte;
- viene annullata se fa fallire la verifica di una parte che prima la superava.

Il primo originale di ogni parte modificata resta in `revisione/backup/`, e ogni correzione applicata viene registrata in `revisione/modifiche.md`.

## `glossario.json`

```json
[{"source": "Brass Warden", "target": "Custode d’Ottone", "tipo": "V", "nota": "automa, maschile", "alias": ["Warden"]}]
```

- **V** è vincolante: il modello non la cambia, e le proposte di cambio finiscono in `stato.json → conflitti_v`.
- **P** è una proposta, e una voce `conflicts` del META può cambiarla.
- Nei task entrano solo i termini il cui `source`, o uno degli `alias`, compare nelle parti del task.

## `stato.json`

```json
{"fatte": [1, 2], "meta_integrati": [1, 2], "da_rivedere": {"0002": ["…"]}, "rivedute": [1],
 "conflitti_v": [], "tentativi": {"0002": 1}, "finito": false}
```

Non contiene hash. Una parte è fatta se esiste `output_chunkNNNN.md`: modificare il glossario non rimette mai in coda le parti già tradotte.

## Cartella di lavoro

```
<libro>_temp/
  chunkNNNN.md  output_chunkNNNN.md  output_chunkNNNN.meta.json
  progetto.json regole.md glossario.json preglossario.json stato.json
  _task/        task in corso (cancellati quando chiusi)
  revisione/    segnalazioni.json rapporto.md modifiche.md backup/ RAPPORTO_FINALE.md
  libro/        <titolo>.epub .docx .pdf
  auto.log      registro della modalità automatica
  input.md images/ manifest.json config.txt   (dalla conversione)
```
