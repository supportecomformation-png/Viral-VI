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
    const map = { home: "home", traders: "traders", trader: "traders", app: "app", sim: "app" };
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

  // ---------------------------------------------------------------- accueil
  const STAR_PATH = "M12 3.5l2.6 5.3 5.9.9-4.3 4.1 1 5.8L12 16.9 6.8 19.6l1-5.8L3.5 9.7l5.9-.9z";

  function initHome() {
    // ----- solde fictif (stocké dans le navigateur : aucun vrai fonds, aucun serveur)
    const BAL_KEY = "copylab_demo_balance";
    const MAX_BALANCE = 10000000;
    const MAX_DEPOSIT = 1000000;
    const balEl = document.getElementById("balance-value");

    function readBalance() {
      try {
        const v = parseFloat(localStorage.getItem(BAL_KEY));
        return isFinite(v) && v > 0 ? Math.min(v, MAX_BALANCE) : 0;
      } catch (e) {
        return 0;
      }
    }
    function writeBalance(v) {
      try { localStorage.setItem(BAL_KEY, String(v)); } catch (e) {}
    }
    function renderBalance() {
      const v = readBalance();
      const whole = Math.floor(v);
      const cents = Math.round((v - whole) * 100);
      balEl.innerHTML = whole.toLocaleString("fr-FR") + '<span class="cents">,' + (cents < 10 ? "0" : "") + cents + " $</span>";
    }
    renderBalance();

    const sheet = document.getElementById("deposit-sheet");
    const chips = document.getElementById("deposit-chips");
    const custom = document.getElementById("deposit-custom");
    const depErr = document.getElementById("deposit-error");
    let chosen = 10000;
    function openSheet() { depErr.hidden = true; custom.value = ""; sheet.hidden = false; }
    function closeSheet() { sheet.hidden = true; }
    document.getElementById("open-deposit").addEventListener("click", openSheet);
    document.getElementById("close-deposit").addEventListener("click", closeSheet);
    sheet.addEventListener("click", function (e) { if (e.target === sheet) closeSheet(); });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape") closeSheet(); });
    chips.addEventListener("click", function (e) {
      const btn = e.target.closest("button");
      if (!btn) return;
      chips.querySelectorAll("button").forEach(function (b) { b.classList.remove("active"); });
      btn.classList.add("active");
      chosen = parseFloat(btn.getAttribute("data-amount"));
      custom.value = "";
    });
    custom.addEventListener("input", function () {
      if (custom.value) chips.querySelectorAll("button").forEach(function (b) { b.classList.remove("active"); });
    });
    document.getElementById("confirm-deposit").addEventListener("click", function () {
      const amount = custom.value ? parseFloat(custom.value) : chosen;
      let msg = null;
      if (!isFinite(amount) || amount < 1) msg = "Entre un montant d'au moins 1 $.";
      else if (amount > MAX_DEPOSIT) msg = "Maximum " + MAX_DEPOSIT.toLocaleString("fr-FR") + " $ par dépôt fictif.";
      else if (readBalance() + amount > MAX_BALANCE) msg = "Solde fictif maximal atteint (" + MAX_BALANCE.toLocaleString("fr-FR") + " $).";
      if (msg) {
        depErr.textContent = msg;
        depErr.hidden = false;
        return;
      }
      writeBalance(Math.round((readBalance() + amount) * 100) / 100);
      renderBalance();
      closeSheet();
    });

    // ----- meilleurs traders de la semaine (track records simulés des traders vedettes)
    const railEl = document.getElementById("top-traders");
    const traders = window.DEMO_TRADERS || [];
    const now = nowSec();
    railEl.innerHTML = traders.map(function (t) {
      return { t: t, s: E.traderStats(t.wallet, now, 7) };
    }).sort(function (a, b) { return b.s.pnlPct - a.s.pnlPct; }).slice(0, 8).map(function (x) {
      return (
        '<a class="rail-card" href="/trader/' + encodeURIComponent(x.t.wallet) + '">' +
        '<span class="rail-head"><span class="avatar" style="' + U.avatarStyle(x.t.wallet) + '"></span>' + U.esc(x.t.handle) + "</span>" +
        '<span class="rail-pnl ' + U.cls(x.s.pnlPct) + '">' + U.pct(x.s.pnlPct, Math.abs(x.s.pnlPct) >= 10 ? 0 : 1) + "</span>" +
        "<small>PnL 7J</small></a>"
      );
    }).join("");

    // ----- marchés : liste des cryptomonnaies
    const listEl = document.getElementById("market-list");
    const moreWrap = document.getElementById("market-more");
    const noteEl = document.getElementById("market-note");
    const searchEl = document.getElementById("market-search");

    function readFavs() {
      try { return new Set(JSON.parse(localStorage.getItem("copylab_favs") || "[]")); } catch (e) { return new Set(); }
    }
    const state = { tab: "tokens", filter: "crypto", query: "", limit: 100, coins: [], prev: {}, favs: readFavs(), ready: false };
    function writeFavs() {
      try { localStorage.setItem("copylab_favs", JSON.stringify(Array.from(state.favs))); } catch (e) {}
    }

    function visibleCoins() {
      let list = state.coins.slice();
      if (state.tab === "favs") list = list.filter(function (c) { return state.favs.has(c.id); });
      const q = state.query.trim().toLowerCase();
      if (q) {
        list = list.filter(function (c) {
          return c.symbol.toLowerCase().indexOf(q) !== -1 || c.name.toLowerCase().indexOf(q) !== -1;
        });
      } else if (state.filter !== "crypto") {
        list = list.slice(0, 100);
      }
      const by = function (key, dir) {
        list.sort(function (a, b) {
          const x = a[key] == null ? -Infinity : a[key];
          const y = b[key] == null ? -Infinity : b[key];
          return dir > 0 ? y - x : x - y;
        });
      };
      if (state.filter === "trending") by("change_24h", 1);
      else if (state.filter === "volume") by("volume", 1);
      else if (state.filter === "losers") by("change_24h", -1);
      return list;
    }

    function row(c) {
      const prev = state.prev[c.id];
      const flash = prev != null && prev !== c.price ? (c.price > prev ? " flash-up" : " flash-down") : "";
      const ch = c.change_24h;
      const chHtml = ch == null
        ? "<small>—</small>"
        : '<small class="' + U.cls(ch) + '">' + (ch >= 0 ? "▲ " : "▼ ") + Math.abs(ch).toFixed(2).replace(".", ",") + " %</small>";
      const on = state.favs.has(c.id);
      return (
        '<div class="coin-row' + flash + '">' +
        '<button type="button" class="fav-btn' + (on ? " on" : "") + '" data-fav="' + U.esc(c.id) + '" aria-label="Favori ' + U.esc(c.symbol) + '">' +
        '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="' + STAR_PATH + '" fill="' + (on ? "currentColor" : "none") + '" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/></svg></button>' +
        '<span class="coin-icon" style="' + U.avatarStyle(c.id) + '"><span>' + U.esc((c.symbol || "?").charAt(0)) + "</span>" +
        (c.image ? '<img src="' + U.esc(c.image) + '" alt="" loading="lazy" onerror="this.remove()">' : "") + "</span>" +
        '<span class="coin-id"><strong>' + U.esc(c.symbol) + "</strong><small>" + U.esc(U.compactUsd(c.market_cap)) + " cap.</small></span>" +
        '<span class="coin-price"><b>' + U.esc(U.price(c.price)) + "</b>" + chHtml + "</span></div>"
      );
    }

    function render() {
      if (!state.ready) return;
      const list = visibleCoins();
      if (!list.length) {
        listEl.innerHTML = '<p class="empty-note">' + (state.tab === "favs" && !state.query
          ? "Aucun favori pour l'instant : touche l'étoile d'un token pour l'ajouter."
          : "Aucun token ne correspond.") + "</p>";
        moreWrap.hidden = true;
        return;
      }
      listEl.innerHTML = list.slice(0, state.limit).map(row).join("");
      moreWrap.hidden = list.length <= state.limit;
    }

    function setActive(container, attr, value) {
      container.querySelectorAll("button").forEach(function (b) {
        b.classList.toggle("active", b.getAttribute(attr) === value);
      });
    }
    document.getElementById("market-tabs").addEventListener("click", function (e) {
      const btn = e.target.closest("button");
      if (!btn) return;
      state.tab = btn.getAttribute("data-tab");
      state.limit = 100;
      setActive(this, "data-tab", state.tab);
      render();
    });
    document.getElementById("market-filters").addEventListener("click", function (e) {
      const btn = e.target.closest("button");
      if (!btn) return;
      state.filter = btn.getAttribute("data-filter");
      state.limit = 100;
      setActive(this, "data-filter", state.filter);
      render();
    });
    searchEl.addEventListener("input", function () {
      state.query = searchEl.value;
      state.limit = 100;
      render();
    });
    listEl.addEventListener("click", function (e) {
      const btn = e.target.closest("[data-fav]");
      if (!btn) return;
      const id = btn.getAttribute("data-fav");
      if (state.favs.has(id)) state.favs.delete(id); else state.favs.add(id);
      writeFavs();
      render();
    });
    document.getElementById("market-more-btn").addEventListener("click", function () {
      state.limit += 100;
      render();
    });

    function load() {
      return fetch("/api/markets", { credentials: "same-origin" })
        .then(function (r) {
          return r.json().then(function (body) {
            if (!r.ok) throw new Error(body.message || "Prix indisponibles.");
            return body;
          });
        })
        .then(function (data) {
          const prev = {};
          state.coins.forEach(function (c) { prev[c.id] = c.price; });
          state.prev = prev;
          state.coins = data.coins || [];
          state.ready = true;
          const src = data.source === "coingecko" ? "CoinGecko" : "CoinPaprika";
          const at = new Date(data.fetched_at * 1000).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
          noteEl.textContent = data.stale
            ? "Prix en cache : le fournisseur est momentanément indisponible (dernière mise à jour à " + at + ")."
            : "Prix en dollars via " + src + ", actualisés toutes les 30 s (dernière mise à jour à " + at + ").";
          render();
        })
        .catch(function (err) {
          if (state.ready) return; // on garde la dernière liste affichée
          listEl.innerHTML = '<p class="empty-note">' + U.esc(err.message) +
            ' <button type="button" class="btn btn-ghost btn-sm" id="market-retry">Réessayer</button></p>';
          const retry = document.getElementById("market-retry");
          if (retry) retry.addEventListener("click", function () {
            listEl.innerHTML = '<p class="empty-note"><span class="spinner"></span> Chargement des prix…</p>';
            load();
          });
        });
    }
    load();
    setInterval(function () { if (!document.hidden) load(); }, 30000);
  }

  // ---------------------------------------------------------------- profil de wallet
  function statCard(label, value, klass) {
    return '<div class="stat"><small>' + label + '</small><b class="' + (klass || "") + '">' + value + "</b></div>";
  }

  function initTrader() {
    const root = document.getElementById("trader-root");
    const wallet = root.getAttribute("data-wallet");
    const chain = root.getAttribute("data-chain");
    const loggedIn = root.getAttribute("data-logged-in") === "1";
    const onchainAvailable = root.getAttribute("data-onchain") === "1";
    let network = root.getAttribute("data-network") || (chain === "solana" ? "solana" : "base");
    U.applyAvatars(document);

    const el = function (id) { return document.getElementById(id); };
    const stateEl = el("trader-state");
    const padEl = el("copy-pad");
    const startBtn = el("start-sim");
    const errEl = el("start-error");
    const perfEl = el("cs-perf-value");
    const displayEl = el("amount-display");

    // Source de données courante : "simulated" ou "onchain" (charge utile Moralis).
    let dataSource = "simulated";
    let payload = null;
    let ready = false;

    // ----- saisie du montant (pavé numérique, boutons rapides, clavier)
    const MIN_AMOUNT = 1;
    const MAX_AMOUNT = 1000000;
    const PENDING_KEY = "copylab_pending_amount:" + wallet;
    let raw = "";

    function amountValue() {
      const v = parseFloat(raw);
      return isFinite(v) ? v : 0;
    }

    function formatAmount() {
      if (!raw) return "0";
      const parts = raw.split(".");
      const whole = (parts[0] === "" ? 0 : parseInt(parts[0], 10)).toLocaleString("fr-FR");
      return parts.length > 1 ? whole + "," + parts[1] : whole;
    }

    function refreshAmount() {
      displayEl.textContent = formatAmount() + " $";
      displayEl.classList.toggle("zero", amountValue() === 0);
      const amount = amountValue();
      const valid = amount >= MIN_AMOUNT;
      startBtn.disabled = !(ready && valid);
      if (!valid) {
        startBtn.textContent = amount > 0 ? "Minimum 1 $" : "Entre un montant";
      } else {
        const label = formatAmount() + " $";
        startBtn.textContent = loggedIn ? "Copier avec " + label : "Créer un compte et copier avec " + label;
      }
      document.querySelectorAll("#quick-amounts button").forEach(function (b) {
        b.classList.toggle("active", parseFloat(b.getAttribute("data-amount")) === amount && !/[.]$/.test(raw));
      });
    }

    function pressKey(key) {
      errEl.hidden = true;
      if (key === "back") {
        raw = raw.slice(0, -1);
      } else if (key === ".") {
        if (raw.indexOf(".") === -1) raw = (raw || "0") + ".";
      } else {
        const next = raw === "0" ? key : raw + key;
        const parts = next.split(".");
        if (parts.length > 1 && parts[1].length > 2) return;
        if (parts[0].length > 7 || parseFloat(next) > MAX_AMOUNT) return;
        raw = next;
      }
      refreshAmount();
    }

    el("keypad").addEventListener("click", function (e) {
      const btn = e.target.closest("button");
      if (btn) pressKey(btn.getAttribute("data-key"));
    });
    el("quick-amounts").addEventListener("click", function (e) {
      const btn = e.target.closest("button");
      if (!btn) return;
      errEl.hidden = true;
      raw = String(parseFloat(btn.getAttribute("data-amount")));
      refreshAmount();
    });
    document.addEventListener("keydown", function (e) {
      const tag = (e.target && e.target.tagName) || "";
      if (tag === "INPUT" || tag === "TEXTAREA" || e.ctrlKey || e.metaKey || e.altKey) return;
      if (/^[0-9]$/.test(e.key)) pressKey(e.key);
      else if (e.key === "." || e.key === ",") pressKey(".");
      else if (e.key === "Backspace") pressKey("back");
      else if (e.key === "Enter" && !startBtn.disabled) start();
    });

    // Montant saisi avant une redirection vers l'inscription : on le retrouve au retour.
    try {
      const pending = sessionStorage.getItem(PENDING_KEY);
      if (pending && /^\d+(\.\d{1,2})?$/.test(pending) && parseFloat(pending) <= MAX_AMOUNT) raw = pending;
      sessionStorage.removeItem(PENDING_KEY);
    } catch (e) {}

    // ----- performance du wallet (résumé en haut à droite)
    function showPerf() {
      const real = dataSource === "onchain" ? payload.trades : null;
      const now = dataSource === "onchain" ? payload.window_end : nowSec();
      const s30 = E.traderStats(wallet, now, 30, real);
      perfEl.textContent = U.pct(s30.pnlPct, Math.abs(s30.pnlPct) >= 10 ? 0 : 1);
      perfEl.className = U.cls(s30.pnlPct);
    }

    function showState(html, withRetry) {
      padEl.hidden = true;
      stateEl.hidden = false;
      perfEl.textContent = "—";
      perfEl.className = "";
      stateEl.innerHTML = '<p class="state-msg">' + html + "</p>" +
        (withRetry ? '<button type="button" class="btn btn-ghost btn-sm" id="retry-load">Réessayer</button>' : "");
      const retry = el("retry-load");
      if (retry) retry.addEventListener("click", load);
    }

    function ingest(data) {
      if (data.source === "onchain") {
        dataSource = "onchain";
        payload = data;
        if (!data.trades.length) {
          ready = false;
          refreshAmount();
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
      }
      ready = true;
      stateEl.hidden = true;
      padEl.hidden = false;
      showPerf();
      refreshAmount();
    }

    async function load() {
      ready = false;
      refreshAmount();
      if (!onchainAvailable) {
        ingest({ source: "simulated" });
        return;
      }
      padEl.hidden = true;
      stateEl.hidden = false;
      stateEl.innerHTML = '<p class="state-msg"><span class="spinner"></span> Analyse des swaps du wallet en cours…</p>';
      try {
        const res = await fetch("/api/wallet/" + encodeURIComponent(wallet) + "/trades?network=" + encodeURIComponent(network), {
          credentials: "same-origin",
        });
        const body = await res.json().catch(function () { return {}; });
        if (!res.ok) throw new Error(body.message || "Données on-chain indisponibles.");
        ingest(body);
      } catch (err) {
        showState(U.esc(err.message), true);
      }
    }

    // Sélecteur de réseau EVM (uniquement avec les données on-chain)
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
      const amount = Math.round(amountValue() * 100) / 100;
      if (!ready || amount < MIN_AMOUNT) return;
      errEl.hidden = true;
      startBtn.disabled = true;
      try {
        const data = await fetch("/api/simulations", {
          method: "POST",
          credentials: "same-origin",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            wallet: wallet,
            balance: amount,
            alloc_pct: 0.1,
            mode: "live",
            speed: 6000,
            source: dataSource,
            network: dataSource === "onchain" ? network : null,
          }),
        }).then(async function (res) {
          if (res.status === 401) {
            try { sessionStorage.setItem(PENDING_KEY, String(amount)); } catch (e) {}
            window.location.href = "/auth/signup?next=" +
              encodeURIComponent(window.location.pathname + "?network=" + encodeURIComponent(network));
            return null;
          }
          const body = await res.json().catch(function () { return {}; });
          if (!res.ok) throw new Error(body.message || "Impossible de lancer la copie.");
          return body;
        });
        if (data) window.location.href = "/sim/" + data.simulation.id;
      } catch (err) {
        errEl.textContent = err.message;
        errEl.hidden = false;
        refreshAmount();
      }
    }
    startBtn.addEventListener("click", start);

    // Le paramètre ?go=1 (adresse collée) ne sert qu'à arriver sur l'écran de saisie.
    if (new URLSearchParams(window.location.search).get("go") === "1") {
      history.replaceState(null, "", window.location.pathname + (onchainAvailable && chain === "evm" ? "?network=" + encodeURIComponent(network) : ""));
    }

    refreshAmount();
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
        listEl.innerHTML = '<p class="empty-note">Aucun trade pour l\'instant. Copie un wallet pour commencer.</p>';
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
  if (page === "home") initHome();
  else if (page === "traders") initTraders();
  else if (page === "trader") initTrader();
  else if (page === "app") initApp();
  else if (page === "sim") initSim();
})();
