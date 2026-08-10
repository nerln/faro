# The four tests of `faro reap`

`reap` is the only part of faro that ends a process it did not start. Everything else
reads. So the interesting question about faro is not what it shows, it is what it is
willing to kill, and this page answers that one.

The code is `orfani()` in [`faro/inventory.py`](../faro/inventory.py). The tests are the
`Orfani` class in [`tools/prova.py`](../tools/prova.py).

## The shape of the problem

A Claude Code session runs `python3 -m http.server 8742 &` from a Bash tool call. The
shell that ran it exits immediately. The server does not: it is reparented to launchd,
which on macOS is pid 1, and it now has no parent that will ever wait for it, no terminal
to be closed, and no entry in any list a person reads. Three of those were found on the
first run, on 10 August 2026, on three different ports, the oldest twenty hours old.

The tempting rule is: `ppid == 1` and it looks like a dev server, so it is garbage.

That rule is wrong, and it is wrong in the direction that costs the most. `ppid == 1`
says the shell is dead. It says nothing about the session, and the session is the thing
that decides whether anybody still wants that server.

## Test 1: the parent is gone

```python
if p["ppid"] != 1:
    continue
```

A process with a living parent belongs to that parent. Somebody started it and is still
there, so faro has no business with it, whatever it looks like.

This is a filter, not evidence. It is first because it is cheap and it removes almost
everything, not because it proves anything on its own. Test 4 exists precisely because of
how little this one proves.

Removing it: `test_a_living_parent_saves_it` gives the same process `ppid == 500` and
expects an empty list.

## Test 2: launchd does not supervise it

```python
supervised = {i.get("pid") for i in loaded.values() if i.get("pid")}
if p["pid"] in supervised:
    continue
```

Everything launchd keeps alive also has `ppid == 1`. Without this test, `reap` would
happily kill `com.plancia.server`, and that is the worst possible failure, worse than
killing something useful: launchd restarts it, so the process comes back, the memory is
not recovered, the board looks the same after the cleanup as before it, and the only
lasting effect is a service that has silently lost its state.

The pids come from `launchctl list`, which is launchd's own declaration of what it owns.
faro does not maintain a list of protected names, because a list of names is a list that
goes stale. A job loaded five minutes ago is protected without anybody adding it
anywhere.

Removing it: `test_launchd_supervision_saves_it` declares the same pid as
`com.plancia.server` in the loaded map and expects an empty list.

## Test 3: it is either in a scratchpad, or it is a server a session is known to start

```python
in_scratch = cwd.startswith(probe.SCRATCH_ROOT)
label = first pattern in SESSION_SPAWNED that matches the command line
if not (in_scratch or label):
    continue
```

Two ways to belong to a session, and one is much stronger than the other.

**The working directory under `/private/tmp/claude-501/…`** is a scratchpad that only a
Claude Code session creates, and the path contains the project and the session uuid. A
process sitting there was started by that session and by nothing else. That is why an
unknown program is enough: `test_a_scratchpad_is_enough_even_for_an_unknown_program` runs
`./qualcosa-che-nessuno-conosce --serve` from a scratchpad and it is still a candidate.

**The command line matching `SESSION_SPAWNED`** is weaker. It is a list of nine patterns
(`http.server`, `vite`, `next dev`, `npm run dev` and relatives, `uvicorn` and `flask
run`, the plancia MCP server, the agentbridge bridge, the codex app server, a generic MCP
server). It is a heuristic, and it is kept short on purpose: **every pattern added to
that list is a new way for faro to kill something.** It earns its place only for
processes a session actually starts.

Outside those two, faro leaves the process alone even when it looks abandoned.
`test_an_unknown_program_outside_a_scratchpad_is_left_alone` uses a postgres started by
hand from the home directory: `ppid == 1`, not supervised, running for hours, and not a
candidate. That is the right answer. Somebody's database is not faro's business.

## Test 4: nobody is using it

This is the one that was added after the question that mattered, and the one worth
reading closely, because the first three would have been enough to ship and wrong.

**An orphan is not necessarily sick.** A session that starts a server from a Bash command
loses the shell in the same instant and the server is reparented to launchd, while the
session is alive, in front of the user, using that server. Tests 1 to 3 cannot tell that
process from a leftover of a session closed at three in the morning, because on those
three tests they are identical.

On 10 August 2026 that was not hypothetical. A server on port 8777 passed the first three
tests and would have been offered for closing. Three sessions, open for half an hour, were
using it. Its working directory was the root of the Drive folder those three sessions were
working in.

So there are three ways to be in use, and any one of them is enough:

```python
viva    = the transcript of the session that owns the scratchpad was written recently
giovane = (p["age"] or 0) < ETA_MINIMA_ORFANO          # 600 s
in_uso  = cwd is, or is under, the working directory of a live session
```

**Too young to judge** (`ETA_MINIMA_ORFANO`, ten minutes). A process born a minute ago
belongs to whoever just started it. Ten minutes is not a measurement, it is a margin: it
is long enough that no plausible startup sequence is still in progress, and short enough
that a real leftover is caught within one board refresh of somebody looking.
`test_a_young_process_is_a_service_and_not_an_orphan` sets the age to 13 seconds.

**The session is still writing** (`SESSIONE_VIVA_SE_SCRITTA_DA`, fifteen minutes). The
scratchpad path `/private/tmp/claude-501/<project>/<uuid>/scratchpad` names the transcript
under `~/.claude/projects/<project>/<uuid>.jsonl`. If that file was touched recently, the
session is alive and what it started is a service, not a residue. This is the strong form
of the test, because the process carries the identity of its owner in its own path.
`test_a_session_still_writing_keeps_its_server` builds both paths in a temporary directory.

**A live session works in that directory.** Outside a scratchpad a process does not carry
its owner's name, so the directory has to say it. faro takes the working directories of
the live sessions it has already found on the board and asks whether this process is
sitting in one of them, or below one. This is the 8777 case, and
`test_a_live_session_in_the_same_folder_keeps_its_server` is that exact situation with the
Drive path.

The containment check is done on path segments, not on string prefixes:

```python
cwd == c or cwd.startswith(c.rstrip("/") + "/")
```

`test_a_folder_below_a_live_session_counts_too` checks that `/dev/sito/docs` counts as
inside `/dev/sito`, and `test_a_similar_name_is_not_the_same_folder` checks that
`/dev/sito-vecchio` does not. A naive `startswith` would pass the first and fail the
second, and failing the second means killing a stranger's server because its name starts
the same way.

## Failing test 4 is not the same as being invisible

A process that fails only the fourth test does not vanish from the board. It appears among
`servizi` with the reason written next to it:

```
servizi           avviati da una sessione, e da lei tenuti
  * dev server python                      3m   43.1MB  in servizio             porta 8770  ·  avviato da 3m, troppo presto per dirlo
```

This matters more than it looks. A cleanup tool that silently drops what it decided not to
touch teaches you to trust it in the only way you should not: you stop being able to check
its judgement. Here the demotion is visible, the reason is one of three known strings, and
if the reason is wrong you can see that it is wrong.

## Two rules around the four tests

**The list is recomputed when `--esegui` runs.** Never taken from a previous board, never
accepted as pids from outside. A pid printed ten minutes ago may since have been reused by
another process, and a stale pid is exactly how a cleanup tool kills the wrong thing. The
GUI does not get an exception: its button calls the same `cmd_reap`, which recomputes.

**The ancestor chain is excluded.** `_my_ancestors()` walks from this process up to
launchd and removes those pids from anything faro would stop. Without it, `faro stop`
typed inside a session can kill the session it was typed into, and `faro reap` run from a
scratchpad could reap its own parent.

## What these tests do not prove

- **They do not prove the process is useless.** They prove nobody faro can see is holding
  it. A server nobody has touched for twenty hours may still be the one you need at noon,
  which is why `reap` without `--esegui` is a dry run and there is no timer anywhere in
  faro.
- **They do not see a user outside this machine.** A port being served to a phone on the
  same wifi looks exactly like a port being served to nobody. faro shows the open ports on
  every row so that you can see what it cannot.
- **`SESSION_SPAWNED` is a heuristic and stays one.** A program whose command line matches
  `vite` and was not started by a session, with a dead parent and older than ten minutes,
  outside any live session's directory, is a false positive that all four tests pass. The
  defence against that is the length of the list, not its cleverness.
- **They are tested against fixtures, not against the real machine.** `Orfani` builds
  process tables in memory. That is what makes the suite safe to run with 53 checks in
  under a second, and it means the tests prove the decision, not the reading. The reading
  is `ps`, `lsof` and `launchctl`, and a mistake there would be a different kind of bug.
