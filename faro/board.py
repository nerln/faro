"""The one screen.

It has to fit in a terminal window without scrolling on a normal day, because
a panel you have to scroll is a panel you stop reading. Everything that is
merely fine gets one line. Everything wrong gets a line and a mark.
"""

import os
import re
import sys

from .inventory import _human_age, _human_bytes

ORDER = ["permanenti", "pianificati", "rada", "sessioni", "servizi", "orfani"]

TITLES = {
    "permanenti": "persistent        always up, session or no session",
    "pianificati": "scheduled         will start on their own, on a clock",
    "rada": "rada              the queue of heavy jobs",
    "sessioni": "sessions          Claude Code alive right now",
    "servizi": "services          started by a session, and still held by it",
    "orfani": "orphans           the session is gone, nobody will stop these",
}


def _tty():
    return sys.stdout.isatty() and os.environ.get("TERM") not in (None, "dumb")


class Ink:
    def __init__(self, on):
        self.on = on

    def __call__(self, text, code):
        return f"\033[{code}m{text}\033[0m" if self.on else text

    def dim(self, t):
        return self(t, "2")

    def bold(self, t):
        return self(t, "1")

    def red(self, t):
        return self(t, "31")

    def green(self, t):
        return self(t, "32")

    def yellow(self, t):
        return self(t, "33")

    def cyan(self, t):
        return self(t, "36")


def _mark(row, ink):
    if row["stato"] == "orphan":
        return ink.red("!")
    if row["allarme"]:
        return ink.yellow("!")
    if row["stato"] in ("up", "alive", "in service", "running",
                        "on schedule", "enabled"):
        return ink.green("*")
    return ink.dim("-")


def _memory_line(mem, ink):
    used = _human_bytes(mem["used"])
    total = _human_bytes(mem["total"])
    swap = mem["swap_used"]
    swap_txt = f"{_human_bytes(swap)} of {_human_bytes(mem['swap_total'])}"
    if swap > 1024 ** 3:
        swap_txt = ink.red(swap_txt)
    elif swap > 0:
        swap_txt = ink.yellow(swap_txt)
    return (f"memory {used} of {total}   compressed {_human_bytes(mem['compressed'])}"
            f"   swap {swap_txt}   pageouts {mem['pageouts']}")


def _collapse(group):
    """One line per kind of service instead of one per process.

    Five sessions mean ten identical rows, and ten identical rows are how the
    interesting eleventh stops being seen. The detail is one flag away.
    """
    by_kind = {}
    for r in group:
        k = by_kind.setdefault(r["nome"], {
            "nome": r["nome"], "n": 0, "rss": 0, "eta": 0,
            "porte": [], "allarme": False, "pid": None,
        })
        k["n"] += 1
        k["rss"] += r["rss"]
        k["eta"] = max(k["eta"], r["eta"] or 0)
        k["allarme"] = k["allarme"] or r["allarme"]
        k["pid"] = r["pid"]
        for m in re.finditer(r"port[a-z]* ([\d, ]+)", r.get("dettaglio", "")):
            for port in m.group(1).split(","):
                port = port.strip()
                if port and port not in k["porte"]:
                    k["porte"].append(port)
    out = []
    for k in sorted(by_kind.values(), key=lambda k: -k["rss"]):
        detail = f"{k['n']} instances" if k["n"] > 1 else f"pid {k['pid']}"
        if k["porte"]:
            detail += "  ·  ports " + ", ".join(k["porte"])
        out.append({
            "strato": "servizi", "id": "", "nome": k["nome"], "stato": "in service",
            "pid": k["pid"], "rss": k["rss"], "eta": k["eta"],
            "quando": f"x{k['n']}" if k["n"] > 1 else "in service",
            "dove": "", "dettaglio": detail, "azione": None, "allarme": k["allarme"],
        })
    return out


def strato_da_nome(parola):
    """La chiave interna di uno strato, dato il nome che la plancia stampa.

    Le chiavi sono dati e sono rimaste italiane; i nomi si leggono e sono
    inglesi. Chi scrive `--only orphans` sta digitando quello che vede, e
    aveva ragione: prima non funzionava, e il README lo prometteva.
    """
    parola = (parola or "").strip().lower()
    if parola in TITLES:
        return parola
    for chiave, titolo in TITLES.items():
        if titolo.partition("  ")[0].lower() == parola:
            return chiave
    return parola


def render(snap, only=None, larghezza=None, dettagli=False):
    only = [strato_da_nome(x) for x in only] if only else None
    ink = Ink(_tty())
    width = larghezza or (os.get_terminal_size().columns if _tty() else 100)
    rows = snap["righe"]
    lines = []

    counts = {k: sum(1 for r in rows if r["strato"] == k) for k in ORDER}
    # Le chiavi degli strati sono dati e restano quelle. Qui si legge, quindi
    # si usano i nomi di TITLES, che sono l'unica versione visibile che esista.
    head = "  ".join(f"{counts[k]} {TITLES[k].partition('  ')[0]}"
                     for k in ORDER if counts[k])
    orf = counts.get("orfani", 0)
    ram_orfana = sum(r["rss"] for r in rows if r["strato"] == "orfani")

    lines.append(ink.bold("faro") + "   " + _memory_line(snap["memoria"], ink))
    lines.append("       " + ink.dim(head))

    # 16 GB. The freeze that made rada exist happened at 2992 MB of swap, so a
    # number in that neighbourhood is not a statistic, it is the warning.
    mem = snap["memoria"]
    if mem["swap_used"] > 2 * 1024 ** 3:
        vive = counts.get("sessioni", 0)
        lines.append("       " + ink.red(
            f"the machine is in swap: {_human_bytes(mem['swap_used'])}, "
            f"{mem['pageouts']} pageouts, {vive} live sessions. "
            f"close one before starting anything else."))
    elif mem["swap_used"] > 512 * 1024 ** 2:
        lines.append("       " + ink.yellow(
            f"swap in use: {_human_bytes(mem['swap_used'])}. keep an eye on it."))

    if orf:
        lines.append("       " + ink.red(
            f"{orf} orphaned process{'es' if orf > 1 else ''} "
            f"{'are' if orf > 1 else 'is'} holding {_human_bytes(ram_orfana)}"
            f"   ->  faro reap"))
    lines.append("")

    for strato in ORDER:
        if only and strato not in only:
            continue
        group = [r for r in rows if r["strato"] == strato]
        if not group:
            continue
        if strato == "servizi" and not dettagli and len(group) > 6:
            group = _collapse(group)
        lines.append(ink.cyan(TITLES[strato]))
        for r in group:
            mark = _mark(r, ink)
            name = r["nome"][:34].ljust(34)
            age = (_human_age(r["eta"]) if r["eta"] else "").rjust(6)
            ram = (_human_bytes(r["rss"]) if r["rss"] else "").rjust(8)
            when = (r["quando"] or r["stato"])[:22].ljust(22)
            line = f"  {mark} {name} {age} {ram}  {when}"
            tail = r.get("dettaglio", "")
            room = max(0, width - len(_strip(line)) - 3)
            if tail and room > 12:
                line += "  " + ink.dim(tail[:room])
            lines.append(line)
            extra = r.get("ultima_riga")
            if extra:
                lines.append("      " + ink.dim("last log line: " + extra[:width - 20]))
        lines.append("")

    if not any(r["strato"] == "orfani" for r in rows):
        lines.append(ink.dim("  no orphans. nothing to reclaim."))
    return "\n".join(lines)


def _strip(s):
    out = []
    skip = False
    for ch in s:
        if ch == "\033":
            skip = True
        elif skip and ch == "m":
            skip = False
        elif not skip:
            out.append(ch)
    return "".join(out)
