"""What is running for you right now, in six layers.

The layers are not a taxonomy for its own sake. They are the six different
places a thing can be started from on this machine, and each one is owned by a
different piece of software, which is why nothing until now could list them
together:

  permanenti   launchd keeps them alive, they outlive every session
  pianificati  something will start them later, on a clock
  rada         admitted or waiting in the heavy job queue
  sessioni     a Claude Code session is alive and holding memory
  servizi      a server a session started and still owns
  orfani       a server whose session is gone and nobody will ever stop

faro reads each layer from the source of truth that owns it, and keeps no
state of its own beyond one optional cache. If faro is deleted, nothing about
the machine changes. That is the point: a control panel that becomes another
thing to supervise has failed before it starts.
"""

import json
import os
import re

from . import probe

HOME = probe.HOME
CLAUDE = os.path.join(HOME, ".claude")
FARO_HOME = os.path.join(HOME, ".faro")
RADA_HOME = os.path.join(HOME, ".rada")
SCHEDULED_CACHE = os.path.join(FARO_HOME, "pianificati.json")

CLAUDE_BIN = "claude.app/Contents/MacOS/claude"

# Things a Claude Code session starts and then forgets. Matched only on
# processes that launchd does not own and whose parent is already gone, so a
# false positive here still cannot touch a supervised service.
SESSION_SPAWNED = [
    (r"python[\d.]* -m http\.server", "server statico di anteprima"),
    (r"\bvite\b", "dev server vite"),
    (r"next (dev|start)", "dev server next"),
    (r"(npm|pnpm|yarn) run (dev|start|preview|serve)", "dev server node"),
    (r"\buvicorn\b|flask run", "dev server python"),
    (r"plancia-mcp", "server MCP di plancia"),
    (r"bridge-server\.js|agentbridge.*daemon\.js", "ponte agentbridge"),
    (r"codex app-server", "app-server di codex"),
    (r"mcp-server|@modelcontextprotocol", "server MCP"),
]

# Labels under these prefixes are not his. They are listed once, counted, and
# otherwise left alone: this is a panel for the things he built.
FOREIGN_PREFIXES = (
    "com.apple.", "com.google.", "com.microsoft.", "com.adobe.",
    "com.valvesoftware.", "com.riot.", "com.lwouis.", "com.docker.",
    "org.chromium.", "com.openai.chat", "application.",
)


def _human_bytes(n):
    if not n:
        return "0"
    for unit in ("B", "KB", "MB", "GB"):
        if abs(n) < 1024 or unit == "GB":
            return f"{n:.0f}{unit}" if unit == "B" else f"{n:.1f}{unit}"
        n /= 1024.0


def _human_age(seconds):
    if seconds is None:
        return "?"
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m"
    if seconds < 86400:
        return f"{seconds // 3600}h{(seconds % 3600) // 60:02d}"
    return f"{seconds // 86400}g{(seconds % 86400) // 3600:02d}h"


def _iso_ago(iso):
    """How long ago an iso timestamp was, in the same words as everything else."""
    try:
        import datetime
        t = datetime.datetime.fromisoformat(iso.replace("Z", "+00:00"))
        delta = probe.now() - t.timestamp()
        return f"{_human_age(delta)} fa" if delta >= 0 else f"tra {_human_age(-delta)}"
    except Exception:
        return iso


def _record(strato, ident, nome, **kw):
    r = {
        "strato": strato,
        "id": ident,
        "nome": nome,
        "stato": kw.get("stato", ""),
        "pid": kw.get("pid"),
        "rss": kw.get("rss", 0),
        "eta": kw.get("eta"),
        "quando": kw.get("quando", ""),
        "dove": kw.get("dove", ""),
        "dettaglio": kw.get("dettaglio", ""),
        "azione": kw.get("azione"),
        "allarme": kw.get("allarme", False),
    }
    return r


def _mine(agent):
    """A LaunchAgent is his if it runs something out of his own folders."""
    if agent["label"].startswith(FOREIGN_PREFIXES):
        return False
    joined = " ".join(agent.get("program") or [])
    return (HOME in joined) or agent["label"].startswith(("com.plancia", "dev.stiva", "it.nerln"))


def _schedule_text(agent):
    if agent.get("interval"):
        return f"ogni {agent['interval']}s"
    cal = agent.get("calendar")
    if cal:
        entries = cal if isinstance(cal, list) else [cal]
        times = []
        for e in entries:
            h = e.get("Hour")
            m = e.get("Minute", 0)
            if h is None:
                times.append(f"al minuto {m} di ogni ora")
            else:
                times.append(f"{h:02d}:{m:02d}")
        return "alle " + " e ".join(times)
    if agent.get("keep_alive"):
        return "sempre"
    if agent.get("run_at_load"):
        return "all'avvio"
    return "a richiesta"


# --------------------------------------------------------------- the layers

def permanenti(procs, loaded, agents, ports):
    """launchd jobs that are meant to be up right now."""
    out = []
    for a in agents:
        if not _mine(a):
            continue
        # A job with a clock belongs to `pianificati`, even when it also asks to
        # run at load. Listing it in both places is how a panel starts lying
        # about how many things are up.
        if a.get("calendar") or a.get("interval"):
            continue
        if not (a.get("keep_alive") or a.get("run_at_load")):
            continue
        info = loaded.get(a["label"], {})
        pid = info.get("pid")
        proc = procs.get(pid) if pid else None
        alive = proc is not None
        stato = "attivo" if alive else ("caricato ma fermo" if a["label"] in loaded else "non caricato")
        porte = ports.get(pid, []) if pid else []
        detail = " ".join(a["program"])[:110]
        if porte:
            detail = f"porta {', '.join(str(p) for p in porte)}  ·  " + detail
        last = probe.log_tail(a.get("stdout"), 1)
        out.append(_record(
            "permanenti", a["label"], a["label"],
            stato=stato,
            pid=pid,
            rss=proc["rss"] if proc else 0,
            eta=proc["age"] if proc else None,
            quando=_schedule_text(a),
            dove=a["path"],
            dettaglio=detail,
            azione=f"faro stop {a['label']}",
            allarme=not alive,
        ))
        # The log only earns a line when the service is not there. When it is
        # up, the last line is decoration and pushes the useful rows down.
        if last and not alive:
            out[-1]["ultima_riga"] = last[0][:110]
    return out


def _frontmatter(path):
    try:
        with open(path, "r", errors="ignore") as f:
            text = f.read(4000)
    except OSError:
        return {}
    m = re.match(r"^---\s*\n(.*?)\n---", text, re.S)
    if not m:
        return {}
    fields = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            fields[k.strip()] = v.strip()
    return fields


def pianificati(procs, loaded, agents):
    """launchd jobs that start later on a clock.

    The scheduled tasks of Claude Code are the other half of this layer and
    live in `pianificati_claude`. Keeping the disk read out of here is what
    lets this function be tested with a plist and nothing else.
    """
    out = []
    for a in agents:
        if not _mine(a) or not (a.get("calendar") or a.get("interval")):
            continue
        info = loaded.get(a["label"], {})
        quando = _schedule_text(a)
        detail = " ".join(a["program"])[:110]
        status = info.get("status")

        # Never date a scheduled job by the mtime of its log. Two jobs on this
        # machine write only when they act: `it.nerln.vesuvius-formwatch` has an
        # empty stderr from five days ago and had in fact run three hours
        # earlier, and `dev.stiva.ccd-percorsi` fires every minute and had a
        # log untouched for fourteen hours. Both looked broken and neither was.
        # launchd counts the runs; that is the number faro is allowed to show.
        d = probe.launchd_detail(a["label"]) if a["label"] in loaded else {}
        bits = []
        if d.get("runs") is not None:
            bits.append(f"{d['runs']} esecuzioni dal caricamento")
        exit_code = d.get("last_exit", status)
        if exit_code:
            bits.append(f"ULTIMA USCITA {exit_code}")
        elif exit_code == 0 and d:
            bits.append("ultima uscita 0")
        prefix = ("  ·  ".join(bits) + "  ·  ") if bits else ""

        out.append(_record(
            "pianificati", a["label"], a["label"],
            stato="in orario" if a["label"] in loaded else "non caricato",
            quando=quando,
            dove=a["path"],
            dettaglio=prefix + detail,
            azione=f"faro stop {a['label']}",
            allarme=bool(exit_code),
        ))
        out[-1]["esecuzioni"] = d.get("runs")
        # The log earns a line only when the job ended badly. That is the one
        # moment when its last line explains something.
        if exit_code:
            tail = probe.log_tail(a.get("stderr") or a.get("stdout"), 1)
            if tail:
                out[-1]["ultima_riga"] = tail[0][:110]
    return out


def pianificati_claude(root=None, cache_path=None):
    """The scheduled tasks of Claude Code.

    Only the prompt of a task is on disk. Its cron line lives inside the
    application, so faro cannot read it and does not pretend to: the schedule
    column says so until a session hands the list over with
    `faro pianifica --importa`.
    """
    out = []
    root = root or os.path.join(CLAUDE, "scheduled-tasks")
    cache_path = cache_path or SCHEDULED_CACHE

    cache = {}
    if os.path.exists(cache_path):
        try:
            with open(cache_path) as f:
                cache = {t["taskId"]: t for t in json.load(f)}
        except Exception:
            cache = {}

    if os.path.isdir(root):
        for name in sorted(os.listdir(root)):
            skill = os.path.join(root, name, "SKILL.md")
            if not os.path.exists(skill):
                continue
            fm = _frontmatter(skill)
            c = cache.get(name, {})
            enabled = c.get("enabled")
            quando = c.get("schedule") or "(orario noto solo all'app)"
            stato = "attivo" if enabled else ("disattivato" if enabled is False else "orario ignoto")
            prefix = ""
            if c.get("lastRunAt"):
                prefix = f"ultima {_iso_ago(c['lastRunAt'])}  ·  "
            out.append(_record(
                "pianificati", f"task:{name}", name,
                stato=stato,
                quando=quando if enabled is not False else "disattivato",
                dove=skill,
                dettaglio=prefix + (fm.get("description") or "")[:110],
                azione="disattivalo dall'app, oppure sposta la cartella",
                allarme=False,
            ))
            if c.get("lastRunAt"):
                out[-1]["ultima_esecuzione_iso"] = c["lastRunAt"]
            if c.get("nextRunAt"):
                out[-1]["prossima_iso"] = c["nextRunAt"]
    return out


def _chi_aspetta(pid, procs):
    """Chi sta aspettando un biglietto: nessuno, un orfano, o una sessione viva.

    Un biglietto in coda ha il pid del processo `rada run` che aspetta. Tre
    casi, e sono tre notizie diverse:

    - il processo non c'e' piu': il biglietto e' un fantasma, tiene un posto in
      coda per un lavoro che nessuno avviera' mai;
    - il processo c'e' ma il suo genitore e' morto: il lavoro partira' davvero
      quando ci sara' posto, ma la sessione che lo aveva chiesto non c'e' piu'
      e nessuno leggera' il risultato finche' non la si riapre;
    - il processo c'e' e ha un genitore vivo: qualcuno sta aspettando adesso.

    Misurato l'11/08/2026: il job MATS e8103a9f aspettava da tre ore con il
    wrapper vivo e la sessione morta, e da nessuna parte si poteva saperlo.
    """
    if not pid:
        return "senza processo che aspetta", True
    p = (procs or {}).get(pid)
    if p is None:
        return "fantasma: chi aspettava non c'e' piu'", True
    if p["ppid"] == 1:
        return "la sessione che lo ha chiesto e' morta, il lavoro no", True
    return "", False


def rada(procs=None):
    """The heavy job queue: what holds a permit, what waits, what the judge said."""
    out = []
    state_path = os.path.join(RADA_HOME, "state.json")
    if not os.path.exists(state_path):
        return out
    try:
        with open(state_path) as f:
            d = json.load(f)
    except Exception:
        return [_record("rada", "rada:stato", "coda rada",
                        stato="illeggibile", dettaglio=state_path, allarme=True)]

    now = probe.now()
    for tid, ls in sorted((d.get("leases") or {}).items(),
                          key=lambda kv: kv[1].get("start", 0)):
        out.append(_record(
            "rada", f"rada:{tid}", ls.get("show", "")[:70] or tid,
            stato="in esecuzione",
            eta=now - ls.get("start", now),
            rss=ls.get("peak") or ls.get("need") or 0,
            dove=ls.get("project", "?"),
            dettaglio=f"permesso {tid}",
            azione=f"rada status",
        ))
    order = list((d.get("judge") or {}).get("order") or [])
    tickets = d.get("tickets") or {}
    for tid in order + [t for t in tickets if t not in order]:
        tk = tickets.get(tid)
        if not tk:
            continue
        age = now - tk.get("enq", now)
        nota, sospetto = _chi_aspetta(tk.get("pid"), procs)
        dettaglio = f"biglietto {tid}"
        if nota:
            dettaglio = f"{nota}  ·  " + dettaglio
        if tk.get("intent"):
            dettaglio += "  ·  " + str(tk["intent"])[:60]
        out.append(_record(
            "rada", f"rada:{tid}", tk.get("show", "")[:70] or tid,
            stato="in coda",
            eta=age,
            rss=tk.get("need") or 0,
            dove=tk.get("project", "?"),
            dettaglio=dettaglio,
            azione=(f"faro spazio {_human_bytes(tk.get('need') or 0)}"
                    if tk.get("need") else f"rada force {tid}"),
            allarme=age > 600 or sospetto,
        ))

    pending = os.path.join(RADA_HOME, "pending")
    if os.path.isdir(pending):
        stale = [f for f in os.listdir(pending) if f.endswith(".cmd")]
        if stale:
            oldest = min(probe.mtime(os.path.join(pending, f)) or now for f in stale)
            out.append(_record(
                "rada", "rada:pending", f"{len(stale)} comandi in sospeso mai ritirati",
                stato="residuo",
                eta=now - oldest,
                dove=pending,
                dettaglio="file .cmd scritti dal gate e non consumati",
                azione="rada reset",
                allarme=(now - oldest) > 86400,
            ))
    return out


def _e_claude(command):
    """Questo processo e' una sessione di Claude Code?

    Non basta cercare il percorso dentro il bundle dell'applicazione. Una
    sessione avviata da un terminale gira come `/Users/x/.local/bin/claude`, e
    in `ps` compare come `claude --resume <id>` e basta.

    Difetto misurato la notte dell'11/08/2026, nel modo peggiore: dopo aver
    riaperto sette sessioni da iTerm2, faro continuava a dire "2 sessioni
    vive". Uno strumento nato per far vedere tutto quello che gira non puo'
    vedere solo quello che ha avviato l'applicazione.
    """
    if CLAUDE_BIN in command:
        return True
    pezzi = command.split()
    return bool(pezzi) and os.path.basename(pezzi[0]) == "claude"


def _live_sessions(procs):
    """Leaf claude processes: one per live session.

    The app starts a wrapper that starts claude, and both match the same path,
    so the one that matters is the claude with no claude child.
    """
    claudes = {p["pid"]: p for p in procs.values() if _e_claude(p["command"])}
    parents = {p["ppid"] for p in claudes.values()}
    return [p for pid, p in claudes.items() if pid not in parents]


SHELL = re.compile(r"^(/bin/|/usr/bin/)?(z|ba|k)?sh( |$)")

# A shell younger than this is almost always the tool call that is drawing this
# very board. Older than this and it is a command someone left running.
SHELL_MIN_AGE = 120


def sessioni(procs, cwd_map, ports, seen):
    """Live Claude Code sessions, with the servers each one is holding."""
    out = []
    for s in sorted(_live_sessions(procs), key=lambda p: -(p["age"] or 0)):
        kids = probe.children_of(procs, s["pid"])
        total = s["rss"] + sum(k["rss"] for k in kids)
        cwd = cwd_map.get(s["pid"], "?")
        name = os.path.basename(cwd.rstrip("/")) or cwd
        seen.add(s["pid"])
        out.append(_record(
            "sessioni", f"pid:{s['pid']}", f"{name} #{s['pid']}",
            stato="viva",
            pid=s["pid"],
            rss=total,
            eta=s["age"],
            dove=cwd,
            dettaglio=f"{len(kids)} figli, {_human_bytes(total)} in tutto  ·  {cwd}",
            azione=f"faro stop {s['pid']}",
            allarme=(s["age"] or 0) > 12 * 3600,
        ))
        for k in sorted(kids, key=lambda k: -k["rss"]):
            seen.add(k["pid"])
            is_shell = SHELL.match(k["command"])
            if is_shell and (k["age"] or 0) < SHELL_MIN_AGE:
                continue
            porte = ports.get(k["pid"], [])
            out.append(_record(
                "servizi", f"pid:{k['pid']}",
                "comando shell in corso" if is_shell else _describe(k["command"]),
                stato="in servizio",
                pid=k["pid"],
                rss=k["rss"],
                eta=k["age"],
                dove=f"figlio di {s['pid']}",
                dettaglio=(f"porta {', '.join(str(p) for p in porte)}  ·  " if porte else "")
                          + k["command"][:90],
                azione=f"faro stop {k['pid']}",
                # A shell a session started and never collected is how a
                # background command outlives the reason it was started for.
                allarme=bool(is_shell) and (k["age"] or 0) > 3600,
            ))
    return out


def sparsi(procs, loaded, ports, seen):
    """Servers that belong to nobody the board has named yet.

    The codex app server sits under the agentbridge daemon, which sits under
    neither launchd nor a session. Without this pass it would be running,
    holding a port, and appear nowhere. A panel with a blind spot is worse than
    no panel, because it is trusted.
    """
    supervised = {i.get("pid") for i in loaded.values() if i.get("pid")}
    out = []
    for p in procs.values():
        if p["pid"] in seen or p["pid"] in supervised or p["ppid"] == 1:
            continue
        # The desktop app supervises its own helpers and restarts them. Listing
        # them would fill the board with rows he can neither act on nor want.
        if p["command"].startswith("/Applications/"):
            continue
        label = None
        for pattern, name in SESSION_SPAWNED:
            if re.search(pattern, p["command"]):
                label = name
                break
        if not label:
            continue
        parent = procs.get(p["ppid"], {})
        porte = ports.get(p["pid"], [])
        out.append(_record(
            "servizi", f"pid:{p['pid']}", label,
            stato="in servizio",
            pid=p["pid"],
            rss=p["rss"],
            eta=p["age"],
            dove=f"figlio di {p['ppid']}",
            dettaglio=(f"porta {', '.join(str(x) for x in porte)}  ·  " if porte else "")
                      + f"sotto {_describe(parent.get('command', '?'))}  ·  "
                      + p["command"][:70],
            azione=f"faro stop {p['pid']}",
        ))
        seen.add(p["pid"])
    return out


def _describe(command):
    for pattern, label in SESSION_SPAWNED:
        if re.search(pattern, command):
            return label
    return command.split()[0].split("/")[-1]


# Un processo nato da poco non si puo' dichiarare abbandonato: la sessione che
# lo ha avviato sta quasi certamente per usarlo.
ETA_MINIMA_ORFANO = 600

# Se il transcript della sessione e' stato scritto da meno di questo, la
# sessione sta ancora lavorando.
SESSIONE_VIVA_SE_SCRITTA_DA = 900


def _sessione_ancora_viva(cwd, adesso=None):
    """La sessione che possiede questo scratchpad sta ancora scrivendo?

    Il percorso di uno scratchpad e'
    `/private/tmp/claude-501/<progetto>/<uuid>/scratchpad`, e lo stesso
    `<progetto>/<uuid>` nomina il transcript sotto `~/.claude/projects`. Se quel
    file e' stato toccato da poco, la sessione e' viva e quello che ha avviato
    e' un servizio, non un residuo.

    Serve perche' `ppid == 1` non prova affatto che la sessione sia morta: una
    shell che avvia un server esce subito, e il server viene riadottato da
    launchd mentre la sessione lo sta ancora usando.
    """
    m = re.search(r"claude-501/([^/]+)/([0-9a-f-]{36})", cwd or "")
    if not m:
        return None  # non si puo' dire
    progetto, sessione = m.group(1), m.group(2)
    transcript = os.path.join(CLAUDE, "projects", progetto, sessione + ".jsonl")
    t = probe.mtime(transcript)
    if t is None:
        return None
    adesso = adesso if adesso is not None else probe.now()
    return (adesso - t) < SESSIONE_VIVA_SE_SCRITTA_DA


def orfani(procs, loaded, cwd_map, ports, cartelle_vive=()):
    """Servers whose session died. Nobody is going to stop these.

    The test is deliberately narrow, because this is the only list faro will
    ever kill from:

      1. the parent is gone, so the process was reparented to launchd;
      2. launchd does not supervise it, checked against the pids it declares;
      3. either it sits in a session scratchpad, or it is one of the handful of
         servers a session is known to start;
      4. and the session that owns it is not still writing, and the process is
         not too young to judge.

    A supervised service always fails the second test, which is what keeps
    `faro reap` from ever touching plancia or stiva.

    The fourth test exists because the first one proves less than it looks
    like. A session that starts a server from a shell command loses the shell
    immediately, and the server is reparented to launchd while the session is
    alive and still using it. Whatever fails only the fourth test is not an
    orphan at all: it comes back as a service, with the reason written next to
    it.
    """
    supervised = {i.get("pid") for i in loaded.values() if i.get("pid")}
    out = []
    for p in procs.values():
        if p["ppid"] != 1 or p["pid"] in supervised:
            continue
        cwd = cwd_map.get(p["pid"], "")
        in_scratch = cwd.startswith(probe.SCRATCH_ROOT)
        label = None
        for pattern, name in SESSION_SPAWNED:
            if re.search(pattern, p["command"]):
                label = name
                break
        if not (in_scratch or label):
            continue

        # Quarta prova, aggiunta dopo la domanda giusta di Eugenio: orfano non
        # vuol dire malato. Un processo giovane appartiene a chi lo ha appena
        # avviato, e una sessione che sta ancora scrivendo il suo transcript
        # non e' morta. In entrambi i casi e' un servizio, e va detto cosi'.
        viva = _sessione_ancora_viva(cwd)
        giovane = (p["age"] or 0) < ETA_MINIMA_ORFANO
        # Il caso piu' ovvio, e quello che per poco non ha fatto uccidere un
        # server in uso: se una sessione viva sta lavorando in quella stessa
        # cartella, quel server e' suo. Vale quando il processo non sta in uno
        # scratchpad e quindi non porta scritto addosso a chi appartiene.
        in_uso = any(cwd == c or cwd.startswith(c.rstrip("/") + "/")
                     for c in cartelle_vive if c and c != "?")
        if viva or giovane or in_uso:
            porte = ports.get(p["pid"], [])
            motivo = ("una sessione viva lavora in questa cartella" if in_uso
                      else "la sessione sta ancora scrivendo" if viva
                      else f"avviato da {_human_age(p['age'])}, troppo presto per dirlo")
            out_servizio = _record(
                "servizi", f"pid:{p['pid']}", label or "processo di sessione",
                stato="in servizio",
                pid=p["pid"], rss=p["rss"], eta=p["age"],
                dove=cwd or "?",
                dettaglio=(f"porta {', '.join(str(x) for x in porte)}  ·  " if porte else "")
                          + motivo,
                azione=f"faro stop {p['pid']}",
            )
            out.append(out_servizio)
            continue

        porte = ports.get(p["pid"], [])
        session = ""
        m = re.search(r"claude-501/[^/]+/([0-9a-f-]{36})", cwd)
        if m:
            session = m.group(1)
        out.append(_record(
            "orfani", f"pid:{p['pid']}", label or "processo di sessione",
            stato="orfano",
            pid=p["pid"],
            rss=p["rss"],
            eta=p["age"],
            dove=cwd or "?",
            dettaglio=(f"porta {', '.join(str(x) for x in porte)}  ·  " if porte else "")
                      + p["command"][:90],
            azione=f"faro reap --esegui",
            allarme=True,
        ))
        if session:
            out[-1]["sessione"] = session
        if porte:
            out[-1]["porte"] = porte
    return sorted(out, key=lambda r: -(r["eta"] or 0))


# ------------------------------------------------------------------ assembly

def snapshot():
    """One reading of everything, with the raw probes shared across layers."""
    procs = probe.processes()
    loaded = probe.launchd_loaded()
    agents = probe.launch_agents()
    ports = probe.listening_ports()

    interesting = [p["pid"] for p in procs.values()
                   if p["ppid"] == 1 or _e_claude(p["command"])]
    interesting += [i["pid"] for i in loaded.values() if i.get("pid")]
    cwd_map = probe.cwds(sorted(set(interesting)))

    seen = set()
    rows = []
    rows += permanenti(procs, loaded, agents, ports)
    rows += pianificati(procs, loaded, agents)
    rows += pianificati_claude()
    rows += rada(procs)
    rows += sessioni(procs, cwd_map, ports, seen)
    rows += sparsi(procs, loaded, ports, seen)
    cartelle_vive = [cwd_map.get(s["pid"], "") for s in _live_sessions(procs)]
    rows += orfani(procs, loaded, cwd_map, ports, cartelle_vive)

    return {
        "ts": probe.now(),
        "memoria": probe.memory(),
        "righe": rows,
    }
