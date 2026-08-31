(function () {
  "use strict";

  const $ = (sel, root) => (root || document).querySelector(sel);
  const $$ = (sel, root) => Array.from((root || document).querySelectorAll(sel));

  const topicInput = $("#topic");
  const angleSelect = $("#angle");
  const toneSelect = $("#tone");
  const useAiCheckbox = $("#use-ai");
  const apiKeyInput = $("#api-key");
  const aiKeyNote = $("#ai-key-note");
  const generateBtn = $("#generate-btn");
  const generateError = $("#generate-error");
  const resultsEmpty = $("#results-empty");
  const resultsList = $("#results-list");
  const variantTemplate = $("#variant-template");
  const creditsRemainingEl = $("#credits-remaining");

  let selectedNewsId = null;

  // --- Présélection d'une actu via ?news_id=xx dans l'URL ---
  const params = new URLSearchParams(window.location.search);
  const preselect = params.get("news_id");
  if (preselect) {
    const radio = $(`input[name="news_pick"][value="${preselect}"]`);
    if (radio) {
      radio.checked = true;
      selectedNewsId = preselect;
      if (topicInput) topicInput.value = radio.dataset.title || "";
    }
  }

  $$('input[name="news_pick"]').forEach((radio) => {
    radio.addEventListener("change", () => {
      selectedNewsId = radio.value;
      if (topicInput && !topicInput.value) topicInput.value = radio.dataset.title || "";
    });
  });

  // Si l'utilisateur tape un sujet libre, on désélectionne l'actu.
  if (topicInput) {
    topicInput.addEventListener("input", () => {
      if (topicInput.value.trim()) {
        $$('input[name="news_pick"]').forEach((r) => (r.checked = false));
        selectedNewsId = null;
      }
    });
  }

  // --- Mode IA : afficher le champ clé + charger/sauver depuis localStorage ---
  if (useAiCheckbox) {
    try {
      const savedKey = localStorage.getItem("viralvi_api_key");
      if (savedKey) apiKeyInput.value = savedKey;
    } catch (e) { /* localStorage indisponible, on ignore */ }

    useAiCheckbox.addEventListener("change", () => {
      const show = useAiCheckbox.checked;
      apiKeyInput.style.display = show ? "block" : "none";
      aiKeyNote.style.display = show ? "block" : "none";
    });

    apiKeyInput.addEventListener("change", () => {
      try {
        if (apiKeyInput.value.trim()) {
          localStorage.setItem("viralvi_api_key", apiKeyInput.value.trim());
        } else {
          localStorage.removeItem("viralvi_api_key");
        }
      } catch (e) { /* ignore */ }
    });
  }

  function scoreColor(score) {
    if (score >= 85) return "#17E9D0";
    if (score >= 70) return "#8B2FF7";
    if (score >= 50) return "#FFB84D";
    return "#FF5C7A";
  }

  function renderVariant(variant, topic, newsId) {
    const node = variantTemplate.content.cloneNode(true);
    const card = node.querySelector(".variant-card");

    const score = variant.score.total;
    const gaugeFill = node.querySelector(".gauge-fill");
    const gaugeValue = node.querySelector(".gauge-value");
    gaugeFill.setAttribute("stroke-dasharray", `${score}, 100`);
    gaugeFill.style.stroke = scoreColor(score);
    gaugeValue.textContent = score;

    node.querySelector(".variant-angle").textContent = variant.angle_label || "";
    node.querySelector(".variant-label").textContent = variant.score.label || "";
    node.querySelector(".variant-hook").textContent = variant.hook;

    const bodyEl = node.querySelector(".variant-body");
    variant.body.forEach((line) => {
      const p = document.createElement("p");
      p.textContent = line;
      bodyEl.appendChild(p);
    });

    node.querySelector(".variant-cta").textContent = "👉 " + variant.cta;
    node.querySelector(".variant-hashtags").textContent = variant.hashtags.join(" ");

    const breakdownEl = node.querySelector(".breakdown-list");
    Object.values(variant.score.breakdown).forEach((crit) => {
      const row = document.createElement("div");
      row.className = "breakdown-row";
      const pct = Math.round((crit.score / crit.max) * 100);
      row.innerHTML = `
        <span class="breakdown-label">${crit.label}</span>
        <span class="breakdown-bar"><span style="width:${pct}%"></span></span>
        <span class="breakdown-value">${crit.score}/${crit.max}</span>
      `;
      breakdownEl.appendChild(row);
    });

    const tipsEl = node.querySelector(".tips-list");
    if (variant.score.tips && variant.score.tips.length) {
      const title = document.createElement("p");
      title.className = "tips-title";
      title.textContent = "💡 Pour aller plus loin :";
      tipsEl.appendChild(title);
      variant.score.tips.forEach((tip) => {
        const li = document.createElement("p");
        li.className = "tip-line";
        li.textContent = tip;
        tipsEl.appendChild(li);
      });
    }

    node.querySelector(".copy-btn").addEventListener("click", () => {
      const text = [variant.hook, "", ...variant.body, "", "👉 " + variant.cta, "", variant.hashtags.join(" ")].join("\n");
      navigator.clipboard.writeText(text).then(() => {
        const btn = card.querySelector(".copy-btn");
        const original = btn.textContent;
        btn.textContent = "✅ Copié !";
        setTimeout(() => (btn.textContent = original), 1500);
      }).catch(() => {});
    });

    node.querySelector(".save-btn").addEventListener("click", async (evt) => {
      const btn = evt.currentTarget;
      btn.disabled = true;
      btn.textContent = "Sauvegarde...";
      try {
        const resp = await fetch("/app/scripts/save", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ variant, topic, news_id: newsId }),
        });
        if (resp.ok) {
          btn.textContent = "✅ Sauvegardé";
          setTimeout(() => window.location.reload(), 700);
        } else {
          btn.textContent = "Erreur";
          btn.disabled = false;
        }
      } catch (e) {
        btn.textContent = "Erreur réseau";
        btn.disabled = false;
      }
    });

    return card;
  }

  if (generateBtn) {
    generateBtn.addEventListener("click", async () => {
      generateError.style.display = "none";
      const topic = topicInput.value.trim();

      if (!topic && !selectedNewsId) {
        generateError.textContent = "Choisis une actu ou décris un sujet avant de générer.";
        generateError.style.display = "block";
        return;
      }

      generateBtn.disabled = true;
      generateBtn.textContent = "Génération en cours...";

      const useAi = useAiCheckbox && useAiCheckbox.checked;
      const apiKey = apiKeyInput ? apiKeyInput.value.trim() : "";

      try {
        const resp = await fetch("/app/generate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            topic,
            angle: angleSelect.value,
            tone: toneSelect.value,
            news_id: selectedNewsId,
            use_ai: useAi,
            api_key: apiKey,
          }),
        });

        const data = await resp.json();

        if (!resp.ok) {
          generateError.textContent = data.message || "Une erreur est survenue.";
          generateError.style.display = "block";
          return;
        }

        resultsEmpty.style.display = "none";
        resultsList.innerHTML = "";
        data.variants.forEach((variant) => {
          resultsList.appendChild(renderVariant(variant, data.topic, data.news_id));
        });

        if (data.ai_error) {
          generateError.textContent = "Mode IA indisponible (" + data.ai_error + "), scripts générés en mode standard à la place.";
          generateError.style.display = "block";
        }

        if (creditsRemainingEl && data.credits_remaining !== null && data.credits_remaining !== undefined) {
          creditsRemainingEl.textContent = data.credits_remaining;
        }
      } catch (e) {
        generateError.textContent = "Erreur réseau, réessaie dans un instant.";
        generateError.style.display = "block";
      } finally {
        generateBtn.disabled = false;
        generateBtn.textContent = "⚡ Générer 3 scripts";
      }
    });
  }

  // --- Historique : suppression ---
  $$(".delete-script-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const id = btn.dataset.id;
      btn.disabled = true;
      try {
        const resp = await fetch(`/app/scripts/${id}/delete`, { method: "POST" });
        if (resp.ok) {
          btn.closest(".history-card").remove();
        }
      } catch (e) { /* ignore */ }
    });
  });

  // --- Colore les pastilles de score dans l'historique ---
  $$(".history-score").forEach((el) => {
    const score = parseInt(el.dataset.score, 10);
    el.style.background = scoreColor(score);
  });
})();
