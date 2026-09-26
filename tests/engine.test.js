// Tests du moteur de simulation : node tests/engine.test.js
const assert = require("assert");
const path = require("path");
const E = require(path.join(__dirname, "..", "static", "js", "engine.js"));

const SOL = "uEUmJSvfB32wmfBgqoFtucjCZSjXSZkLfVBWKLMV73Ji";
const EVM = "0xdd5782086918b3114daa8818ca48d9a220bb125c";
const NOW = 1790000000;
const DAY = E.DAY;
let passed = 0;

function test(name, fn) {
  fn();
  passed++;
  console.log("  ok -", name);
}

test("détection de chaîne / validation d'adresses", () => {
  assert.strictEqual(E.detectChain(SOL), "solana");
  assert.strictEqual(E.detectChain(EVM), "evm");
  assert.strictEqual(E.detectChain("0x123"), null);
  assert.strictEqual(E.detectChain("hello world"), null);
  assert.strictEqual(E.detectChain(""), null);
  assert.strictEqual(E.detectChain("0OIl" + "1".repeat(30)), null); // caractères base58 interdits
  assert.strictEqual(E.walletKey("0xDD5782086918B3114DAA8818CA48D9A220BB125C"), EVM);
});

test("déterminisme : même wallet => mêmes trades", () => {
  const a = E.tradesBetween(SOL, NOW - 10 * DAY, NOW);
  const b = E.tradesBetween(SOL, NOW - 10 * DAY, NOW);
  assert.deepStrictEqual(a, b);
  assert.ok(a.length > 5);
  const other = E.tradesBetween(EVM, NOW - 10 * DAY, NOW);
  assert.notDeepStrictEqual(a.map((t) => t.id), other.map((t) => t.id).concat("x"));
});

test("multiplicateur : 1 à l'ouverture, 1+ret à la clôture", () => {
  E.tradesBetween(SOL, NOW - 5 * DAY, NOW).forEach((t) => {
    assert.ok(Math.abs(E.multiplier(t, t.open) - 1) < 1e-9);
    assert.ok(Math.abs(E.multiplier(t, t.close) - (1 + t.ret)) < 1e-9);
    assert.ok(E.multiplier(t, (t.open + t.close) / 2) > 0);
  });
});

test("simulation : pas de NaN, cash >= 0, équité cohérente", () => {
  [SOL, EVM, "8XppUi3uK7ZiJzzD6dq415g9WEUgXRZwuP9VVa643Tu"].forEach((w) => {
    const r = E.simulate(w, { startSim: NOW - 30 * DAY, endSim: NOW, balance: 10000, allocPct: 0.25 });
    assert.ok(isFinite(r.equity) && isFinite(r.cash) && isFinite(r.pnl));
    assert.ok(r.cash >= -1e-6, "cash négatif");
    const openValue = r.open.reduce((s, p) => s + p.value, 0);
    assert.ok(Math.abs(r.cash + openValue - r.equity) < 1e-6, "équité != cash + positions");
    assert.strictEqual(r.curve.length, 80);
    r.curve.forEach((p) => assert.ok(isFinite(p.equity) && p.equity > 0));
    r.closed.forEach((c) => assert.ok(isFinite(c.pnl) && c.invested > 0));
  });
});

test("sans frais ni engagement (alloc 0) l'équité ne bouge pas", () => {
  const r = E.simulate(SOL, { startSim: NOW - 10 * DAY, endSim: NOW, balance: 5000, allocPct: 0 });
  assert.strictEqual(r.equity, 5000);
  assert.strictEqual(r.tradesCount, 0);
});

test("les frais réduisent le résultat du copieur", () => {
  const args = { startSim: NOW - 30 * DAY, endSim: NOW, balance: 10000, allocPct: 0.1 };
  const noFee = E.simulate(SOL, Object.assign({ feePct: 0 }, args));
  const fee = E.simulate(SOL, Object.assign({ feePct: 0.008 }, args));
  assert.ok(fee.equity < noFee.equity);
});

test("le temps ne remonte pas : positions cohérentes entre deux instants", () => {
  const start = NOW - 20 * DAY;
  const r1 = E.simulate(SOL, { startSim: start, endSim: start + 5 * DAY, balance: 10000, allocPct: 0.1 });
  const r2 = E.simulate(SOL, { startSim: start, endSim: start + 10 * DAY, balance: 10000, allocPct: 0.1 });
  assert.ok(r2.closed.length >= r1.closed.length);
  const ids1 = new Set(r1.closed.map((c) => c.id));
  r2.closed.filter((c) => ids1.has(c.id)).forEach((c) => {
    const c1 = r1.closed.find((x) => x.id === c.id);
    assert.ok(Math.abs(c1.pnl - c.pnl) < 1e-6, "un trade clôturé ne doit pas changer");
  });
});

test("statistiques de trader", () => {
  const s = E.traderStats(SOL, NOW, 30);
  assert.ok(s.trades > 10);
  assert.ok(s.winRate >= 0 && s.winRate <= 1);
  assert.ok(isFinite(s.pnlPct));
  assert.strictEqual(s.curve.length, 40);
});

test("évaluation live : temps accéléré, arrêt, plafond de 90 jours", () => {
  const sim = { wallet: SOL, mode: "live", balance: 10000, alloc_pct: 0.1, speed: 1200, started_at: NOW, stopped_at: null };
  const t0 = E.evaluateSimulation(sim, NOW);
  assert.strictEqual(t0.status, "active");
  assert.strictEqual(t0.equity, 10000);
  const t1 = E.evaluateSimulation(sim, NOW + 3600 * 3); // 3 h réelles = 150 j simulés => plafonné
  assert.strictEqual(t1.status, "finished");
  assert.ok(Math.abs(t1.simDays - E.MAX_SIM_DAYS) < 1e-9);
  const t2 = E.evaluateSimulation(sim, NOW + 600); // 10 min réelles = 8,3 j simulés
  assert.strictEqual(t2.status, "active");
  assert.ok(Math.abs(t2.simDays - 600 * 1200 / DAY) < 1e-9);
  const stopped = Object.assign({}, sim, { stopped_at: NOW + 600 });
  const t3 = E.evaluateSimulation(stopped, NOW + 99999);
  assert.strictEqual(t3.status, "stopped");
  assert.ok(Math.abs(t3.simDays - t2.simDays) < 1e-9);
  assert.ok(Math.abs(t3.equity - t2.equity) < 1e-9);
});

test("évaluation backtest : rejoue 30 jours instantanément", () => {
  const sim = { wallet: EVM, mode: "backtest", balance: 10000, alloc_pct: 0.25, speed: 300, started_at: NOW, stopped_at: null };
  const r = E.evaluateSimulation(sim, NOW);
  assert.strictEqual(r.status, "finished");
  assert.ok(Math.abs(r.simDays - E.HISTORY_DAYS) < 1e-9);
  assert.ok(r.tradesCount > 5);
  const later = E.evaluateSimulation(sim, NOW + 99999);
  assert.strictEqual(later.equity, r.equity);
});

test("distribution réaliste : la plupart des wallets aléatoires ne sont pas des machines à cash", () => {
  const crypto = require("crypto");
  let pos = 0;
  const N = 120;
  for (let i = 0; i < N; i++) {
    const w = "0x" + crypto.randomBytes(20).toString("hex");
    if (E.traderStats(w, NOW, 30).pnlPct > 0) pos++;
  }
  assert.ok(pos / N < 0.6, "trop de wallets rentables: " + pos / N);
  assert.ok(pos / N > 0.1, "pas assez de wallets rentables: " + pos / N);
});

// ---------------------------------------------------------------- trades on-chain réels
const T0 = 1789000000;
const REAL = [
  { id: "a-1", token: "AAA", open: T0 + 3600, close: T0 + 7200, ret: 0.5, size_usd: 500 },
  { id: "b-2", token: "BBB", open: T0 + 3 * DAY, close: T0 + 3 * DAY + 7200, ret: -0.2, size_usd: 300 },
  { id: "c-3", token: "CCC", open: T0 + 5 * DAY, close: T0 + 5 * DAY + 600, ret: 1.0, size_usd: 100 },
];

test("trades réels : rendement réalisé exact à la clôture (sans frais, 100 % engagé)", () => {
  const dec = E.decorateRealTrades(REAL);
  const r = E.simulate("anywallet", { trades: dec, startSim: T0, endSim: T0 + 2 * DAY, balance: 1000, allocPct: 1, feePct: 0 });
  assert.strictEqual(r.tradesCount, 1);
  assert.ok(Math.abs(r.equity - 1500) < 1e-6, "équité " + r.equity);
  const r2 = E.simulate("anywallet", { trades: dec, startSim: T0, endSim: T0 + 4 * DAY, balance: 1000, allocPct: 1, feePct: 0 });
  assert.ok(Math.abs(r2.equity - 1500 * 0.8) < 1e-6, "équité " + r2.equity);
});

test("trades réels : la courbe intermédiaire relie l'entrée à la sortie", () => {
  const dec = E.decorateRealTrades(REAL);
  dec.forEach((t) => {
    assert.ok(Math.abs(E.multiplier(t, t.open) - 1) < 1e-9);
    assert.ok(Math.abs(E.multiplier(t, t.close) - (1 + t.ret)) < 1e-9);
  });
  assert.strictEqual(E.decorateRealTrades(REAL), dec, "décoration mémoïsée");
});

test("trades réels : traderStats", () => {
  const s = E.traderStats("anywallet", T0 + 6 * DAY, 30, REAL);
  assert.strictEqual(s.winRate, 2 / 3);
  assert.strictEqual(s.trades, 3);
  assert.ok(s.pnlPct > 0);
  const s2 = E.traderStats("anywallet", T0 + 6 * DAY, 2, REAL); // seulement le trade c-3 (ouvert à J+5)
  assert.strictEqual(s2.trades, 1);
});

test("évaluation on-chain : rejeu accéléré de la fenêtre réelle puis fin", () => {
  const snap = { window_start: T0, window_end: T0 + 6 * DAY, trades: REAL };
  const sim = { wallet: "w", mode: "live", source: "onchain", snapshot: snap, balance: 10000, alloc_pct: 0.5, speed: 6000, started_at: 5000000, stopped_at: null };
  const a = E.evaluateSimulation(sim, sim.started_at);
  assert.strictEqual(a.status, "active");
  assert.strictEqual(a.equity, 10000);
  assert.strictEqual(a.source, "onchain");
  assert.ok(Math.abs(a.horizonDays - 6) < 1e-9);
  const mid = E.evaluateSimulation(sim, sim.started_at + 3 * DAY / 6000); // 3 jours simulés écoulés
  assert.strictEqual(mid.status, "active");
  assert.ok(Math.abs(mid.simDays - 3) < 1e-9);
  assert.ok(Math.abs(mid.progress - 0.5) < 1e-9);
  assert.ok(mid.tradesCount >= 1);
  const end = E.evaluateSimulation(sim, sim.started_at + 99999);
  assert.strictEqual(end.status, "finished");
  assert.ok(Math.abs(end.simDays - 6) < 1e-9);
  assert.strictEqual(end.tradesCount, 3);
  const stopped = E.evaluateSimulation(Object.assign({}, sim, { stopped_at: sim.started_at + 3 * DAY / 6000 }), sim.started_at + 99999);
  assert.strictEqual(stopped.status, "stopped");
  assert.ok(Math.abs(stopped.equity - mid.equity) < 1e-9);
});

test("évaluation on-chain : le rejeu saute le temps mort avant le premier trade", () => {
  const late = REAL.map((t) => Object.assign({}, t, { open: t.open + 2 * DAY, close: t.close + 2 * DAY }));
  const snap = { window_start: T0, window_end: T0 + 8 * DAY, trades: late };
  const sim = { wallet: "w", mode: "live", source: "onchain", snapshot: snap, balance: 10000, alloc_pct: 0.5, speed: 6000, started_at: 5000000, stopped_at: null };
  const a = E.evaluateSimulation(sim, sim.started_at);
  assert.ok(Math.abs(a.horizonDays - (8 - 2 - 3600 / DAY + 3600 / DAY)) < 1e-6 || a.horizonDays < 8, "horizon " + a.horizonDays);
  assert.ok(a.horizonDays < 6.1);
  const soon = E.evaluateSimulation(sim, sim.started_at + 2 * 3600 / 6000 + 1);
  assert.strictEqual(soon.open.length + soon.tradesCount >= 1, true);
});

test("évaluation on-chain : backtest instantané, insensible à l'horloge", () => {
  const snap = { window_start: T0, window_end: T0 + 6 * DAY, trades: REAL };
  const sim = { wallet: "w", mode: "backtest", source: "onchain", snapshot: snap, balance: 10000, alloc_pct: 0.25, speed: 300, started_at: 5000000, stopped_at: null };
  const a = E.evaluateSimulation(sim, 5000000);
  const b = E.evaluateSimulation(sim, 9999999);
  assert.strictEqual(a.status, "finished");
  assert.strictEqual(a.equity, b.equity);
  assert.strictEqual(a.tradesCount, 3);
});

console.log(passed + " tests OK");
