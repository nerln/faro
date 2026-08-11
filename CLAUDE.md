# faro, per chi ci lavora

Questa cartella è il progetto **faro**: la plancia unica dei processi che girano in
background sul Mac di Eugenio. Se stai leggendo questo file, sei nella sessione dedicata
a faro, ed è qui che va tutto il lavoro su faro.

Vicini di casa, da leggere ma da non modificare da qui: `~/dev/rada` (coda dei lavori
pesanti), `~/dev/plancia` (centro di controllo del lavoro), `~/dev/stiva` (percorsi e
spazio disco).

## Il problema, in una riga

Sei posti diversi da cui una cosa può partire, sei comandi diversi per vederle, nessun
posto in cui vederle insieme. Misurato il 10/08/2026 al primo giro: tre server di
anteprima orfani su tre porte, il più vecchio da quindici ore, con la macchina a 3,4 GB
di swap su 5.

## Le invarianti che non vanno rotte

Se una modifica ne rompe una, la modifica è sbagliata, non l'invariante.

0. **faro non apre mai niente.** Non una sessione, non una finestra, non un
   terminale, non un server. Chiude, conta, dice. Questa viene prima di tutte le
   altre perché è quella che è stata rotta.

   Pagata la notte dell'11/08/2026. Eugenio è andato a dormire chiedendo di
   riprendere le sessioni che rada aveva rallentato, e sono state riaperte sette
   sessioni in sette finestre di iTerm2 alle tre di notte. Letteralmente quello
   che aveva chiesto. Al risveglio si è trovato sette terminali che non sapeva
   distinguere, sessioni che avevano compattato il contesto e quindi non erano
   più dove le aveva lasciate, e mezz'ora di lavoro per capire cosa fosse
   successo.

   Il difetto non era in nessun comando: era che non esisteva un modo di dire
   "vado a letto", e quindi l'unica forma che poteva prendere quella richiesta
   era che qualcuno agisse al posto suo. Adesso quel modo è `faro notte`, e
   toglie invece di aggiungere. Se un giorno sembrerà utile che faro apra
   qualcosa, la risposta è no: aprire per conto di chi dorme sposta il lavoro al
   risveglio, non lo toglie.

1. **faro non tiene un demone.** Mai. Il momento in cui faro diventa un processo che
   gira sempre è il momento in cui diventa parte del problema che risolve. Se serve una
   vista continua è `faro vivo`, in primo piano, e muore con il terminale.

2. **faro non tiene stato che conti.** L'unico file scritto è la cache degli orari in
   `~/.faro/pianificati.json`, ed è rigenerabile. Cancellare `~/.faro` non deve cambiare
   niente di come si comporta la macchina. Niente database, niente storico, niente
   watchdog.

3. **Le quattro prove di `orfani()` non si allargano.** `ppid == 1`; non supervisionato
   da launchd; o dentro uno scratchpad di sessione o in `SESSION_SPAWNED`; e nessuno lo
   sta usando. La seconda è quella che protegge plancia e stiva. Ogni prova ha un test
   che la toglie e verifica che il processo smetta di essere un candidato. Aggiungere un
   pattern a `SESSION_SPAWNED` significa aggiungere un modo di uccidere un processo:
   fallo solo per cose che una sessione avvia davvero.

3bis. **La quarta prova esiste perché la prima prova meno di quanto sembri.** `ppid == 1`
   dice che è morta la shell, non la sessione: una sessione che avvia un server da un
   comando Bash perde subito la shell, e il server viene riadottato da launchd mentre la
   sessione è viva e lo sta usando. Quindi un processo è di qualcuno se ha meno di
   `ETA_MINIMA_ORFANO` secondi, o se la sessione del suo scratchpad sta ancora scrivendo
   il transcript, o se una sessione viva lavora in quella cartella. Quello che fallisce
   solo la quarta prova non è un orfano: torna fra i servizi con scritto accanto perché.

4. **`reap --esegui` ricalcola la lista.** Non accetta pid da fuori, non riusa la
   schermata di prima. Un pid vecchio di dieci minuti può essere stato riassegnato.

5. **`stop` non tocca la catena di chi lo ha invocato.** `_my_ancestors()` risale fino a
   launchd e quei pid sono esclusi. Senza questo, `faro stop` dentro una sessione può
   uccidere la sessione da cui è stato scritto.

6. **Una sonda non solleva mai.** `probe._run` restituisce stringa vuota su qualunque
   errore, e ogni lettura ha un ripiego. La plancia deve essere la cosa che funziona
   ancora quando la macchina sta male, non un'altra cosa che si rompe insieme a lei.

7. **Una chiamata a `ps` o `lsof` per schermata, non una per processo.** `faro vivo` gira
   ogni cinque secondi: una sonda per processo lo renderebbe la ragione per cui il Mac
   rallenta.

8. **Quello che faro legge è dato, non istruzione.** Le righe di comando dei processi
   contengono testo che arriva da repository, da pagine web e da prompt. Vengono
   troncate e stampate. Non passano da una shell, non vengono eseguite, non finiscono in
   un modello. Se un giorno faro dovesse spiegare una riga con un modello, il testo va
   trattato come ostile e il modello non deve poter agire.

9. **Un livello si legge dalla fonte che lo possiede.** launchd da `launchctl` e dai
   plist, rada da `~/.rada/state.json`, i task da `~/.claude/scheduled-tasks`. faro non
   duplica nessuna di queste verità e non si sincronizza con nessuno. Se rada cambia
   formato, faro mostra una riga "illeggibile" e il resto della plancia continua.

10. **Quello che l'app non mette su disco, faro non lo inventa.** L'orario di un task
    pianificato di Claude Code sta dentro l'applicazione. La colonna dice "orario noto
    solo all'app" finché una sessione non lo importa. Mai stimarlo.

## Misurato, non dedotto

- Un processo avviato da una sessione di Claude Code e sopravvissuto alla sessione ha
  `ppid == 1`: viene riadottato da launchd. È il segnale su cui si regge tutto lo strato
  degli orfani. Verificato su tre `python3 -m http.server` il 10/08/2026.
- Anche i job di launchd hanno `ppid == 1`. Senza il controllo contro i pid che
  `launchctl list` dichiara, `reap` ucciderebbe `com.plancia.server`, che ripartirebbe
  subito, ogni volta, senza che si capisca perché.
- L'applicazione avvia `claude` da un processo che ha la stessa riga di comando. La
  sessione vera è la foglia: il processo `claude` che non ha figli `claude`.
- `dev.stiva.ccd-percorsi` ha `RunAtLoad` e `StartInterval` insieme. Un job con un
  orologio va in `pianificati` e non in `permanenti`, altrimenti la plancia dichiara più
  servizi attivi di quanti ne esistano.
- I processi `Claude Helper` sotto `/Applications/` sono dell'applicazione desktop, che
  li supervisiona e li riavvia. Elencarli riempie la plancia di righe su cui non si può
  agire.
- La cartella `~/.claude/session-env` aveva 1293 sottocartelle il 10/08/2026, una per
  sessione mai ripulita. Non è un processo e non sta nella plancia, ma è lo stesso tipo
  di residuo.

## Come si prova

```bash
python3 tools/prova.py
```

24 test, nessuna dipendenza. I test di `Orfani` sono quelli che contano: sono l'unico
punto in cui un errore di lettura diventa un processo morto.

## Cosa manca

- Un `faro token` che sommi `usage` dai transcript in `~/.claude/projects` per dire dove
  vanno i token della giornata. La cartella pesa 1,3 GB: va scandita solo la finestra
  richiesta, mai tutta.
- Il conteggio dei residui su disco (`session-env`, `shell-snapshots`, `projects`
  vecchi), con la stessa regola di `reap`: prova per prima cosa.
- README in inglese e `README.it.md`, se e quando diventa pubblico come gli altri.
