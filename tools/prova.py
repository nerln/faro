#!/usr/bin/env python3
"""Tests for faro. Run with `python3 tools/prova.py`.

Most of these are about one thing: what `faro reap` is allowed to kill. That
list is the only place where a reading mistake turns into a dead process, so
each of the three conditions has a test that removes it and checks the process
stops being a candidate.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from faro import board, inventory, probe  # noqa: E402


def proc(pid, ppid, command, rss=1024 * 1024, age=3600):
    return {"pid": pid, "ppid": ppid, "rss": rss, "age": age, "command": command}


SCRATCH = probe.SCRATCH_ROOT + "/-Users-x/1111aaaa-2222-3333-4444-555566667777/scratchpad"


class Orfani(unittest.TestCase):
    """The three conditions, one test each for their absence."""

    def base(self):
        procs = {900: proc(900, 1, "python3 -m http.server 8742")}
        loaded = {}
        cwds = {900: SCRATCH}
        ports = {900: [8742]}
        return procs, loaded, cwds, ports

    def test_orphan_is_found(self):
        rows = inventory.orfani(*self.base())
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["pid"], 900)
        self.assertEqual(rows[0]["porte"], [8742])
        self.assertEqual(rows[0]["sessione"], "1111aaaa-2222-3333-4444-555566667777")

    def test_a_young_process_is_a_service_and_not_an_orphan(self):
        """La domanda di Eugenio: orfano vuol dire per forza male? No.

        Una sessione che avvia un server da un comando shell perde subito la
        shell, e il server viene riadottato da launchd mentre la sessione e'
        viva e lo sta usando. `ppid == 1` non prova che la sessione sia morta.
        """
        procs, loaded, cwds, ports = self.base()
        procs[900]["age"] = 13
        rows = inventory.orfani(procs, loaded, cwds, ports)
        self.assertEqual([r["strato"] for r in rows], ["servizi"])
        self.assertIn("too soon", rows[0]["dettaglio"])

    def test_a_session_still_writing_keeps_its_server(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            uuid = "1111aaaa-2222-3333-4444-555566667777"
            proj = "-Users-prova"
            os.makedirs(os.path.join(d, "projects", proj))
            open(os.path.join(d, "projects", proj, uuid + ".jsonl"), "w").close()
            vecchio_claude = inventory.CLAUDE
            inventory.CLAUDE = d
            try:
                procs, loaded, cwds, ports = self.base()
                cwds[900] = f"{probe.SCRATCH_ROOT}/{proj}/{uuid}/scratchpad"
                rows = inventory.orfani(procs, loaded, cwds, ports)
                self.assertEqual([r["strato"] for r in rows], ["servizi"])
                self.assertIn("still writing", rows[0]["dettaglio"])
            finally:
                inventory.CLAUDE = vecchio_claude

    def test_a_live_session_in_the_same_folder_keeps_its_server(self):
        """Il caso che per poco non ha fatto uccidere un server in uso.

        Il server sulla porta 8777 aveva come cartella la radice del Drive, e
        li' dentro c'erano tre sessioni vive aperte da mezz'ora. Fuori da uno
        scratchpad un processo non porta scritto a chi appartiene: lo dice la
        cartella.
        """
        procs, loaded, cwds, ports = self.base()
        drive = "/Users/e/Library/CloudStorage/GoogleDrive-x/Il mio Drive"
        cwds[900] = drive
        rows = inventory.orfani(procs, loaded, cwds, ports, cartelle_vive=[drive])
        self.assertEqual([r["strato"] for r in rows], ["servizi"])
        self.assertIn("live session is working", rows[0]["dettaglio"])

    def test_a_folder_below_a_live_session_counts_too(self):
        procs, loaded, cwds, ports = self.base()
        cwds[900] = "/Users/e/dev/sito/docs"
        rows = inventory.orfani(procs, loaded, cwds, ports,
                                cartelle_vive=["/Users/e/dev/sito"])
        self.assertEqual([r["strato"] for r in rows], ["servizi"])

    def test_a_similar_name_is_not_the_same_folder(self):
        """`/dev/sito-vecchio` non sta dentro `/dev/sito`."""
        procs, loaded, cwds, ports = self.base()
        cwds[900] = "/Users/e/dev/sito-vecchio"
        rows = inventory.orfani(procs, loaded, cwds, ports,
                                cartelle_vive=["/Users/e/dev/sito"])
        self.assertEqual([r["strato"] for r in rows], ["orfani"])

    def test_a_living_parent_saves_it(self):
        procs, loaded, cwds, ports = self.base()
        procs[900]["ppid"] = 500
        self.assertEqual(inventory.orfani(procs, loaded, cwds, ports), [])

    def test_launchd_supervision_saves_it(self):
        """This is the one that protects plancia and stiva."""
        procs, loaded, cwds, ports = self.base()
        loaded = {"com.plancia.server": {"pid": 900, "status": 0}}
        self.assertEqual(inventory.orfani(procs, loaded, cwds, ports), [])

    def test_an_unknown_program_outside_a_scratchpad_is_left_alone(self):
        procs, loaded, cwds, ports = self.base()
        procs[900]["command"] = "/opt/homebrew/bin/postgres -D /usr/local/var/postgres"
        cwds[900] = "/Users/eugenionerelli"
        self.assertEqual(inventory.orfani(procs, loaded, cwds, ports), [])

    def test_a_scratchpad_is_enough_even_for_an_unknown_program(self):
        procs, loaded, cwds, ports = self.base()
        procs[900]["command"] = "./qualcosa-che-nessuno-conosce --serve"
        rows = inventory.orfani(procs, loaded, cwds, ports)
        self.assertEqual(len(rows), 1)


class Sessioni(unittest.TestCase):
    def test_the_wrapper_is_not_counted_as_a_session(self):
        """The app starts claude from claude. Only the leaf is a session."""
        procs = {
            10: proc(10, 1, f"/x/{inventory.CLAUDE_BIN} --wrapper"),
            11: proc(11, 10, f"/x/{inventory.CLAUDE_BIN} --output-format stream-json"),
        }
        live = inventory._live_sessions(procs)
        self.assertEqual([p["pid"] for p in live], [11])

    def test_children_are_attributed_to_their_session(self):
        procs = {
            11: proc(11, 10, f"/x/{inventory.CLAUDE_BIN} --x", rss=100 * 1024 * 1024),
            12: proc(12, 11, "python3 /Users/e/dev/plancia/bin/plancia-mcp",
                     rss=10 * 1024 * 1024),
        }
        rows = inventory.sessioni(procs, {11: "/Users/e/dev/rada"}, {}, set())
        sess = [r for r in rows if r["strato"] == "sessioni"]
        serv = [r for r in rows if r["strato"] == "servizi"]
        self.assertEqual(len(sess), 1)
        self.assertEqual(sess[0]["rss"], 110 * 1024 * 1024)
        self.assertEqual(serv[0]["nome"], "plancia MCP server")

    def test_a_fresh_shell_is_not_a_service(self):
        """Otherwise every board shows the command that drew it."""
        procs = {
            11: proc(11, 10, f"/x/{inventory.CLAUDE_BIN} --x"),
            12: proc(12, 11, "/bin/zsh -c source /tmp/snapshot && faro", age=3),
        }
        rows = inventory.sessioni(procs, {}, {}, set())
        self.assertEqual([r for r in rows if r["strato"] == "servizi"], [])

    def test_an_old_shell_is_a_service_and_is_flagged(self):
        procs = {
            11: proc(11, 10, f"/x/{inventory.CLAUDE_BIN} --x"),
            12: proc(12, 11, "/bin/zsh -c ./addestra.sh", age=7200),
        }
        rows = inventory.sessioni(procs, {}, {}, set())
        serv = [r for r in rows if r["strato"] == "servizi"]
        self.assertEqual(len(serv), 1)
        self.assertTrue(serv[0]["allarme"])


class Sparsi(unittest.TestCase):
    def test_a_server_under_no_session_is_still_listed(self):
        """The codex app server. Without this pass it is invisible."""
        procs = {
            50: proc(50, 40, "node /x/codex app-server --listen ws://127.0.0.1:4500"),
            40: proc(40, 30, "bun run /x/agentbridge/server/daemon.js"),
        }
        rows = inventory.sparsi(procs, {}, {50: [4500]}, set())
        # Both are servers worth a line: the daemon that holds the bridge, and
        # the codex process under it that holds the port.
        self.assertEqual({r["nome"] for r in rows},
                         {"codex app server", "agentbridge bridge"})
        codex = [r for r in rows if r["nome"] == "codex app server"][0]
        self.assertIn("4500", codex["dettaglio"])

    def test_the_desktop_app_helpers_are_left_out(self):
        procs = {60: proc(60, 40, "/Applications/Claude.app/x/Claude Helper --mcp-server")}
        self.assertEqual(inventory.sparsi(procs, {}, {}, set()), [])

    def test_it_does_not_repeat_what_a_session_already_showed(self):
        seen = {50}
        procs = {50: proc(50, 40, "node /x/codex app-server")}
        self.assertEqual(inventory.sparsi(procs, {}, {}, seen), [])


class Launchd(unittest.TestCase):
    def test_a_job_with_a_clock_is_scheduled_and_not_permanent(self):
        """dev.stiva.ccd-percorsi has RunAtLoad and StartInterval both."""
        agent = {
            "label": "dev.stiva.ccd-percorsi", "path": "/x.plist",
            "program": [f"/usr/bin/python3", f"{probe.HOME}/dev/stiva/ccd_paths.py"],
            "run_at_load": True, "keep_alive": False,
            "interval": 60, "calendar": None, "stdout": None, "stderr": None,
        }
        perm = inventory.permanenti({}, {}, [agent], {})
        pian = inventory.pianificati({}, {}, [agent])
        self.assertEqual(perm, [])
        self.assertEqual(len(pian), 1)
        self.assertEqual(pian[0]["quando"], "every 60s")

    def test_a_task_of_claude_code_says_when_the_schedule_is_unknown(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "prova-task"))
            with open(os.path.join(d, "prova-task", "SKILL.md"), "w") as f:
                f.write("---\nname: prova-task\ndescription: fa una cosa\n---\ncorpo\n")
            rows = inventory.pianificati_claude(root=d, cache_path="/tmp/non-esiste")
            self.assertEqual(len(rows), 1)
            self.assertIn("known only to the app", rows[0]["quando"])
            self.assertIn("fa una cosa", rows[0]["dettaglio"])

    def test_a_scheduled_job_is_never_dated_by_its_log(self):
        """Misurato il 10/08/2026 su due job, che sembravano rotti e non lo erano.

        vesuvius-formwatch aveva uno stderr vuoto di cinque giorni prima ed era
        girato tre ore prima. ccd-percorsi scatta ogni minuto e aveva un log
        fermo da quattordici ore. Un log scritto solo quando il job agisce non
        dice quando il job e' girato.
        """
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".log", delete=False) as f:
            f.write(b"vecchio\n")
            vecchio = f.name
        os.utime(vecchio, (0, 0))  # 1970
        agent = {
            "label": "it.nerln.prova", "path": "/x.plist",
            "program": ["/bin/bash", f"{probe.HOME}/.prova/check.sh"],
            "run_at_load": False, "keep_alive": False, "interval": None,
            "calendar": [{"Hour": 9, "Minute": 30}],
            "stdout": None, "stderr": vecchio,
        }
        rows = inventory.pianificati({}, {}, [agent])
        os.unlink(vecchio)
        self.assertEqual(len(rows), 1)
        self.assertNotIn("last 5", rows[0]["dettaglio"])
        self.assertNotIn("ago  ", rows[0]["dettaglio"])
        self.assertIsNone(rows[0]["eta"])

    def test_other_peoples_agents_are_not_shown(self):
        agent = {
            "label": "com.google.keystone.agent", "path": "/x.plist",
            "program": ["/Library/Google/GoogleSoftwareUpdate/x"],
            "run_at_load": True, "keep_alive": True,
            "interval": None, "calendar": None, "stdout": None, "stderr": None,
        }
        self.assertEqual(inventory.permanenti({}, {}, [agent], {}), [])

    def test_two_calendar_entries_read_as_two_times(self):
        agent = {"label": "it.nerln.x", "calendar": [{"Hour": 9, "Minute": 30},
                                                     {"Hour": 19, "Minute": 30}]}
        self.assertEqual(inventory._schedule_text(agent), "at 09:30 and 19:30")


class Tabella(unittest.TestCase):
    def test_the_board_survives_an_empty_machine(self):
        snap = {"ts": 0, "memoria": {"total": 0, "free": 0, "used": 0, "compressed": 0,
                                     "swap_total": 0, "swap_used": 0, "pageouts": 0},
                "righe": []}
        out = board.render(snap, larghezza=100)
        self.assertIn("no orphans", out)

    def test_identical_services_collapse_to_one_line(self):
        rows = [{"strato": "servizi", "nome": "agentbridge bridge", "stato": "in servizio",
                 "pid": i, "rss": 10 * 1024 * 1024, "eta": 60 * i, "quando": "",
                 "dove": "", "dettaglio": "porta 4501", "azione": None, "allarme": False}
                for i in range(1, 8)]
        collapsed = board._collapse(rows)
        self.assertEqual(len(collapsed), 1)
        self.assertEqual(collapsed[0]["rss"], 70 * 1024 * 1024)
        self.assertEqual(collapsed[0]["quando"], "x7")

    def test_colour_codes_do_not_count_towards_the_width(self):
        ink = board.Ink(True)
        self.assertEqual(board._strip(ink.red("ciao")), "ciao")


class Letture(unittest.TestCase):
    """The probes run against the real machine. They must never raise."""

    def test_memory_reads_something_plausible(self):
        m = probe.memory()
        self.assertGreater(m["total"], 1024 ** 3)
        self.assertGreaterEqual(m["used"], 0)

    def test_a_missing_log_is_not_an_error(self):
        self.assertEqual(probe.log_tail("/tmp/questo-file-non-esiste-mai"), [])

    def test_a_failing_command_returns_empty(self):
        self.assertEqual(probe._run(["/bin/questo-comando-non-esiste"]), "")

    def test_etime_in_all_three_shapes(self):
        self.assertEqual(probe._etime_seconds("05:30"), 330)
        self.assertEqual(probe._etime_seconds("01:05:30"), 3930)
        self.assertEqual(probe._etime_seconds("2-01:05:30"), 176730)
        self.assertIsNone(probe._etime_seconds("boh"))

    def test_the_whole_snapshot_runs(self):
        snap = inventory.snapshot()
        self.assertIn("righe", snap)
        for r in snap["righe"]:
            self.assertIn(r["strato"], board.ORDER)


# --------------------------------------------------------- la gui e l'annuncio
#
# La prova che conta qui e' una sola: una pagina web qualunque puo' fare
# richieste a 127.0.0.1, quindi una POST senza gettone non deve poter arrivare
# fino alle funzioni che chiudono processi. Il finto `bin/faro` qui sotto serve
# esattamente a misurare questo: non basta che la risposta sia 403, deve non
# essere stata chiamata nessuna azione.

import json  # noqa: E402
import threading  # noqa: E402
import urllib.error  # noqa: E402
import urllib.request  # noqa: E402

from faro import annuncio, web  # noqa: E402


class _CliFinto:
    """Un `bin/faro` finto: un test non deve poter fermare niente davvero."""

    def __init__(self):
        self.chiamate = []

    def cmd_reap(self, args):
        self.chiamate.append(("reap", args.esegui, args.piu_vecchi_di))
        print("niente da chiudere.")
        return 0

    def cmd_stop(self, args):
        self.chiamate.append(("stop", args.cosa, args.per_sempre))
        print(f"pid {args.cosa}: chiuso.")
        return 0


def _chiama(porta, percorso, dati=None, gettone=None, origine=None, host=None):
    req = urllib.request.Request(
        f"http://127.0.0.1:{porta}{percorso}",
        data=json.dumps(dati).encode() if dati is not None else None,
        method="POST" if dati is not None else "GET")
    if gettone:
        req.add_header("X-Faro-Token", gettone)
    if origine:
        req.add_header("Origin", origine)
    if host:
        req.add_header("Host", host)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, r.read().decode(), dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(), dict(e.headers)


class Gui(unittest.TestCase):
    """I tre muri: gettone, Origin, Host."""

    def setUp(self):
        self.cli = _CliFinto()
        self.server, self.gettone = web.crea_server(cli=self.cli)
        self.porta = self.server.server_address[1]
        self.thread = threading.Thread(
            target=self.server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

    def test_una_post_senza_gettone_e_403_e_non_fa_niente(self):
        codice, _, _ = _chiama(self.porta, "/api/reap", {"esegui": True})
        self.assertEqual(codice, 403)
        # Il 403 da solo non basterebbe: la cosa da provare e' che nessuna
        # azione sia partita prima di rispondere.
        self.assertEqual(self.cli.chiamate, [])

    def test_una_post_col_gettone_arriva_alla_stessa_funzione_della_cli(self):
        codice, corpo, _ = _chiama(self.porta, "/api/reap", {"esegui": True},
                                   gettone=self.gettone)
        self.assertEqual(codice, 200)
        self.assertEqual(self.cli.chiamate, [("reap", True, 0)])
        self.assertIn("niente da chiudere", json.loads(corpo)["testo"])

    def test_solo_il_booleano_vero_chiude_davvero_i_processi(self):
        """Trovato dalla revisione avversariale dell'11/08/2026.

        `esegui` decideva fra una prova e la chiusura vera con la verita' di
        Python su un json non validato. La stringa "false" e la stringa "0"
        sono esattamente quello che manda chi passa un flag da un altro
        linguaggio, e chiudevano i processi.
        """
        for bugiardo in ("false", "no", "0", ["x"], {"a": 1}, 1, "true"):
            with self.subTest(bugiardo=bugiardo):
                self.cli.chiamate.clear()
                codice, _, _ = _chiama(self.porta, "/api/reap",
                                       {"esegui": bugiardo}, gettone=self.gettone)
                self.assertEqual(codice, 200)
                self.assertEqual(self.cli.chiamate, [("reap", False, 0)])

    def test_un_gettone_non_ascii_non_fa_morire_il_thread(self):
        """compare_digest solleva TypeError sulle str non ASCII, e le
        intestazioni HTTP arrivano decodificate in latin-1. Un byte sopra 127
        lasciava il client senza risposta e stampava una traccia."""
        codice, _, _ = _chiama(self.porta, "/api/reap", {"esegui": True},
                               gettone="pippò" + "x" * 38)
        self.assertEqual(codice, 403)
        self.assertEqual(self.cli.chiamate, [])

    def test_un_host_lunghissimo_non_riempie_il_terminale(self):
        codice, _, _ = _chiama(self.porta, "/api/reap", {"esegui": True},
                               gettone=self.gettone, host="a" * 4000 + ":1")
        self.assertEqual(codice, 403)
        self.assertEqual(self.cli.chiamate, [])

    def test_la_difesa_non_regge_su_un_attributo_diverso_da_quello_giusto(self):
        """La classe base aveva `gettone = ""`, e con l'intestazione assente il
        confronto era vero: passava solo perche' falliva prima il muro
        dell'Host. Un gettone vuoto deve essere un rifiuto per conto suo."""
        class Nudo(web._Manico):
            gettone = ""
        finto = Nudo.__new__(Nudo)
        finto.headers = {}
        self.assertFalse(web._Manico._gettone_buono(finto))

    def test_un_gettone_sbagliato_non_passa(self):
        codice, _, _ = _chiama(self.porta, "/api/ferma", {"pid": 999999},
                               gettone="x" * 43)
        self.assertEqual(codice, 403)
        self.assertEqual(self.cli.chiamate, [])

    def test_un_origin_estraneo_non_passa_nemmeno_col_gettone(self):
        codice, _, _ = _chiama(self.porta, "/api/reap", {"esegui": True},
                               gettone=self.gettone, origine="https://evil.example")
        self.assertEqual(codice, 403)
        self.assertEqual(self.cli.chiamate, [])

    def test_un_host_estraneo_non_passa_nemmeno_col_gettone(self):
        """Il dns rebinding e' l'unico caso in cui il browser lo lascerebbe fare."""
        codice, _, _ = _chiama(self.porta, "/api/reap", {"esegui": True},
                               gettone=self.gettone, host="evil.example")
        self.assertEqual(codice, 403)
        self.assertEqual(self.cli.chiamate, [])

    def test_la_preflight_non_passa_e_non_c_e_nessuna_intestazione_cors(self):
        req = urllib.request.Request(f"http://127.0.0.1:{self.porta}/api/reap",
                                     method="OPTIONS")
        req.add_header("Origin", "https://evil.example")
        req.add_header("Access-Control-Request-Method", "POST")
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                codice, intestazioni = r.status, dict(r.headers)
        except urllib.error.HTTPError as e:
            codice, intestazioni = e.code, dict(e.headers)
        self.assertEqual(codice, 403)
        for nome in intestazioni:
            self.assertFalse(nome.lower().startswith("access-control"))

    def test_lo_stato_non_si_legge_senza_gettone(self):
        self.assertEqual(_chiama(self.porta, "/api/stato")[0], 403)
        self.assertEqual(_chiama(self.porta, "/api/stato", gettone=self.gettone)[0], 200)

    def test_la_pagina_si_prende_senza_gettone_perche_non_contiene_niente(self):
        codice, corpo, intestazioni = _chiama(self.porta, "/")
        self.assertEqual(codice, 200)
        self.assertIn("<title>faro</title>", corpo)
        self.assertEqual(intestazioni.get("X-Frame-Options"), "DENY")

    def test_ferma_accetta_solo_un_pid_e_non_un_etichetta_launchd(self):
        """Un bottone che fa `launchctl bootout` e' potere che qui non serve."""
        codice, _, _ = _chiama(self.porta, "/api/ferma", {"pid": "com.plancia.server"},
                               gettone=self.gettone)
        self.assertEqual(codice, 400)
        self.assertEqual(self.cli.chiamate, [])

    def test_ferma_passa_il_pid_alla_stop_della_cli(self):
        codice, _, _ = _chiama(self.porta, "/api/ferma", {"pid": 999999},
                               gettone=self.gettone)
        self.assertEqual(codice, 200)
        self.assertEqual(self.cli.chiamate, [("stop", "999999", False)])


class PaginaSola(unittest.TestCase):
    def test_un_percorso_ostile_non_arriva_intero_sul_terminale(self):
        """Chi viene respinto sceglie il percorso, e il rifiuto lo legge un
        terminale: una sequenza di escape ansi ci scriverebbe quello che vuole."""
        self.assertEqual(web._pulito("/api/\x1b[2J\x1b[31mciao"), "/api/?[2J?[31mciao")
        self.assertLessEqual(len(web._pulito("x" * 500)), 70)

    def test_la_pagina_non_chiede_niente_a_nessuno(self):
        p = web.pagina()
        self.assertIsNone(web._ESTERNO.search(p))
        self.assertIn("<style>", p)
        self.assertNotIn('<script src=', p)

    def test_le_azioni_della_gui_sono_le_funzioni_di_bin_faro(self):
        """Se un domani divergono, la gui chiude quello che la cli protegge."""
        cli = web._cli_modulo()
        self.assertTrue(callable(cli.cmd_reap))
        self.assertTrue(callable(cli.cmd_stop))
        # La quinta invariante vive li' dentro e la gui la eredita.
        self.assertTrue(callable(cli._my_ancestors))

    def test_le_parole_degli_strati_sono_quelle_della_plancia(self):
        """La gui non ha un suo elenco di nomi: prende quelli di board.TITLES.

        Prima questo si verificava contro board.ORDER, che sono le chiavi
        interne, e funzionava solo perche' i nomi visibili erano uguali alle
        chiavi. Tradotta la plancia in inglese le due cose si sono separate, ed
        e' giusto: le chiavi sono dati e non cambiano, i nomi si leggono. Qui
        si verifica quello che conta davvero, cioe' che siano una copia sola.
        """
        nomi = [s["nome"] for s in web._strati()]
        attesi = [board.TITLES[k].partition("  ")[0] for k in board.ORDER]
        self.assertEqual(nomi, attesi)
        self.assertEqual(len(nomi), len(board.ORDER))


def _snap(righe=(), **memoria):
    base = {"total": 16 * 1024 ** 3, "free": 8 * 1024 ** 3, "used": 8 * 1024 ** 3,
            "compressed": 0, "swap_total": 5 * 1024 ** 3, "swap_used": 0, "pageouts": 0,
            # 1 e' normale: il caso di gran lunga piu' comune, e quello in cui
            # lo swap allocato non vuol dire che la macchina stia soffrendo.
            "pressione": 1, "libero_pct": 70}
    base.update(memoria)
    return {"ts": 0, "memoria": base, "righe": list(righe)}


def _riga(strato, **kw):
    r = {"strato": strato, "id": "x", "nome": "cosa", "stato": "", "pid": None,
         "rss": 0, "eta": 0, "quando": "", "dove": "", "dettaglio": "", "azione": None,
         "allarme": False}
    r.update(kw)
    return r


class Annuncio(unittest.TestCase):
    """Una notifica che arriva sempre e' una notifica che si impara a ignorare."""

    def test_su_una_macchina_tranquilla_non_si_dice_niente(self):
        self.assertEqual(annuncio.forti(annuncio.valuta(_snap())), [])

    def test_gli_orfani_valgono_una_notifica(self):
        righe = [_riga("orfani", stato="orfano", pid=900, rss=11 * 1024 ** 2, eta=54000)]
        notizie = annuncio.forti(annuncio.valuta(_snap(righe)))
        self.assertEqual(len(notizie), 1)
        self.assertIn("1 orphaned process", notizie[0]["titolo"])
        self.assertIn("11.0MB", notizie[0]["testo"])

    def test_lo_swap_sopra_i_due_giga_vale_una_notifica_solo_sotto_pressione(self):
        """Il test diceva 'swap alto uguale allarme', e dall'11/08/2026 non e'
        piu' vero: macOS tiene i file di swap allocati per ore dopo che la
        pressione e' tornata normale, e notificare quel numero e' come suonare
        un allarme antincendio davanti alla cenere. Serve anche il kernel che
        dichiara di stare faticando."""
        calmo = annuncio.valuta(_snap(swap_used=3 * 1024 ** 3, pressione=1))
        self.assertEqual([n["gravita"] for n in calmo], ["medium"])
        self.assertEqual(annuncio.forti(calmo), [])

        sotto_sforzo = annuncio.valuta(_snap(swap_used=3 * 1024 ** 3, pressione=4))
        self.assertEqual([n["gravita"] for n in sotto_sforzo], ["high"])

        basso = annuncio.valuta(_snap(swap_used=700 * 1024 ** 2))
        self.assertEqual([n["gravita"] for n in basso], ["medium"])
        self.assertEqual(annuncio.forti(basso), [])

    def test_un_job_pianificato_uscito_male_vale_una_notifica(self):
        # La dicitura e' quella che scrive inventory.pianificati, e le due cose
        # sono accoppiate: se una cambia lingua e l'altra no, l'annuncio smette
        # di leggere il codice di uscita e nessuno se ne accorge finche' un job
        # non fallisce davvero. E' successo traducendo, e questo test lo ha
        # fermato.
        righe = [_riga("pianificati", nome="dev.stiva.ccd-percorsi", allarme=True,
                       dettaglio="12 runs since load  ·  LAST EXIT 78")]
        notizie = annuncio.forti(annuncio.valuta(_snap(righe)))
        self.assertEqual(len(notizie), 1)
        self.assertIn("dev.stiva.ccd-percorsi", notizie[0]["titolo"])
        self.assertIn("78", notizie[0]["testo"])

    def test_un_permanente_fermo_vale_una_notifica(self):
        righe = [_riga("permanenti", nome="com.plancia.server", stato="caricato ma fermo",
                       allarme=True)]
        self.assertEqual(len(annuncio.forti(annuncio.valuta(_snap(righe)))), 1)

    def test_il_testo_non_entra_mai_nel_sorgente_applescript(self):
        """Un nome arriva da un plist o da una riga di comando: e' dato ostile."""
        cattivo = 'x" & (do shell script "rm -rf ~") & "'
        cmd = annuncio.comando_notifica("faro", cattivo, "corpo")
        self.assertEqual(cmd[0], "osascript")
        sorgente = cmd[2]
        self.assertNotIn("do shell script", sorgente)
        self.assertIn("item 2 of argv", sorgente)
        self.assertIn(cattivo, cmd[3:])

    def test_il_testo_di_una_notifica_e_una_riga_sola_e_corta(self):
        sporco = "una\nriga\x00con dentro di tutto " + "a" * 400
        pulito = annuncio._pulisci(sporco)
        self.assertNotIn("\n", pulito)
        self.assertNotIn("\x00", pulito)
        self.assertLessEqual(len(pulito), annuncio.MAX_TESTO)

    def test_boa_non_e_una_dipendenza(self):
        vero = annuncio.BOA
        try:
            annuncio.BOA = "/non/esiste/da/nessuna/parte/boa"
            self.assertFalse(annuncio.scrivi_su_boa("ciao"))
        finally:
            annuncio.BOA = vero

    def test_la_gui_e_la_notifica_dicono_la_stessa_cosa(self):
        """Un solo giudizio: se divergono, uno dei due mente."""
        righe = [_riga("orfani", stato="orfano", pid=900, rss=1024, eta=4000)]
        snap = _snap(righe, swap_used=3 * 1024 ** 3)
        dalla_pagina = web.stato(snap)["notizie"]
        self.assertEqual(dalla_pagina, annuncio.valuta(snap))


class Spazio(unittest.TestCase):
    """`faro spazio`: cosa chiudere perche' un lavoro entri.

    Nato la notte dell'11/08/2026, davanti a un lavoro fermo in coda da tre ore
    a cui nessuno dei tre strumenti sapeva rispondere.
    """

    def mem(self, usata_gb, totale_gb=16):
        g = 1024 ** 3
        return {"total": totale_gb * g, "used": int(usata_gb * g), "free": 0,
                "compressed": 0, "swap_total": 0, "swap_used": 0, "pageouts": 0}

    def test_il_bilancio_e_quello_di_rada(self):
        """riserva = max(15% del totale, 1536 MB), bilancio = totale - riserva - usata."""
        from faro import spazio
        g = 1024 ** 3
        self.assertEqual(spazio.bilancio(self.mem(8)), 16 * g - int(16 * g * 0.15) - 8 * g)
        # su una macchina piccola vince il pavimento, non la frazione
        piccola = self.mem(1, totale_gb=4)
        self.assertEqual(spazio.bilancio(piccola), 4 * g - 1536 * 1024 ** 2 - 1 * g)

    def test_se_ci_sta_gia_non_chiede_di_chiudere_niente(self):
        from faro import spazio
        testo = spazio.racconta(1024 ** 3, mem=self.mem(5), procs={})
        self.assertIn("it fits as it is", testo)

    def test_dice_chiaro_quando_non_basta_chiudere_tutto(self):
        """Il caso vero: 5 GB su una macchina occupata, e nessun elefante."""
        from faro import spazio
        procs = {i: {"pid": i, "ppid": 1, "rss": 50 * 1024 ** 2, "age": 10,
                     "command": "/System/Library/qualcosa"} for i in range(10)}
        testo = spazio.racconta(5 * 1024 ** 3, mem=self.mem(13), procs=procs)
        self.assertIn("NOT ENOUGH", testo)
        self.assertIn("rada telling you", testo)

    def test_il_sistema_non_finisce_mai_fra_le_cose_da_chiudere(self):
        from faro import spazio
        procs = {1: {"pid": 1, "ppid": 0, "rss": 4 * 1024 ** 3, "age": 10,
                     "command": "/System/Library/CoreServices/WindowServer"}}
        scelti, _, _ = spazio.piano(5 * 1024 ** 3, self.mem(12), procs)
        self.assertEqual(scelti, [])

    def test_le_sessioni_ferme_vengono_prima_di_quello_che_costa(self):
        from faro import spazio
        procs = {
            1: {"pid": 1, "ppid": 0, "rss": 500 * 1024 ** 2, "age": 10,
                "command": "/Applications/Visual Studio Code.app/x Code Helper"},
            2: {"pid": 2, "ppid": 0, "rss": 100 * 1024 ** 2, "age": 10,
                "command": "/x/claude-code/2.1.222/claude.app/y"},
        }
        scelti, _, _ = spazio.piano(6 * 1024 ** 3, self.mem(12), procs)
        self.assertEqual(scelti[0]["nome"], "Claude Code sessions")


class BigliettiFermi(unittest.TestCase):
    """Un biglietto in coda dice anche chi lo sta aspettando."""

    def test_un_biglietto_senza_processo_e_un_fantasma(self):
        nota, sospetto = inventory._chi_aspetta(999999, {})
        self.assertIn("ghost", nota)
        self.assertTrue(sospetto)

    def test_un_wrapper_riadottato_vuol_dire_sessione_morta(self):
        """Il caso misurato: il job MATS aspettava da tre ore cosi'."""
        procs = {50: {"pid": 50, "ppid": 1, "rss": 0, "age": 11000,
                      "command": "python3 rada run --need 5G"}}
        nota, sospetto = inventory._chi_aspetta(50, procs)
        self.assertIn("session", nota)
        self.assertTrue(sospetto)

    def test_un_wrapper_con_genitore_vivo_non_e_una_notizia(self):
        procs = {50: {"pid": 50, "ppid": 42, "rss": 0, "age": 10,
                      "command": "python3 rada run"}}
        nota, sospetto = inventory._chi_aspetta(50, procs)
        self.assertEqual(nota, "")
        self.assertFalse(sospetto)


class Conto(unittest.TestCase):
    """`faro token`: dove sono andati i token."""

    def scrivi(self, d, righe):
        import json
        prog = os.path.join(d, "-Users-prova")
        os.makedirs(prog, exist_ok=True)
        p = os.path.join(prog, "sess.jsonl")
        with open(p, "w") as f:
            for r in righe:
                f.write(json.dumps(r) + "\n")
        return p

    def uso(self, ident, out):
        return {"type": "assistant", "uuid": ident,
                "message": {"id": ident, "model": "claude-opus-5",
                            "usage": {"output_tokens": out, "input_tokens": 2,
                                      "cache_read_input_tokens": 100,
                                      "cache_creation_input_tokens": 10}}}

    def test_le_voci_doppie_non_raddoppiano_il_conto(self):
        """Lo stesso usage compare piu' volte nel transcript. Verificato su un
        transcript vero l'11/08/2026: due righe identiche di seguito."""
        from faro import conto
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            self.scrivi(d, [self.uso("a", 100), self.uso("a", 100), self.uso("b", 50)])
            conti, _ = conto.raccogli(0, root=d)
            tot = sum(c["out"] for c in conti.values())
            self.assertEqual(tot, 150)

    def test_i_file_fuori_finestra_non_si_aprono_nemmeno(self):
        from faro import conto
        import tempfile, time
        with tempfile.TemporaryDirectory() as d:
            p = self.scrivi(d, [self.uso("a", 100)])
            os.utime(p, (0, 0))
            conti, visti = conto.raccogli(time.time() - 60, root=d)
            self.assertEqual(visti, 0)
            self.assertEqual(conti, {})

    def test_i_subagenti_si_contano_a_parte(self):
        from faro import conto
        p = os.path.join(conto.PROGETTI, "-x", "subagents", "agent-1.jsonl")
        self.assertEqual(conto._chi(p)[1], "subagents")
        self.assertEqual(conto._chi(os.path.join(conto.PROGETTI, "-x", "s.jsonl"))[1],
                         "sessions")

    def test_una_finestra_vuota_lo_dice(self):
        from faro import conto
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            self.assertIn("no tokens", conto.racconta(root=d))


class SessioniDaTerminale(unittest.TestCase):
    """Una sessione avviata da un terminale non gira dentro il bundle dell'app.

    Difetto misurato la notte dell'11/08/2026 nel modo peggiore: dopo aver
    riaperto sette sessioni da iTerm2, faro continuava a dire "2 sessioni vive".
    """

    def test_una_sessione_da_terminale_viene_riconosciuta(self):
        self.assertTrue(inventory._e_claude("claude --resume 5d59fc7c-2af7"))
        self.assertTrue(inventory._e_claude("/Users/e/.local/bin/claude"))

    def test_quella_dentro_il_bundle_pure(self):
        self.assertTrue(inventory._e_claude(f"/x/{inventory.CLAUDE_BIN} --output-format"))

    def test_un_percorso_che_contiene_claude_non_basta(self):
        """Altrimenti mezza cartella ~/.claude diventerebbe una sessione."""
        self.assertFalse(inventory._e_claude(
            "python3 /Users/e/.claude/plugins/qualcosa/server.py"))
        self.assertFalse(inventory._e_claude("bun run /Users/e/.claude/x/bridge.js"))
        self.assertFalse(inventory._e_claude(""))

    def test_le_sessioni_da_terminale_entrano_nel_conto(self):
        procs = {
            11: proc(11, 10, "claude --resume aaa"),
            12: proc(12, 10, f"/x/{inventory.CLAUDE_BIN} --x"),
        }
        vive = inventory._live_sessions(procs)
        self.assertEqual(sorted(p["pid"] for p in vive), [11, 12])


class Notte(unittest.TestCase):
    """`faro notte`: la funzione del vado a letto.

    L'invariante 0 e' che non apre mai niente, ed e' l'unica invariante nata
    da un errore vero invece che da una previsione.
    """

    def piano(self, usata_gb=12, orfani=(), ferme=(), coda=()):
        from faro import notte, spazio
        g = 1024 ** 3
        mem = {"total": 16 * g, "used": int(usata_gb * g), "free": 0,
               "compressed": 0, "swap_total": 0, "swap_used": 0, "pageouts": 0}
        libera = sum(o["rss"] for o in orfani) + sum(f["rss"] for f in ferme)
        dopo = max(0, mem["used"] - int(libera * spazio.RESA))
        return {"orfani": list(orfani), "ferme": list(ferme), "coda": list(coda),
                "memoria": mem, "libera": libera,
                "bilancio_ora": spazio.bilancio(mem),
                "bilancio_dopo": spazio.bilancio(mem, usata=dopo)}

    def test_dice_sempre_che_non_apre_niente(self):
        """La riga deve esserci anche quando non c'e' niente da fare."""
        from faro import notte
        testo = notte.racconta(self.piano())
        self.assertIn("opens nothing", testo)

    def test_chiudere_alza_il_bilancio_di_rada(self):
        from faro import notte
        g = 1024 ** 3
        p = self.piano(ferme=[{"pid": 1, "rss": 2 * g}])
        self.assertGreater(p["bilancio_dopo"], p["bilancio_ora"])

    def test_dice_se_un_lavoro_in_coda_entrerebbe_dopo(self):
        from faro import notte
        g = 1024 ** 3
        coda = [{"strato": "rada", "stato": "in coda", "nome": "un lavoro",
                 "rss": 1 * g, "eta": 100, "pid": None, "quando": "", "dove": "",
                 "dettaglio": "", "azione": None, "allarme": True}]
        p = self.piano(usata_gb=11, ferme=[{"pid": 1, "rss": 2 * g}], coda=coda)
        self.assertIn("FITS", notte.racconta(p))

    def test_e_dice_quanto_manca_quando_non_entra(self):
        from faro import notte
        g = 1024 ** 3
        coda = [{"strato": "rada", "stato": "in coda", "nome": "un lavoro grosso",
                 "rss": 9 * g, "eta": 100, "pid": None, "quando": "", "dove": "",
                 "dettaglio": "", "azione": None, "allarme": True}]
        testo = notte.racconta(self.piano(coda=coda))
        self.assertIn("short", testo)
        self.assertIn("faro space", testo)

    def test_il_rapporto_scrive_che_non_ha_aperto_niente(self):
        from faro import notte
        import tempfile
        vecchia = notte.FARO_HOME
        with tempfile.TemporaryDirectory() as d:
            notte.FARO_HOME = d
            try:
                path = notte.rapporto(self.piano(), 0, 0)
                testo = open(path).read()
                self.assertIn("no session was opened", testo)
                self.assertIn("claude --resume", testo)
            finally:
                notte.FARO_HOME = vecchia

    def test_la_sessione_che_lancia_il_comando_non_e_mai_fra_le_ferme(self):
        from faro import notte
        procs = probe.processes()
        mia = notte._catena_mia(procs)
        self.assertIn(os.getpid(), mia)
        ferme = {s["pid"] for s in notte.sessioni_ferme()}
        self.assertEqual(ferme & mia, set())


class NomiDegliStrati(unittest.TestCase):
    """`--only` accetta sia la chiave interna sia il nome che la plancia stampa.

    Le chiavi sono dati e sono rimaste italiane, i nomi si leggono e sono
    inglesi. Chi scrive `--only orphans` sta digitando quello che vede: prima
    non funzionava, e il README lo prometteva.
    """

    def test_il_nome_inglese_trova_la_chiave(self):
        self.assertEqual(board.strato_da_nome("orphans"), "orfani")
        self.assertEqual(board.strato_da_nome("scheduled"), "pianificati")
        self.assertEqual(board.strato_da_nome("SESSIONS"), "sessioni")

    def test_la_chiave_interna_continua_a_valere(self):
        for k in board.ORDER:
            self.assertEqual(board.strato_da_nome(k), k)

    def test_una_parola_sconosciuta_torna_com_era(self):
        """Non si indovina: se non e' uno strato, filtra su niente e la
        plancia esce vuota, che e' la risposta giusta a un nome sbagliato."""
        self.assertEqual(board.strato_da_nome("pippo"), "pippo")

    def test_ogni_nome_stampato_e_risolvibile(self):
        for k in board.ORDER:
            nome = board.TITLES[k].partition("  ")[0]
            self.assertEqual(board.strato_da_nome(nome), k)


class SwapEPressione(unittest.TestCase):
    """Lo swap allocato non e' lo swap che fa male.

    Misurato l'11/08/2026: chiuse quattro sessioni, la memoria usata scesa di
    1 GB, i pageout fermi a zero per un minuto intero, e lo swap rimasto a
    5,34 GB. macOS non restituisce i file di swap quando la pressione cala.
    Una plancia che grida leggendo solo quel numero grida per ore dopo che il
    problema e' finito, e allora non la si guarda piu'.
    """

    def _snap(self, swap_gb, pressione):
        g = 1024 ** 3
        return {"ts": 0, "righe": [], "memoria": {
            "total": 16 * g, "free": 8 * g, "used": 8 * g, "compressed": 0,
            "swap_total": 7 * g, "swap_used": int(swap_gb * g), "pageouts": 300000,
            "pressione": pressione, "libero_pct": 70}}

    def test_molto_swap_con_pressione_normale_non_e_un_allarme(self):
        out = board.render(self._snap(5.3, 1), larghezza=100)
        self.assertIn("still allocated", out)
        self.assertNotIn("struggling", out)

    def test_molto_swap_con_pressione_alta_lo_e(self):
        out = board.render(self._snap(5.3, 2), larghezza=100)
        self.assertIn("struggling", out)

    def test_la_pressione_compare_sempre_nella_riga_della_memoria(self):
        self.assertIn("pressure normal", board.render(self._snap(0.1, 1), larghezza=100))
        self.assertIn("pressure critical", board.render(self._snap(0.1, 4), larghezza=100))

    def test_annuncia_non_notifica_per_swap_se_la_pressione_e_normale(self):
        from faro import annuncio
        self.assertEqual(annuncio.forti(annuncio.valuta(self._snap(5.3, 1))), [])
        forti = annuncio.forti(annuncio.valuta(self._snap(5.3, 4)))
        self.assertEqual(len(forti), 1)
        self.assertIn("struggling", forti[0]["titolo"])

    def test_senza_il_campo_pressione_si_comporta_come_prima_del_dubbio(self):
        """Un vecchio json senza il campo non deve far esplodere niente."""
        snap = self._snap(5.3, 1)
        del snap["memoria"]["pressione"]
        out = board.render(snap, larghezza=100)
        self.assertIn("still allocated", out)

if __name__ == "__main__":
    unittest.main(verbosity=2)
