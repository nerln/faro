# Come è stato condotto il lavoro

Eugenio ha chiesto di illustrare il metodo in modo meticoloso, e di "loggare tutto il
pensiero". Comincio dal limite, perché condiziona tutto il resto.

**Quello che segue è un registro di decisioni, non un dump del ragionamento.** Le due
cose non coincidono, e la differenza è la stessa di cui parla il paper in `docs/xai/`:
una narrazione del proprio processo è prodotta insieme al risultato, non estratta da
esso. Quello che posso dare con onestà è la lista dei bivi, la ragione scelta a ogni
bivio, e i punti in cui mi sono sbagliato. Quello che non posso dare è la garanzia che
questa lista sia il processo e non una ricostruzione plausibile.

Con quel limite dichiarato, ecco i bivi.

---

## 1. Ricognizione prima di costruire

**Bivio.** Costruire subito un pannello, o prima censire.

**Scelto: censire.** Sette letture in parallelo su sorgenti diverse: `launchctl`, i
plist, `crontab`, `ps`, `lsof`, `~/.claude/scheduled-tasks`, `~/.rada`. La ragione è che
il problema dichiarato era "non ho il controllo", e un pannello costruito su una
tassonomia inventata avrebbe dato un controllo apparente. Le sei famiglie del pannello
non sono una classificazione scelta a tavolino: sono i sei posti da cui una cosa può
partire su questa macchina, trovati guardando.

**Cosa ha prodotto.** Tre server orfani su tre porte, il più vecchio da quindici ore, e
la macchina a 3,4 GB di swap. Nessuno dei due fatti era noto prima.

## 2. Nessun demone

**Bivio.** Un servizio che sorveglia e avvisa, oppure un comando che si lancia.

**Scelto: comando.** Il problema di partenza era troppa roba che girava senza che
nessuno l'avesse chiesta. Un sorvegliante permanente sarebbe stato la settima famiglia
di processi, e la più difficile da giustificare. È diventata l'invariante 1 di faro, e
ha già respinto due tentazioni successive: il timer nella GUI e il LaunchAgent per gli
annunci. La seconda l'ho risolta agganciandomi a `SessionStart`, un evento che accade
già.

## 3. Leggere ogni strato dalla fonte che lo possiede

**Bivio.** Un database di faro che sincronizza tutto, oppure niente stato.

**Scelto: niente stato.** L'unico file che faro scrive è la cache degli orari che l'app
non mette su disco. La ragione è la reversibilità: cancellare `~/.faro` non cambia
niente. Uno strumento di controllo che accumula una verità propria diventa una terza
versione dei fatti da riconciliare con le altre due.

## 4. Il momento in cui ho sbagliato, e chi mi ha corretto

**L'errore.** Le prime tre prove di `reap` erano: genitore morto, non supervisionato da
launchd, in uno scratchpad o in una lista di server noti. Le ho scritte con tre test
ciascuna e le ho presentate come solide.

**Erano insufficienti, e me l'ha fatto notare Eugenio** con una domanda che non era
tecnica: "anche se è orfano vuol dire per forza che sia male?". La risposta è no, e il
difetto era grave: `ppid == 1` dimostra che è morta la shell, non la sessione. Una
sessione che avvia un server da un comando Bash perde la shell subito, e il server viene
riadottato da launchd mentre lei è viva e lo sta usando.

**Conseguenza misurata.** Il server sulla porta 8777 era usato da tre sessioni aperte da
mezz'ora nella stessa cartella. Con le tre prove, `faro` me lo avrebbe fatto chiudere.
La quarta prova è nata da lì, e la lezione che ho scritto nell'agente `nostromo` è: se un
processo ti sembra in uso e `faro` lo elenca fra gli orfani, credi al dubbio.

**Perché lo scrivo qui.** Perché il difetto non l'ha trovato un test, e non l'avrebbe
trovato un revisore avversariale a cui avessi dato le mie stesse tre prove da attaccare.
L'ha trovato una persona che guardava lo stesso schermo con un'altra domanda in testa.

## 5. Il secondo errore: datare un job dal suo log

**L'errore.** faro diceva che `vesuvius-formwatch` era girato l'ultima volta cinque
giorni prima. Era girato tre ore prima. Diceva che `ccd-percorsi`, che scatta ogni
minuto, aveva un log fermo da quattordici ore.

**La causa.** Stavo deducendo l'ora dell'ultima esecuzione dal `mtime` del file di log.
Entrambi quei job scrivono solo quando agiscono. Due automatismi sani sembravano rotti.

**La correzione.** `launchctl print` espone `runs`, che launchd conta davvero: 1083
contro 2. Ho sostituito una deduzione con una lettura. È diventata l'invariante 10 di
faro: quello che l'app o il sistema non mettono su disco, faro non lo inventa.

## 6. Non fare fan-out quando il vincolo è la memoria

**Bivio.** Eugenio aveva chiesto di far ripartire sei sessioni. La macchina era a 13,7 GB
di swap su 15.

**Scelto: non spawnare, e dirlo.** Sei sessioni in parallelo avrebbero causato
esattamente il guasto che stavamo diagnosticando. Ho provato in serie, e ho scoperto un
fatto che ha chiuso la questione: `claude --resume -p` su un transcript da 5 MB risponde
`Prompt is too long`, perché in headless non c'è la compattazione automatica. Non era un
problema di permessi. Il fan-out di adesso è diverso: gli agenti di un workflow sono
chiamate dentro questo processo, non sessioni nuove, e la macchina era risalita a 5,8 GB
di swap.

**Nota di metodo.** Il classificatore dei permessi ha bloccato tre volte l'avvio di
sessioni autonome con i permessi pre-accettati. Dopo il terzo tentativo mi sono fermato e
ho chiesto, invece di cercare una quarta forma che passasse. Un blocco ripetuto è
informazione, non un ostacolo da aggirare.

## 7. La divisione del lavoro fra gli agenti

**Criterio.** I perimetri sono disgiunti sui file, non sui temi. Due agenti che lavorano
sullo stesso repo ma su file diversi non si pestano; due agenti che lavorano sullo stesso
tema ma senza confini di file si sovrascrivono. Per questo la GUI e il comando `annuncia`
sono andati allo stesso agente: toccano tutti e due `bin/faro`.

**Fasi.** Fondamenta in parallelo, rifinitura in parallelo dopo, verifica alla fine. La
barriera fra fondamenta e rifinitura è vera: non si scrive il README di una cosa che non
esiste ancora, e il collaudatore deve poter provare i comandi che i README promettono.

**Il revisore avversariale ha istruzioni di attaccare, non di confermare.** Il punto su
cui gli ho detto di insistere è quello che considero il difetto più probabile: che la GUI
riscriva le quattro prove invece di importarle, e quindi uccida cose che la CLI protegge.

## 8. Quello che ho progettato io e non ho delegato

Tre cose, per la stessa ragione: sono contratti, e un contratto scritto da chi lo deve
poi implementare tende a piegarsi verso quello che è comodo implementare.

- `PROGETTO.md` di boa, con l'invariante che quello che arriva dalla lavagna è dato e
  mai istruzione. Uno strumento che fa comparire testo di una sessione nel contesto di
  un'altra è un amplificatore di prompt injection, e la difesa va nel contratto, non
  aggiunta dopo.
- `PRINCIPIO.md`, il bene comune fra sessioni: tre tipi di scarsità, tre meccanismi,
  e la ragione per cui scrivono i modelli invece di un aggregatore.
- La nota in prima persona in `docs/xai/`, che nessun agente poteva scrivere al posto
  mio senza che diventasse una finzione.
