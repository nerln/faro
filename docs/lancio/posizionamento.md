# Posizionamento: il piano di controllo che manca

Questo documento dice la tesi che tiene insieme `rada`, `faro`, `boa` e `plancia`, e la
argomenta con i numeri che sono stati misurati su questa macchina. Non sostituisce
`~/.claude/skills/social-media-manager/references/positioning.md`: quello dice chi è
l'account e come si scrive, e resta valido. Questo dice di cosa parla una riga di
prodotti, e sta dentro il pilastro 1 di quel documento (agent tooling that survives
contact) appoggiandosi al pilastro 3 (verification).

## La tesi, in una riga

**Più agenti sulla stessa macchina sono un sistema distribuito che nessuno sta
amministrando.** Questi strumenti sono il piano di controllo che manca.

## Perché è letteralmente un sistema distribuito, e non una metafora

Un sistema distribuito ha cinque proprietà che lo rendono difficile. Otto sessioni di
Claude Code e una di Codex sullo stesso portatile le hanno tutte e cinque.

| proprietà | come si presenta qui |
|---|---|
| processi autonomi | ogni sessione decide da sola, e ha ragione di farlo |
| nessuna vista condivisa | l'isolamento per progetto è voluto, ed è quello che le rende utili |
| risorse contese | memoria, processi, porte, disco: una sola macchina fisica |
| guasto parziale | una sessione muore e lascia in piedi quello che aveva avviato |
| nessun orologio comune | nessuna sa cosa stava facendo un'altra dieci minuti fa |

La differenza con un cluster è che un cluster ha tre cose che qui non ci sono: uno
scheduler che sa quanta memoria c'è, un inventario di cosa gira, e qualcuno che risponde
quando un nodo muore. Non mancano perché siano difficili da fare. Mancano perché finché
si tratta di "il mio portatile" a nessuno viene in mente che servano.

**Il difetto non è nelle sessioni. È che il comune non ha nessuno che lo rappresenta.**
Questa frase sta già in `~/dev/boa/PRINCIPIO.md` e regge tutto il resto.

## I fatti che costringono alla tesi

Tutti misurati, tutti con la fonte accanto. Nessuno stimato.

| fatto | numero | dove è scritto |
|---|---|---|
| quattro sessioni hanno avviato quattro lavori pesanti insieme, e la macchina si è fermata per minuti | 2992 MB di 4096 di swap, 88000 pageout | `~/dev/rada/README.md` |
| il primo giro di `faro`, il 10/08/2026 | tre server di anteprima orfani su tre porte, il più vecchio da quindici ore, 3,4 GB di swap su 5, cinque sessioni vive | `~/dev/faro/README.md` |
| la coda al suo peggio | 14,3 GB di swap su 15, venti lavori in coda, uno da 5 GB in testa che bloccava dodici comandi che non consumavano niente | `~/dev/boa/PRINCIPIO.md` |
| un automatismo dato per morto perché il suo diario era fermo | il sistema ne contava 1083 esecuzioni | `~/dev/faro/docs/come-e-stato-condotto.md` |
| il server sulla porta 8777, che una pulizia con tre controlli su quattro avrebbe chiuso | tre sessioni aperte da mezz'ora lo stavano usando | `~/dev/faro/docs/come-e-stato-condotto.md` |
| due sessioni hanno lavorato sullo stesso README senza accorgersene | 10/08/2026 | `~/dev/boa/CLAUDE.md` |
| cartelle di sessione mai ripulite | 1293 il 10/08/2026 | `~/dev/faro/CLAUDE.md` |

Quattro di questi sette fatti non erano noti prima che esistesse uno strumento che li
guardava. Questo è l'argomento, e va detto in questa forma: **il problema non è che la
macchina va piano. È che non c'era un posto da cui accorgersene.**

## Tre scarsità, tre meccanismi, tre strumenti

La divisione non è estetica. Sono tre tipi diversi di scarsità e tre meccanismi diversi,
e questo è il motivo per cui non è un cruscotto solo.

| cosa una sessione toglie alle altre | perché guardare non basta | chi se ne occupa |
|---|---|---|
| **memoria** | è finita e istantanea: quando manca è già tardi | `rada`, che mette in coda prima |
| **processi e porte** | non sono scarsi ma si accumulano, e nessuno li possiede | `faro`, che li rende visibili |
| **intenzione** | non è scarsa affatto: è che nessuno la dichiara | `boa`, dove i modelli la scrivono |

Intorno ci sono altri due pezzi, e vanno nominati per quello che sono, non messi nella
stessa fila.

- **`plancia` è il registro.** Tiene il lavoro che sopravvive alla sessione. La regola
  del confine sta in `PRINCIPIO.md` e va ripetuta ovunque: plancia è il registro, boa è
  il filo. Un task su plancia dice "questo va fatto". Una voce su boa dice "lo sto
  facendo io, adesso, e sto tenendo questa porta".
- **`vedetta` è il confine verso fuori.** Non amministra la macchina: decide a quali
  condizioni qualcosa che viene da internet può entrare nel contesto di un agente. È lo
  stesso principio degli altri tre applicato al bordo, e per questo appartiene alla
  stessa riga anche se risolve un altro problema.

Un cruscotto unico che facesse tutto sarebbe la quarta cosa che gira e che nessuno
amministra. Questo va detto quando qualcuno chiede perché non è un prodotto solo.

## Le tre regole che valgono per tutti

Sono la parte difendibile del posizionamento, perché sono verificabili una per una
aprendo i repository. Chi copia il concetto non copia queste.

**1. Niente gira quando non stai guardando.**
Nessuno dei quattro tiene un demone. `faro` non ha un processo che gira sempre, e la
ragione sta scritta nella sua prima invariante: il problema di partenza era troppa roba
che girava senza che nessuno l'avesse chiesta, e un sorvegliante permanente sarebbe
stato la settima famiglia di processi. `rada` coordina con un file e un lock. `boa` è un
file in append e due hook. Cancellare `~/.faro` o `~/.boa` non cambia niente di come si
comporta la macchina.

**2. Quello che si legge è dato, mai istruzione.**
Le righe di comando che `faro` stampa arrivano da repository e da pagine web: vengono
troncate e mostrate, non passano da una shell e non finiscono in un modello. Ogni voce
che `boa` consegna passa da una cornice che dice a chi la riceve che è una proposta di
un'altra sessione e non una richiesta dell'utente, e non esiste un flag che tolga la
cornice. `vedetta` recinta il contenuto con un marcatore generato a ogni invocazione, in
modo che una pagina non possa chiudere la recinzione e uscire. Il giudice di `rada` gira
senza strumenti, senza server, con contesto nuovo ogni volta.
Questa regola ha anche l'unico numero onesto che nessuno pubblica: `rada` ha misurato sei
attacchi contro il suo giudice e **uno ha funzionato**, e ha pubblicato la tabella con
dentro quello che ha funzionato.

**3. I numeri sono misurati, e gli errori si pubblicano.**
`faro` ha un documento che elenca due errori suoi: una pulizia che avrebbe chiuso un
server in uso, e una data dedotta da un file di log invece che letta dal sistema.
`boa` ha una soglia fissata a meno della metà del punto in cui il guasto è stato visto,
e scrive perché. `rada` ha due difetti veri che sono diventati due test.
Questo è il pilastro "verification" del posizionamento generale, applicato a una riga di
prodotti invece che a un singolo repository.

## Perché questa posizione regge nel tempo

Tre ragioni, e la terza è quella che conta.

1. **Il problema cresce da solo.** Il numero di agenti per persona sale, non scende. Chi
   oggi ne tiene due aperti fra un anno ne tiene sei, e incontra questi guasti nello
   stesso ordine: prima la macchina che si ferma, poi le porte occupate, poi due agenti
   che rifanno lo stesso lavoro.
2. **Non si può occupare senza averlo pagato.** Questi numeri non si trovano in un blog.
   Si ottengono mandando in ginocchio la propria macchina e misurando mentre succede.
3. **È vero.** È la ragione per cui il posizionamento generale dice che la posizione è
   sopravvivibile nei mesi. Una tesi che descrive quello che è successo davvero non ha
   bisogno di essere difesa quando qualcuno controlla.

## Come si dice, a seconda di chi arriva

Il registro cambia con il lettore, e la regola non è negoziabile perché è già costata
un lotto di post buttati (positioning.md, 2 agosto 2026).

- **Su X e su LinkedIn** arriva qualcuno che non stava cercando niente. Vale la regola
  del lettore non tecnico: niente nomi di librerie, niente numeri che hanno bisogno di
  una definizione, niente righe di comando. "Tre programmi accesi che non avevo acceso
  io" si capisce. "3,4 GB di swap" no, e la parola swap in un post è un lettore perso.
- **Sul sito e nei README** arriva qualcuno che stava cercando esattamente questo. Lì i
  numeri veri, le invarianti e i limiti sono la ragione per cui resta.

Questa non è una contraddizione. È la differenza fra la porta e la stanza.

## Cosa non dire, mai

- **"Orchestrazione multi agente".** È un'altra cosa: quella coordina più agenti dentro
  un compito. Qui si amministra una macchina su cui girano agenti che non collaborano.
  Confondere le due fa sembrare questi strumenti un framework, che è la categoria in cui
  muoiono.
- **"Il primo", "l'unico", "il migliore".** Non serve e non si può verificare.
- **Promesse di risparmio.** Nessuno ha misurato token risparmiati, quindi non si dice.
- **Che qualcosa giri in CI quando non è vero.** Vale la nota su `scriba` in
  positioning.md: un lettore controlla.
- **Che `boa` sia pubblico, o che `faro` abbia un README in inglese.** Al momento in cui
  questo documento è stato scritto, `faro` ha tre commit e nessun remoto, e `boa` non è
  nemmeno un repository. Vedi le liste "prima di pubblicare" in `annuncio-faro.md` e
  `annuncio-boa.md`.

## Nota su un numero del brief

Il brief di lancio chiedeva di usare "20 ore" per l'orfano più vecchio. Il numero
misurato e scritto in tre posti diversi del repository (`README.md`, `CLAUDE.md`,
`docs/come-e-stato-condotto.md`) è **quindici ore**. Ho tenuto quindici. Se venti è il
numero giusto e viene da una misura successiva, va prima corretto nel repository e poi
nei testi di lancio, mai il contrario.
