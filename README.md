# faro

One board for everything running in the background on your Mac on your behalf.

[Italiano](README.it.md)

```
faro
```

Python 3 and the standard library. No dependencies, no installer, no daemon.

## Why this exists

Six different kinds of thing can start on a laptop, and each of them is visible from
somewhere else:

- **launchd** keeps `com.plancia.server` up and restarts `dev.stiva.ccd-percorsi` every
  minute;
- **the scheduled tasks of Claude Code** fire on their own and spend tokens, on a clock
  that lives inside the application;
- **rada** holds a queue of heavy jobs, with tickets and permissions;
- **the live Claude Code sessions**, each with its own memory;
- **the servers a session starts**: a preview server, an MCP server, a bridge to another
  agent;
- **the orphans**: a preview server started by a session that was closed at three in the
  morning, holding a port, which nobody is ever going to stop.

Every one of those is visible somewhere, with a different command and in a different
format. Together they are visible nowhere. That is how the machine ends up in swap with
nobody able to say who is eating it.

The first time faro ran, on 10 August 2026, it found three orphaned `python3 -m
http.server` on three different ports, the oldest of them twenty hours old, on a machine
that was holding 3.4 GB of its 5 GB of swap with five live sessions.

Nothing in that story is a bug. Sessions are isolated by design, launchd is doing its
job, and a shell that exits leaves its children to be reparented, which is exactly what
POSIX says should happen. It only means that on one machine, nobody is counting.

## What it shows

Six layers on one screen, with the memory first, because the memory is the reason you
came:

```
faro   memoria 10.8GB di 16.0GB   compressa 2.3GB   swap 3.4GB di 5.0GB   pageout 110300
       1 permanenti  7 pianificati  1 rada  5 sessioni  14 servizi  3 orfani
       la macchina e' in swap: 3.4GB, 110300 pageout, 5 sessioni vive.
       3 processi orfani tengono 10.8MB   ->  faro reap
```

| layer | what is in it |
|---|---|
| `permanenti` | always up, session or no session |
| `pianificati` | will start on their own, on a clock |
| `rada` | the queue of heavy jobs |
| `sessioni` | Claude Code alive right now |
| `servizi` | started by a session, and still held by it |
| `orfani` | the session is gone, nobody will stop these |

Anything that is merely fine gets one line. Anything wrong gets a line and a mark. The
screen has to fit in a terminal window without scrolling on a normal day, because a panel
you have to scroll is a panel you stop reading.

Each layer is read from the source that owns it: launchd from `launchctl` and the plists,
rada from `~/.rada/state.json`, the tasks from `~/.claude/scheduled-tasks`. faro
duplicates none of those truths and synchronises with nobody. If rada changes format,
faro shows one unreadable row and the rest of the board carries on.

## Commands

```bash
faro                      # the board
faro --dettagli           # one process per row instead of one kind per row
faro vivo                 # the same, refreshed every 5 seconds
faro --solo orfani,rada   # only some layers
faro orfani               # only what nobody is going to stop
faro reap                 # what would be closed. closes nothing
faro reap --esegui        # closes them
faro stop <label>         # stop a launchd job
faro stop <pid>           # stop a process
faro gui                  # the same board in the browser, in the foreground
faro annuncia             # says something only if there is something to say
faro spazio 5G            # what to close so a 5G job fits, and whether it can
faro token                # where the tokens went today, and who spent them
faro notte                # going to bed: clears blocks, opens nothing
faro mattina              # what happened while you slept
faro json                 # everything, for another program
```

## What to close so a job fits

`rada` queues a heavy job until there is room. What neither tool could say was the
thing you actually need at that moment: **which windows to close so it fits, and
whether an answer exists at all.**

```
$ faro spazio 5G
serve 5.0GB   rada adesso ne concede 3.5GB   memoria usata 10.1GB di 16.0GB
   swap gia' in uso: 4.3GB

  chiudendo, in quest'ordine:
        1.4GB  sessioni di Claude Code      (12 processi)
               perdi: niente: i transcript restano e si riprendono con claude --resume
      492.3MB  Chrome
               perdi: le schede, che Chrome riapre da solo al riavvio
```

Candidates come ranked by what closing them costs you, not by size: sessions whose
transcripts survive come before a browser that reopens its tabs, and that comes before
an editor that may hold unsaved work. The system itself is never a candidate.

The estimate is stated as an estimate. Closing an application holding 1 GB of RSS does
not hand rada back 1 GB: shared pages are counted more than once and compressed pages
weigh less than they measure. When closing everything closable still is not enough,
`faro spazio` says so, rather than suggesting you force it.

## Where the tokens went

```
$ faro token
token da mezzanotte   43 transcript toccati

  in uscita 3.5M   cache letta 1086.8M   cache scritta 31.2M
  quello che conta e' l'uscita: la cache letta costa una frazione.

  sessioni: 3.4M   subagenti: 63k
```

Three things make this less trivial than it looks. The same `usage` block appears more
than once per message in a transcript, so summing rows doubles the bill: entries are
deduplicated on the message id. The number that matters is output, not the total, since
cache reads dominate by an order of magnitude and cost a fraction. And the transcript
directory holds 1.3 GB, so only files touched inside the window are opened, with a
substring check before any JSON parsing. It answers in about a third of a second.

## What it does not do

- **It keeps no daemon.** There is nothing of faro running while you are not looking. A
  control panel that becomes one more thing to watch has already failed.
- **It keeps no state.** The only file it writes is `~/.faro/pianificati.json`, the cache
  of the schedules the Claude Code application does not put on disk. Deleting `~/.faro`
  changes nothing about how the machine behaves.
- **It kills nothing on its own.** `reap` without `--esegui` is a dry run. No timer, no
  automatic cleanup, nothing that acts while you sleep.
- **It never runs what it reads.** The command lines on the board are truncated text.
  They do not go through a shell, they are not executed, and they do not go into a model.

## What `faro reap` will close

Only processes that pass all four of these tests:

1. **the parent is gone**, so the process has been reparented to launchd (`ppid == 1`);
2. **launchd does not supervise it**, checked against the pids launchd itself declares;
3. **it sits in a session scratchpad, or it is one of the handful of servers a session is
   known to start** (`http.server`, `vite`, `npm run dev`, and a short list of named
   ones);
4. **and nobody is using it**: it is older than ten minutes, the session that owns its
   scratchpad has stopped writing its transcript, and no live session is working in that
   directory.

The second test is the one that keeps `reap` away from supervised services: a job launchd
keeps alive fails it always, which matters because killing such a job does not stop it, it
restarts it. Every test has a test that removes it and checks that the process stops being
a candidate.

The fourth exists because **an orphan is not necessarily sick**, and because the first
test proves less than it looks like. `ppid == 1` says the shell died, not the session. A
session that starts a server from a Bash command loses the shell immediately, and the
server is reparented to launchd while the session is alive and using it. Without the
fourth test, on 10 August 2026 faro would have offered to close a server on port 8777
that three sessions, open for half an hour, were using. Whatever fails only the fourth
test does not appear among the orphans at all: it goes back to the services, with the
reason written next to it.

The list is recomputed at the moment `reap --esegui` starts, and never taken from an
earlier screen. A pid printed ten minutes ago may since have been reused by something
else, and a stale pid is exactly how a cleanup tool kills the wrong thing.

The reasoning behind each test, and what happens when you remove it, is in
[docs/four-tests.md](docs/four-tests.md).

## Never date a scheduled job by its log

The first version of faro decided whether a scheduled job was healthy from the
modification time of its log. Two jobs on this machine looked broken that way and neither
was: `dev.stiva.ccd-percorsi` fires every minute and had **1083 runs** against a log
untouched for **fourteen hours**, and `it.nerln.vesuvius-formwatch` had an empty stderr
from five days earlier and had in fact run three hours before.

A log is written when a job has something to say, which is not the same as when it ran.
`launchctl print` counts the runs and gives the last exit code, and that is what faro
shows. Neither `launchctl list` nor `launchctl print` gives a timestamp, so faro never
claims to know when a scheduled job last ran. The honest thing it can say is how many
times.

## The schedules faro cannot read

For a scheduled task of Claude Code, only the prompt is on disk. The cron line lives
inside the application. faro says so instead of guessing, and a session that has the
`scheduled-tasks` tool can hand the list over once:

```bash
faro pianifica --importa lista.json     # the output of list_scheduled_tasks
faro pianifica                          # what is known now
```

Until then the schedule column reads `orario noto solo all'app`, the schedule is known
only to the application.

## The same board in a browser

```bash
faro gui
```

It stays in the foreground, opens the browser, and dies with ctrl-c or with the terminal
that hosts it. No fork, no plist, no restart, no file written. If that process goes away,
nothing of faro is left running.

The page is one file with the CSS and the JS inlined: no CDN, no external fonts, no
libraries. It works identically with the network unplugged, which is also the moment you
want to see what is running.

Most of that file is about one problem. Any web page, open in another tab, can make
requests to 127.0.0.1, and binding to localhost is not a defence, it is only an address.
A GUI that accepts a POST which closes processes is a GUI a hostile site can use to close
your processes while you touch nothing. Three walls, each standing on its own:

1. **A random token per launch.** It is in the URL faro opens, the page puts it in
   sessionStorage and strips it from the address bar, and from then on sends it in a
   header on every call. Another site cannot read it: the same-origin policy keeps it out
   of our page and our storage. The comparison is constant time.
2. **Origin on the list, or nothing.** An HTML form can send a cross-site POST without
   the browser asking permission, but it cannot add a header, and its request arrives
   with the sender's Origin. A fetch that wanted the header would trigger a preflight,
   and the preflight gets 403 with no CORS headers at all, so the browser stops before
   trying.
3. **Host on the list.** This is the one against DNS rebinding, the only attack where the
   browser considers the attacker same-origin with us and can therefore add whatever
   headers it likes. A name that resolves to 127.0.0.1 still arrives with its own Host,
   and that Host is refused.

The actions are a subset of the CLI, never a superset: the page can stop a pid, and a
launchd label has to be stopped from the terminal. A button in a page that runs
`launchctl bootout` is power that is not needed here. `reap` from the page runs the dry
run first and shows you that exact list before anything is closed.

And the page does not reimplement the four tests. Its actions call the same `cmd_reap`
and `cmd_stop` the CLI runs, and capture their output. A GUI with its own copy of the
tests is a GUI that one day closes what the CLI protects.

## Saying it once, and only when it matters

```bash
faro annuncia --prova    # what it would say, without notifying anything
faro annuncia            # a macOS notification, only if there is something to say
```

Two rules, and they are the whole design of that file:

**If there is nothing to say, it says nothing.** A notification that always arrives is a
notification you learn to ignore, and from that moment it is useless even when it is
telling the truth. The empty answer is the normal case.

**It says, and that is all.** It kills nothing, offers to kill nothing, opens nothing.
The decision stays with whoever reads it.

The judgement lives in one function, shared by the notification and by the red band in
the GUI, so that the page and the notification cannot one day disagree. The text goes to
`osascript` through argv and never into the AppleScript source: a process name comes from
a plist or a command line, which is data faro does not control, and concatenating it into
a script would be the most convenient way to make a machine that was only looking run
something.

## Install

Python 3 and nothing else.

```bash
git clone https://github.com/nerln/faro.git ~/dev/faro
ln -s ~/dev/faro/bin/faro ~/.local/bin/faro
```

macOS only. It reads `ps`, `lsof`, `launchctl`, `vm_stat` and `sysctl`, and it assumes
launchd. On anything else it would have to be a different program.

## Tests

```bash
python3 tools/prova.py
```

53 checks, under a second, no dependencies and no processes killed. The ones that count
are `Orfani`: that is the only place in faro where a reading mistake becomes a dead
process. Each of the four tests has a case that removes it and checks that the process
stops being a candidate, and the GUI has cases for the token, the Origin, the Host, the
preflight and the absence of any request to the network in the page.

## In the family

`rada` counts memory, `plancia` counts work, `faro` counts processes. None of the three
knows anything about the others, and faro reads all of them from their own source without
asking them for anything: if faro disappears, rada and plancia do not notice.

## Licence

MIT. See [LICENSE](LICENSE).
