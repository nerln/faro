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
        self.assertIn("troppo presto", rows[0]["dettaglio"])

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
                self.assertIn("ancora scrivendo", rows[0]["dettaglio"])
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
        self.assertIn("sessione viva lavora", rows[0]["dettaglio"])

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
        self.assertEqual(serv[0]["nome"], "server MCP di plancia")

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
                         {"app-server di codex", "ponte agentbridge"})
        codex = [r for r in rows if r["nome"] == "app-server di codex"][0]
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
        self.assertEqual(pian[0]["quando"], "ogni 60s")

    def test_a_task_of_claude_code_says_when_the_schedule_is_unknown(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "prova-task"))
            with open(os.path.join(d, "prova-task", "SKILL.md"), "w") as f:
                f.write("---\nname: prova-task\ndescription: fa una cosa\n---\ncorpo\n")
            rows = inventory.pianificati_claude(root=d, cache_path="/tmp/non-esiste")
            self.assertEqual(len(rows), 1)
            self.assertIn("noto solo all'app", rows[0]["quando"])
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
        self.assertNotIn("ultima 5", rows[0]["dettaglio"])
        self.assertNotIn("fa  ", rows[0]["dettaglio"])
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
        self.assertEqual(inventory._schedule_text(agent), "alle 09:30 e 19:30")


class Tabella(unittest.TestCase):
    def test_the_board_survives_an_empty_machine(self):
        snap = {"ts": 0, "memoria": {"total": 0, "free": 0, "used": 0, "compressed": 0,
                                     "swap_total": 0, "swap_used": 0, "pageouts": 0},
                "righe": []}
        out = board.render(snap, larghezza=100)
        self.assertIn("nessun orfano", out)

    def test_identical_services_collapse_to_one_line(self):
        rows = [{"strato": "servizi", "nome": "ponte agentbridge", "stato": "in servizio",
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
