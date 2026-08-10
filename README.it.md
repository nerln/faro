# faro

Una plancia sola per tutto quello che gira in background sul Mac per conto tuo.

[English](README.md)

```
faro
```

Python 3 e la libreria standard. Nessuna dipendenza, nessun installatore, nessun demone.

## Perché esiste

Sul portatile girano sei categorie di cose, e ognuna è visibile da un posto diverso:

- **launchd** tiene su `com.plancia.server`, e riavvia `dev.stiva.ccd-percorsi` ogni
  minuto;
- **i task pianificati di Claude Code** partono da soli e spendono token, con un orario
  che sta dentro l'applicazione;
- **rada** tiene una coda di lavori pesanti, con biglietti e permessi;
- **le sessioni di Claude Code** vive, ciascuna con la sua memoria;
- **i server che una sessione avvia**: un server di anteprima, un server MCP, un ponte
  verso un altro agente;
- **gli orfani**: un server di anteprima avviato da una sessione chiusa alle tre di
  notte, che tiene una porta e non lo fermerà mai nessuno.

Ognuna di queste è visibile da qualche parte, con un comando diverso e in un formato
diverso. Insieme non sono visibili da nessuna parte. È così che la macchina finisce in
swap senza che si sappia chi la stia consumando.

La prima volta che `faro` è girato, il 10/08/2026, ha trovato tre `python3 -m http.server`
orfani su tre porte diverse, il più vecchio da venti ore, su una macchina che teneva
3,4 GB dei suoi 5 GB di swap con cinque sessioni vive.

Niente di tutto questo è un difetto. Le sessioni sono isolate per scelta, launchd fa il
suo mestiere, e una shell che esce lascia i figli a farsi riadottare, che è esattamente
quello che POSIX dice di fare. Vuol dire soltanto che su una macchina sola nessuno tiene
il conto.

## Cosa mostra

Sei strati su una schermata, con la memoria in testa, perché è per la memoria che sei
venuto:

```
faro   memoria 10.8GB di 16.0GB   compressa 2.3GB   swap 3.4GB di 5.0GB   pageout 110300
       1 permanenti  7 pianificati  1 rada  5 sessioni  14 servizi  3 orfani
       la macchina e' in swap: 3.4GB, 110300 pageout, 5 sessioni vive.
       3 processi orfani tengono 10.8MB   ->  faro reap
```

| strato | cosa ci sta dentro |
|---|---|
| `permanenti` | girano sempre, anche a sessioni chiuse |
| `pianificati` | partiranno da soli, a orario |
| `rada` | la coda dei lavori pesanti |
| `sessioni` | Claude Code vivo adesso |
| `servizi` | avviati da una sessione, e da lei tenuti |
| `orfani` | la sessione non c'è più, nessuno li fermerà |

Quello che sta soltanto bene prende una riga. Quello che non va prende una riga e un
segno. La schermata deve entrare in una finestra di terminale senza scorrere in una
giornata normale, perché un pannello che devi scorrere è un pannello che smetti di
leggere.

Ogni strato si legge dalla fonte che lo possiede: launchd da `launchctl` e dai plist,
rada da `~/.rada/state.json`, i task da `~/.claude/scheduled-tasks`. faro non duplica
nessuna di queste verità e non si sincronizza con nessuno. Se rada cambia formato, faro
mostra una riga illeggibile e il resto della plancia continua.

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
faro gui                  # la stessa plancia nel browser, in primo piano
faro annuncia             # se c'è qualcosa da sapere lo dice, se no tace
faro json                 # tutto, per un altro programma
```

## Cosa non fa

- **Non tiene un demone.** Non c'è niente di `faro` che gira quando non stai guardando.
  Un pannello di controllo che diventa un'altra cosa da sorvegliare ha già fallito.
- **Non tiene stato.** L'unico file che scrive è `~/.faro/pianificati.json`, la cache
  degli orari che l'app di Claude Code non mette su disco. Cancellare `~/.faro` non
  cambia niente di come funziona la macchina.
- **Non uccide niente da solo.** `reap` senza `--esegui` è una prova. Nessun timer,
  nessuna pulizia automatica, niente che agisca mentre dormi.
- **Non esegue mai quello che legge.** Le righe di comando che mostra sono testo
  troncato: non passano da una shell, non vengono eseguite, non finiscono in un modello.

## Cosa può chiudere `faro reap`

Solo processi che passano tutte e quattro queste prove:

1. **il genitore è morto**, quindi il processo è stato riadottato da launchd
   (`ppid == 1`);
2. **launchd non lo supervisiona**, verificato contro i pid che launchd stesso dichiara;
3. **o sta nella cartella di lavoro temporanea di una sessione, o è uno dei pochi server
   che una sessione notoriamente avvia** (`http.server`, `vite`, `npm run dev`, e una
   lista corta di server con un nome);
4. **e nessuno lo sta usando**: ha più di dieci minuti, la sessione del suo scratchpad ha
   smesso di scrivere il transcript, e nessuna sessione viva lavora in quella cartella.

La seconda prova è quella che tiene `reap` lontano dai servizi supervisionati: un job che
launchd tiene in vita la fallisce sempre, e conta perché ucciderlo non lo ferma, lo fa
ripartire. Ogni prova ha un test che la toglie e verifica che il processo smetta di
essere un candidato.

La quarta esiste perché **orfano non vuol dire malato**, e perché la prima prova dimostra
meno di quanto sembri. `ppid == 1` dice che è morta la shell, non la sessione. Una
sessione che avvia un server da un comando Bash perde subito la shell, e il server viene
riadottato da launchd mentre lei è viva e lo sta usando. Senza la quarta prova, il
10/08/2026 `faro` avrebbe proposto di chiudere un server sulla porta 8777 che tre sessioni
aperte da mezz'ora stavano usando. Quello che fallisce solo la quarta prova non compare
fra gli orfani: torna fra i servizi, con scritto accanto perché.

La lista viene ricalcolata nel momento in cui `reap --esegui` parte, e mai presa da una
schermata di prima: un pid stampato dieci minuti fa può essere stato riusato da un altro
processo, ed è esattamente così che uno strumento di pulizia uccide la cosa sbagliata.

Il ragionamento dietro ogni prova, e cosa succede se la togli, sta in
[docs/four-tests.md](docs/four-tests.md), in inglese.

## Un job pianificato non si data mai dal suo log

La prima versione di faro decideva se un job pianificato stesse bene dall'orario di
modifica del suo log. Due job su questa macchina sembravano rotti così e non lo erano:
`dev.stiva.ccd-percorsi` parte ogni minuto e aveva **1083 esecuzioni** contro un log
fermo da **quattordici ore**, e `it.nerln.vesuvius-formwatch` aveva uno stderr vuoto di
cinque giorni prima ed era in realtà partito tre ore prima.

Un log viene scritto quando un job ha qualcosa da dire, che non è la stessa cosa di
quando è partito. `launchctl print` conta le esecuzioni e dà l'ultimo codice di uscita,
ed è quello che faro mostra. Né `launchctl list` né `launchctl print` danno una data,
quindi faro non dichiara mai di sapere quando un job pianificato è partito l'ultima
volta. La cosa onesta che può dire è quante volte.

## Gli orari che faro non può leggere

Di un task pianificato di Claude Code, su disco c'è solo il prompt. La riga cron sta
dentro l'applicazione. `faro` lo dice invece di inventarselo, e una sessione che ha lo
strumento `scheduled-tasks` può passargliela una volta:

```bash
faro pianifica --importa lista.json     # l'uscita di list_scheduled_tasks
faro pianifica                          # cosa si sa adesso
```

Finché non succede, nella colonna dell'orario c'è scritto `orario noto solo all'app`.

## La stessa plancia nel browser

```bash
faro gui
```

Sta in primo piano, apre il browser, e muore con ctrl-c o con il terminale che lo ospita.
Nessun fork, nessun plist, nessun riavvio, nessun file scritto. Se quel processo se ne
va, di faro non resta niente in esecuzione.

La pagina è un file solo, con il CSS e il JS dentro: niente CDN, niente font esterni,
niente librerie. Funziona identica con la rete staccata, che è anche il momento in cui
uno guarda cosa sta girando.

Quasi tutto quel file esiste per un problema solo. Una pagina web qualunque, aperta in
un'altra scheda, può fare richieste a 127.0.0.1, e legarsi al localhost non è una difesa:
è solo un indirizzo. Una GUI che accetta una POST che chiude processi è una GUI con cui
un sito ostile chiude i tuoi processi senza che tu tocchi niente. Tre muri, e ognuno
regge da solo:

1. **Un gettone casuale per avvio.** Sta nell'URL che faro apre, la pagina se lo mette in
   sessionStorage e lo toglie subito dalla barra, e da lì in poi lo manda in un header su
   ogni chiamata. Un altro sito non può leggerlo: la same-origin policy gli impedisce di
   vedere la nostra pagina e la nostra memoria. Il confronto è a tempo costante.
2. **Origin nella lista, o niente.** Un modulo HTML può mandare una POST cross-site senza
   che il browser chieda permesso, ma non può aggiungere un header, e la sua richiesta
   arriva con l'Origin di chi l'ha mandata. Una fetch che volesse aggiungere l'header
   farebbe scattare la preflight, e qui la preflight riceve 403 e nessuna intestazione
   CORS: il browser si ferma prima di provare.
3. **Host nella lista.** È la difesa contro il DNS rebinding, l'unico attacco in cui il
   browser considera l'aggressore same-origin con noi e quindi può aggiungere header a
   piacere. Un nome che si risolve su 127.0.0.1 arriva comunque con il suo Host, e quel
   Host viene rifiutato.

Le azioni sono un sottoinsieme di quelle della CLI, mai un sovrainsieme: la pagina può
fermare un pid, e un'etichetta launchd va fermata dal terminale. Un bottone in una pagina
che fa `launchctl bootout` è potere che qui non serve. Il `reap` della pagina fa prima la
prova e ti mostra quella lista esatta, prima che venga chiuso qualcosa.

E la pagina non riscrive le quattro prove. Le sue azioni chiamano lo stesso `cmd_reap` e
lo stesso `cmd_stop` che gira la CLI, e ne catturano l'uscita. Una GUI con la sua copia
delle prove è una GUI che un giorno chiude quello che la CLI protegge.

## Dirlo una volta sola, e solo se conta

```bash
faro annuncia --prova    # dice cosa direbbe, senza notificare niente
faro annuncia            # una notifica di macOS, solo se c'è qualcosa da dire
```

Due regole, e sono tutto il progetto di quel file:

**Se non c'è niente da dire, si tace.** Una notifica che arriva sempre è una notifica che
si impara a ignorare, e da quel momento non serve più a niente nemmeno quando dice una
cosa vera. La risposta vuota è il caso normale.

**Dice, e basta.** Non uccide niente, non propone di farlo da solo, non apre niente. La
decisione resta a chi legge.

Il giudizio sta in una funzione sola, condivisa fra la notifica e la fascia rossa della
GUI, così la pagina e la notifica non possono un domani dire il contrario l'una
dell'altra. Il testo passa per argv di `osascript` e mai dentro il sorgente AppleScript:
il nome di un processo arriva da un plist o da una riga di comando, cioè da dato che faro
non controlla, e concatenarlo in uno script sarebbe il modo più comodo di far eseguire
qualcosa a una macchina che stava soltanto guardando.

## Installazione

Python 3, niente altro.

```bash
git clone https://github.com/nerln/faro.git ~/dev/faro
ln -s ~/dev/faro/bin/faro ~/.local/bin/faro
```

Solo macOS. Legge `ps`, `lsof`, `launchctl`, `vm_stat` e `sysctl`, e dà per scontato
launchd. Su qualunque altra cosa dovrebbe essere un programma diverso.

## Test

```bash
python3 tools/prova.py
```

53 controlli, meno di un secondo, nessuna dipendenza e nessun processo ucciso. Quelli che
contano sono gli `Orfani`: è l'unico punto di faro in cui un errore di lettura diventa un
processo morto. Ognuna delle quattro prove ha un caso che la toglie e verifica che il
processo smetta di essere un candidato, e la GUI ha i casi per il gettone, l'Origin,
l'Host, la preflight e l'assenza di qualunque richiesta di rete nella pagina.

## In famiglia

`rada` conta la memoria, `plancia` conta il lavoro, `faro` conta i processi. Nessuno dei
tre sa delle cose degli altri, e `faro` li legge tutti dalla loro fonte senza chiedergli
niente: se `faro` sparisce, `rada` e `plancia` non se ne accorgono.

## Licenza

MIT. Vedi [LICENSE](LICENSE).
