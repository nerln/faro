# Annuncio di faro

Testi pronti. Non sono stati pubblicati da nessuna parte. La lista "prima di pubblicare"
in fondo dice cosa deve essere vero prima che questi testi possano uscire.

**Regola del lettore** (positioning.md, 2 agosto 2026): scrive per qualcuno che non sa
cosa sta leggendo. Niente nomi di librerie, niente numeri che hanno bisogno di una
definizione, niente righe di comando. Per questo nei post non compaiono né la parola
swap, né 3,4 GB, né la porta 8777: sono numeri veri che in un post non significano
niente. Stanno nel README e nel sito, dove il lettore è arrivato apposta.

**Angolo scelto:** Admission. È quello che il posizionamento indica come più adatto a
questa voce, ed è anche l'unico modo onesto di raccontare `faro`, perché la parte
interessante è un errore corretto.

---

## X, versione inglese (quella che va pubblicata)

Il profilo ha la bio in inglese e i repository pubblici sono in inglese. Su X esce
questa.

> Three programs I never started were running.
> The oldest for fifteen hours.
> My coding assistants had left them behind when their windows closed, and nothing on
> the machine was counting.
> faro shows all of them in one place.

## X, versione italiana

> Tre programmi accesi che non avevo acceso io.
> Il più vecchio da quindici ore.
> Li avevano lasciati lì gli assistenti che scrivono codice per me, chiudendosi. Nessuno
> teneva il conto.
> faro li mostra tutti in un posto solo.

## Le due varianti scartate, e perché

Il metodo dice di scriverne diverse e tenerne una. Queste restano scritte perché se la
prima non funziona si riparte da qui, non da zero.

**Variante contrarian.**
> A slow laptop is usually not a slow laptop.
> Mine had three programs running that nobody had asked for, one of them since the day
> before.
> faro is the command that finds them.

Scartata perché la prima riga insegna qualcosa invece di raccontare qualcosa, e chi non
ha il problema scorre.

**Variante numerica.**
> Six places on my laptop can start something on their own.
> Six different ways to look at them. No way to look at them together.
> faro is the seventh place, and it is the one that shows the other six.

Scartata perché "sei posti" chiede al lettore di fidarsi di una lista che non vede, e
perché "il settimo posto" è una battuta che funziona solo per chi ha già capito.

---

## LinkedIn, versione italiana (quella che va pubblicata)

Su LinkedIn il pubblico è in buona parte italiano ed è quello che conosce lui di
persona. Esce questa.

> **Tre programmi accesi che non avevo acceso io.**
>
> Sul mio portatile lavorano insieme fino a otto assistenti che scrivono codice. Ognuno
> apre la sua finestra, fa il suo lavoro, e ogni tanto avvia qualcosa che resta acceso:
> un piccolo server per guardare una pagina, un processo per provare una cosa al volo.
> Quando la finestra si chiude, quella roba resta lì.
>
> Ho scritto un comando che li mette tutti sulla stessa schermata. Al primo giro ne ha
> trovati tre, il più vecchio acceso da quindici ore, su una macchina che da giorni
> andava piano senza che si capisse perché.
>
> Nessuno degli assistenti aveva sbagliato. Ognuno vede solo quello che ha fatto lui. È
> che nessuno teneva il conto.
>
> La cosa che ho imparato scrivendolo non è tecnica. La prima versione dello strumento
> proponeva di spegnere un programma che in quel momento tre finestre aperte stavano
> usando. Non l'ha trovato un test. L'ha trovato una domanda che mi sono fatto guardando
> lo schermo: essere rimasto acceso vuol dire per forza essere di troppo? No. Adesso
> prima di proporre di spegnere qualcosa ci sono quattro controlli invece di tre, e il
> quarto è quello che chiede se per caso serve ancora a qualcuno.
>
> C'è un secondo errore che ho corretto e che mi piace di più del primo. Lo strumento
> diceva che un automatismo era fermo da cinque giorni. Era partito tre ore prima. Stavo
> indovinando la data dal suo diario invece di chiedere al sistema quante volte l'aveva
> avviato davvero: 1083 volte. Ho tolto una deduzione e ci ho messo una lettura.
>
> faro non spegne niente da solo, non gira quando non lo stai guardando, e non tiene
> nessun archivio. Mostra, e la decisione resta a chi legge.

## LinkedIn, versione inglese

Da usare se e quando il post va anche fuori dalla rete italiana. Stesso contenuto, stessa
struttura.

> **Three programs I never started were running on my laptop.**
>
> Up to eight coding assistants work on this machine at the same time. Each one opens its
> own window, does its own job, and every so often starts something that stays up: a
> small server to look at a page, a process to try something quickly. When the window
> closes, that thing keeps running.
>
> I wrote a command that puts all of them on one screen. On the first run it found three,
> the oldest up for fifteen hours, on a machine that had been slow for days without
> anybody knowing why.
>
> None of the assistants had done anything wrong. Each one only sees its own work. It is
> that nobody was counting.
>
> What I learned writing it was not technical. The first version offered to shut down a
> program that three open windows were using right then. No test found that. A question
> found it, one I asked myself looking at the screen: does left running have to mean
> unwanted? It does not. Now there are four checks before anything is proposed for
> shutdown instead of three, and the fourth one asks whether somebody still needs it.
>
> There is a second mistake I fixed, and I like it better than the first. The tool said
> one of my automations had been dead for five days. It had run three hours earlier. I
> was guessing the date from its diary instead of asking the system how many times it had
> actually started: 1083 times. I replaced a guess with a reading.
>
> faro shuts nothing down on its own, does not run when you are not looking at it, and
> keeps no archive. It shows, and the decision stays with the person reading.

---

## Cosa c'è dentro e non è nei post

Sta qui perché serve nelle risposte ai commenti, non nel post.

- Il primo giro, il 10/08/2026: tre server di anteprima orfani su tre porte diverse, il
  più vecchio da quindici ore, 3,4 GB di swap su 5, cinque sessioni vive.
- Il programma che la prima versione avrebbe spento stava sulla porta 8777, e tre
  sessioni aperte da mezz'ora lo stavano usando.
- Le quattro prove: genitore morto, non supervisionato dal sistema, avviato da una
  sessione, e nessuno lo sta usando. Ogni prova ha un test che la toglie e verifica che
  il processo smetta di essere un candidato.
- 53 test, nessuna dipendenza, meno di un secondo. Verificati verdi l'11/08/2026.
- Sei famiglie di cose che partono da sole, e non sono una tassonomia inventata: sono i
  sei posti trovati guardando.

## Prima di pubblicare

Niente di questo è stato fatto, e finché non è fatto i post promettono una cosa che il
lettore non trova.

1. **`faro` non è pubblicato.** Tre commit in locale e nessun remoto configurato. Un post
   senza link è un post buttato.
2. **Manca il README in inglese.** Oggi `README.md` è in italiano. Come gli altri repo
   servono `README.md` in inglese e `README.it.md`, e vanno passati da
   `python3 ~/dev/scriba/tools/stylecheck.py`.
3. **Il README non nomina due comandi che esistono**, `faro gui` e `faro annuncia`. Chi
   arriva dal post e prova la GUI non la trova scritta da nessuna parte.
4. **Nessuna data nei post, ed è voluto.** La misura è del 10/08/2026, che era un lunedì.
   Un giorno della settimana in un post che esce dopo diventa falso da solo, quindi il
   testo dice solo cosa è successo. La data sta nel README, dove non invecchia.
5. **Passare i due post da `tools/postcheck.py`** della skill social: grado di lettura e
   termini tecnici segnalati. Un post sopra il grado 9 non esce.
6. **Farli leggere a due persone non tecniche** e chiedere, con parole loro, cosa fa la
   cosa. Dove sbagliano, sbaglia il post.
