#!/usr/bin/env python3
"""Traduzione AUTOMATICA dall'inizio alla fine: traduzione → revisione → libro.

Uso:  auto.py [--motore codex|claude|comando] [--modello M] [--paralleli 3]
              [--motore-revisione claude] [--revisione completa|segnalate|nessuna]
              [--fino N] [--senza-build] [--dir CARTELLA]
      auto.py --sfondo …   parte in background (con caffeinate su macOS) e torna subito
      auto.py --stato      ultime righe di auto.log e stato del lavoro

L'orchestratore è questo script: nessun modello spende token per coordinare.
Ogni gruppo di parti è UNA chiamata al motore (task su stdin, risposta = blocchi
@@PARTE@@), senza strumenti. Le parti respinte dal controllo vengono ritradotte
fino a `tentativi` volte con l'elenco degli errori; poi vengono accettate e
segnalate per la revisione, così il lavoro arriva sempre fino in fondo.
Si può interrompere e rilanciare in qualsiasi momento: riprende da dove era.
Registro: auto.log nella cartella di lavoro.
"""
import argparse, concurrent.futures as CF, os, shutil, subprocess, sys, time
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import comune as C
import lavoro as L
import motore as M
import revisione as R
import task as T


class Log:
    def __init__(self, d):
        self.p = os.path.join(d, 'auto.log')

    def __call__(self, msg):
        riga = time.strftime('%Y-%m-%d %H:%M ') + msg
        print(riga, flush=True)
        with open(self.p, 'a', encoding='utf-8') as f:
            f.write(riga + '\n')


def traduci_gruppo(d, ids, cfg, terms, regole, log):
    """Ritorna {n: problemi} per le parti accettate con problemi (dopo i tentativi)."""
    problemi = None
    for tentativo in range(1 + cfg['tentativi']):
        path = T.traduzione(d, ids, cfg, terms, regole, modo='diretto', problemi=problemi)
        risposta, err = M.chiama(cfg, C.leggi(path), d)
        if err:
            log(f'  {ids[0]:04d}-{ids[-1]:04d}: errore del motore: {err}')
            problemi = None
            continue
        salvate, probs, errori = L.salva_blocchi(d, risposta, cfg, terms, attese=ids, tutto_o_niente=False)
        manc = [n for n in ids if n not in salvate]
        resto = sorted(set(manc) | set(probs))
        if not resto:
            os.remove(path)
            return {}
        problemi = {n: probs.get(n) or [e for e in errori if f'{n:04d}' in e] or ['parte mancante nella risposta']
                    for n in resto}
        log(f'  tentativo {tentativo + 1}: da rifare ' + ', '.join(f'{n:04d}' for n in resto)
            + ' — ' + '; '.join(problemi[resto[0]])[:160])
        os.remove(path)
        ids = resto
    return {n: problemi[n] for n in ids if C.tradotta(d, n)} if problemi else {}


def fase_traduzione(d, cfg, fino, log):
    g, par = cfg['gruppo'], cfg['paralleli']
    stallo = 0
    while True:
        mancanti = [n for n in range(1, fino + 1) if not C.tradotta(d, n)]
        if not mancanti:
            return True
        lotto = R.gruppi(mancanti[:g * par], g)
        terms = C.glossario(d); regole = C.leggi(os.path.join(d, 'regole.md')).strip()
        t0 = time.time()
        with CF.ThreadPoolExecutor(par) as ex:
            ris = list(ex.map(lambda ids: traduci_gruppo(d, ids, cfg, terms, regole, log), lotto))
        da_riv = {n: p for r in ris for n, p in r.items()}
        st = C.stato(d)
        L.chiudi(d, [n for gr in lotto for n in gr], st, da_rivedere=da_riv, stampa=log)
        log(f'{lotto[0][0]:04d}-{lotto[-1][-1]:04d} in {int(time.time() - t0)} s · ' + L.riga_stato(d))
        rimaste = [n for n in range(1, fino + 1) if not C.tradotta(d, n)]
        stallo = stallo + 1 if len(rimaste) == len(mancanti) else 0
        if stallo >= 2:
            log('STOP: nessun progresso in due giri (motore non disponibile o risposte non valide). '
                'Controlla auto.log e rilancia.')
            return False


def rivedi_gruppo(d, ids, cfg, terms, regole, seg, log):
    for tentativo in range(2):
        path = T.revisione(d, ids, cfg, terms, regole, seg, modo='diretto')
        risposta, err = M.chiama(cfg, C.leggi(path), d, revisione=True)
        os.remove(path)
        if err:
            log(f'  revisione {ids[0]:04d}-{ids[-1]:04d}: errore del motore: {err}'); continue
        ok, scartate, viste = L.applica_patch(d, risposta, cfg, terms)
        if viste:
            for n, m in scartate[:5]:
                log(f'  scartata {n:04d}: {m}')
            return [n for n in viste if n in ids], ok
        log(f'  revisione {ids[0]:04d}-{ids[-1]:04d}: risposta senza blocchi @@PARTE@@')
    return [], 0


def fase_revisione(d, cfg, log):
    if cfg['revisione'] == 'nessuna':
        return
    seg = R.analizza(d, log)
    stallo = 0
    while True:
        ids = R.da_fare(d)
        if not ids:
            return
        lotto = R.gruppi(ids, cfg['gruppo_revisione'])[:cfg['paralleli']]
        terms = C.glossario(d); regole = C.leggi(os.path.join(d, 'regole.md')).strip()
        with CF.ThreadPoolExecutor(cfg['paralleli']) as ex:
            ris = list(ex.map(lambda g: rivedi_gruppo(d, g, cfg, terms, regole, seg, log), lotto))
        st = C.stato(d)
        viste = [n for v, _ in ris for n in v]
        st['rivedute'] = sorted(set(st['rivedute']) | set(viste)); C.salva_stato(d, st)
        log(f'revisione {lotto[0][0]:04d}-{lotto[-1][-1]:04d}: {sum(k for _, k in ris)} correzioni · '
            f'rivedute {len(st["rivedute"])}, da fare {len(R.da_fare(d))}')
        stallo = 0 if viste else stallo + 1
        if stallo >= 2:
            log('STOP revisione: nessun progresso in due giri. Rilancia auto.py per riprendere.'); return


def _vivo(pid):
    try:
        os.kill(pid, 0); return pid > 0
    except OSError:
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--motore'); ap.add_argument('--modello'); ap.add_argument('--paralleli', type=int)
    ap.add_argument('--motore-revisione'); ap.add_argument('--modello-revisione')
    ap.add_argument('--revisione', choices=['completa', 'segnalate', 'nessuna'])
    ap.add_argument('--fino', type=int); ap.add_argument('--senza-build', action='store_true'); ap.add_argument('--dir')
    ap.add_argument('--sfondo', action='store_true'); ap.add_argument('--stato', action='store_true')
    o = ap.parse_args(); d = C.trova_dir(o.dir); cfg = C.progetto(d); log = Log(d)
    if o.stato:
        righe = open(log.p, encoding='utf-8').read().splitlines()[-8:] if os.path.exists(log.p) else []
        pid = os.path.join(d, 'auto.pid')
        attivo = os.path.exists(pid) and _vivo(int(open(pid).read() or 0))
        print('\n'.join(righe)); print(('IN CORSO · ' if attivo else 'FERMO · ') + L.riga_stato(d)); return
    if o.sfondo:
        pidf = os.path.join(d, 'auto.pid')
        if os.path.exists(pidf) and _vivo(int(open(pidf).read().strip() or 0)):
            sys.exit('auto.py è già in esecuzione su questa cartella: usa auto.py --stato.')
        argv = [a for a in sys.argv[1:] if a != '--sfondo'] + ['--dir', d]
        cmd = ([shutil.which('caffeinate'), '-i'] if shutil.which('caffeinate') else []) + [sys.executable, os.path.realpath(__file__)] + argv
        with open(os.path.join(d, 'auto.out'), 'a') as out:
            pr = subprocess.Popen(cmd, stdout=out, stderr=out, stdin=subprocess.DEVNULL, start_new_session=True, cwd=d)
        print(f'Avviato in background (pid {pr.pid}). Stato: auto.py --stato · registro: {log.p}'); return
    pidf = os.path.join(d, 'auto.pid')
    if os.path.exists(pidf):
        vecchio = int(open(pidf).read().strip() or 0)
        if vecchio != os.getpid() and _vivo(vecchio):
            sys.exit(f'ERRORE: auto.py è già in esecuzione su questa cartella (pid {vecchio}).')
    with open(pidf, 'w') as f:
        f.write(str(os.getpid()))
    for k, v in {'motore': o.motore, 'modello': o.modello, 'paralleli': o.paralleli, 'revisione': o.revisione,
                 'motore_revisione': o.motore_revisione, 'modello_revisione': o.modello_revisione}.items():
        if v:
            cfg[k] = v
    tot = C.n_parti(d); fino = min(o.fino or tot, tot)
    if not M.disponibile(cfg):
        sys.exit(f'ERRORE: motore «{cfg["motore"]}» non disponibile. Usa --motore oppure la modalità in chat (passo.py).')
    log(f'AVVIO {cfg.get("titolo", "")}: motore {cfg["motore"]} {cfg.get("modello", "")}, gruppi da {cfg["gruppo"]}, '
        f'{cfg["paralleli"]} in parallelo, revisione {cfg["revisione"]} · ' + L.riga_stato(d))
    if not fase_traduzione(d, cfg, fino, log):
        sys.exit(1)
    if fino < tot:
        log(f'Fermato alla parte {fino:04d} come richiesto.'); return
    if cfg['revisione'] != 'nessuna' and not M.disponibile(cfg, revisione=True):
        sys.exit(f'ERRORE: motore di revisione «{cfg["motore_revisione"]}» non disponibile.')
    fase_revisione(d, cfg, log)
    if o.senza_build:
        R.analizza(d, log); log('Traduzione e revisione completate (build saltata).'); return
    R.finale(d, log)


if __name__ == '__main__':
    main()
