"""Dove sono andati i token, e chi li ha spesi.

La lamentela da cui nasce: "i miei token si perdono". Non si perdono, ma sono
spesi da cose diverse che nessuno somma insieme: le sessioni che apri tu, i
task pianificati che scattano da soli, e i subagenti che una sessione avvia e
di cui non vedi il conto.

## Le tre cose che rendono questo conto meno banale di quanto sembri

**Le voci sono duplicate.** Lo stesso `usage` compare piu' volte nel
transcript, per lo stesso messaggio. Sommare le righe raddoppia il conto. Si
deduplica sull'id del messaggio, e dove manca sull'uuid della riga.

**Il numero che conta e' l'output.** Input e cache dominano i totali di un
ordine di grandezza, ma sono in gran parte lettura di cache, che costa una
frazione. Qui si mostrano tutti e tre e si dice quale guardare, invece di
sommarli in un totale unico che non vuol dire niente.

**La cartella pesa 1,3 GB.** Si guardano solo i file toccati dentro la
finestra chiesta, e di ogni riga si fa il pre-controllo su una sottostringa
prima di provare a decodificare il json. Uno strumento che per dirti quanto hai
speso ti mangia mezzo minuto di macchina ha gia' perso.
"""

import json
import os
import time

from . import probe

CLAUDE = os.path.join(probe.HOME, ".claude")
PROGETTI = os.path.join(CLAUDE, "projects")


def _finestra(ore=None, giorni=None):
    """(inizio, etichetta). Senza argomenti: da mezzanotte."""
    now = time.time()
    if ore:
        return now - ore * 3600, f"ultime {ore} ore"
    if giorni:
        return now - giorni * 86400, f"ultimi {giorni} giorni"
    t = time.localtime(now)
    mezzanotte = time.mktime((t.tm_year, t.tm_mon, t.tm_mday, 0, 0, 0, 0, 0, -1))
    return mezzanotte, "da mezzanotte"


def _chi(path):
    """Chi ha speso: il progetto, e se e' un subagente o un task pianificato."""
    rel = os.path.relpath(path, PROGETTI)
    parti = rel.split(os.sep)
    progetto = parti[0] if parti else "?"
    if "subagents" in parti:
        genere = "subagenti"
    elif "workflows" in parti:
        genere = "workflow"
    else:
        genere = "sessioni"
    nome = progetto.replace("-Users-eugenionerelli-", "").replace("-", " ").strip()
    return nome[:44] or "?", genere


def raccogli(inizio, root=None):
    """Somma i token per (chi, genere), leggendo solo i file dentro la finestra."""
    root = root or PROGETTI
    conti = {}
    file_visti = 0
    for cartella, _, files in os.walk(root):
        for f in files:
            if not f.endswith(".jsonl"):
                continue
            p = os.path.join(cartella, f)
            try:
                if os.path.getmtime(p) < inizio:
                    continue
            except OSError:
                continue
            file_visti += 1
            chi, genere = _chi(p)
            c = conti.setdefault((chi, genere), {
                "chi": chi, "genere": genere, "out": 0, "in": 0,
                "cache_letta": 0, "cache_scritta": 0, "messaggi": 0,
                "modelli": set(), "ultimo": 0,
            })
            visti = set()
            try:
                fh = open(p, "r", errors="ignore")
            except OSError:
                continue
            with fh:
                for riga in fh:
                    # Pre-controllo a stringa: decodificare ogni riga di un
                    # transcript da 60 MB per trovarne cento e' il modo di
                    # rendere questo comando piu' caro di quello che misura.
                    if '"usage"' not in riga:
                        continue
                    try:
                        d = json.loads(riga)
                    except Exception:
                        continue
                    m = d.get("message") or {}
                    u = m.get("usage")
                    if not isinstance(u, dict):
                        continue
                    ident = m.get("id") or d.get("uuid")
                    if ident:
                        if ident in visti:
                            continue
                        visti.add(ident)
                    c["out"] += u.get("output_tokens") or 0
                    c["in"] += u.get("input_tokens") or 0
                    c["cache_letta"] += u.get("cache_read_input_tokens") or 0
                    c["cache_scritta"] += u.get("cache_creation_input_tokens") or 0
                    c["messaggi"] += 1
                    if m.get("model"):
                        c["modelli"].add(m["model"])
            try:
                c["ultimo"] = max(c["ultimo"], os.path.getmtime(p))
            except OSError:
                pass
    return conti, file_visti


def _mille(n):
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1000:
        return f"{n / 1000:.0f}k"
    return str(n)


def racconta(ore=None, giorni=None, root=None):
    inizio, etichetta = _finestra(ore, giorni)
    conti, file_visti = raccogli(inizio, root=root)
    if not conti:
        return f"nessun token speso {etichetta}."

    righe = [f"token {etichetta}   {file_visti} transcript toccati", ""]
    tot_out = sum(c["out"] for c in conti.values())
    tot_letta = sum(c["cache_letta"] for c in conti.values())
    tot_scritta = sum(c["cache_scritta"] for c in conti.values())
    righe.append(f"  in uscita {_mille(tot_out)}   "
                 f"cache letta {_mille(tot_letta)}   "
                 f"cache scritta {_mille(tot_scritta)}")
    righe.append("  quello che conta e' l'uscita: la cache letta costa una frazione.")
    righe.append("")

    per_genere = {}
    for c in conti.values():
        per_genere.setdefault(c["genere"], 0)
        per_genere[c["genere"]] += c["out"]
    righe.append("  " + "   ".join(
        f"{g}: {_mille(v)}" for g, v in sorted(per_genere.items(), key=lambda kv: -kv[1])))
    righe.append("")

    for c in sorted(conti.values(), key=lambda c: -c["out"]):
        if not c["out"]:
            continue
        modelli = ", ".join(sorted(m.split("-2")[0] for m in c["modelli"]))[:34]
        righe.append(f"  {_mille(c['out']):>7} out  {c['genere']:<10} {c['chi']:<44} "
                     f"{c['messaggi']:>5} msg  {modelli}")
    return "\n".join(righe)
