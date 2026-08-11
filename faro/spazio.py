"""Cosa devo chiudere perche' un lavoro da N GB entri.

Nata la notte dell'11/08/2026 da una domanda a cui nessuno dei tre strumenti
sapeva rispondere. rada teneva in coda da tre ore un lavoro che chiedeva 5 GB,
faro diceva che la macchina era a 12,9 GB su 16, e da nessuna parte si poteva
sapere la cosa che serviva davvero: **quali finestre chiudere per farlo
entrare, e se esiste una risposta.**

Questo modulo non chiude niente. Conta, ordina, e dice anche quando la risposta
e' che non si puo'.

## Perche' i numeri non tornano mai del tutto

Il conto della memoria che fa rada e' `usata = wired + compressa + anonima`, e
il suo bilancio e' `TOTALE - riserva - usata`, con la riserva a 2,4 GB su una
macchina da 16. Il conto che si puo' fare guardando i processi e' invece la
somma degli RSS, che non e' la stessa cosa: le pagine condivise fra processi
vengono contate piu' volte, e le pagine compresse valgono meno di quanto
pesano.

Chiudere un'applicazione da 1 GB di RSS quindi **non** restituisce 1 GB al
bilancio di rada. Restituisce qualcosa fra la meta' e tutto. Qui si dichiara
la stima e si dice che e' una stima, invece di promettere un numero preciso e
sbagliato.
"""

import os
import re

from . import probe
from .inventory import _human_bytes

# La formula di rada, ripetuta qui perche' e' l'unico modo di parlare la sua
# lingua senza importarlo. Se rada la cambia, questa va cambiata: sta scritto
# anche in CLAUDE.md.
RISERVA_FRAZIONE = 0.15
RISERVA_MINIMA = 1536 * 1024 ** 2

# Quanto di un RSS torna davvero al bilancio quando l'applicazione si chiude.
# Prudente di proposito: meglio dire che serve chiudere una cosa in piu' che
# promettere che basta e lasciarlo con il lavoro ancora in coda.
RESA = 0.7

GRUPPI = [
    # (regex sul comando, nome, categoria, cosa si perde)
    (r"^/System/|^/usr/libexec|^/usr/sbin|kernel_task|WindowServer|loginwindow",
     "sistema", "intoccabile", "il sistema operativo"),
    (r"claude-code/[\d.]+/claude\.app", "sessioni di Claude Code", "recuperabile",
     "niente: i transcript restano e si riprendono con claude --resume"),
    (r"^/Applications/Claude\.app", "app Claude desktop", "caro",
     "chiude tutte le sessioni di Claude Code, compresa quella da cui stai leggendo"),
    (r"Google Chrome|Chromium", "Chrome", "poco",
     "le schede, che Chrome riapre da solo al riavvio"),
    (r"^/Applications/Safari|SafariServices", "Safari", "poco",
     "le schede, che Safari riapre da solo"),
    (r"Visual Studio Code|Code Helper", "VS Code", "caro",
     "il lavoro non salvato negli editor aperti"),
    (r"Docker|com\.docker", "Docker", "poco", "i contenitori in esecuzione"),
    (r"AppleSpell", "correttore ortografico", "recuperabile",
     "niente: il sistema lo riavvia da solo quando serve"),
    (r"AdGuard", "AdGuard", "poco", "il blocco della pubblicita' finche' non riparte"),
    (r"agentbridge|codex", "codex e il ponte", "recuperabile",
     "il collegamento con Codex, che si rifa'"),
    (r"plancia", "plancia", "caro", "il centro di controllo e la sua dashboard"),
]

ORDINE = {"recuperabile": 0, "poco": 1, "caro": 2, "intoccabile": 9}


def _gruppo(comando):
    for rx, nome, categoria, perdita in GRUPPI:
        if re.search(rx, comando):
            return nome, categoria, perdita
    return "altro", "poco", "quello che stava facendo"


def raggruppa(procs):
    """RSS per applicazione, con la categoria e cosa costa chiuderla."""
    tot = {}
    for p in procs.values():
        nome, categoria, perdita = _gruppo(p["command"])
        g = tot.setdefault(nome, {"nome": nome, "categoria": categoria,
                                  "perdita": perdita, "rss": 0, "processi": 0})
        g["rss"] += p["rss"]
        g["processi"] += 1
    return sorted(tot.values(),
                  key=lambda g: (ORDINE.get(g["categoria"], 5), -g["rss"]))


def bilancio(mem, usata=None):
    """Il bilancio che rada concederebbe con questa memoria usata."""
    totale = mem["total"]
    usata = mem["used"] if usata is None else usata
    riserva = max(int(totale * RISERVA_FRAZIONE), RISERVA_MINIMA)
    return max(0, totale - riserva - usata)


def piano(serve, mem, procs):
    """Cosa chiudere, in ordine di quanto costa, per arrivare a `serve` byte.

    Restituisce (righe, raggiunto, stima_liberata).
    """
    gruppi = raggruppa(procs)
    ora = bilancio(mem)
    if ora >= serve:
        return [], True, 0

    manca = serve - ora
    # Quanta memoria usata bisogna togliere: il bilancio cresce di uno per ogni
    # byte di usata che sparisce.
    scelti, liberato = [], 0
    for g in gruppi:
        if g["categoria"] == "intoccabile":
            continue
        if liberato >= manca:
            break
        resa = int(g["rss"] * RESA)
        if resa <= 0:
            continue
        scelti.append(g)
        liberato += resa
    return scelti, liberato >= manca, liberato


def racconta(serve, mem=None, procs=None):
    """Il testo che vede l'utente."""
    mem = mem or probe.memory()
    procs = procs or probe.processes()
    ora = bilancio(mem)
    righe = []

    righe.append(
        f"serve {_human_bytes(serve)}   rada adesso ne concede {_human_bytes(ora)}"
        f"   memoria usata {_human_bytes(mem['used'])} di {_human_bytes(mem['total'])}")
    if mem["swap_used"]:
        righe.append(f"   swap gia' in uso: {_human_bytes(mem['swap_used'])}")
    righe.append("")

    if ora >= serve:
        righe.append("  entra cosi' com'e'. non devi chiudere niente.")
        return "\n".join(righe)

    scelti, raggiunto, liberato = piano(serve, mem, procs)
    righe.append("  chiudendo, in quest'ordine:")
    for g in scelti:
        righe.append(f"    {_human_bytes(g['rss']):>9}  {g['nome']:<28} "
                     f"({g['processi']} processi)")
        righe.append(f"    {'':>9}  perdi: {g['perdita']}")
    righe.append("")
    righe.append(f"  stima di quanto tornerebbe al bilancio: {_human_bytes(liberato)}"
                 f"  ({int(RESA * 100)}% dell'RSS, prudente)")

    if raggiunto:
        righe.append("  con questo il lavoro entra.")
    else:
        righe.append(ATTENZIONE_NON_ENTRA.format(
            serve=_human_bytes(serve),
            manca=_human_bytes(serve - ora - liberato)))
    return "\n".join(righe)


ATTENZIONE_NON_ENTRA = """  NON BASTA. Anche chiudendo tutto quello che si puo' chiudere restano
  {manca} da trovare, e quello che resta e' il sistema operativo.

  Un lavoro da {serve} su questa macchina vuole la macchina quasi vuota. Non e'
  un difetto di rada: e' rada che te lo sta dicendo. Le strade vere sono tre, e
  nessuna e' "forzalo e speriamo":
    - chiudere tutto e lanciarlo da solo, con `rada force` a macchina ferma;
    - farlo chiedere meno, se la richiesta era una stima e non una misura;
    - portarlo su una macchina piu' grande."""
