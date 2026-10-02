/* Copy Trade — notifications push côté navigateur (service worker + abonnement Web Push). */
(function () {
  "use strict";

  const ua = navigator.userAgent || "";
  const isIOS = /iphone|ipad|ipod/i.test(ua) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
  const standalone =
    (window.matchMedia && window.matchMedia("(display-mode: standalone)").matches) || window.navigator.standalone === true;

  const swSupported = "serviceWorker" in navigator;
  const pushSupported = swSupported && "PushManager" in window && "Notification" in window;

  let regPromise = null;
  function register() {
    if (!swSupported) return Promise.resolve(null);
    if (!regPromise) {
      regPromise = navigator.serviceWorker.register("/sw.js")
        .then(function () { return navigator.serviceWorker.ready; })
        .catch(function () { return null; });
    }
    return regPromise;
  }

  function keyToBytes(b64) {
    const pad = "=".repeat((4 - (b64.length % 4)) % 4);
    const raw = atob((b64 + pad).replace(/-/g, "+").replace(/_/g, "/"));
    const out = new Uint8Array(raw.length);
    for (let i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
    return out;
  }

  function post(url, body) {
    return fetch(url, {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {}),
    }).then(function (res) {
      return res.json().catch(function () { return {}; }).then(function (data) {
        if (!res.ok) throw new Error(data.message || "Erreur " + res.status);
        return data;
      });
    });
  }

  function config() {
    return fetch("/api/push/config", { credentials: "same-origin" })
      .then(function (r) { return r.json(); })
      .catch(function () { return { enabled: false }; });
  }

  function currentSubscription() {
    return register().then(function (reg) { return reg ? reg.pushManager.getSubscription() : null; });
  }

  // État : "unsupported" | "install" (iPhone hors écran d'accueil) | "denied" | "off" | "on"
  function state() {
    if (isIOS && !standalone) return Promise.resolve("install");
    if (!pushSupported) return Promise.resolve("unsupported");
    if (Notification.permission === "denied") return Promise.resolve("denied");
    if (Notification.permission !== "granted") return Promise.resolve("off");
    return currentSubscription().then(function (sub) { return sub ? "on" : "off"; });
  }

  // À appeler directement depuis un clic : la demande d'autorisation doit rester dans le geste.
  function enable() {
    return Notification.requestPermission().then(function (perm) {
      if (perm !== "granted") throw new Error("Autorisation refusée : active les notifications dans les réglages du navigateur.");
      return Promise.all([config(), register()]);
    }).then(function (res) {
      const cfg = res[0], reg = res[1];
      if (!cfg.enabled) throw new Error("Les notifications ne sont pas encore disponibles sur ce site.");
      if (!reg) throw new Error("Ce navigateur ne permet pas les notifications.");
      return reg.pushManager.getSubscription().then(function (existing) {
        return existing || reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: keyToBytes(cfg.public_key) });
      });
    }).then(function (sub) {
      return post("/api/push/subscribe", { subscription: sub.toJSON() });
    });
  }

  // Ré-enregistre l'abonnement existant côté serveur (au cas où il aurait été purgé).
  function resync() {
    return currentSubscription().then(function (sub) {
      return sub ? post("/api/push/subscribe", { subscription: sub.toJSON() }) : null;
    }).catch(function () { return null; });
  }

  function disable() {
    return currentSubscription().then(function (sub) {
      if (!sub) return null;
      const endpoint = sub.endpoint;
      return post("/api/push/unsubscribe", { endpoint: endpoint }).catch(function () {}).then(function () {
        return sub.unsubscribe();
      });
    });
  }

  function test() {
    return post("/api/push/test");
  }

  // Garantit un appareil abonné. À appeler directement depuis un clic : si l'autorisation n'a pas
  // encore été demandée, requestPermission() part dans le geste (indispensable sur iPhone).
  function ensure() {
    if (isIOS && !standalone) {
      return Promise.reject(new Error("Sur iPhone, ajoute d'abord Copy Trade à l'écran d'accueil (Partager, puis « Sur l'écran d'accueil »), puis ouvre l'app depuis son icône."));
    }
    if (!pushSupported) return Promise.reject(new Error("Ce navigateur ne permet pas les notifications."));
    if (Notification.permission === "denied") {
      return Promise.reject(new Error("Les notifications sont bloquées pour ce site : autorise-les dans les réglages."));
    }
    if (Notification.permission === "default") return enable();
    return currentSubscription().then(function (sub) { return sub ? resync() : enable(); });
  }

  window.addEventListener("load", register);

  window.CopyPush = {
    state: state, enable: enable, ensure: ensure, disable: disable, resync: resync, test: test, config: config,
    isIOS: isIOS, standalone: standalone,
  };
})();
