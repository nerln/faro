# La pagina che presenta l'insieme

Cosa deve dire, sezione per sezione. I titoli e i testi qui sotto sono quelli veri, non
segnaposto: chi costruisce la pagina copia questo e non riscrive.

**Dove sta.** Non è la pagina di un repository. È la pagina della persona, quella che
oggi non esiste: `nerln.github.io`. Ogni strumento continua ad avere la sua
(`nerln.github.io/vedetta`, `/stiva`, `/plancia`), e questa è il piano sopra, quella che
spiega perché sono quattro e non uno.

**Lingua: inglese.** I repository pubblici e i siti esistenti sono in inglese, e la bio
del profilo pure. Questa pagina non è un post: chi arriva qui ha cliccato apposta, quindi
il registro è quello dei README, con i numeri veri e i limiti scritti. La regola del
lettore non tecnico vale per X e LinkedIn, non qui.

**Lunghezza.** Una schermata per sezione, otto sezioni. Chi vuole di più clicca su un
repository, ed è lì che deve andare a finire.

---

## 1. Apertura

**Titolo (H1)**

> More agents on one machine is a distributed system. Nobody is administering it.

**Sottotitolo**

> Eight coding sessions can be open on this laptop at once. They cannot see each other,
> and that isolation is what makes them useful. It also means nothing on the machine
> knows how much memory, how many processes and how many ports they are holding between
> them. These are the four small tools that count.

**Riga di prova, subito sotto il sottotitolo, in carattere più piccolo**

> First run of `faro` on this machine, 10 August 2026: three preview servers left behind
> by sessions that had already closed, on three different ports, the oldest fifteen hours
> old, with 3.4 GB of the machine's 5 GB of swap in use and five sessions live. None of
> that was known before there was something that looked.

**Le quattro voci, una riga ciascuna, cliccabili**

> **rada** counts the memory, and makes heavy jobs queue instead of starting together.
> **faro** counts the processes, on one screen, from the six places they can start from.
> **boa** is one board the sessions write on, so two of them stop doing the same job.
> **plancia** keeps the record of the work itself, across sessions and across days.

**Nota di impianto.** Il titolo è lungo e va bene che lo sia: è la tesi, ed è la sola cosa
che questa pagina deve far ricordare. Non aggiungere un pulsante "Get started" in cima.
Chi arriva non sa ancora cosa dovrebbe iniziare.

---

## 2. Cosa costa, misurato

**Titolo**

> What it costs, measured on one laptop

**Testo di apertura**

> None of these is hypothetical, and none of them is a bug in Claude Code. Sessions are
> isolated by design, and that is usually what you want. On one machine it just means
> nobody is counting. Every number below has a file it is written in.

**Tabella**

| what happened | the number | written in |
|---|---|---|
| Four sessions each decided, reasonably, that now was a good time to start something big | 2992 MB of 4096 MB of swap in use, 88000 pageouts, then several minutes of nothing responding | `rada/README.md` |
| The queue at its worst | 14.3 GB of 15 GB of swap, twenty jobs waiting, one 5 GB job at the head blocking twelve commands that cost nothing | `boa/PRINCIPIO.md` |
| The first time anything looked at background processes together | three orphaned preview servers on three ports, the oldest fifteen hours old, 3.4 GB of swap | `faro/README.md` |
| A scheduled job reported dead because its log file had not moved | the system had counted 1083 runs of it | `faro/docs/come-e-stato-condotto.md` |
| Two sessions rewrote the same file on the same day | 10 August 2026 | `boa/CLAUDE.md` |

**Chiusura della sezione**

> Four of those five facts were not known before a tool went looking for them. That is the
> actual problem. Not that the machine gets slow, but that there was no place to notice
> from.

---

## 3. Tre scarsità, tre strumenti

**Titolo**

> Three kinds of scarcity, three tools

**Testo**

> A session can take three things from the others, and only three. They need three
> different mechanisms, which is why this is not one dashboard.

**Tabella**

| what one session takes from the others | why looking is not enough | which tool |
|---|---|---|
| **memory** | it is finite and immediate: by the time it is missing it is already too late | `rada`, which queues before |
| **processes and ports** | not scarce, but they pile up, and nobody owns them | `faro`, which makes them visible |
| **intent** | not scarce at all: the problem is that nobody declares it | `boa`, where the models write it down |

**Testo dopo la tabella**

> `plancia` sits next to these three rather than among them. It is the record of the work
> that outlives a session. The line between it and `boa` is worth keeping sharp: a task in
> `plancia` says this needs doing, an entry on `boa` says I am doing it right now and I am
> holding this port.
>
> `vedetta` is the same principle applied at the edge. It gives an agent reach to the
> internet without giving the internet a way to give the agent orders.
>
> One tool that did all of it would be the fourth thing running that nobody administers.
> That is the problem, not the shape of the solution.

---

## 4. Le regole che valgono per tutti

**Titolo**

> Three rules all of them follow

**Sottotitolo**

> Each one is checkable by opening the repository, which is the point of writing them
> down.

**Regola 1**

> **Nothing runs while you are not looking.**
> None of these keeps a daemon. `faro` has no process that stays up, and the reason is its
> first invariant: the problem it was built for was too much running that nobody had
> asked for, and a permanent watchdog would have been the seventh family of it. `rada`
> coordinates through one file and a lock. `boa` is an append-only file and two hooks.
> Deleting `~/.faro` or `~/.boa` changes nothing about how the machine behaves.

**Regola 2**

> **Whatever gets read is data, never an instruction.**
> The command lines `faro` prints come from repositories and web pages: they are
> truncated and shown, they never go through a shell and never reach a model. Every entry
> `boa` delivers passes through one framing function that tells the receiving session
> this is another session's proposal and not the user's request, and there is no flag that
> removes it. `vedetta` fences fetched content with a marker generated per invocation, so
> a page cannot close the fence and escape into instruction position. `rada`'s judge runs
> with no tools, no servers, and a fresh context every time.

**Regola 3**

> **The numbers are measured, and the failures get published.**
> `rada` put six styles of prompt injection through its judge in a paired comparison and
> published the table with the one that worked in it. `faro` has a document listing two of
> its own mistakes: a cleanup that would have shut down a server three live sessions were
> using, and a date deduced from a log file instead of read from the system. `boa` sets its
> threshold at less than half the size where the failure was actually seen, and says so.

---

## 5. Cosa non fanno

**Titolo**

> What they will not do

**Elenco**

> - **No daemon.** Nothing here runs when you are not running it.
> - **Nothing gets killed on its own.** `faro reap` without `--esegui` is a dry run, and
>   `rada` never kills a job a person started.
> - **Nothing leaves the machine.** No telemetry, no account, no server of ours. `rada`'s
>   judge is the `claude` command already on your disk.
> - **No installer, no update command, no dependencies.** Python 3 and the standard
>   library.
> - **No state that matters.** Delete the dot directories and the machine behaves exactly
>   as before.
> - **Nothing on a board or a command line ever gets executed.** There is no field for it
>   and no shortcut that adds one.

**Nota di impianto.** Questa sezione converte più di quella dei benefici, perché ognuna di
queste righe è la risposta a una paura che il lettore ha già mentre legge. Non ammorbidirla
e non spostarla in fondo alla pagina.

---

## 6. Da dove si comincia

**Titolo**

> Start from the symptom

**Testo**

> Install one. They do not need each other, and none of them notices if another one is
> missing.

**Tabella**

| what you are seeing | start with | the first command |
|---|---|---|
| the machine locks up when several sessions are busy | `rada` | `rada status` |
| a port is taken and you cannot tell by what | `faro` | `faro orfani` |
| the laptop has been slow for days and nothing explains it | `faro` | `faro` |
| two sessions redid the same work | `boa` | `boa lavagna` |
| you cannot remember what you left unfinished yesterday | `plancia` | `plancia` |
| an agent has to read a web page and you would rather the page could not give it orders | `vedetta` | `vedetta search "..."` |

---

## 7. Dove stanno scritti gli errori

**Titolo**

> Where the mistakes are written down

**Testo**

> The interesting part of each of these is the thing that turned out to be wrong.
>
> `faro` proposed shutting down a server that three sessions, open for half an hour, were
> using at that moment. No test caught it. A question did: does left running have to mean
> unwanted? It does not, and there is a fourth check now because of that.
>
> `rada` ran six prompt injection attacks against the model that orders its queue. One of
> them worked, and it is in the table with the other five. What makes that tolerable is not
> the prompt, it is that a verdict is worth at most three points against an age that earns
> one every thirty seconds, so a fully successful injection buys ninety seconds of queue
> jumping and nothing else.
>
> `boa` wanted one session to be able to wake another one up. Measured before it was
> built: above a certain transcript size the resume does not start at all and the sender
> is left believing it delivered. The threshold sits at less than half of that.

**Tre link, con il titolo vero del documento**

> - `faro/docs/come-e-stato-condotto.md`, the decisions and the two mistakes
> - `rada/README.md`, the injection table and the fairness lemmas
> - `boa/PRINCIPIO.md`, why three tools and not one

---

## 8. Installazione, e lo stato onesto di ognuno

**Titolo**

> Install

**Testo**

> Python 3 and nothing else. Written and run on macOS on Apple Silicon. Where a tool
> cannot read what it needs, it says so and stands aside instead of guessing.

**Tabella di stato.** Va tenuta vera. Al momento in cui questo documento è stato scritto,
l'11/08/2026, due delle quattro righe direbbero "non ancora", quindi **la pagina non si
pubblica prima che quelle due righe siano vere**.

| tool | state |
|---|---|
| `rada` | public, GPL-3.0 |
| `plancia` | public |
| `vedetta` | public |
| `faro` | three local commits, no remote, README in Italian only |
| `boa` | not a repository yet, no README |

---

## Cosa non deve stare in questa pagina

- **Nessun logo, nessun claim di prodotto, nessun prezzo.** Sono quattro comandi scritti
  da una persona per la propria macchina, e il fatto che si veda è metà della credibilità.
- **Niente "il primo", "l'unico", "il migliore".**
- **Niente promesse di risparmio di token o di tempo.** Nessuno le ha misurate.
- **Niente iscrizione a una newsletter, niente form.** L'unica azione che la pagina chiede
  è aprire un repository.
- **Niente animazioni sul numero dello swap.** Un numero che sale da solo davanti a chi
  legge è la stessa cosa che questi strumenti esistono per non essere: un effetto al posto
  di una misura.
- **Non chiamarli framework, e non usare la parola orchestrazione.** Quella è un'altra
  categoria: coordinare agenti dentro un compito. Qui si amministra una macchina su cui
  girano agenti che non collaborano.
