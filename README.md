# faro

Una plancia sola per tutto quello che gira in background sul Mac per conto tuo.

```
faro
```

## Il problema

Sul portatile girano sei categorie di cose che nessuno guarda insieme:

- **launchd** tiene su `com.plancia.server`, e riavvia `dev.stiva.ccd-percorsi` ogni minuto;
- **i task pianificati di Claude Code** partono da soli e spendono token: `x-account-daily-check`
  ogni giorno feriale alle 14:01, `gh-dorada-actualizar` martedì e venerdì;
- **rada** tiene una coda di lavori pesanti, con biglietti e permessi;
- **le sessioni di Claude Code** vive, ciascuna con la sua memoria;
- **i server che una sessione avvia**: il ponte agentbridge, il server MCP di plancia,
  l'app-server di codex;
- **gli orfani**: un server di anteprima avviato da una sessione chiusa alle tre di notte,
  che tiene una porta e non lo fermerà mai nessuno.

Ognuna di queste è visibile da qualche parte, con un comando diverso e in un formato
diverso. Insieme non sono visibili da nessuna parte. È così che la macchina finisce in
swap senza che si sappia chi la stia consumando.

Misurato la prima volta che `faro` è girato, il 10/08/2026: tre server di anteprima
orfani su tre porte diverse, il più vecchio da quindici ore, e 3,4 GB di swap su 5 con
cinque sessioni vive.

## Cosa fa

Legge, e basta. Sei strati su una schermata, con la memoria in testa:

```
faro   memoria 10.8GB di 16.0GB   compressa 2.3GB   swap 3.4GB di 5.0GB   pageout 110300
       1 permanenti  7 pianificati  1 rada  5 sessioni  14 servizi  3 orfani
       la macchina e' in swap: 3.4GB, 110300 pageout, 5 sessioni vive.
       3 processi orfani tengono 10.8MB   ->  faro reap
```

## Comandi

```bash
faro                      # la plancia
faro --dettagli           # un processo per riga invece di un tipo per riga
faro vivo                 # la stessa, che si aggiorna ogni 5 secondi
faro --solo orfani,rada   # solo alcuni strati
faro orfani               # solo quello che nessuno fermerà più
faro reap                 # cosa verrebbe chiuso. non chiude niente
faro reap --esegui        # li chiude
faro stop <etichetta>     # ferma un job launchd
faro stop <pid>           # ferma un processo
faro json                 # tutto, per un altro programma
```

## Cosa non fa

- **Non tiene un demone.** Non c'è niente di `faro` che gira quando non stai guardando.
  Un pannello di controllo che diventa un'altra cosa da sorvegliare ha già fallito.
- **Non tiene stato.** L'unico file che scrive è `~/.faro/pianificati.json`, la cache
  degli orari che l'app di Claude Code non mette su disco. Cancellare `~/.faro` non
  cambia niente di come funziona la macchina.
- **Non uccide niente da solo.** `reap` senza `--esegui` è una prova. Nessun timer,
  nessuna pulizia automatica.
- **Non esegue niente che legge.** Le righe di comando che mostra sono testo troncato:
  non passano da una shell e non finiscono in nessun modello.

## Cosa può chiudere `faro reap`

Solo processi che passano tutte e tre queste prove:

1. il genitore è morto, quindi il processo è stato riadottato da launchd (`ppid == 1`);
2. launchd non lo supervisiona, verificato contro i pid che launchd stesso dichiara;
3. e o sta nella cartella di lavoro temporanea di una sessione, o è uno dei pochi
   server che una sessione notoriamente avvia (`http.server`, `vite`, `npm run dev`,
   il server MCP di plancia, il ponte agentbridge, l'app-server di codex).

La seconda prova è quella che impedisce a `reap` di toccare `plancia` o `stiva`: un
servizio supervisionato la fallisce sempre. Ogni prova ha un test che la toglie e
verifica che il processo smetta di essere un candidato (`tools/prova.py`).

La lista viene ricalcolata nel momento in cui `reap --esegui` parte, e mai presa da una
schermata di prima: un pid stampato dieci minuti fa può essere stato riusato da un altro
processo, ed è esattamente così che uno strumento di pulizia uccide la cosa sbagliata.

## Gli orari che faro non può leggere

Di un task pianificato di Claude Code, su disco c'è solo il prompt. La riga cron sta
dentro l'applicazione. `faro` lo dice invece di inventarselo, e una sessione che ha lo
strumento `scheduled-tasks` può passargliela una volta:

```bash
faro pianifica --importa lista.json     # l'uscita di list_scheduled_tasks
```

## Installazione

Python 3, niente altro. Nessuna dipendenza, nessun installatore.

```bash
ln -s ~/dev/faro/bin/faro ~/.local/bin/faro
```

## Test

```bash
python3 tools/prova.py
```

## In famiglia

`rada` conta la memoria, `plancia` conta il lavoro, `faro` conta i processi. Nessuno dei
tre sa delle cose degli altri, e `faro` li legge tutti dalla loro fonte senza chiedergli
niente: se `faro` sparisce, `rada` e `plancia` non se ne accorgono.
