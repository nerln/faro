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
     "the system", "untouchable", "the operating system"),
    (r"claude-code/[\d.]+/claude\.app", "Claude Code sessions", "recoverable",
     "nothing: the transcripts stay, and resume with claude --resume"),
    (r"^/Applications/Claude\.app", "Claude desktop app", "costly",
     "closes every Claude Code session, including the one you are reading this in"),
    (r"Google Chrome|Chromium", "Chrome", "cheap",
     "the tabs, which Chrome reopens by itself on restart"),
    (r"^/Applications/Safari|SafariServices", "Safari", "cheap",
     "the tabs, which Safari reopens by itself"),
    (r"Visual Studio Code|Code Helper", "VS Code", "costly",
     "unsaved work in the open editors"),
    (r"Docker|com\.docker", "Docker", "cheap", "the running containers"),
    (r"AppleSpell", "spell checker", "recoverable",
     "nothing: the system restarts it when it needs it"),
    (r"AdGuard", "AdGuard", "cheap", "ad blocking until it starts again"),
    (r"agentbridge|codex", "codex and the bridge", "recoverable",
     "the link to Codex, which is rebuilt"),
    (r"plancia", "plancia", "costly", "the control centre and its dashboard"),
]

ORDINE = {"recoverable": 0, "cheap": 1, "costly": 2, "untouchable": 9}


def _gruppo(comando):
    for rx, nome, categoria, perdita in GRUPPI:
        if re.search(rx, comando):
            return nome, categoria, perdita
    return "other", "cheap", "whatever it was doing"


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
        if g["categoria"] == "untouchable":
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
        f"needs {_human_bytes(serve)}   rada allows {_human_bytes(ora)} right now"
        f"   memory used {_human_bytes(mem['used'])} of {_human_bytes(mem['total'])}")
    if mem["swap_used"]:
        righe.append(f"   swap already in use: {_human_bytes(mem['swap_used'])}")
    righe.append("")

    if ora >= serve:
        righe.append("  it fits as it is. you do not have to close anything.")
        return "\n".join(righe)

    scelti, raggiunto, liberato = piano(serve, mem, procs)
    righe.append("  closing, in this order:")
    for g in scelti:
        righe.append(f"    {_human_bytes(g['rss']):>9}  {g['nome']:<28} "
                     f"({g['processi']} processes)")
        righe.append(f"    {'':>9}  you lose: {g['perdita']}")
    righe.append("")
    righe.append(f"  estimate of what would come back to the budget: {_human_bytes(liberato)}"
                 f"  ({int(RESA * 100)}% of RSS, deliberately low)")

    if raggiunto:
        righe.append("  with that, the job fits.")
    else:
        righe.append(ATTENZIONE_NON_ENTRA.format(
            serve=_human_bytes(serve),
            manca=_human_bytes(serve - ora - liberato)))
    return "\n".join(righe)


ATTENZIONE_NON_ENTRA = """  NOT ENOUGH. Even closing everything that can be closed leaves
  {manca} to find, and what is left is the operating system.

  A {serve} job on this machine wants the machine nearly empty. That is not a
  defect in rada: that is rada telling you. There are three real roads, and
  none of them is "force it and hope":
    - close everything and run it alone, with `rada force` on a quiet machine;
    - make it ask for less, if the figure was an estimate and not a measurement;
    - move it to a bigger machine."""
