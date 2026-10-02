/*
 * CopyLab — moteur de simulation de copy trading (DÉMO, argent fictif).
 *
 * Toutes les données sont SIMULÉES : le "track record" d'un wallet est généré
 * de façon déterministe à partir de son adresse (même adresse => mêmes trades).
 * Aucune donnée on-chain réelle n'est lue ici. Pour brancher de vraies
 * transactions plus tard, il suffit de remplacer `tradesBetween`.
 *
 * Le fichier est utilisable dans le navigateur (window.CopyEngine) et sous
 * Node (module.exports) pour les tests.
 */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.CopyEngine = factory();
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  const DAY = 86400;
  const MIN_TRADE_SECONDS = 300;
  const MAX_TRADE_SECONDS = 36 * 3600;
  const FEE_PCT = 0.008; // frais + slippage simulés, par côté (achat / vente)
  const HISTORY_DAYS = 30;
  const MAX_SIM_DAYS = 90;

  const TOKENS = [
    "MOONCAT", "ZOOMER", "NEONDOG", "FROGLET", "SLOTHY", "ORBITZ", "KAWAII",
    "MEMEX", "LASERCAT", "YETIX", "BLOBBY", "COSMIX", "HYPERDUCK", "TOASTY",
    "GLITCH", "PIXELPIG", "VOLTFOX", "NACHOS",
  ];

  // ---------- PRNG déterministe ----------
  function hash32(str) {
    let h = 1779033703 ^ str.length;
    for (let i = 0; i < str.length; i++) {
      h = Math.imul(h ^ str.charCodeAt(i), 3432918353);
      h = (h << 13) | (h >>> 19);
    }
    h = Math.imul(h ^ (h >>> 16), 2246822507);
    h = Math.imul(h ^ (h >>> 13), 3266489909);
    return (h ^ (h >>> 16)) >>> 0;
  }

  function mulberry32(seed) {
    let a = seed | 0;
    return function () {
      a = (a + 0x6d2b79f5) | 0;
      let t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  function rng(key) {
    return mulberry32(hash32(key));
  }

  // ---------- Adresses ----------
  const EVM_RE = /^0x[a-fA-F0-9]{40}$/;
  const SOL_RE = /^[1-9A-HJ-NP-Za-km-z]{32,44}$/;

  function detectChain(address) {
    const a = (address || "").trim();
    if (EVM_RE.test(a)) return "evm";
    if (SOL_RE.test(a)) return "solana";
    return null;
  }

  function shortAddress(address) {
    const a = (address || "").trim();
    return a.length > 12 ? a.slice(0, 4) + "…" + a.slice(-4) : a;
  }

  // EVM : adresse insensible à la casse -> clé normalisée
  function walletKey(address) {
    const a = (address || "").trim();
    return EVM_RE.test(a) ? a.toLowerCase() : a;
  }

  // ---------- Profil de trader (déterministe) ----------
  function profileFor(wallet) {
    const r = rng("profile|" + walletKey(wallet));
    return {
      winRate: 0.3 + 0.24 * r(),
      avgWin: 0.06 + 0.2 * r(),
      avgLoss: 0.06 + 0.09 * r(),
      tradesPerDay: 1.5 + 4.5 * r(),
      avgHoldHours: 0.6 + 7 * r(),
    };
  }

  function tradesForDay(wallet, profile, day) {
    const key = walletKey(wallet);
    const r = rng("day|" + key + "|" + day);
    const count = Math.max(0, Math.round(profile.tradesPerDay * (0.5 + r())));
    const out = [];
    for (let k = 0; k < count; k++) {
      const open = day * DAY + Math.floor(r() * DAY);
      const dur = Math.min(
        MAX_TRADE_SECONDS,
        Math.max(MIN_TRADE_SECONDS, Math.floor(profile.avgHoldHours * 3600 * -Math.log(1 - r() * 0.98) * 0.9))
      );
      let ret;
      const roll = r();
      if (roll < 0.012) {
        ret = -0.9; // rug pull
        r();
      } else if (r() < profile.winRate) {
        ret = Math.min(3, Math.max(0.03, profile.avgWin * (0.3 + 0.8 * -Math.log(1 - r() * 0.97))));
      } else {
        ret = -Math.min(0.5, Math.max(0.02, profile.avgLoss * (0.4 + 1.2 * r())));
      }
      out.push({
        id: day + "-" + k,
        token: TOKENS[Math.floor(r() * TOKENS.length)],
        open: open,
        close: open + dur,
        ret: ret,
        gamma: 0.6 + r() * 1.0,
        amp: 0.04 + r() * 0.16,
        freq: 1 + Math.floor(r() * 3),
        phase: r() * Math.PI * 2,
      });
    }
    return out;
  }

  // ---------- Trades réels (on-chain) ----------
  // Un trade réel : { id, token, open, close, ret, size_usd } (entrée et sortie
  // réelles). Les paramètres de la courbe intermédiaire (interpolée, purement
  // illustrative) sont dérivés de l'id pour rester déterministes.
  const decorated = new WeakMap();
  function decorateRealTrades(list) {
    if (!list) return null;
    if (decorated.has(list)) return decorated.get(list);
    const out = list.map(function (t) {
      const r = rng('rt|' + t.id);
      return {
        id: t.id,
        token: t.token,
        open: t.open,
        close: Math.max(t.close, t.open + 60),
        ret: t.ret,
        size_usd: t.size_usd,
        gamma: 0.7 + r() * 0.7,
        amp: 0.03 + r() * 0.09,
        freq: 1 + Math.floor(r() * 3),
        phase: r() * Math.PI * 2,
      };
    }).sort(function (a, b) {
      return a.open - b.open;
    });
    decorated.set(list, out);
    return out;
  }

  // Trades ouverts dans [t0, t1] (secondes epoch), triés par ouverture.
  // Si "real" est fourni (trades décorés), on l'utilise à la place du générateur simulé.
  function tradesBetween(wallet, t0, t1, real) {
    if (real) {
      return real.filter(function (t) {
        return t.open >= t0 && t.open <= t1;
      });
    }
    const profile = profileFor(wallet);
    const out = [];
    for (let d = Math.floor(t0 / DAY); d <= Math.floor(t1 / DAY); d++) {
      const day = tradesForDay(wallet, profile, d);
      for (let i = 0; i < day.length; i++) {
        if (day[i].open >= t0 && day[i].open <= t1) out.push(day[i]);
      }
    }
    out.sort(function (a, b) {
      return a.open - b.open;
    });
    return out;
  }

  // Multiplicateur de valeur d'un trade à l'instant t (1 à l'ouverture, 1+ret à la clôture).
  function multiplier(trade, t) {
    const span = trade.close - trade.open;
    let s = span > 0 ? (t - trade.open) / span : 1;
    s = Math.min(1, Math.max(0, s));
    const drift = Math.pow(1 + trade.ret, Math.pow(s, trade.gamma));
    const wiggle = Math.exp(trade.amp * Math.sin(2 * Math.PI * trade.freq * s + trade.phase) * 4 * s * (1 - s));
    return drift * wiggle;
  }

  // ---------- Simulation de copie ----------
  /*
   * opts: { startSim, endSim, balance, allocPct, feePct, samples }
   * Copie chaque trade du wallet ouvert entre startSim et endSim avec
   * `allocPct` de l'équité courante (dans la limite du cash disponible).
   */
  function simulate(wallet, opts) {
    const startSim = opts.startSim;
    const endSim = Math.max(opts.endSim, startSim);
    const balance = opts.balance;
    const allocPct = opts.allocPct;
    const fee = opts.feePct == null ? FEE_PCT : opts.feePct;
    const nSamples = opts.samples || 80;

    const trades = tradesBetween(wallet, startSim, endSim, opts.trades);
    const events = [];
    trades.forEach(function (t) {
      events.push({ time: t.open, type: "open", trade: t });
      if (t.close <= endSim) events.push({ time: t.close, type: "close", trade: t });
    });
    events.sort(function (a, b) {
      if (a.time !== b.time) return a.time - b.time;
      return a.type === b.type ? 0 : a.type === "close" ? -1 : 1;
    });

    const samples = [];
    for (let i = 0; i < nSamples; i++) {
      samples.push(nSamples === 1 ? endSim : startSim + ((endSim - startSim) * i) / (nSamples - 1));
    }

    let cash = balance;
    const positions = {};
    const closed = [];
    const feed = [];
    const curve = [];

    function equityAt(t) {
      let v = cash;
      for (const id in positions) {
        const p = positions[id];
        v += p.units * multiplier(p.trade, t);
      }
      return v;
    }

    let si = 0;
    function flushSamples(upTo) {
      while (si < samples.length && samples[si] <= upTo) {
        curve.push({ t: samples[si], equity: equityAt(samples[si]) });
        si++;
      }
    }

    for (let i = 0; i < events.length; i++) {
      const ev = events[i];
      flushSamples(ev.time);
      const trade = ev.trade;
      if (ev.type === "open") {
        const eq = equityAt(ev.time);
        const size = Math.min(cash, eq * allocPct);
        if (size >= 0.01) {
          cash -= size;
          positions[trade.id] = { trade: trade, invested: size, units: size * (1 - fee), openTime: ev.time };
          feed.push({ type: "open", time: ev.time, token: trade.token, size: size });
        }
      } else {
        const p = positions[trade.id];
        if (p) {
          const proceeds = p.units * (1 + trade.ret) * (1 - fee);
          cash += proceeds;
          const pnl = proceeds - p.invested;
          closed.push({
            id: trade.id,
            token: trade.token,
            openTime: p.openTime,
            closeTime: ev.time,
            invested: p.invested,
            proceeds: proceeds,
            pnl: pnl,
            pnlPct: pnl / p.invested,
          });
          feed.push({ type: "close", time: ev.time, token: trade.token, size: p.invested, pnl: pnl, pnlPct: pnl / p.invested });
          delete positions[trade.id];
        }
      }
    }
    flushSamples(endSim + 1);

    const open = [];
    for (const id in positions) {
      const p = positions[id];
      const value = p.units * multiplier(p.trade, endSim);
      open.push({
        id: id,
        token: p.trade.token,
        openTime: p.openTime,
        invested: p.invested,
        value: value,
        pnl: value - p.invested,
        pnlPct: (value - p.invested) / p.invested,
      });
    }
    open.sort(function (a, b) {
      return b.openTime - a.openTime;
    });

    const equity = equityAt(endSim);
    const wins = closed.filter(function (c) {
      return c.pnl > 0;
    }).length;
    return {
      startSim: startSim,
      endSim: endSim,
      balance: balance,
      equity: equity,
      cash: cash,
      pnl: equity - balance,
      pnlPct: (equity - balance) / balance,
      open: open,
      closed: closed,
      feed: feed.slice(-40).reverse(),
      feedAll: feed,
      curve: curve,
      tradesCount: closed.length,
      winRate: closed.length ? wins / closed.length : null,
    };
  }

  // Stats "du trader" sur les `days` derniers jours avant `now` (sans frais).
  // `realTrades` : liste de trades on-chain bruts (sinon track record simulé).
  function traderStats(wallet, now, days, realTrades) {
    const sim = simulate(wallet, {
      trades: decorateRealTrades(realTrades),
      startSim: now - days * DAY,
      endSim: now,
      balance: 10000,
      allocPct: 0.15,
      feePct: 0,
      samples: 40,
    });
    return {
      pnlPct: sim.pnlPct,
      winRate: sim.winRate,
      trades: sim.tradesCount + sim.open.length,
      curve: sim.curve,
      open: sim.open,
      closed: sim.closed,
      feed: sim.feed,
    };
  }

  // ---------- Simulation utilisateur (paramètres stockés côté serveur) ----------
  /*
   * sim: { wallet, mode: 'live'|'backtest', balance, alloc_pct, speed,
   *        started_at, stopped_at }  (temps en secondes epoch, horloge serveur)
   * nowReal: horloge serveur estimée (secondes)
   */
  function evaluateSimulation(sim, nowReal) {
    // Données on-chain : la simulation rejoue la fenêtre réelle figée dans
    // `sim.snapshot` (trades réels), de son début à sa fin.
    // Données simulées : "live" part de l'instant de lancement et court vers le
    // futur (jusqu'à 90 jours simulés) ; "backtest" rejoue les 30 derniers jours.
    const snap = sim.source === "onchain" && sim.snapshot ? sim.snapshot : null;
    const real = snap ? decorateRealTrades(snap.trades) : null;
    let winStart, winEnd, horizonDays;
    if (snap) {
      // On saute le temps mort du début : le rejeu démarre 1 h avant le premier trade réel.
      const firstOpen = real.length ? real[0].open : snap.window_start;
      winStart = Math.max(snap.window_start, firstOpen - 3600);
      winEnd = snap.window_end;
      horizonDays = (winEnd - winStart) / DAY;
    } else if (sim.mode === "backtest") {
      winStart = sim.started_at - HISTORY_DAYS * DAY;
      winEnd = sim.started_at;
      horizonDays = HISTORY_DAYS;
    } else {
      winStart = sim.started_at;
      winEnd = sim.started_at + MAX_SIM_DAYS * DAY;
      horizonDays = MAX_SIM_DAYS;
    }

    let endSim, status = "active", progress = null;
    if (sim.mode === "backtest") {
      endSim = winEnd;
      status = "finished";
    } else {
      const stopAt = sim.stopped_at != null ? sim.stopped_at : nowReal;
      const elapsedReal = Math.max(0, stopAt - sim.started_at);
      endSim = winStart + elapsedReal * sim.speed;
      if (endSim >= winEnd) {
        endSim = winEnd;
        status = "finished";
      }
      if (sim.stopped_at != null && status !== "finished") status = "stopped";
      progress = (endSim - winStart) / (winEnd - winStart);
    }

    const res = simulate(sim.wallet, {
      trades: real,
      startSim: winStart,
      endSim: endSim,
      balance: sim.balance,
      allocPct: sim.alloc_pct,
      samples: 90,
    });
    res.status = status;
    res.progress = progress;
    res.simDays = (endSim - winStart) / DAY;
    res.horizonDays = horizonDays;
    res.source = snap ? "onchain" : "simulated";
    return res;
  }

  return {
    DAY: DAY,
    FEE_PCT: FEE_PCT,
    HISTORY_DAYS: HISTORY_DAYS,
    MAX_SIM_DAYS: MAX_SIM_DAYS,
    detectChain: detectChain,
    shortAddress: shortAddress,
    walletKey: walletKey,
    profileFor: profileFor,
    tradesBetween: tradesBetween,
    decorateRealTrades: decorateRealTrades,
    multiplier: multiplier,
    simulate: simulate,
    traderStats: traderStats,
    evaluateSimulation: evaluateSimulation,
  };
});
