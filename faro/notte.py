"""`faro notte`: quello che si fa prima di chiudere il portatile.

Nato da un errore, e vale la pena scrivere quale.

La notte dell'11/08/2026 Eugenio e' andato a dormire lasciando un lavoro fermo
in coda, e ha chiesto di riprendere le sessioni che rada aveva rallentato. Sono
state riaperte sette sessioni in sette finestre di iTerm2, alle tre di notte.
Tecnicamente era quello che aveva chiesto. Al risveglio si e' trovato sette
terminali aperti, non capiva quali fossero partiti da soli, e le sessioni
riaperte avevano compattato il contesto, quindi non erano piu' nello stato in
cui le aveva lasciate.

Il difetto non era in nessuno dei comandi. Era che **non esisteva un modo di
dire alla macchina "vado a letto"**, e quindi l'unica forma che poteva prendere
quella richiesta era che qualcuno agisse al posto suo, di notte, su cose che al
risveglio avrebbe dovuto ricostruire.

Questo comando e' quel modo. Fa tre cose e nessuna di piu':

  1. **toglie**: gli orfani, e le sessioni che non stanno facendo niente;
  2. **sblocca**: guarda i lavori fermi in coda e dice se dopo la pulizia
     entrano, cosi' rada li ammette da solo mentre lui dorme;
  3. **scrive**: un rapporto che al risveglio si legge in trenta secondi.

E soprattutto: **non apre mai niente.** E' l'invariante che questo file
esiste per far rispettare. Aprire una sessione per conto di qualcuno che dorme
sposta il lavoro dalla notte al risveglio invece di toglierlo.
"""

import json
import os
import time

from . import inventory, probe, spazio
from .inventory import _human_age, _human_bytes

FARO_HOME = inventory.FARO_HOME

# Una sessione senza cpu per questo tempo, e senza una shell in corso, non sta
# facendo niente: e' una finestra aperta. Il campionamento e' corto perche' una
# sessione che lavora usa cpu di continuo.
CAMPIONE = 12


def _cpu(procs_a, procs_b, pid):
    return procs_b.get(pid, {}).get("cpu", 0) - procs_a.get(pid, {}).get("cpu", 0)


def _con_cpu():
    """La tabella dei processi con il tempo di cpu, due volte a distanza."""
    def leggi():
        out = probe._run(["ps", "-axo", "pid=,ppid=,rss=,time=,command="], timeout=10)
        d = {}
        for l in out.splitlines():
            p = l.split(None, 4)
            if len(p) < 5:
                continue
            try:
                pid, ppid, rss = int(p[0]), int(p[1]), int(p[2]) * 1024
            except ValueError:
                continue
            sec = 0
            try:
                q = p[3].replace(".", ":").split(":")
                sec = int(q[0]) * 60 + int(q[1])
            except Exception:
                pass
            d[pid] = {"pid": pid, "ppid": ppid, "rss": rss, "cpu": sec, "command": p[4]}
        return d
    a = leggi()
    time.sleep(CAMPIONE)
    return a, leggi()


def _catena_mia(procs):
    """Io e tutti i miei antenati. Non si tocca nessuno di loro."""
    chain, pid = set(), os.getpid()
    for _ in range(40):
        chain.add(pid)
        p = procs.get(pid)
        if not p or p["ppid"] in (0, 1):
            break
        pid = p["ppid"]
    chain.add(pid)
    return chain


def sessioni_ferme():
    """Le sessioni vive che non stanno facendo niente, con quanto tengono.

    Tre condizioni, e servono tutte:
      - nessun tempo di cpu consumato nella finestra di campionamento;
      - nessuna shell fra i figli, perche' una shell e' un comando in corso;
      - non e' la sessione da cui questo comando e' stato scritto.
    """
    a, b = _con_cpu()
    mia = _catena_mia(b)
    claudes = {p["pid"]: p for p in b.values() if inventory._e_claude(p["command"])}
    genitori = {p["ppid"] for p in claudes.values()}
    ferme = []
    for pid, p in claudes.items():
        if pid in genitori or pid in mia:
            continue
        if _cpu(a, b, pid) > 0:
            continue
        figli = [c for c in b.values() if c["ppid"] == pid]
        if any(inventory.SHELL.match(c["command"]) for c in figli):
            continue
        ferme.append({"pid": pid, "rss": p["rss"] + sum(c["rss"] for c in figli)})
    return sorted(ferme, key=lambda s: -s["rss"])


def bloccati(snap):
    """I lavori fermi in coda, con quanto chiedono."""
    return [r for r in snap["righe"]
            if r["strato"] == "rada" and r["stato"] == "in coda"]


def piano(snap=None):
    """Cosa farebbe `faro notte`, senza farlo."""
    snap = snap or inventory.snapshot()
    orfani = [r for r in snap["righe"] if r["strato"] == "orfani"]
    ferme = sessioni_ferme()
    coda = bloccati(snap)
    mem = snap["memoria"]
    libera = sum(r["rss"] for r in orfani) + sum(s["rss"] for s in ferme)
    dopo = max(0, mem["used"] - int(libera * spazio.RESA))
    return {
        "orfani": orfani,
        "ferme": ferme,
        "coda": coda,
        "memoria": mem,
        "libera": libera,
        "bilancio_ora": spazio.bilancio(mem),
        "bilancio_dopo": spazio.bilancio(mem, usata=dopo),
    }


def racconta(p):
    r = []
    m = p["memoria"]
    r.append(f"memoria {_human_bytes(m['used'])} di {_human_bytes(m['total'])}"
             f"   swap {_human_bytes(m['swap_used'])}"
             f"   rada concede {_human_bytes(p['bilancio_ora'])}")
    r.append("")

    if p["orfani"]:
        r.append(f"  chiudo {len(p['orfani'])} orfani "
                 f"({_human_bytes(sum(x['rss'] for x in p['orfani']))})")
        for x in p["orfani"]:
            r.append(f"    pid {x['pid']}  {x['nome']}  da {_human_age(x['eta'])}")
    else:
        r.append("  nessun orfano.")

    if p["ferme"]:
        r.append(f"  chiudo {len(p['ferme'])} sessioni ferme "
                 f"({_human_bytes(sum(x['rss'] for x in p['ferme']))})")
        r.append("    i transcript restano: si riaprono con claude --resume")
    else:
        r.append("  nessuna sessione ferma.")

    r.append("")
    r.append(f"  dopo, rada concederebbe {_human_bytes(p['bilancio_dopo'])}"
             f" invece di {_human_bytes(p['bilancio_ora'])}")

    if p["coda"]:
        r.append("")
        r.append("  lavori fermi in coda:")
        for c in p["coda"]:
            serve = c["rss"]
            entra = "ENTRA" if serve and serve <= p["bilancio_dopo"] else "non entra ancora"
            r.append(f"    {_human_bytes(serve):>8}  {entra:<16} {c['nome'][:52]}")
            if entra != "ENTRA" and serve:
                manca = serve - p["bilancio_dopo"]
                r.append(f"    {'':>8}  mancano {_human_bytes(manca)}: "
                         f"`faro spazio {_human_bytes(serve)}` dice cosa chiudere")
    else:
        r.append("")
        r.append("  niente in coda.")

    r.append("")
    r.append("  non apro niente. mai. e' l'invariante di questo comando.")
    return "\n".join(r)


def rapporto(p, chiusi_orfani, chiuse_sessioni):
    """Il file che si legge al risveglio."""
    os.makedirs(FARO_HOME, exist_ok=True)
    quando = time.strftime("%Y-%m-%d-%H%M")
    path = os.path.join(FARO_HOME, f"notte-{quando}.md")
    m = p["memoria"]
    testo = [
        f"# La notte del {time.strftime('%d/%m/%Y alle %H:%M')}",
        "",
        f"- memoria alla chiusura: {_human_bytes(m['used'])} di {_human_bytes(m['total'])}, "
        f"swap {_human_bytes(m['swap_used'])}",
        f"- orfani chiusi: {chiusi_orfani}",
        f"- sessioni ferme chiuse: {chiuse_sessioni} "
        f"(i transcript restano, si riaprono con `claude --resume`)",
        f"- bilancio di rada dopo la pulizia: {_human_bytes(p['bilancio_dopo'])}",
        "",
    ]
    if p["coda"]:
        testo.append("## Lavori che erano in coda")
        testo.append("")
        for c in p["coda"]:
            entra = "dovrebbe essere partito" if c["rss"] <= p["bilancio_dopo"] else \
                    "non entrava nemmeno dopo la pulizia"
            testo.append(f"- {_human_bytes(c['rss'])}  {c['nome'][:60]}  ({entra})")
        testo.append("")
    testo.append("## Cosa non e' stato fatto, di proposito")
    testo.append("")
    testo.append("- non e' stata aperta nessuna sessione, e non lo sara' mai:")
    testo.append("  aprire finestre per conto di chi dorme sposta il lavoro al risveglio.")
    testo.append("- niente e' stato forzato in coda: se un lavoro non entrava,")
    testo.append("  `faro spazio <quanto>` dice cosa chiudere per farlo entrare.")
    with open(path, "w") as f:
        f.write("\n".join(testo) + "\n")
    return path


def ultimo_rapporto():
    try:
        files = sorted(f for f in os.listdir(FARO_HOME) if f.startswith("notte-"))
    except OSError:
        return None
    if not files:
        return None
    return os.path.join(FARO_HOME, files[-1])
