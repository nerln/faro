"""Cosa vale la pena dire, e come dirlo una volta sola.

Il caso vero e' questo: una sessione si accorge che ci sono orfani, o che la
macchina e' andata in swap, e l'utente non sta guardando il terminale. Deve
poterlo sapere e decidere lui.

Due regole, e sono tutto il progetto di questo file:

1. **Se non c'e' niente da dire, si tace.** Una notifica che arriva sempre e'
   una notifica che si impara a ignorare, e da quel momento non serve piu' a
   niente nemmeno quando dice una cosa vera. Per questo `valuta()` puo'
   restituire una lista vuota, ed e' il caso normale.
2. **Dice, e basta.** Non uccide niente, non propone di farlo da solo, non
   apre niente. La decisione resta a chi legge.

`valuta()` sta qui e non nella GUI perche' il giudizio deve essere uno solo:
la fascia rossa che compare nella pagina e il testo della notifica di macOS
escono dalla stessa funzione, altrimenti un domani la pagina dice che va tutto
bene mentre la notifica dice il contrario.

Il testo che finisce nella notifica passa per argv di osascript e mai dentro il
sorgente AppleScript (CLAUDE.md, invariante 8): il nome di un processo o di un
job arriva da un plist o da una riga di comando, cioe' da dato che faro non
controlla, e concatenarlo in uno script sarebbe il modo piu' comodo di far
eseguire qualcosa a una macchina che stava soltanto guardando.
"""

import os
import re
import subprocess

from . import inventory
from .inventory import _human_age, _human_bytes

# Le stesse due soglie della plancia (board.py). 16 GB: il blocco che ha fatto
# nascere rada e' successo a 2992 MB di swap, quindi il numero in quella zona
# non e' una statistica, e' l'avviso.
SWAP_ALLARME = 2 * 1024 ** 3
SWAP_ATTENZIONE = 512 * 1024 ** 2

# Dove sta la lavagna condivisa, se e' installata. Se non c'e', non e' un
# errore: boa e' un vicino, non una dipendenza.
BOA = os.path.expanduser("~/dev/boa/bin/boa")

# Una notifica di macOS taglia da sola quello che non entra, ma il testo passa
# comunque per argv e viene da fonti che faro non controlla.
MAX_TESTO = 240


def _pulisci(testo):
    """Una riga sola, corta, senza caratteri di controllo.

    Serve perche' i nomi arrivano da plist e da righe di comando: dato, non
    istruzione. Passa per argv e non per il sorgente AppleScript, ma resta
    testo di cui non ci si fida.
    """
    testo = re.sub(r"[\x00-\x1f\x7f]+", " ", str(testo))
    testo = re.sub(r"\s+", " ", testo).strip()
    return testo[:MAX_TESTO]


def _notizia(chiave, gravita, titolo, testo):
    return {"chiave": chiave, "gravita": gravita,
            "titolo": _pulisci(titolo), "testo": _pulisci(testo)}


def _plurale(n, singolare, plurale):
    return singolare if n == 1 else plurale


def valuta(snap):
    """Le cose che meritano di essere dette adesso, in ordine di gravita'.

    `alta` merita una notifica. `media` merita una riga nella pagina e nient'
    altro: e' la fascia in cui una notifica sarebbe rumore.
    """
    righe = snap.get("righe", [])
    mem = snap.get("memoria", {})
    notizie = []

    orfani = [r for r in righe if r["strato"] == "orfani"]
    if orfani:
        rss = sum(r["rss"] for r in orfani)
        vecchio = max((r["eta"] or 0) for r in orfani)
        n = len(orfani)
        notizie.append(_notizia(
            "orfani", "alta",
            f"{n} {_plurale(n, 'processo orfano', 'processi orfani')}",
            f"{_plurale(n, 'tiene', 'tengono')} {_human_bytes(rss)}, "
            f"il piu' vecchio da {_human_age(vecchio)}. "
            f"`faro reap` mostra cosa verrebbe chiuso."))

    swap = mem.get("swap_used", 0)
    if swap > SWAP_ALLARME:
        vive = sum(1 for r in righe if r["strato"] == "sessioni")
        notizie.append(_notizia(
            "swap", "alta",
            f"la macchina e' in swap: {_human_bytes(swap)}",
            f"{mem.get('pageouts', 0)} pageout, {vive} "
            f"{_plurale(vive, 'sessione viva', 'sessioni vive')}. "
            f"chiudine una prima di avviare altro."))
    elif swap > SWAP_ATTENZIONE:
        notizie.append(_notizia(
            "swap", "media",
            f"swap in uso: {_human_bytes(swap)}",
            "ancora poco, ma da qui in genere sale."))

    for r in righe:
        if r["strato"] != "pianificati" or not r.get("allarme"):
            continue
        m = re.search(r"ULTIMA USCITA (\d+)", r.get("dettaglio", ""))
        codice = m.group(1) if m else "diverso da zero"
        notizie.append(_notizia(
            "pianificato:" + r["id"], "alta",
            f"{r['nome']} e' uscito male",
            f"ultima uscita {codice}. il job resta in orario e riprovera'."))

    for r in righe:
        # Un permanente e' per definizione una cosa che dovrebbe essere su
        # adesso. Che non lo sia e' esattamente il tipo di silenzio che questo
        # comando esiste per rompere.
        if r["strato"] == "permanenti" and r.get("allarme"):
            notizie.append(_notizia(
                "permanente:" + r["id"], "alta",
                f"{r['nome']} non e' in piedi",
                f"{r.get('stato') or 'fermo'}. launchd lo dichiara ma non c'e' un processo."))

    ordine = {"alta": 0, "media": 1}
    return sorted(notizie, key=lambda n: ordine.get(n["gravita"], 9))


def forti(notizie):
    """Solo quelle che valgono un'interruzione."""
    return [n for n in notizie if n["gravita"] == "alta"]


def riassunto(notizie, massimo=3):
    """Sottotitolo e corpo della notifica, da al massimo tre notizie.

    Una notifica per notizia sarebbe una pila di banner, cioe' di nuovo rumore.
    """
    scelte = notizie[:massimo]
    sottotitolo = ", ".join(n["titolo"] for n in scelte)
    corpo = " ".join(n["testo"] for n in scelte)
    resto = len(notizie) - len(scelte)
    if resto > 0:
        corpo += f" (e altre {resto} cose: `faro`)"
    return _pulisci(sottotitolo), _pulisci(corpo)


# ------------------------------------------------------------------ consegna

# Il testo non entra mai nel sorgente: lo script legge argv. Cambiare questo in
# una f-string significa dare a chi scrive una riga di comando la possibilita'
# di far eseguire AppleScript a questa macchina.
_SCRIPT = (
    "on run argv\n"
    "  display notification (item 3 of argv) "
    "with title (item 1 of argv) subtitle (item 2 of argv)\n"
    "end run"
)


def comando_notifica(titolo, sottotitolo, corpo):
    """La riga esatta che verrebbe eseguita. Separata per poterla provare."""
    return ["osascript", "-e", _SCRIPT, _pulisci(titolo),
            _pulisci(sottotitolo), _pulisci(corpo)]


def notifica(sottotitolo, corpo, titolo="faro", prova=False):
    cmd = comando_notifica(titolo, sottotitolo, corpo)
    if prova:
        return cmd
    try:
        subprocess.run(cmd, capture_output=True, timeout=10)
    except Exception:
        # Una notifica che non parte non deve far fallire il comando: quello
        # che aveva da dire lo dice comunque su stdout.
        pass
    return cmd


def scrivi_su_boa(testo, prova=False, chiave=None):
    """Una voce di tipo avviso sulla lavagna, se boa e' installato.

    Restituisce True se e' stata scritta. Se boa non c'e', non e' un errore e
    non si dice niente: faro legge i vicini dalla loro fonte e non pretende
    che esistano.
    """
    if not (os.path.exists(BOA) and os.access(BOA, os.X_OK)):
        return False
    cmd = [BOA, "scrivi", "--tipo", "avviso", _pulisci(testo)]
    if chiave:
        cmd += ["--una-volta", "--chiave", chiave]
    if prova:
        return cmd
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if p.returncode != 0:
            return False
        # Con una chiave, boa risponde a vuoto quando la voce c'era gia'. E'
        # cosi' che faro sa di essersi ripetuto senza tenersi uno stato suo:
        # l'invariante 2 dice che l'unico file che faro scrive e' la cache
        # degli orari, e questa memoria appartiene alla lavagna.
        return bool(p.stdout.strip()) if chiave else True
    except Exception:
        return False


def main(args):
    snap = inventory.snapshot()
    notizie = valuta(snap)
    urgenti = forti(notizie)
    prova = getattr(args, "prova", False)

    if not urgenti:
        # Il caso normale, ed e' il motivo per cui questa notifica si guarda:
        # tace.
        if prova:
            print("niente da dire.")
            for n in notizie:
                print(f"  (solo pagina) {n['titolo']}: {n['testo']}")
        return 0

    sottotitolo, corpo = riassunto(urgenti)

    # La chiave e' fatta dai tipi di notizia, non dai numeri. "swap alto piu'
    # orfani" resta la stessa notizia mentre i GB e i pageout cambiano a ogni
    # lettura, ed e' quello che serve perche' non venga ridetta ogni volta.
    chiave = "+".join(sorted({n["chiave"] for n in urgenti}))

    if prova:
        cmd = scrivi_su_boa(f"{sottotitolo}. {corpo}", prova=True, chiave=chiave)
        print("direi:")
        print("  titolo      faro")
        print(f"  sottotitolo {sottotitolo}")
        print(f"  corpo       {corpo}")
        print(f"  chiave      {chiave}")
        print(f"  su boa      {'si' if cmd else 'no, boa non risulta installato'}")
        return 0

    # Prima la lavagna, poi la notifica. L'ordine non e' casuale: e' boa che
    # sa se questa notizia e' gia' stata data, e se lo e' stata tace anche la
    # notifica. Senza, la notte dell'11/08/2026 lo SessionStart ha prodotto
    # dodici avvisi quasi identici in un'ora, consegnati poi a ogni sessione a
    # ogni prompt.
    nuova = True
    if not getattr(args, "senza_boa", False):
        nuova = scrivi_su_boa(f"{sottotitolo}. {corpo}", chiave=chiave)
        if nuova is False and _boa_c_e():
            return 0

    notifica(sottotitolo, corpo)
    print(f"{sottotitolo}. {corpo}")
    return 0


def _boa_c_e():
    return os.path.exists(BOA) and os.access(BOA, os.X_OK)
