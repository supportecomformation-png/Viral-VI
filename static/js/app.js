/* CopyLab — logique des pages (classement, profil de wallet, simulations). */
(function () {
  "use strict";

  const E = window.CopyEngine;
  const U = window.UI;
  const page = document.body.getAttribute("data-page") || "";

  function nowSec() {
    return Date.now() / 1000;
  }

  function $(sel, root) {
    return (root || document).querySelector(sel);
  }

  function chainLabel(chain) {
    return chain === "solana" ? "Solana" : "EVM";
  }

  async function api(url, options) {
    const opts = Object.assign({ credentials: "same-origin", headers: {} }, options || {});
    if (opts.body && !opts.headers["Content-Type"]) opts.headers["Content-Type"] = "application/json";
    const res = await fetch(url, opts);
    let data = null;
    try {
      data = await res.json();
    } catch (e) {}
    if (res.status === 401) {
      window.location.href = "/auth/login?next=" + encodeURIComponent(window.location.pathname + window.location.search);
      throw new Error("auth_required");
    }
    if (!res.ok) {
      const err = new Error((data && data.message) || "Erreur inattendue");
      err.status = res.status;
      throw err;
    }
    return data;
  }

  // ---------------------------------------------------------------- nav active
  (function markNav() {
    const map = { landing: "", traders: "traders", trader: "traders", app: "app", sim: "app" };
    const key = map[page];
    if (!key) return;
    const a = document.querySelector('.bottom-nav [data-nav="' + key + '"]');
    if (a) a.classList.add("active");
  })();

  // ---------------------------------------------------------------- coller un wallet
  function initPasteForms() {
    document.querySelectorAll(".paste-form").forEach(function (form) {
      const input = $(".paste-input", form);
      const err = form.parentElement.querySelector(".paste-error");

      function showError(msg) {
        if (!err) return;
        err.textContent = msg;
        err.hidden = false;
      }

      function go() {
        const v = input.value.trim();
        if (!v) return;
        if (!E.detectChain(v)) {
          showError("Adresse invalide : colle une adresse Solana (32-44 caractères) ou EVM (0x…).");
          return;
        }
        if (err) err.hidden = true;
        window.location.href = "/trader/" + encodeURIComponent(E.walletKey(v)) + "?go=1";
      }

      form.addEventListener("submit", function (e) {
        e.preventDefault();
        go();
      });
      // Coller une adresse valide lance directement la suite.
      input.addEventListener("paste", function () {
        setTimeout(function () {
          if (E.detectChain(input.value.trim())) go();
        }, 0);
      });
    });
  }

  // ---------------------------------------------------------------- classement
  function traderRow(t, stats, rank) {
    const wr = stats.winRate == null ? "—" : Math.round(stats.winRate * 100) + " %";
    return (
      '<a class="trader-row" href="/trader/' + encodeURIComponent(t.wallet) + '">' +
      '<span class="rank">' + rank + "</span>" +
      '<span class="avatar" style="' + U.avatarStyle(t.wallet) + '"></span>' +
      '<span class="t-id"><strong>' + U.esc(t.handle) + "</strong><small>" + U.esc(E.shortAddress(t.wallet)) +
      ' <span class="chain-badge chain-' + t.chain + '">' + chainLabel(t.chain) + "</span></small></span>" +
      '<span class="t-spark">' + U.sparkline(stats.curve.map(function (p) { return p.equity; })) + "</span>" +
      '<span class="t-stat"><b class="' + U.cls(stats.pnlPct) + '">' + U.pct(stats.pnlPct, Math.abs(stats.pnlPct) >= 10 ? 0 : 1) +
      "</b><small>PnL</small></span>" +
      '<span class="t-stat t-wr"><b>' + wr + "</b><small>Win rate</small></span>" +
      '<span class="t-cta btn btn-ghost btn-sm">Copier</span>' +
      "</a>"
    );
  }

  function computeAll(traders) {
    const now = nowSec();
    const out = {};
    [7, 30].forEach(function (days) {
      out[days] = {};
      traders.forEach(function (t) {
        out[days][t.wallet] = E.traderStats(t.wallet, now, days);
      });
    });
    return out;
  }

  function initLanding() {
    const el = $("#landing-traders");
    const traders = window.DEMO_TRADERS || [];
    if (!el || !traders.length) return;
    const all = computeAll(traders)[30];
    const ranked = traders.slice().sort(function (a, b) {
      return all[b.wallet].pnlPct - all[a.wallet].pnlPct;
    }).slice(0, 3);
    el.innerHTML = ranked.map(function (t, i) {
      return traderRow(t, all[t.wallet], i + 1);
    }).join("");
  }

  function initTraders() {
    const listEl = $("#trader-list");
    const traders = window.DEMO_TRADERS || [];
    const stats = computeAll(traders);
    let period = 30;
    let sort = "pnl";

    function render() {
      const s = stats[period];
      const ranked = traders.slice().sort(function (a, b) {
        if (sort === "winrate") return (s[b.wallet].winRate || 0) - (s[a.wallet].winRate || 0);
        return s[b.wallet].pnlPct - s[a.wallet].pnlPct;
      });
      listEl.innerHTML = ranked.map(function (t, i) {
        return traderRow(t, s[t.wallet], i + 1);
      }).join("");
    }

    function bindSeg(id, attr, setter) {
      const seg = document.getElementById(id);
      seg.addEventListener("click", function (e) {
        const btn = e.target.closest("button");
        if (!btn) return;
        seg.querySelectorAll("button").forEach(function (b) { b.classList.remove("active"); });
        btn.classList.add("active");
        setter(btn.getAttribute(attr));
        render();
      });
    }
    bindSeg("period-seg", "data-period", function (v) { period = parseInt(v, 10); });
    bindSeg("sort-seg", "data-sort", function (v) { sort = v; });
    render();

    // Wallets réels récemment analysés (uniquement si les données on-chain sont branchées).
    const realSection = document.getElementById("real-section");
    if (realSection) {
      const realList = document.getElementById("real-list");
      fetch("/api/wallets/leaderboard", { credentials: "same-origin" })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          const wallets = data.wallets || [];
          if (!wallets.length) {
            realList.innerHTML = '<p class="empty-note">Aucun wallet analysé pour l\'instant : colle une adresse ci-dessus, elle apparaîtra ici si elle a assez de trades.</p>';
            return;
          }
          realList.innerHTML = wallets.map(function (w, i) {
            const netLabel = w.chain === "solana" ? "Solana" : (w.network || "EVM");
            return (
              '<a class="trader-row" href="/trader/' + encodeURIComponent(w.wallet) + "?network=" + encodeURIComponent(w.network) + '">' +
              '<span class="rank">' + (i + 1) + "</span>" +
              '<span class="avatar" style="' + U.avatarStyle(w.wallet) + '"></span>' +
              '<span class="t-id"><strong>' + U.esc(E.shortAddress(w.wallet)) + "</strong><small>" + U.esc(netLabel) +
              " · " + w.trades + " trades</small></span>" +
              '<span class="t-spark">' + U.sparkline(w.curve) + "</span>" +
              '<span class="t-stat"><b class="' + U.cls(w.roi) + '">' + U.pct(w.roi, Math.abs(w.roi) >= 10 ? 0 : 1) +
              "</b><small>ROI réalisé</small></span>" +
              '<span class="t-stat t-wr"><b>' + (w.win_rate == null ? "—" : Math.round(w.win_rate * 100) + " %") + "</b><small>Win rate</small></span>" +
              '<span class="t-cta btn btn-ghost btn-sm">Copier</span>' +
              "</a>"
            );
          }).join("");
        })
        .catch(function () {
          realList.innerHTML = '<p class="empty-note">Classement indisponible pour le moment.</p>';
        });
    }
  }

  // ---------------------------------------------------------------- profil de wallet
  function statCard(label, value, klass) {
    return '<div class="stat"><small>' + label + '</small><b class="' + (klass || "") + '">' + value + "</b></div>";
  }

  const SIM_NOTICE_HTML =
    "Track record <strong>simulé</strong> : généré à partir de l'adresse, ce ne sont pas les vraies transactions de ce wallet.";

  function initTrader() {
    const root = document.getElementById("trader-root");
    const wallet = root.getAttribute("data-wallet");
    const chain = root.getAttribute("data-chain");
    const loggedIn = root.getAttribute("data-logged-in") === "1";
    const onchainAvailable = root.getAttribute("data-onchain") === "1";
    let network = root.getAttribute("data-network") || (chain === "solana" ? "solana" : "base");
    U.applyAvatars(document);

    const copyBtn = document.getElementById("copy-addr");
    copyBtn.addEventListener("click", function () {
      U.copyText(copyBtn.getAttribute("data-value")).then(function () {
        copyBtn.textContent = "Adresse copiée";
        setTimeout(function () { copyBtn.textContent = "Copier l'adresse"; }, 1500);
      });
    });

    const el = function (id) { return document.getElementById(id); };
    const noticeEl = el("data-notice");
    const stateEl = el("trader-state");
    const contentEl = el("trader-content");
    const startBtn = el("start-sim");
    const errEl = el("start-error");
    const panel = el("copy-panel");
    const speedBlock = el("speed-block");

    // Source de données courante : "simulated" ou "onchain" (charge utile Moralis).
    let dataSource = "simulated";
    let payload = null;
    let ready = false;

    // ----- panneau de copie
    const state = { balance: 10000, alloc_pct: 0.1, mode: "live", speed: 6000 };
    panel.querySelectorAll(".chips").forEach(function (group) {
      group.addEventListener("click", function (e) {
        const btn = e.target.closest("button");
        if (!btn) return;
        group.querySelectorAll("button").forEach(function (b) { b.classList.remove("active"); });
        btn.classList.add("active");
        const field = group.getAttribute("data-field");
        const raw = btn.getAttribute("data-value");
        state[field] = field === "mode" ? raw : parseFloat(raw);
        if (field === "mode") speedBlock.hidden = raw === "backtest";
      });
    });
    if (!loggedIn) startBtn.textContent = "Créer un compte et lancer";

    function setStartEnabled(enabled) {
      startBtn.disabled = !enabled;
    }

    function relabelModes() {
      const live = panel.querySelector('[data-field="mode"] [data-value="live"]');
      const back = panel.querySelector('[data-field="mode"] [data-value="backtest"]');
      if (dataSource === "onchain") {
        live.textContent = "Rejeu accéléré des 30 derniers jours réels";
        back.textContent = "Résultat instantané sur 30 jours réels";
      } else {
        live.textContent = "En direct (temps accéléré)";
        back.textContent = "Rejouer les 30 derniers jours";
      }
    }

    // ----- affichage
    function setNotice(html, klass) {
      noticeEl.className = "sim-notice" + (klass ? " " + klass : "");
      noticeEl.innerHTML = html;
    }

    function showState(html, withRetry) {
      contentEl.hidden = true;
      stateEl.hidden = false;
      stateEl.innerHTML = '<p class="state-msg">' + html + "</p>" +
        (withRetry ? '<button type="button" class="btn btn-ghost btn-sm" id="retry-load">Réessayer</button>' : "");
      const retry = el("retry-load");
      if (retry) retry.addEventListener("click", load);
    }

    function render() {
      stateEl.hidden = true;
      contentEl.hidden = false;
      const real = dataSource === "onchain" ? payload.trades : null;
      const now = dataSource === "onchain" ? payload.window_end : nowSec();
      const s7 = E.traderStats(wallet, now, 7, real);
      const s30 = E.traderStats(wallet, now, 30, real);

      el("trader-stats").innerHTML =
        statCard("PnL 7J", U.pct(s7.pnlPct, Math.abs(s7.pnlPct) >= 10 ? 0 : 1), U.cls(s7.pnlPct)) +
        statCard("PnL 30J", U.pct(s30.pnlPct, Math.abs(s30.pnlPct) >= 10 ? 0 : 1), U.cls(s30.pnlPct)) +
        statCard("Win rate 30J", s30.winRate == null ? "—" : Math.round(s30.winRate * 100) + " %") +
        statCard("Trades 30J", String(s30.trades));

      const chartEl = el("trader-chart");
      const drawChart = function (days) {
        U.lineChart(chartEl, (days === 7 ? s7 : s30).curve, { base: 10000 });
      };
      const activeSeg = el("chart-seg").querySelector("button.active");
      drawChart(activeSeg ? parseInt(activeSeg.getAttribute("data-period"), 10) : 30);
      el("chart-seg").onclick = function (e) {
        const btn = e.target.closest("button");
        if (!btn) return;
        this.querySelectorAll("button").forEach(function (b) { b.classList.remove("active"); });
        btn.classList.add("active");
        drawChart(parseInt(btn.getAttribute("data-period"), 10));
      };

      // Positions ouvertes
      if (dataSource === "onchain") {
        const rows = (payload.open_positions || []).map(function (p) {
          return "<tr><td><b>$" + U.esc(p.token) + "</b></td><td>" + U.timeAgo(p.open, now) + "</td><td>" +
            U.usd(p.cost_usd) + "</td></tr>";
        }).join("");
        el("open-table").innerHTML =
          "<thead><tr><th>Token</th><th>Ouverte</th><th>Coût d'entrée</th></tr></thead><tbody>" +
          (rows || '<tr><td colspan="3" class="empty-note">Aucune position ouverte détectée.</td></tr>') + "</tbody>";
        el("open-note").hidden = false;
      } else {
        const rows = s30.open.map(function (p) {
          return "<tr><td><b>$" + U.esc(p.token) + "</b></td><td>" + U.timeAgo(p.openTime, now) +
            '</td><td class="' + U.cls(p.pnlPct) + '">' + U.pct(p.pnlPct) + "</td></tr>";
        }).join("");
        el("open-table").innerHTML =
          "<thead><tr><th>Token</th><th>Ouverte</th><th>PnL</th></tr></thead><tbody>" +
          (rows || '<tr><td colspan="3" class="empty-note">Aucune position ouverte.</td></tr>') + "</tbody>";
        el("open-note").hidden = true;
      }

      // Derniers trades clôturés
      const sizeById = {};
      if (real) real.forEach(function (t) { sizeById[t.id] = t.size_usd; });
      const closedRows = s30.closed.slice(-10).reverse().map(function (c) {
        const size = real ? "<td>" + U.usd(sizeById[c.id] || 0) + "</td>" : "";
        return "<tr><td><b>$" + U.esc(c.token) + "</b></td><td>" + U.timeAgo(c.closeTime, now) + "</td><td>" +
          U.duration(c.closeTime - c.openTime) + "</td>" + size + '<td class="' + U.cls(c.pnlPct) + '">' + U.pct(c.pnlPct) + "</td></tr>";
      }).join("");
      const sizeHead = real ? "<th>Taille</th>" : "";
      el("closed-table").innerHTML =
        "<thead><tr><th>Token</th><th>Clôturé</th><th>Durée</th>" + sizeHead + "<th>Résultat</th></tr></thead><tbody>" +
        (closedRows || '<tr><td colspan="5" class="empty-note">Pas encore de trade.</td></tr>') + "</tbody>";
    }

    function ingest(data) {
      if (data.source === "onchain") {
        dataSource = "onchain";
        payload = data;
        const partial = data.truncated
          ? " Historique partiel : seuls les swaps les plus récents ont pu être analysés."
          : "";
        setNotice(
          "<strong>Données on-chain réelles</strong> (" + data.swaps_count + " swaps DEX sur 30 jours, via Moralis). " +
          "Seuls les trades clôturés sont comptés ; le PnL est réalisé et estimé en dollars, et la courbe entre l'entrée " +
          "et la sortie de chaque trade est interpolée." + partial,
          "real"
        );
        if (!data.trades.length) {
          ready = false;
          setStartEnabled(false);
          relabelModes();
          showState(
            "Aucun trade clôturé détecté sur les 30 derniers jours pour ce wallet" +
            (chain === "evm" ? " sur ce réseau. Essaie un autre réseau ci-dessus." : ".") +
            " Il n'y a rien à copier.",
            false
          );
          return;
        }
      } else {
        dataSource = "simulated";
        payload = null;
        setNotice(SIM_NOTICE_HTML, "");
      }
      ready = true;
      setStartEnabled(true);
      relabelModes();
      render();
    }

    async function load() {
      ready = false;
      if (!onchainAvailable) {
        ingest({ source: "simulated" });
        maybeAutostart();
        return;
      }
      setStartEnabled(false);
      setNotice("Chargement des données on-chain…", "");
      showState('<span class="spinner"></span> Analyse des swaps du wallet en cours…', false);
      try {
        const res = await fetch("/api/wallet/" + encodeURIComponent(wallet) + "/trades?network=" + encodeURIComponent(network), {
          credentials: "same-origin",
        });
        const body = await res.json().catch(function () { return {}; });
        if (!res.ok) throw new Error(body.message || "Données on-chain indisponibles.");
        ingest(body);
      } catch (err) {
        setNotice("Données on-chain indisponibles.", "");
        setStartEnabled(false);
        showState(U.esc(err.message), true);
      }
      maybeAutostart();
    }

    // Sélecteur de réseau EVM
    const netSeg = el("network-seg");
    if (netSeg) {
      netSeg.addEventListener("click", function (e) {
        const btn = e.target.closest("button");
        if (!btn) return;
        netSeg.querySelectorAll("button").forEach(function (b) { b.classList.remove("active"); });
        btn.classList.add("active");
        network = btn.getAttribute("data-network");
        history.replaceState(null, "", window.location.pathname + "?network=" + encodeURIComponent(network));
        load();
      });
    }

    async function start() {
      if (!ready) return;
      errEl.hidden = true;
      startBtn.disabled = true;
      try {
        const data = await fetch("/api/simulations", {
          method: "POST",
          credentials: "same-origin",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            wallet: wallet,
            balance: state.balance,
            alloc_pct: state.alloc_pct,
            mode: state.mode,
            speed: state.speed,
            source: dataSource,
            network: dataSource === "onchain" ? network : null,
          }),
        }).then(async function (res) {
          if (res.status === 401) {
            window.location.href = "/auth/signup?next=" +
              encodeURIComponent(window.location.pathname + "?go=1&network=" + encodeURIComponent(network));
            return null;
          }
          const body = await res.json().catch(function () { return {}; });
          if (!res.ok) throw new Error(body.message || "Impossible de lancer la simulation.");
          return body;
        });
        if (data) window.location.href = "/sim/" + data.simulation.id;
      } catch (err) {
        errEl.textContent = err.message;
        errEl.hidden = false;
        startBtn.disabled = false;
      }
    }
    startBtn.addEventListener("click", start);

    // Adresse collée depuis la page d'accueil : lancement direct si connecté
    // (une fois les données chargées).
    let autostart = new URLSearchParams(window.location.search).get("go") === "1";
    if (autostart) {
      history.replaceState(null, "", window.location.pathname + (onchainAvailable && chain === "evm" ? "?network=" + encodeURIComponent(network) : ""));
    }
    function maybeAutostart() {
      if (!autostart || !ready) return;
      autostart = false;
      if (loggedIn) {
        startBtn.textContent = "Lancement…";
        start();
      } else {
        panel.classList.add("attention");
      }
    }

    load();
  }

  // ---------------------------------------------------------------- mes simulations
  function statusInfo(sim, res) {
    if (sim.mode === "backtest") return { label: "Backtest 30J", klass: "badge-muted" };
    if (res.status === "active") return { label: "En cours", klass: "badge-live" };
    if (res.status === "stopped") return { label: "Arrêtée", klass: "badge-muted" };
    return { label: "Terminée", klass: "badge-muted" };
  }

  function initApp() {
    const listEl = document.getElementById("sim-list");
    let sims = [];
    let offset = 0;

    function render() {
      if (!sims.length) {
        listEl.innerHTML = '<p class="empty-note">Aucune simulation pour l\'instant. Copie un wallet pour commencer.</p>';
        return false;
      }
      let anyActive = false;
      const now = nowSec() + offset;
      listEl.innerHTML = sims.map(function (s) {
        const res = E.evaluateSimulation(s, now);
        if (res.status === "active") anyActive = true;
        const st = statusInfo(s, res);
        const name = s.handle || "Wallet " + E.shortAddress(s.wallet);
        return (
          '<a class="sim-card" href="/sim/' + s.id + '">' +
          '<span class="avatar" style="' + U.avatarStyle(s.wallet) + '"></span>' +
          '<span class="t-id"><strong>' + U.esc(name) + '</strong><small>' + U.esc(E.shortAddress(s.wallet)) +
          ' <span class="badge ' + st.klass + '">' + st.label + "</span>" +
          (s.source === "onchain" ? ' <span class="badge badge-live">On-chain</span>' : "") + "</small></span>" +
          '<span class="t-spark">' + U.sparkline(res.curve.map(function (p) { return p.equity; })) + "</span>" +
          '<span class="t-stat"><b>' + U.usd(res.equity) + '</b><small class="' + U.cls(res.pnlPct) + '">' +
          U.pct(res.pnlPct) + "</small></span>" +
          "</a>"
        );
      }).join("");
      return anyActive;
    }

    api("/api/simulations").then(function (data) {
      sims = data.simulations;
      offset = data.server_now - nowSec();
      const active = render();
      if (active) {
        setInterval(render, 4000);
      }
    }).catch(function (err) {
      if (err.message !== "auth_required") listEl.innerHTML = '<p class="empty-note">' + U.esc(err.message) + "</p>";
    });
  }

  // ---------------------------------------------------------------- suivi d'une simulation
  function initSim() {
    const root = document.getElementById("sim-root");
    const id = root.getAttribute("data-sim-id");
    let sim = null;
    let offset = 0;
    let timer = null;

    const el = function (i) { return document.getElementById(i); };

    function setSim(data) {
      sim = data.simulation;
      offset = data.server_now - nowSec();
    }

    function drawStatic() {
      const name = sim.handle || "Wallet " + E.shortAddress(sim.wallet);
      el("sim-name").textContent = name;
      el("sim-addr").textContent = E.shortAddress(sim.wallet);
      el("sim-avatar").setAttribute("style", U.avatarStyle(sim.wallet));
      const onchain = sim.source === "onchain";
      el("btn-again").setAttribute(
        "href",
        "/trader/" + encodeURIComponent(sim.wallet) + (onchain && sim.network ? "?network=" + encodeURIComponent(sim.network) : "")
      );
      const srcBadge = el("sim-source");
      srcBadge.textContent = onchain ? "Données on-chain" : "Données simulées";
      srcBadge.className = "badge " + (onchain ? "badge-live" : "badge-muted");
      const params = [
        ["Wallet", '<span title="' + U.esc(sim.wallet) + '">' + U.esc(E.shortAddress(sim.wallet)) + " (" + chainLabel(sim.chain) + ")</span>"],
        ["Données", onchain ? "On-chain réelles (Moralis)" : "Simulées"],
      ];
      if (onchain && sim.network && sim.network !== "solana") params.push(["Réseau", U.esc(sim.network)]);
      params.push(
        ["Solde de départ", U.usd(sim.balance)],
        ["Part par trade", Math.round(sim.alloc_pct * 100) + " %"],
        ["Mode", sim.mode === "live"
          ? (onchain ? "Rejeu accéléré (30 j réels)" : "En direct (accéléré)")
          : (onchain ? "Instantané (30 j réels)" : "Backtest 30 jours")]
      );
      if (sim.mode === "live") params.push(["Vitesse", "×" + sim.speed]);
      params.push(["Lancée le", U.fmtDateTime(sim.started_at)]);
      el("sim-params").innerHTML = params.map(function (p) {
        return "<dt>" + p[0] + "</dt><dd>" + p[1] + "</dd>";
      }).join("");
    }

    function draw() {
      const res = E.evaluateSimulation(sim, nowSec() + offset);
      const st = statusInfo(sim, res);
      const badge = el("sim-status");
      badge.textContent = st.label;
      badge.className = "badge " + st.klass;

      el("sim-equity").textContent = U.usd(res.equity);
      const pnlEl = el("sim-pnl");
      pnlEl.className = "equity-pnl " + U.cls(res.pnl);
      pnlEl.textContent = U.usd(res.pnl, { sign: true }) + "  ·  " + U.pct(res.pnlPct);

      U.lineChart(el("sim-chart"), res.curve, { base: sim.balance });

      const invested = res.equity - res.cash;
      el("sim-stats").innerHTML =
        statCard("Cash disponible", U.usd(res.cash)) +
        statCard("Investi", U.usd(invested)) +
        statCard("Trades clôturés", String(res.tradesCount)) +
        statCard("Win rate", res.winRate == null ? "—" : Math.round(res.winRate * 100) + " %");

      const wrap = el("sim-progress-wrap");
      if (res.progress != null) {
        wrap.hidden = false;
        el("sim-progress").style.width = Math.min(100, res.progress * 100).toFixed(1) + "%";
        el("sim-progress-label").textContent =
          "Jour " + res.simDays.toFixed(1).replace(".", ",") + " sur " + Math.round(res.horizonDays) + " (temps accéléré ×" + sim.speed + ")";
      } else {
        wrap.hidden = true;
        el("sim-progress-label").textContent = res.source === "onchain"
          ? "Rejeu des " + Math.round(res.horizonDays) + " derniers jours réels de ce wallet (trades on-chain)."
          : "Rejeu des " + E.HISTORY_DAYS + " derniers jours de ce wallet.";
      }

      const openRows = res.open.map(function (p) {
        return "<tr><td><b>$" + U.esc(p.token) + "</b></td><td>" + U.fmtSimTime(p.openTime) + "</td><td>" +
          U.usd(p.invested) + "</td><td>" + U.usd(p.value) + '</td><td class="' + U.cls(p.pnlPct) + '">' + U.pct(p.pnlPct) + "</td></tr>";
      }).join("");
      el("sim-open").innerHTML =
        "<thead><tr><th>Token</th><th>Ouverte</th><th>Investi</th><th>Valeur</th><th>PnL</th></tr></thead><tbody>" +
        (openRows || '<tr><td colspan="5" class="empty-note">Aucune position ouverte pour le moment.</td></tr>') + "</tbody>";

      const feedHtml = res.feed.map(function (f) {
        if (f.type === "open") {
          return '<li><span class="feed-dot buy"></span><div><b>Achat $' + U.esc(f.token) + "</b><small>" +
            U.fmtSimTime(f.time) + " · " + U.usd(f.size) + "</small></div></li>";
        }
        return '<li><span class="feed-dot sell"></span><div><b>Vente $' + U.esc(f.token) + ' <span class="' + U.cls(f.pnl) + '">' +
          U.pct(f.pnlPct) + "</span></b><small>" + U.fmtSimTime(f.time) + " · " + U.usd(f.pnl, { sign: true }) + "</small></div></li>";
      }).join("");
      el("sim-feed").innerHTML = feedHtml || '<li class="empty-note">Aucun trade copié pour le moment — patience, le wallet n\'a pas encore bougé.</li>';

      const stopBtn = el("btn-stop");
      stopBtn.hidden = !(sim.mode === "live" && res.status === "active");

      if (res.status !== "active" && timer) {
        clearInterval(timer);
        timer = null;
      }
    }

    api("/api/simulations/" + id).then(function (data) {
      setSim(data);
      drawStatic();
      draw();
      if (sim.mode === "live" && sim.stopped_at == null) {
        timer = setInterval(draw, 1500);
      }
    }).catch(function (err) {
      if (err.message !== "auth_required") el("sim-name").textContent = err.message;
    });

    el("btn-stop").addEventListener("click", function () {
      api("/api/simulations/" + id + "/stop", { method: "POST" }).then(function (data) {
        setSim(data);
        draw();
      });
    });

    el("btn-delete").addEventListener("click", function () {
      if (!window.confirm("Supprimer définitivement cette simulation ?")) return;
      api("/api/simulations/" + id, { method: "DELETE" }).then(function () {
        window.location.href = "/app";
      });
    });
  }

  // ---------------------------------------------------------------- démarrage
  initPasteForms();
  if (page === "landing") initLanding();
  else if (page === "traders") initTraders();
  else if (page === "trader") initTrader();
  else if (page === "app") initApp();
  else if (page === "sim") initSim();
})();
