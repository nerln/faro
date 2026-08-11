"""Raw readings of the machine. Nothing here decides anything.

Every function returns what the operating system says, parsed and no more. The
rules about what counts as an orphan, or what belongs to Eugenio rather than to
Apple, live in inventory.py. Keeping the split means a wrong rule is a wrong
rule and not a wrong reading.

No third party packages. One subprocess call per kind of reading, never one per
process, because the board is meant to be cheap enough to run in a loop.
"""

import os
import plistlib
import re
import subprocess
import time

HOME = os.path.expanduser("~")
LAUNCH_AGENTS = os.path.join(HOME, "Library", "LaunchAgents")
SCRATCH_ROOT = "/private/tmp/claude-501"


def _run(cmd, timeout=5):
    """Run a command and return stdout, or "" if anything at all goes wrong.

    A probe that raises would take the whole board down with it. The board is
    supposed to be the thing that still works when the machine is unhappy.
    """
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return p.stdout
    except Exception:
        return ""


# ------------------------------------------------------------------ memory

def _sysctl(name):
    out = _run(["sysctl", "-n", name]).strip()
    return out


def memory():
    """Total, used, swap and a page-out counter, in bytes."""
    try:
        total = int(_sysctl("hw.memsize"))
    except ValueError:
        total = 0

    swap_total = swap_used = 0
    m = re.search(r"total = ([\d.]+)([MG]).*used = ([\d.]+)([MG])", _sysctl("vm.swapusage"))
    if m:
        mult = {"M": 1024 ** 2, "G": 1024 ** 3}
        swap_total = int(float(m.group(1)) * mult[m.group(2)])
        swap_used = int(float(m.group(3)) * mult[m.group(4)])

    free = pageouts = 0
    vm = _run(["vm_stat"])
    pagesize = 4096
    mp = re.search(r"page size of (\d+) bytes", vm)
    if mp:
        pagesize = int(mp.group(1))
    counts = dict(re.findall(r"^(.+?):\s+(\d+)\.$", vm, re.M))
    for key in ("Pages free", "Pages inactive", "Pages speculative"):
        free += int(counts.get(key, 0)) * pagesize
    pageouts = int(counts.get("Pageouts", 0))
    compressed = int(counts.get("Pages occupied by compressor", 0)) * pagesize

    # Il livello di pressione e il livello di jetsam sono le due cose che dicono
    # se la macchina sta soffrendo **adesso**, e si leggono senza tenere stato.
    # Servono perche' `swap_used` e' memoria *allocata*: macOS non restituisce i
    # file di swap quando la pressione cala, li tiene finche' decide lui o
    # finche' non si riavvia. Misurato l'11/08/2026: chiuse quattro sessioni, la
    # memoria usata e' scesa di 1 GB, i pageout si sono fermati, e lo swap e'
    # rimasto a 5,34 GB. Una plancia che grida "in swap" leggendo solo quel
    # numero grida per ore dopo che il problema e' finito, e allora non la si
    # guarda piu'.
    try:
        livello = int(_sysctl("kern.memorystatus_vm_pressure_level") or 1)
    except ValueError:
        livello = 1
    try:
        libero_pct = int(_sysctl("kern.memorystatus_level") or 100)
    except ValueError:
        libero_pct = 100

    return {
        "total": total,
        "free": free,
        "used": max(0, total - free),
        "compressed": compressed,
        "swap_total": swap_total,
        "swap_used": swap_used,
        "pageouts": pageouts,
        # 1 normale, 2 avviso, 4 critico: gli stessi valori delle bandiere di
        # memorypressure di dispatch.
        "pressione": livello,
        "libero_pct": libero_pct,
    }


# ----------------------------------------------------------------- processes

_ETIME = re.compile(r"^(?:(\d+)-)?(?:(\d+):)?(\d+):(\d+)$")


def _etime_seconds(s):
    m = _ETIME.match(s.strip())
    if not m:
        return None
    days, hours, mins, secs = m.groups()
    return (int(days or 0) * 86400 + int(hours or 0) * 3600
            + int(mins) * 60 + int(secs))


def processes():
    """Every process of this user, as a dict keyed by pid.

    rss is in bytes. age is in seconds and comes from etime, which counts wall
    clock since the process started and not cpu time.
    """
    out = _run(["ps", "-axo", "pid=,ppid=,rss=,etime=,command="], timeout=10)
    procs = {}
    for line in out.splitlines():
        parts = line.split(None, 4)
        if len(parts) < 5:
            continue
        pid, ppid, rss, etime, command = parts
        try:
            pid = int(pid)
            ppid = int(ppid)
            rss = int(rss) * 1024
        except ValueError:
            continue
        procs[pid] = {
            "pid": pid,
            "ppid": ppid,
            "rss": rss,
            "age": _etime_seconds(etime),
            "command": command,
        }
    return procs


def cwds(pids):
    """Working directory of each pid, in one lsof call.

    lsof is asked for a single descriptor and in field mode, which is the only
    shape of the call that stays fast when the machine has cloud mounts on it.
    """
    if not pids:
        return {}
    out = _run(["lsof", "-a", "-d", "cwd", "-Fn", "-p",
                ",".join(str(p) for p in pids)], timeout=10)
    result = {}
    current = None
    for line in out.splitlines():
        if line.startswith("p"):
            try:
                current = int(line[1:])
            except ValueError:
                current = None
        elif line.startswith("n") and current is not None:
            result.setdefault(current, line[1:])
    return result


def listening_ports():
    """Map pid to the list of tcp ports it listens on."""
    out = _run(["lsof", "-nP", "-iTCP", "-sTCP:LISTEN", "-Fpn"], timeout=10)
    result = {}
    current = None
    for line in out.splitlines():
        if line.startswith("p"):
            try:
                current = int(line[1:])
            except ValueError:
                current = None
        elif line.startswith("n") and current is not None:
            m = re.search(r":(\d+)$", line)
            if m:
                result.setdefault(current, [])
                port = int(m.group(1))
                if port not in result[current]:
                    result[current].append(port)
    return result


def children_of(procs, pid):
    return [p for p in procs.values() if p["ppid"] == pid]


# ------------------------------------------------------------------- launchd

def launchd_loaded():
    """Label to (pid, last exit status) for everything launchd holds."""
    out = _run(["launchctl", "list"])
    loaded = {}
    for line in out.splitlines()[1:]:
        parts = line.split("\t")
        if len(parts) != 3:
            continue
        pid, status, label = parts
        loaded[label.strip()] = {
            "pid": None if pid.strip() == "-" else int(pid),
            "status": int(status) if status.strip().lstrip("-").isdigit() else None,
        }
    return loaded


def launchd_detail(label, uid=None):
    """How many times launchd has run a job, and how it ended.

    `launchctl list` gives the last exit code and nothing else. `launchctl
    print` also gives `runs`, a counter since the job was loaded. Neither gives
    a timestamp, which is why faro must never claim to know when a scheduled
    job last ran: the only thing it can honestly say is how many times.

    One call per user job, five of them on this machine, not one per process.
    """
    uid = os.getuid() if uid is None else uid
    out = _run(["launchctl", "print", f"gui/{uid}/{label}"], timeout=5)
    if not out:
        return {}
    detail = {}
    m = re.search(r"^\s*runs = (\d+)", out, re.M)
    if m:
        detail["runs"] = int(m.group(1))
    m = re.search(r"^\s*last exit code = (\d+)", out, re.M)
    if m:
        detail["last_exit"] = int(m.group(1))
    m = re.search(r"^\s*state = (\S+)", out, re.M)
    if m:
        detail["state"] = m.group(1)
    return detail


def launch_agents():
    """Every user LaunchAgent plist, parsed.

    plistlib is in the standard library and reads both the xml and the binary
    form, so there is no need to shell out to plutil.
    """
    agents = []
    try:
        names = sorted(os.listdir(LAUNCH_AGENTS))
    except OSError:
        return agents
    for name in names:
        if not name.endswith(".plist"):
            continue
        path = os.path.join(LAUNCH_AGENTS, name)
        try:
            with open(path, "rb") as f:
                data = plistlib.load(f)
        except Exception:
            continue
        agents.append({
            "label": data.get("Label", name[:-6]),
            "path": path,
            "program": (data.get("ProgramArguments")
                        or ([data["Program"]] if data.get("Program") else [])),
            "run_at_load": bool(data.get("RunAtLoad")),
            "keep_alive": bool(data.get("KeepAlive")),
            "interval": data.get("StartInterval"),
            "calendar": data.get("StartCalendarInterval"),
            "stdout": data.get("StandardOutPath"),
            "stderr": data.get("StandardErrorPath"),
        })
    return agents


# ----------------------------------------------------------------- log files

def log_tail(path, lines=3, max_bytes=65536):
    """Last few lines of a log, read from the end.

    Some of these logs are large and grow all day. Reading the whole file to
    show three lines is how a status tool becomes the thing that slows the
    machine down.
    """
    if not path or not os.path.exists(path):
        return []
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as f:
            f.seek(max(0, size - max_bytes))
            data = f.read().decode("utf-8", "replace")
        return [l for l in data.splitlines() if l.strip()][-lines:]
    except Exception:
        return []


def mtime(path):
    try:
        return os.path.getmtime(path)
    except OSError:
        return None


def now():
    return time.time()
