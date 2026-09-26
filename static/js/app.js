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
  }

  // ---------------------------------------------------------------- profil de wallet
  function statCard(label, value, klass) {
    return '<div class="stat"><small>' + label + '</small><b class="' + (klass || "") + '">' + value + "</b></div>";
  }

  function initTrader() {
    const root = document.getElementById("trader-root");
    const wallet = root.getAttribute("data-wallet");
    const loggedIn = root.getAttribute("data-logged-in") === "1";
    U.applyAvatars(document);

    const copyBtn = document.getElementById("copy-addr");
    copyBtn.addEventListener("click", function () {
      U.copyText(copyBtn.getAttribute("data-value")).then(function () {
        copyBtn.textContent = "Adresse copiée";
        setTimeout(function () { copyBtn.textContent = "Copier l'adresse"; }, 1500);
      });
    });

    const now = nowSec();
    const s7 = E.traderStats(wallet, now, 7);
    const s30 = E.traderStats(wallet, now, 30);

    document.getElementById("trader-stats").innerHTML =
      statCard("PnL 7J", U.pct(s7.pnlPct, Math.abs(s7.pnlPct) >= 10 ? 0 : 1), U.cls(s7.pnlPct)) +
      statCard("PnL 30J", U.pct(s30.pnlPct, Math.abs(s30.pnlPct) >= 10 ? 0 : 1), U.cls(s30.pnlPct)) +
      statCard("Win rate 30J", s30.winRate == null ? "—" : Math.round(s30.winRate * 100) + " %") +
      statCard("Trades 30J", String(s30.trades));

    const chartEl = document.getElementById("trader-chart");
    function drawChart(days) {
      U.lineChart(chartEl, (days === 7 ? s7 : s30).curve, { base: 10000 });
    }
    drawChart(30);
    document.getElementById("chart-seg").addEventListener("click", function (e) {
      const btn = e.target.closest("button");
      if (!btn) return;
      this.querySelectorAll("button").forEach(function (b) { b.classList.remove("active"); });
      btn.classList.add("active");
      drawChart(parseInt(btn.getAttribute("data-period"), 10));
    });

    const openRows = s30.open.map(function (p) {
      return "<tr><td><b>$" + U.esc(p.token) + "</b></td><td>" + U.timeAgo(p.openTime, now) +
        '</td><td class="' + U.cls(p.pnlPct) + '">' + U.pct(p.pnlPct) + "</td></tr>";
    }).join("");
    document.getElementById("open-table").innerHTML =
      "<thead><tr><th>Token</th><th>Ouverte</th><th>PnL</th></tr></thead><tbody>" +
      (openRows || '<tr><td colspan="3" class="empty-note">Aucune position ouverte.</td></tr>') + "</tbody>";

    const closedRows = s30.closed.slice(-10).reverse().map(function (c) {
      return "<tr><td><b>$" + U.esc(c.token) + "</b></td><td>" + U.timeAgo(c.closeTime, now) + "</td><td>" +
        U.duration(c.closeTime - c.openTime) + '</td><td class="' + U.cls(c.pnlPct) + '">' + U.pct(c.pnlPct) + "</td></tr>";
    }).join("");
    document.getElementById("closed-table").innerHTML =
      "<thead><tr><th>Token</th><th>Clôturé</th><th>Durée</th><th>Résultat</th></tr></thead><tbody>" +
      (closedRows || '<tr><td colspan="4" class="empty-note">Pas encore de trade.</td></tr>') + "</tbody>";

    // ----- panneau de copie
    const state = { balance: 10000, alloc_pct: 0.1, mode: "live", speed: 6000 };
    const panel = document.getElementById("copy-panel");
    const speedBlock = document.getElementById("speed-block");
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

    const startBtn = document.getElementById("start-sim");
    const errEl = document.getElementById("start-error");
    if (!loggedIn) startBtn.textContent = "Créer un compte et lancer";

    async function start() {
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
          }),
        }).then(async function (res) {
          if (res.status === 401) {
            window.location.href = "/auth/signup?next=" + encodeURIComponent(window.location.pathname + "?go=1");
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

    // Adresse collée depuis la page d'accueil : lancement direct si connecté.
    const params = new URLSearchParams(window.location.search);
    if (params.get("go") === "1") {
      history.replaceState(null, "", window.location.pathname);
      if (loggedIn) {
        startBtn.textContent = "Lancement…";
        start();
      } else {
        panel.classList.add("attention");
      }
    }
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
          ' <span class="badge ' + st.klass + '">' + st.label + "</span></small></span>" +
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
      el("btn-again").setAttribute("href", "/trader/" + encodeURIComponent(sim.wallet));
      const params = [
        ["Wallet", '<span title="' + U.esc(sim.wallet) + '">' + U.esc(E.shortAddress(sim.wallet)) + " (" + chainLabel(sim.chain) + ")</span>"],
        ["Solde de départ", U.usd(sim.balance)],
        ["Part par trade", Math.round(sim.alloc_pct * 100) + " %"],
        ["Mode", sim.mode === "live" ? "En direct (accéléré)" : "Backtest 30 jours"],
      ];
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
          "Jour " + res.simDays.toFixed(1).replace(".", ",") + " sur " + E.MAX_SIM_DAYS + " (temps accéléré ×" + sim.speed + ")";
      } else {
        wrap.hidden = true;
        el("sim-progress-label").textContent = "Rejeu des " + E.HISTORY_DAYS + " derniers jours de ce wallet.";
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
