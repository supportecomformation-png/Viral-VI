/* CopyLab — helpers d'affichage (formats, avatars, graphiques SVG). */
(function (root) {
  "use strict";

  const nfInt = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 0 });
  const nf2 = new Intl.NumberFormat("fr-FR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

  function esc(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function usd(v, opts) {
    opts = opts || {};
    const sign = v < 0 ? "−" : opts.sign && v > 0 ? "+" : "";
    const abs = Math.abs(v);
    return sign + (abs >= 1000 ? nfInt.format(abs) : nf2.format(abs)) + " $";
  }

  function pct(v, dec) {
    if (v == null || !isFinite(v)) return "—";
    const d = dec == null ? 1 : dec;
    const sign = v > 0.00005 ? "+" : v < -0.00005 ? "−" : "";
    return sign + Math.abs(v * 100).toFixed(d).replace(".", ",") + " %";
  }

  // Prix d'un token : 2 décimales au-dessus de 1 $, davantage en dessous.
  function price(v) {
    if (v == null || !isFinite(v)) return "—";
    if (v >= 1) return nf2.format(v) + " $";
    if (v <= 0) return "0 $";
    const digits = Math.min(10, Math.max(4, 2 - Math.floor(Math.log10(v))));
    return v.toFixed(digits).replace(".", ",") + " $";
  }

  // Capitalisation : 1,6 T$ / 324 Md$ / 12 M$.
  function compactUsd(v) {
    if (v == null || !isFinite(v) || v <= 0) return "—";
    const fmt = function (x, unit) {
      return (x >= 100 ? nfInt.format(x) : x.toFixed(1).replace(".", ",")) + " " + unit;
    };
    if (v >= 1e12) return fmt(v / 1e12, "T$");
    if (v >= 1e9) return fmt(v / 1e9, "Md$");
    if (v >= 1e6) return fmt(v / 1e6, "M$");
    return nfInt.format(v) + " $";
  }

  function cls(v) {
    return v > 0.00005 ? "up" : v < -0.00005 ? "down" : "";
  }

  function fmtSimTime(sec) {
    return new Date(sec * 1000).toLocaleString("fr-FR", {
      day: "2-digit",
      month: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  function fmtDateTime(sec) {
    return new Date(sec * 1000).toLocaleString("fr-FR", {
      day: "2-digit",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  function timeAgo(sec, now) {
    const d = Math.max(0, now - sec);
    if (d < 60) return "à l'instant";
    if (d < 3600) return "il y a " + Math.floor(d / 60) + " min";
    if (d < 86400) return "il y a " + Math.floor(d / 3600) + " h";
    return "il y a " + Math.floor(d / 86400) + " j";
  }

  function duration(sec) {
    if (sec < 3600) return Math.max(1, Math.round(sec / 60)) + " min";
    const h = Math.floor(sec / 3600);
    const m = Math.round((sec % 3600) / 60);
    return h + " h" + (m ? " " + (m < 10 ? "0" : "") + m : "");
  }

  function hashStr(str) {
    let h = 2166136261;
    for (let i = 0; i < str.length; i++) {
      h ^= str.charCodeAt(i);
      h = Math.imul(h, 16777619);
    }
    h ^= h >>> 15;
    h = Math.imul(h, 2246822507);
    h ^= h >>> 13;
    return h >>> 0;
  }

  function avatarStyle(wallet) {
    const h = hashStr(wallet);
    const h1 = h % 360;
    const h2 = (h1 + 40 + (h % 80)) % 360;
    return "background:linear-gradient(135deg,hsl(" + h1 + " 80% 58%),hsl(" + h2 + " 85% 45%))";
  }

  function applyAvatars(scope) {
    (scope || document).querySelectorAll("[data-avatar]").forEach(function (el) {
      el.setAttribute("style", avatarStyle(el.getAttribute("data-avatar")));
    });
  }

  function sparkline(values, opts) {
    opts = opts || {};
    const w = opts.w || 96;
    const h = opts.h || 32;
    if (!values || values.length < 2) return "";
    let min = Math.min.apply(null, values);
    let max = Math.max.apply(null, values);
    if (max === min) max = min + 1;
    const pts = values.map(function (v, i) {
      const x = (i / (values.length - 1)) * w;
      const y = 3 + (1 - (v - min) / (max - min)) * (h - 6);
      return x.toFixed(1) + "," + y.toFixed(1);
    });
    const up = values[values.length - 1] >= values[0];
    return (
      '<svg class="spark ' + (up ? "up" : "down") + '" viewBox="0 0 ' + w + " " + h +
      '" preserveAspectRatio="none" aria-hidden="true"><polyline points="' + pts.join(" ") +
      '" fill="none" stroke-width="2" stroke-linejoin="round" stroke-linecap="round" vector-effect="non-scaling-stroke"/></svg>'
    );
  }

  function lineChart(el, curve, opts) {
    opts = opts || {};
    if (!curve || !curve.length) {
      el.innerHTML = "";
      return;
    }
    if (curve.length === 1) curve = [curve[0], curve[0]];
    const W = 600;
    const H = opts.height || 220;
    const padT = 16;
    const padB = 16;
    const base = opts.base;
    const vals = curve.map(function (p) {
      return p.equity;
    });
    let min = Math.min.apply(null, vals);
    let max = Math.max.apply(null, vals);
    if (base != null) {
      min = Math.min(min, base);
      max = Math.max(max, base);
    }
    if (max === min) max = min + 1;
    const span = max - min;
    min -= span * 0.05;
    max += span * 0.05;

    const x = function (i) {
      return (i / (curve.length - 1)) * W;
    };
    const y = function (v) {
      return padT + (1 - (v - min) / (max - min)) * (H - padT - padB);
    };
    let d = "";
    curve.forEach(function (p, i) {
      d += (i ? "L" : "M") + x(i).toFixed(1) + " " + y(p.equity).toFixed(1) + " ";
    });
    const area = d + "L" + W + " " + (H - padB) + " L0 " + (H - padB) + " Z";
    const ref = base != null ? base : vals[0];
    const up = vals[vals.length - 1] >= ref;
    const id = "g" + Math.floor(Math.random() * 1e6);
    el.innerHTML =
      '<svg class="chart-svg ' + (up ? "up" : "down") + '" viewBox="0 0 ' + W + " " + H +
      '" preserveAspectRatio="none" role="img" aria-label="Courbe de performance">' +
      '<defs><linearGradient id="' + id + '" x1="0" y1="0" x2="0" y2="1">' +
      '<stop offset="0%" class="stop-a"/><stop offset="100%" class="stop-b"/></linearGradient></defs>' +
      (base != null
        ? '<line class="base-line" x1="0" x2="' + W + '" y1="' + y(base).toFixed(1) + '" y2="' + y(base).toFixed(1) + '" vector-effect="non-scaling-stroke"/>'
        : "") +
      '<path class="area" d="' + area + '" fill="url(#' + id + ')"/>' +
      '<path class="line" d="' + d + '" fill="none" vector-effect="non-scaling-stroke"/></svg>';
  }

  function copyText(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      return navigator.clipboard.writeText(text);
    }
    return new Promise(function (resolve) {
      const ta = document.createElement("textarea");
      ta.value = text;
      document.body.appendChild(ta);
      ta.select();
      try {
        document.execCommand("copy");
      } catch (e) {}
      document.body.removeChild(ta);
      resolve();
    });
  }

  root.UI = {
    esc: esc,
    usd: usd,
    price: price,
    compactUsd: compactUsd,
    pct: pct,
    cls: cls,
    fmtSimTime: fmtSimTime,
    fmtDateTime: fmtDateTime,
    timeAgo: timeAgo,
    duration: duration,
    avatarStyle: avatarStyle,
    applyAvatars: applyAvatars,
    sparkline: sparkline,
    lineChart: lineChart,
    copyText: copyText,
  };
})(window);
