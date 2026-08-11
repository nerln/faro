"""La stessa plancia, per chi in quel momento non vuole aprire un terminale.

`faro gui` sta in primo piano, apre il browser, e muore con ctrl-c o con il
terminale che lo ospita. Non e' un demone e non deve diventarlo (CLAUDE.md,
invariante 1): niente fork, niente plist, niente riavvio, nessun file scritto.
Se questo processo se ne va, di faro non resta niente in esecuzione.

## Perche' questo file e' quasi tutto sicurezza

Una pagina web qualunque, aperta in un'altra scheda, puo' fare richieste a
127.0.0.1. Legarsi al localhost non e' una difesa: e' solo un indirizzo. Se
questa GUI accettasse una POST che chiude processi, un sito ostile potrebbe
chiudere i processi di Eugenio senza che lui tocchi niente, e faro sarebbe
passato dall'essere lo strumento che gli mostra i danni all'essere il danno.

Tre muri, e ognuno regge da solo:

1. **Un gettone casuale per avvio.** Sta nell'URL che apriamo, la pagina se lo
   mette in sessionStorage e lo toglie subito dalla barra, e da li' in poi lo
   manda in un header su ogni chiamata. Un altro sito non puo' leggerlo: la
   same-origin policy gli impedisce di vedere la nostra pagina e la nostra
   memoria. Il confronto e' a tempo costante.
2. **Origin nella lista, o niente.** Un modulo HTML puo' mandare una POST
   cross-site senza che il browser chieda permesso, ma non puo' aggiungere un
   header, e la sua richiesta arriva con l'Origin di chi l'ha mandata. Una
   fetch che volesse aggiungere l'header farebbe scattare la preflight, e qui
   la preflight riceve 403 e nessuna intestazione CORS: il browser si ferma
   prima di provare.
3. **Host nella lista.** E' la difesa contro il DNS rebinding, l'unico attacco
   in cui il browser considera l'aggressore same-origin con noi e quindi puo'
   aggiungere header a piacere. Un nome che si risolve su 127.0.0.1 arriva
   comunque con il suo Host, e qui viene rifiutato.

Le azioni sono un sottoinsieme di quelle della CLI, mai un sovrainsieme:
`ferma` accetta solo un pid, e un'etichetta launchd va fermata dal terminale.
Un bottone in una pagina che fa `launchctl bootout` e' potere che non serve
qui.

## Perche' non riscrive le quattro prove

Le azioni chiamano `cmd_reap` e `cmd_stop` di `bin/faro`, gli stessi che gira
la CLI, e ne catturano l'uscita. La lista degli orfani viene ricalcolata li'
dentro come sempre (invariante 4), la catena degli antenati resta esclusa
(invariante 5), e le quattro prove restano scritte in un posto solo. Se un
domani una prova cambia, cambia anche qui: una GUI con la sua copia delle
prove e' una GUI che un giorno chiude quello che la CLI protegge.
"""

import contextlib
import hmac
import http.server
import importlib.machinery
import importlib.util
import io
import json
import os
import re
import secrets
import sys
import threading
import time
import webbrowser
from argparse import Namespace

from . import annuncio, board, inventory

HERE = os.path.dirname(os.path.abspath(__file__))
# `faro/web/` sta accanto a `faro/web.py` e non e' un pacchetto: e' una cartella
# di asset. Python preferisce il modulo alla cartella senza `__init__.py`, ed e'
# per questo che `import faro.web` prende questo file. Mettere un `__init__.py`
# li' dentro rovescerebbe la cosa e romperebbe la gui.
ASSETS = os.path.join(HERE, "web")

HEADER_GETTONE = "X-Faro-Token"

# Il piu' vecchio snapshot che una richiesta puo' ricevere senza rileggere la
# macchina. La pagina si aggiorna ogni cinque secondi e le schede aperte
# possono essere piu' di una: senza questo, tre schede sono tre `ps` e tre
# `lsof` ogni cinque secondi, e la plancia diventa la ragione per cui il Mac
# rallenta (invariante 7). Sta in memoria e muore con il processo.
ETA_MASSIMA_LETTURA = 2.0


# ------------------------------------------------------------------ la pagina

def _asset(nome):
    with open(os.path.join(ASSETS, nome), encoding="utf-8") as f:
        return f.read()


def pagina():
    """L'unica pagina, con css e js dentro.

    Gli asset stanno in `faro/web/` come file separati perche' si modificano
    meglio, ma escono di qui come una cosa sola: niente CDN, niente font
    esterni, niente librerie. Deve funzionare identica con la rete staccata,
    che e' anche il momento in cui uno guarda cosa sta girando.
    """
    html = _asset("index.html")
    html = html.replace('<link rel="stylesheet" href="stile.css">',
                        "<style>\n" + _asset("stile.css") + "\n</style>")
    html = html.replace('<script src="app.js"></script>',
                        "<script>\n" + _asset("app.js") + "\n</script>")
    return html


# -------------------------------------------------------------------- lo stato

def _strati():
    """Nome e spiegazione dei sei strati, prese dalla plancia del terminale.

    Le parole sono quelle di board.TITLES e non una seconda versione scritta
    qui: due schermate che chiamano la stessa cosa in due modi diversi sono
    due schermate da imparare.
    """
    out = []
    for nome in board.ORDER:
        titolo, _, spiega = board.TITLES[nome].partition("  ")
        out.append({"nome": titolo.strip(), "spiega": spiega.strip()})
    return out


def _riga_umana(r):
    d = dict(r)
    d["rss_umano"] = inventory._human_bytes(r["rss"]) if r["rss"] else ""
    d["eta_umana"] = inventory._human_age(r["eta"]) if r["eta"] else ""
    # Solo un pid si puo' fermare da qui. Le etichette launchd restano
    # nell'azione scritta, da copiare nel terminale.
    #
    # E non basta avere un pid: i servizi dello strato `permanenti` sono tenuti
    # in vita da launchd, e `cmd_stop` rifiuta i loro pid perche' ucciderli non
    # li ferma, li fa ripartire. Disegnare il bottone lo stesso significa
    # mettere sulla pagina un comando che non funziona mai proprio sui servizi
    # che contano, e insegnare che i bottoni a volte non fanno niente.
    d["fermabile"] = bool(r.get("pid")) and r.get("strato") != "permanenti"
    return d


def stato(snap=None):
    """Quello che la pagina disegna: uno snapshot piu' le parole per dirlo."""
    snap = snap if snap is not None else inventory.snapshot()
    mem = snap["memoria"]
    righe = [_riga_umana(r) for r in snap["righe"]]
    conteggi = {k: sum(1 for r in righe if r["strato"] == k) for k in board.ORDER}
    return {
        "ts": snap["ts"],
        "memoria": {
            **mem,
            "usata_umana": inventory._human_bytes(mem["used"]),
            "totale_umana": inventory._human_bytes(mem["total"]),
            "compressa_umana": inventory._human_bytes(mem["compressed"]),
            "swap_umano": inventory._human_bytes(mem["swap_used"]),
            "swap_totale_umano": inventory._human_bytes(mem["swap_total"]),
            "swap_allarme": mem["swap_used"] > annuncio.SWAP_ALLARME,
            "swap_attenzione": mem["swap_used"] > annuncio.SWAP_ATTENZIONE,
        },
        "strati": _strati(),
        "righe": righe,
        "conteggi": conteggi,
        "rss_orfani": inventory._human_bytes(
            sum(r["rss"] for r in righe if r["strato"] == "orfani")),
        # Lo stesso giudizio che manda le notifiche di `faro annuncia`.
        "notizie": annuncio.valuta(snap),
    }


class _Letture:
    """Una lettura sola condivisa fra le schede aperte, per pochi secondi."""

    def __init__(self):
        self._lock = threading.Lock()
        self._quando = 0.0
        self._dato = None

    def stato(self):
        with self._lock:
            if self._dato is None or (time.time() - self._quando) > ETA_MASSIMA_LETTURA:
                self._dato = stato()
                self._quando = time.time()
            return self._dato

    def scade(self):
        """Dopo un'azione la lettura di prima non vale piu' niente."""
        with self._lock:
            self._dato = None


# -------------------------------------------------------------------- azioni

def _cli_modulo():
    """`bin/faro` come modulo, quando non ce lo passa gia' lui.

    Serve ai test e a chi importa `faro.web` da solo. Non ha estensione .py,
    quindi va caricato per percorso: e' comunque meglio che riscrivere qui la
    logica di reap.
    """
    percorso = os.path.join(os.path.dirname(HERE), "bin", "faro")
    spec = importlib.util.spec_from_loader(
        "faro_cli", importlib.machinery.SourceFileLoader("faro_cli", percorso))
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


# Le azioni si fanno una alla volta: catturano stdout, che e' del processo e
# non del thread, e due reap in parallelo sarebbero due liste calcolate sullo
# stesso momento.
_UNA_ALLA_VOLTA = threading.Lock()


def _esegui(funzione, **campi):
    buffer = io.StringIO()
    with _UNA_ALLA_VOLTA:
        with contextlib.redirect_stdout(buffer):
            codice = funzione(Namespace(**campi))
    return {"codice": codice, "testo": buffer.getvalue().rstrip()}


def azione_reap(cli, esegui):
    """La stessa `faro reap`, con o senza --esegui."""
    return _esegui(cli.cmd_reap, esegui=bool(esegui), piu_vecchi_di=0)


def azione_ferma(cli, pid):
    """La stessa `faro stop <pid>`, e solo su un pid."""
    return _esegui(cli.cmd_stop, cosa=str(int(pid)), per_sempre=False)


def azione_notte(cli, esegui):
    """La stessa `faro notte`, con o senza --esegui.

    Come per reap, la GUI chiama la funzione della CLI invece di rifare il
    lavoro: cosi' l'invariante 0, quella che dice che faro non apre mai niente,
    sta scritta in un posto solo e non puo' divergere fra le due strade.
    """
    return _esegui(cli.cmd_notte, esegui=bool(esegui))


# ------------------------------------------------------------------ il server

_CONTROLLO = re.compile(r"[\x00-\x1f\x7f]")


def _pulito(testo, quanto=70):
    """Testo di ignoti pronto per essere stampato su un terminale."""
    return _CONTROLLO.sub("?", str(testo))[:quanto]


class _Manico(http.server.BaseHTTPRequestHandler):
    server_version = "faro"
    sys_version = ""
    protocol_version = "HTTP/1.1"

    # popolati da crea_server
    gettone = ""
    cli = None
    letture = None
    ammessi = ()

    # -- muri

    def _origine_buona(self):
        origine = self.headers.get("Origin")
        if origine is None:
            # Le GET della pagina e alcune fetch same-origin non lo mandano.
            # Il gettone resta l'unica cosa che serve davvero.
            return True
        return origine in self.ammessi

    def _host_buono(self):
        host = (self.headers.get("Host") or "").strip()
        return host in {o.split("//", 1)[1] for o in self.ammessi}

    def _gettone_buono(self):
        # Due difetti trovati dalla revisione avversariale dell'11/08/2026, e
        # tutti e due qui dentro.
        #
        # Il primo: la classe base ha `gettone = ""`, e con l'intestazione
        # assente il confronto era vero. Oggi non era sfruttabile perche'
        # `ammessi = ()` faceva fallire prima il muro dell'Host, ma la difesa
        # reggeva su un attributo diverso da quello che deve reggerla. Un
        # gettone vuoto adesso e' un rifiuto, e basta.
        #
        # Il secondo: `hmac.compare_digest` solleva TypeError se una delle due
        # stringhe ha caratteri fuori dall'ASCII, e le intestazioni HTTP
        # arrivano decodificate in latin-1. Un solo byte sopra 127 faceva
        # morire il thread senza risposta e con una traccia nel terminale.
        atteso = self.gettone
        if not atteso:
            return False
        dato = self.headers.get(HEADER_GETTONE) or ""
        try:
            return hmac.compare_digest(dato.encode("utf-8", "surrogateescape"),
                                       atteso.encode("utf-8"))
        except Exception:
            return False

    def _permesso(self):
        """403 con un motivo, o None se puo' passare."""
        if not self._host_buono():
            return "host " + repr(self.headers.get("Host"))
        if not self._origine_buona():
            return "origin " + repr(self.headers.get("Origin"))
        if not self._gettone_buono():
            return "gettone assente o sbagliato"
        return None

    # -- risposte

    def version_string(self):
        return self.server_version

    def _manda(self, codice, corpo, tipo="application/json; charset=utf-8", chiudi=False):
        dati = corpo.encode("utf-8") if isinstance(corpo, str) else corpo
        self.send_response(codice)
        if chiudi:
            # Una richiesta rifiutata ha ancora il suo corpo nel socket, e noi
            # non lo leggiamo apposta: non si legge il corpo di chi non e'
            # autorizzato. Tenendo aperta la connessione quei byte
            # diventerebbero la richiesta dopo, cioe' righe di spazzatura nel
            # terminale di Eugenio. Si chiude e basta.
            self.close_connection = True
            self.send_header("Connection", "close")
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(dati)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        # Nessuna intestazione CORS, mai: e' quella la difesa.
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(dati)

    def _json(self, codice, oggetto, chiudi=False):
        self._manda(codice, json.dumps(oggetto, ensure_ascii=False), chiudi=chiudi)

    def _nega(self, motivo):
        # Il percorso lo sceglie chi chiama, e chi chiama qui e' per ipotesi
        # qualcuno che non doveva: passa per _pulito, se no una pagina ostile
        # scrive quello che vuole nel terminale di Eugenio con una sequenza di
        # escape (CLAUDE.md, invariante 8: e' dato, non istruzione).
        # `motivo` contiene il repr di un Host o di un Origin, cioe' testo di
        # chi ha bussato, e passava al formato senza tetto: un Host da 60 KB
        # riempiva il terminale, e succedeva prima di qualunque autorizzazione.
        self.log_error("respinta una %s su %s: %s",
                       _pulito(self.command), _pulito(self.path),
                       _pulito(motivo, 120))
        self._json(403, {"errore": "non autorizzato"}, chiudi=True)

    # -- rotte

    def do_GET(self):
        percorso = self.path.split("?", 1)[0]
        if percorso == "/":
            # La pagina non contiene dati e non serve a niente senza gettone.
            if not self._host_buono():
                return self._nega("host " + repr(self.headers.get("Host")))
            return self._manda(200, pagina(), "text/html; charset=utf-8")
        if percorso == "/api/stato":
            motivo = self._permesso()
            if motivo:
                return self._nega(motivo)
            return self._json(200, self.letture.stato())
        self._json(404, {"errore": "non c'e'"}, chiudi=True)

    def do_POST(self):
        percorso = self.path.split("?", 1)[0]
        motivo = self._permesso()
        if motivo:
            return self._nega(motivo)

        try:
            lunghezza = int(self.headers.get("Content-Length") or 0)
            corpo = json.loads(self.rfile.read(lunghezza) or b"{}")
            if not isinstance(corpo, dict):
                raise ValueError("mi aspetto un oggetto")
        except Exception as e:
            return self._json(400, {"errore": f"corpo illeggibile: {e}"}, chiudi=True)

        if percorso == "/api/reap":
            # `esegui` decide fra una prova e la chiusura vera dei processi, e
            # decideva con la verita' di Python su un json non validato: la
            # stringa "false", la stringa "0" e la lista vuota di un altro
            # linguaggio chiudevano davvero. L'unica cosa che vale come si' e'
            # il booleano vero.
            esegui = corpo.get("esegui") is True
            esito = azione_reap(self.cli, esegui)
            if esegui:
                self.letture.scade()
                self.log_error("chiusi gli orfani dalla gui")
            return self._json(200, esito)

        if percorso == "/api/notte":
            # Stessa regola di reap: solo il booleano vero vale come si'.
            esegui = corpo.get("esegui") is True
            esito = azione_notte(self.cli, esegui)
            if esegui:
                self.letture.scade()
                self.log_error("eseguita la notte dalla gui")
            return self._json(200, esito)

        if percorso == "/api/ferma":
            pid = corpo.get("pid")
            if not isinstance(pid, int) or pid <= 1:
                return self._json(400, {"errore": "serve un pid"}, chiudi=True)
            esito = azione_ferma(self.cli, pid)
            self.letture.scade()
            self.log_error("chiesto dalla gui di fermare il pid %d", pid)
            return self._json(200, esito)

        self._json(404, {"errore": "non c'e'"}, chiudi=True)

    def do_OPTIONS(self):
        # Nessuna preflight passa: e' il muro che ferma le fetch cross-site.
        self._nega("preflight")

    def log_message(self, formato, *args):
        # Le richieste normali sono una ogni cinque secondi per scheda e non
        # dicono niente. Restano solo i rifiuti e le azioni, che passano da
        # log_error e finiscono qui sotto.
        pass

    def log_error(self, formato, *args):
        sys.stdout.write("       " + (formato % args) + "\n")
        sys.stdout.flush()


class _Server(http.server.ThreadingHTTPServer):
    daemon_threads = True


def crea_server(cli=None, porta=0, indirizzo="127.0.0.1"):
    """Il server pronto ma fermo, con il suo gettone. Separato per i test.

    Il legame fra gettone e server sta in una sottoclasse creata qui e non su
    `_Manico`: due server nello stesso processo (i test ne fanno uno per
    prova) non devono poter usare il gettone l'uno dell'altro.
    """
    cli = cli if cli is not None else _cli_modulo()
    gettone = secrets.token_urlsafe(32)
    # Il socket va aperto prima di sapere la porta, e la porta serve per la
    # lista degli Origin ammessi: quindi prima si lega, poi si lega il manico.
    server = _Server((indirizzo, porta), _Manico)
    vera = server.server_address[1]
    server.RequestHandlerClass = type("_ManicoLegato", (_Manico,), {
        "gettone": gettone,
        "cli": cli,
        "letture": _Letture(),
        "ammessi": (f"http://127.0.0.1:{vera}", f"http://localhost:{vera}"),
    })
    return server, gettone


def serve(cli=None, porta=0, apri=True):
    """Sta qui davanti finche' non gli dici di andarsene."""
    if not os.path.isdir(ASSETS):
        print(f"manca la cartella degli asset: {ASSETS}")
        return 1
    server, gettone = crea_server(cli=cli, porta=porta)
    vera = server.server_address[1]
    url = f"http://127.0.0.1:{vera}/?t={gettone}"

    # flush: con lo stdout su una pipe python bufferizza a blocchi, e chi ha
    # avviato faro per leggergli l'indirizzo resterebbe fermo ad aspettarlo.
    print(f"faro gui   {url}", flush=True)
    print("           in primo piano: se chiudi questo terminale, la gui muore con lui.",
          flush=True)
    print("           ctrl-c per uscire.", flush=True)
    if apri:
        # In un thread: `open` su macOS torna subito, ma un browser che non
        # parte non deve poter tenere fermo il server.
        threading.Thread(target=webbrowser.open, args=(url,), daemon=True).start()
    try:
        server.serve_forever(poll_interval=0.3)
    except KeyboardInterrupt:
        print("\n           chiusa. non e' rimasto niente in esecuzione.")
    finally:
        server.shutdown()
        server.server_close()
    return 0


# Usato solo dai test: dice se una stringa somiglia a una richiesta di rete.
_ESTERNO = re.compile(r"""(?:src|href)\s*=\s*["']https?://|@import|//cdn\.""", re.I)
