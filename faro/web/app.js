/* faro, la pagina. Nessuna libreria, nessuna rete oltre a se stessa.
 *
 * Due cose da non toccare senza pensarci:
 *
 * 1. Il gettone. Arriva nella barra degli indirizzi, finisce subito in
 *    sessionStorage (che vive quanto la scheda) e sparisce dall'URL, cosi' non
 *    resta nella cronologia. Da li' in poi viaggia in un header: e' quello che
 *    impedisce a un'altra pagina aperta nel browser di chiudere i processi di
 *    Eugenio con una POST.
 *
 * 2. Il testo. Nomi, percorsi e righe di comando arrivano da repository, da
 *    pagine web e da prompt: sono dato ostile (CLAUDE.md, invariante 8). Qui
 *    dentro si scrive solo con textContent. Se un giorno compare un innerHTML
 *    con dentro un pezzo di snapshot, quella e' una falla, non una comodita'.
 */
(() => {
  "use strict";

  const CHIAVE = "faro-gettone";
  const p = new URLSearchParams(location.search);
  let gettone = p.get("t");
  if (gettone) {
    sessionStorage.setItem(CHIAVE, gettone);
    history.replaceState(null, "", location.pathname);
  } else {
    gettone = sessionStorage.getItem(CHIAVE) || "";
  }

  const OGNI = 5000;
  const $ = (id) => document.getElementById(id);
  let fermo = false, spento = false, firma = "", ultimo = 0, attesa = null;

  function el(tag, cls, testo) {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (testo !== undefined && testo !== null && testo !== "") n.textContent = testo;
    return n;
  }

  async function api(percorso, corpo) {
    const opzioni = {
      method: corpo ? "POST" : "GET",
      headers: { "X-Faro-Token": gettone },
      cache: "no-store",
    };
    if (corpo) {
      opzioni.headers["Content-Type"] = "application/json";
      opzioni.body = JSON.stringify(corpo);
    }
    const r = await fetch(percorso, opzioni);
    if (r.status === 403) { fuoriGioco(); throw new Error("403"); }
    if (!r.ok) throw new Error("HTTP " + r.status);
    return r.json();
  }

  function fuoriGioco() {
    spento = true;
    $("punto").className = "punto rotto";
    $("battito").textContent = "gettone non valido";
    nota("Questa pagina non ha piu' il gettone di questo avvio.\n" +
         "Riaprila dal terminale con `faro gui`.", true);
  }

  function nota(testo, male) {
    const n = $("nota");
    n.textContent = testo;
    n.classList.toggle("male", !!male);
    n.hidden = false;
    clearTimeout(nota._t);
    nota._t = setTimeout(() => { n.hidden = true; }, male ? 30000 : 14000);
  }
  document.addEventListener("click", (e) => {
    if (e.target === $("nota")) $("nota").hidden = true;
  });

  /* -------------------------------------------------------------- memoria */

  function cella(k, v, piccolo, n, classe) {
    const c = el("div", "cella" + (classe ? " " + classe : ""));
    c.append(el("div", "k", k));
    const val = el("div", "v", v);
    if (piccolo) val.append(el("small", null, " " + piccolo));
    c.append(val);
    if (n) c.append(el("div", "n", n));
    return c;
  }

  function disegnaMemoria(dati) {
    const m = dati.memoria;
    const box = $("memoria");
    box.textContent = "";

    const usata = cella("memoria", m.usata_umana, "di " + m.totale_umana,
                        m.compressa_umana + " compressa");
    const barra = el("div", "barra");
    const quotaUsata = m.total ? Math.max(0, (m.used - m.compressed) / m.total) : 0;
    const quotaCompressa = m.total ? m.compressed / m.total : 0;
    const a = el("i", "usata"); a.style.width = (quotaUsata * 100).toFixed(1) + "%";
    const b = el("i", "compressa"); b.style.width = (quotaCompressa * 100).toFixed(1) + "%";
    barra.append(a, b);
    usata.insertBefore(barra, usata.lastChild);
    box.append(usata);

    // Lo swap e' la ragione per cui questa pagina esiste: quando supera i 2 GB
    // deve essere la prima cosa che si vede, non un numero in fondo.
    const classe = m.swap_allarme ? "allarme" : (m.swap_attenzione ? "attenzione" : "");
    box.append(cella("swap", m.swap_umano, "di " + m.swap_totale_umano,
                     m.pageouts.toLocaleString("it-IT") + " pageout", classe));
    box.append(cella("sessioni", String(dati.conteggi.sessioni || 0), null,
                     "Claude Code vivo adesso"));
    const orf = dati.conteggi.orfani || 0;
    box.append(cella("orfani", String(orf), null,
                     orf ? dati.rss_orfani + " da recuperare" : "niente da recuperare",
                     orf ? "allarme" : ""));
  }

  /* --------------------------------------------------------------- avvisi */

  function disegnaAvvisi(notizie) {
    const box = $("avvisi");
    box.textContent = "";
    for (const n of notizie) {
      const riga = el("div", "avviso" + (n.gravita === "media" ? " media" : ""));
      riga.append(el("b", null, n.titolo));
      riga.append(el("span", null, n.testo));
      if (n.chiave === "orfani") {
        const b = el("button", "ghost spinta", "chiudili");
        b.type = "button";
        b.addEventListener("click", chiediReap);
        riga.append(b);
      }
      box.append(riga);
    }
  }

  async function copia(testo) {
    try {
      await navigator.clipboard.writeText(testo);
      nota("copiato:  " + testo);
    } catch (e) {
      nota("da battere nel terminale:\n" + testo);
    }
  }

  /* --------------------------------------------------------------- strati */

  function classeStato(r) {
    if (r.stato === "orfano") return "stato rosso";
    if (r.allarme) return "stato giallo";
    if (["attivo", "viva", "in servizio", "in esecuzione", "in orario"].includes(r.stato))
      return "stato acceso";
    return "stato";
  }

  function disegnaRiga(r) {
    const riga = el("div", "riga" + (r.stato === "orfano" ? " grave" : ""));
    riga.append(el("i", classeStato(r)));

    const nome = el("div", "nome", r.nome);
    if (r.pid) nome.append(el("em", null, "pid " + r.pid));
    nome.title = r.dove || r.nome;
    riga.append(nome);

    riga.append(el("div", "eta", r.eta_umana));
    riga.append(el("div", "ram", r.rss_umano));
    riga.append(el("div", "quando", r.quando || r.stato));

    const dett = el("div", "dett", r.dettaglio || r.dove || "");
    dett.title = r.dettaglio || "";
    riga.append(dett);

    const azione = el("div", "azione");
    if (r.fermabile) {
      const b = el("button", "ghost", "ferma");
      b.type = "button";
      b.addEventListener("click", () => chiediFerma(r));
      azione.append(b);
    } else if (r.azione && /^(faro|rada) /.test(r.azione)) {
      // Un'etichetta launchd non si ferma da qui: la pagina puo' solo passarti
      // il comando da battere. Un bottone che fa `launchctl bootout` sarebbe
      // potere che questa pagina non ha nessun bisogno di avere.
      const b = el("button", "ghost", "copia");
      b.type = "button";
      b.title = r.azione;
      b.addEventListener("click", () => copia(r.azione));
      azione.append(b);
    }
    riga.append(azione);
    return riga;
  }

  function disegnaStrati(dati) {
    const box = $("strati"), indice = $("indice");
    box.textContent = "";
    indice.textContent = "";

    for (const s of dati.strati) {
      const righe = dati.righe.filter((r) => r.strato === s.nome);
      const quanti = righe.length;

      const voce = el("a", "indice-voce" + (quanti ? "" : " vuoto") +
                      (s.nome === "orfani" && quanti ? " grave" : ""));
      voce.href = "#strato-" + s.nome;
      voce.append(el("span", null, s.nome));
      voce.append(el("em", null, String(quanti)));
      indice.append(voce);

      const sez = el("section", "strato " + s.nome);
      sez.id = "strato-" + s.nome;
      const testa = el("header");
      testa.append(el("h2", null, s.nome));
      testa.append(el("p", null, s.spiega));
      if (quanti) testa.append(el("span", "quanti", quanti + (quanti === 1 ? " voce" : " voci")));
      sez.append(testa);

      if (!quanti) {
        sez.append(el("div", "vuoto-strato", "niente."));
      } else {
        for (const r of righe) sez.append(disegnaRiga(r));
      }
      box.append(sez);
    }
  }

  /* ------------------------------------------------------------- conferme */

  function chiedi({ titolo, testo, pre, conseguenza, verbo }) {
    const d = $("conferma");
    $("conferma-titolo").textContent = titolo;
    $("conferma-testo").textContent = testo;
    const blocco = $("conferma-pre");
    blocco.textContent = pre || "";
    blocco.hidden = !pre;
    $("conferma-conseguenza").textContent = conseguenza;
    $("conferma-si").textContent = verbo;
    return new Promise((risolvi) => {
      const chiudi = (risposta) => {
        $("conferma-si").removeEventListener("click", si);
        $("conferma-no").removeEventListener("click", no);
        d.removeEventListener("cancel", no);
        d.close();
        risolvi(risposta);
      };
      const si = () => chiudi(true);
      const no = () => chiudi(false);
      $("conferma-si").addEventListener("click", si);
      $("conferma-no").addEventListener("click", no);
      // esc chiude il dialogo: e' sempre un no.
      d.addEventListener("cancel", no);
      d.showModal();
    });
  }

  async function chiediFerma(r) {
    const dove = r.dove ? "\nin " + r.dove : "";
    let conseguenza =
      "faro gli chiede di uscire con SIGTERM, una volta sola. " +
      "Se non esce, te lo dice e lo lascia dov'e'.";
    if (r.strato === "sessioni") {
      conseguenza = "Questa e' una sessione di Claude Code viva: quello che sta " +
        "facendo si ferma qui, e la memoria di quella sessione con lui. " + conseguenza;
    }
    const ok = await chiedi({
      titolo: "Fermare il pid " + r.pid + "?",
      testo: r.nome + " · " + (r.rss_umano || "?") + " di memoria · avviato da " +
             (r.eta_umana || "?") + dove,
      conseguenza,
      verbo: "ferma il pid " + r.pid,
    });
    if (!ok) return;
    try {
      const esito = await api("/api/ferma", { pid: r.pid });
      nota(esito.testo || "fatto.", esito.codice !== 0);
      aggiorna();
    } catch (e) { if (e.message !== "403") nota("non ha funzionato: " + e.message, true); }
  }

  async function chiediReap() {
    let prova;
    try {
      prova = await api("/api/reap", { esegui: false });
    } catch (e) {
      if (e.message !== "403") nota("non ha funzionato: " + e.message, true);
      return;
    }
    if (prova.testo.indexOf("niente da chiudere") === 0) { nota(prova.testo); return; }
    const ok = await chiedi({
      titolo: "Chiudere gli orfani?",
      testo: "Questi sono i processi che nessuna sessione fermera' piu'. " +
             "Sotto c'e' la stessa lista che stampa `faro reap`.",
      pre: prova.testo,
      conseguenza: "La lista viene ricalcolata nel momento in cui confermi, mai presa " +
        "da questa schermata: un pid letto un minuto fa puo' essere gia' di qualcun " +
        "altro. Prima SIGTERM, poi SIGKILL solo a chi non e' uscito.",
      verbo: "chiudili",
    });
    if (!ok) return;
    try {
      const esito = await api("/api/reap", { esegui: true });
      nota(esito.testo || "fatto.", esito.codice !== 0);
      aggiorna();
    } catch (e) { if (e.message !== "403") nota("non ha funzionato: " + e.message, true); }
  }

  /* ------------------------------------------------------------- il giro */

  function battito(testo, classe) {
    $("battito").textContent = testo;
    $("punto").className = "punto" + (classe ? " " + classe : "");
  }

  async function aggiorna() {
    if (spento) return;
    if (attesa) { clearTimeout(attesa); attesa = null; }
    battito("lettura", "lavora");
    try {
      const dati = await api("/api/stato");
      disegnaMemoria(dati);
      disegnaAvvisi(dati.notizie);
      // Ridisegnare sei sezioni ogni cinque secondi farebbe sfarfallare la
      // pagina anche quando non e' cambiato niente, e non e' cambiato niente
      // quasi sempre.
      const nuova = JSON.stringify(dati.righe);
      if (nuova !== firma) { firma = nuova; disegnaStrati(dati); }
      ultimo = Date.now();
      battito(fermo ? "in pausa" : "aggiornato", fermo ? "ferma" : "");
    } catch (e) {
      if (e.message === "403") return;
      // Il caso normale di questo errore e' il piu' bello: hai premuto ctrl-c.
      battito("il server non c'e' piu'", "ferma");
      nota("Il server non risponde: probabilmente hai chiuso `faro gui` nel " +
           "terminale. E' cosi' che deve funzionare, faro non lascia niente acceso.",
           true);
      spento = true;
      return;
    }
    programma();
  }

  function programma() {
    if (attesa) clearTimeout(attesa);
    if (fermo || spento) return;
    attesa = setTimeout(() => {
      // Con la scheda nascosta non si legge la macchina: `ps` e `lsof` costano,
      // e nessuno sta guardando (CLAUDE.md, invariante 7).
      if (document.hidden || $("conferma").open) { programma(); return; }
      aggiorna();
    }, OGNI);
  }

  document.addEventListener("visibilitychange", () => {
    if (!document.hidden && !fermo && !spento && Date.now() - ultimo > OGNI) aggiorna();
  });

  $("pausa").addEventListener("click", () => {
    fermo = !fermo;
    $("pausa").textContent = fermo ? "riprendi" : "pausa";
    if (fermo) { battito("in pausa", "ferma"); if (attesa) clearTimeout(attesa); }
    else aggiorna();
  });

  aggiorna();
})();
