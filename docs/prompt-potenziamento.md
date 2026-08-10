# Il prompt da dare alle sessioni che hanno costruito gli automatismi

Sei automatismi, sei sessioni che li hanno scritti. Nessuna di quelle sessioni sapeva
delle altre, ed è per questo che nessuna ha reso il proprio processo visibile da fuori.
Il prompt qui sotto va incollato in ognuna, cambiando solo le due righe in cima.

Riprendi una sessione con:

```bash
claude --resume <id>
```

## Le sessioni

| automatismo | sessione | cartella | come si riconosce |
|---|---|---|---|
| **rada** (gate + coda) | `ea03b387-96b3-4d67-9313-04e3d9d5eca5` | `~/Library/CloudStorage/.../Il mio Drive` | è la sessione Vesuvius, dentro cui è nata rada |
| **rada** (seconda) | `3305375d-98e8-4de4-8b6e-9f3eeb0661ce` | idem | "Creami una app che mi gestisca tutte queste gestioni" |
| **plancia** (server + hook) | `3305375d-98e8-4de4-8b6e-9f3eeb0661ce` | idem | stessa sessione: plancia e rada sono nate insieme |
| **stiva ccd-percorsi** + `drive-root-guard` | `022edbb8-bed3-4ab4-9e30-6af82ebf524a` | idem | "Considera il mio intero google drive" |
| **vesuvius-formwatch** | `24aa07f2-c3b8-4310-84f4-118d435754b7` | idem | la sessione Vesuvius dell'8 agosto |
| **x-account-daily-check** | `9d32bf8e-68ef-4931-b7c7-739aaf708616` | idem | "cerca una skill esperta in social media" |
| **gh-dorada-actualizar** | `b0cb8ada-709d-4150-8076-f41057b03d9f` | `~/dev/kart-highlights` | il predittore del Gran Hermano |

---

## Il prompt

> **L'automatismo di cui parlo è: `<NOME>`** (per esempio `com.plancia.server`,
> `dev.stiva.ccd-percorsi`, `x-account-daily-check`, il gate di rada).
>
> Da oggi c'è un posto solo da cui guardo tutto quello che gira in background su questo
> Mac: `faro`, in `~/dev/faro`, installato come `~/.local/bin/faro`. Leggi prima
> `~/dev/faro/README.md` e `~/dev/faro/CLAUDE.md`, poi lancia `faro` e guarda come
> compare la cosa che hai costruito tu.
>
> Il problema che sto risolvendo: ho sei famiglie di processi in background, scritte in
> sessioni diverse che non si conoscevano, e finora non c'era nessun punto da cui
> vederle insieme. Il risultato è che la macchina va in swap e non so chi la sta
> consumando, che dei task pianificati spendono token da soli senza che me ne accorga, e
> che restano in giro server di sessioni chiuse che tengono porte occupate.
>
> Voglio che tu renda il tuo automatismo leggibile da `faro`. Nell'ordine:
>
> 1. **Guarda com'è adesso.** Lancia `faro` e trova la riga del tuo automatismo. Se non
>    c'è, quello è il primo difetto: un automatismo che non compare in `faro` è un
>    automatismo che fra un mese non ricorderò di avere.
>
> 2. **Se non compare, o compare male, aggiusta `faro`, non il tuo processo.** La logica
>    sta in `~/dev/faro/faro/inventory.py`, un livello per funzione. Rispetta le dieci
>    invarianti in `~/dev/faro/CLAUDE.md` (le prime due: nessun demone, nessuno stato che
>    conti) e lascia verde `python3 ~/dev/faro/tools/prova.py`, aggiungendo un test per
>    quello che hai cambiato.
>
> 3. **Dammi un log con una data.** Se sei un LaunchAgent, devi avere `StandardOutPath`
>    e `StandardErrorPath` su file veri: senza, `faro` non può dire quando sei girato
>    l'ultima volta, e la colonna resta vuota. Se sei già a posto, dimmelo e non toccare
>    niente.
>
> 4. **Dimmi cosa costi, con un numero misurato e non stimato.** Quanta memoria tieni
>    quando giri (`ps -o rss=`), quanto duri, e se sei un task pianificato di Claude Code
>    quanti token spendi a ogni scatto: quello lo leggi dal transcript dell'ultima
>    esecuzione, non dalla tua impressione. Scrivilo nel README del tuo progetto, sotto
>    una voce che si chiami "cosa costa".
>
> 5. **Esci in silenzio quando non c'è niente da fare.** Vale per i task su orologio.
>    Se scatti due volte a settimana e la maggior parte delle volte non c'è lavoro, il
>    primo controllo deve chiudere la sessione subito. Verifica che sia davvero così
>    rileggendo il tuo prompt in `~/.claude/scheduled-tasks/<nome>/SKILL.md`.
>
> 6. **Non lasciare processi dietro di te.** Se avvii un server (di anteprima, di
>    sviluppo, un MCP), deve morire con la sessione o essere un LaunchAgent
>    supervisionato. La via di mezzo è quella che mi ha lasciato tre `http.server` su tre
>    porte, il più vecchio da quindici ore. Se il tuo processo ne avvia uno, dimmi quale
>    delle due strade prende.
>
> 7. **Una riga per il nostromo.** C'è un agente dedicato a questa gestione, definito in
>    `~/.claude/agents/nostromo.md`. Se il tuo automatismo ha un modo di fallire che non
>    si vede da `faro` (una credenziale che scade, un sito che cambia forma, una quota),
>    scrivilo lì sotto forma di "cosa guardare", in una riga sola.
>
> Non riscrivere quello che funziona e non fare refactoring. Se secondo te un pezzo del
> tuo automatismo non dovrebbe esistere più, dimmelo invece di toglierlo.
>
> Alla fine rispondi con: cosa compariva in `faro` prima, cosa compare adesso, il numero
> del punto 4, e le cose che hai lasciato come stavano.

---

## Un dettaglio sull'ordine

Fai per prima `022edbb8` (stiva). È l'unica che tocca `~/.claude/hooks/drive-root-guard.py`,
cioè un hook che gira a ogni comando di ogni sessione: se qualcosa lì è rotto, lo è per
tutte le altre.

Le due sessioni di rada sono grosse (24 e 64 MB di transcript) e riaprirle costa contesto.
Se ti serve solo il gate, `~/dev/rada/CLAUDE.md` ha già dentro le sette invarianti e i
quattro fatti verificati a mano su Claude Code: spesso è più economico partire da lì con
una sessione nuova in `~/dev/rada` che riprendere quelle.
