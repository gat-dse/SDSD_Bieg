(() => {
  const ACCESS_HASH = 211969171;
  const ACCESS_SESSION_KEY = "floor-system-assessment-access";
  const records = window.PAIRWISE_DATA?.records || [];
  const criteria = [
    { key: "GWP", label: "GWP", color: "#2f7d4a" },
    { key: "height", label: "Height", color: "#6c91bf" },
    { key: "mass", label: "Mass", color: "#a6772e" },
    { key: "cost", label: "Cost", color: "#805aa6" },
    { key: "time", label: "Construction time", color: "#bd6545" },
  ];
  const systemColors = {
    "Rectangular concrete": "#2E7D32",
    "Rectangular concrete PT dist.": "#60B5E8",
    "Rectangular concrete PT band.": "#0B3D91",
    "Rectangular wood": "#A6761D",
    "TCC flat, kerve": "#7A7A7A",
    "TCC ribs, DBS": "#6A3D9A",
    "Ribbed timber hollow core": "#B86B2B",
    "Ribbed concrete": "#005F3C",
  };
  const state = { caseName: "", scenario: "", span: 0, chartScope: "struct", weights: {} };
  criteria.forEach(c => state.weights[c.key] = 20);

  const byId = id => document.getElementById(id);
  const unique = values => [...new Set(values)];
  const metricFor = (criterion, scope) => {
    const prefix = { GWP: "GWP", height: "h", mass: "m", cost: "cost", time: "time" }[criterion];
    return `${prefix}_${scope}`;
  };
  const splitLabel = label => {
    const parts = label.replaceAll("*", "").split(" | ");
    return { title: parts[0], detail: parts.slice(1).join(" · ") };
  };

  function accessHash(value) {
    let hash = 5381;
    for (const character of value) {
      hash = ((hash * 33) ^ character.charCodeAt(0)) >>> 0;
    }
    return hash;
  }

  function unlockAssessment() {
    document.body.classList.remove("access-locked");
    byId("access-gate").hidden = true;
  }

  function setupAccessGate(onSuccess) {
    let alreadyAuthorized = false;
    try {
      alreadyAuthorized = sessionStorage.getItem(ACCESS_SESSION_KEY) === "granted";
    } catch (_error) {
      // Some file URL configurations disable web storage; login still works.
    }
    if (alreadyAuthorized) {
      unlockAssessment();
      onSuccess();
      return;
    }

    byId("access-form").addEventListener("submit", event => {
      event.preventDefault();
      const input = byId("access-key");
      const valid = accessHash(input.value) === ACCESS_HASH;
      byId("access-error").hidden = valid;
      if (!valid) {
        input.select();
        return;
      }
      try {
        sessionStorage.setItem(ACCESS_SESSION_KEY, "granted");
      } catch (_error) {
        // Continue without persistence when web storage is unavailable.
      }
      unlockAssessment();
      onSuccess();
    });
  }

  function populateSelect(select, values, formatter = value => value) {
    select.innerHTML = values.map(v => `<option value="${v}">${formatter(v)}</option>`).join("");
  }

  function availableScenarios() {
    return unique(records.filter(r => r.case === state.caseName).map(r => r.scenario));
  }
  function availableSpans() {
    return unique(records.filter(r => r.case === state.caseName && r.scenario === state.scenario).map(r => r.span)).sort((a,b) => a-b);
  }

  function setupControls() {
    const caseSelect = byId("case-select");
    const scenarioSelect = byId("scenario-select");
    const spanSelect = byId("span-select");
    const cases = unique(records.map(r => r.case));
    populateSelect(caseSelect, cases);
    state.caseName = cases.includes("Residential") ? "Residential" : cases[0];
    caseSelect.value = state.caseName;

    const updateScenario = () => {
      const scenarios = availableScenarios();
      populateSelect(scenarioSelect, scenarios, v => v.replace(/^./, c => c.toUpperCase()));
      if (!scenarios.includes(state.scenario)) state.scenario = scenarios[0];
      scenarioSelect.value = state.scenario;
      updateSpans();
    };
    const updateSpans = () => {
      const spans = availableSpans();
      populateSelect(spanSelect, spans, v => `${v} m`);
      if (!spans.includes(Number(state.span))) state.span = spans[0];
      spanSelect.value = String(state.span);
      render();
    };

    caseSelect.addEventListener("change", e => { state.caseName = e.target.value; state.scenario = ""; updateScenario(); });
    scenarioSelect.addEventListener("change", e => { state.scenario = e.target.value; updateSpans(); });
    spanSelect.addEventListener("change", e => { state.span = Number(e.target.value); render(); });
    updateScenario();
  }

  function setupWeights() {
    const container = byId("weight-controls");
    container.innerHTML = criteria.map(c => `
      <div class="weight-control">
        <header><span class="weight-name">${c.label}</span><span class="weight-value" id="value-${c.key}">20</span></header>
        <input id="weight-${c.key}" type="range" min="0" max="100" value="20" aria-label="${c.label} weight">
      </div>`).join("");
    criteria.forEach(c => byId(`weight-${c.key}`).addEventListener("input", e => {
      state.weights[c.key] = Number(e.target.value);
      byId(`value-${c.key}`).textContent = e.target.value;
      render();
    }));
    byId("equalize-button").addEventListener("click", () => {
      criteria.forEach(c => {
        state.weights[c.key] = 20;
        byId(`weight-${c.key}`).value = 20;
        byId(`value-${c.key}`).textContent = "20";
      });
      render();
    });
  }

  function normalizedWeights() {
    const sum = criteria.reduce((acc, c) => acc + state.weights[c.key], 0);
    return Object.fromEntries(criteria.map(c => [c.key, sum ? state.weights[c.key] / sum : 0]));
  }

  function hasActiveWeight() {
    return criteria.some(c => state.weights[c.key] > 0);
  }

  function weightedScores(scope, span = state.span) {
    const filtered = records.filter(r => r.case === state.caseName && r.scenario === state.scenario && r.span === Number(span));
    const weights = normalizedWeights();
    const systems = unique(filtered.map(r => r.system));
    return systems.map(system => {
      const systemRows = filtered.filter(r => r.system === system);
      let score = 0;
      criteria.forEach(c => {
        const row = systemRows.find(r => r.metric === metricFor(c.key, scope));
        score += weights[c.key] * (row?.score || 0);
      });
      const row = systemRows[0];
      return { system, label: row?.label || system, score };
    }).sort((a,b) => b.score - a.score);
  }

  function renderAllocation() {
    const weights = normalizedWeights();
    byId("weight-allocation").innerHTML = criteria.map(c => `<span class="allocation-segment" title="${c.label}: ${(weights[c.key]*100).toFixed(1)}%" style="width:${weights[c.key]*100}%;background:${c.color}"></span>`).join("");
  }

  function renderRanking(scope) {
    const scores = weightedScores(scope);
    const winner = scores[0];
    byId(`${scope}-winner`).innerHTML = !hasActiveWeight()
      ? "Set at least<br>one weight"
      : winner ? `Winner<br>${splitLabel(winner.label).title}` : "No result";
    byId(`${scope}-ranking`).innerHTML = scores.map((row, index) => {
      const label = splitLabel(row.label);
      const color = systemColors[row.system] || "#43564a";
      return `<div class="rank-row">
        <span class="rank-number">${index + 1}</span>
        <span class="system-name">${label.title}<small>${label.detail}</small></span>
        <span class="score-track"><span class="score-fill" style="display:block;width:${row.score*100}%;background:${color}"></span></span>
        <span class="score-number">${row.score.toFixed(3)}</span>
      </div>`;
    }).join("");
  }

  function renderChart() {
    const spans = availableSpans();
    const allScores = Object.fromEntries(spans.map(span => [span, weightedScores(state.chartScope, span)]));
    const systems = unique(Object.values(allScores).flat().map(row => row.system));
    const width = 1160, height = 360, margin = { left: 58, right: 24, top: 18, bottom: 45 };
    const x = span => margin.left + (spans.indexOf(span) / Math.max(spans.length - 1, 1)) * (width - margin.left - margin.right);
    const y = score => margin.top + (1 - score) * (height - margin.top - margin.bottom);
    const grid = [0, .25, .5, .75, 1].map(v => `<line class="chart-grid" x1="${margin.left}" y1="${y(v)}" x2="${width-margin.right}" y2="${y(v)}"/><text class="chart-label" x="${margin.left-12}" y="${y(v)+5}" text-anchor="end">${v.toFixed(2)}</text>`).join("");
    const xLabels = spans.map(s => `<text class="chart-label" x="${x(s)}" y="${height-14}" text-anchor="middle">${s} m</text>`).join("");
    const lines = systems.map(system => {
      const points = spans.map(span => ({ span, score: allScores[span].find(r => r.system === system)?.score || 0 }));
      const color = systemColors[system] || "#43564a";
      const path = points.map((p,i) => `${i ? "L" : "M"}${x(p.span)},${y(p.score)}`).join(" ");
      const circles = points.map(p => `<circle class="chart-point" cx="${x(p.span)}" cy="${y(p.score)}" r="5" fill="${color}"/>`).join("");
      return `<path class="chart-line" d="${path}" stroke="${color}"/>${circles}`;
    }).join("");
    byId("span-chart").innerHTML = `<svg class="chart-svg" viewBox="0 0 ${width} ${height}" role="img" aria-label="Sustainability scores across spans">${grid}<line class="chart-axis" x1="${margin.left}" y1="${y(0)}" x2="${width-margin.right}" y2="${y(0)}"/>${xLabels}${lines}</svg><div class="chart-legend">${systems.map(system => {
      const label = splitLabel(records.find(r => r.system === system)?.label || system);
      const qualifier = label.detail.startsWith("(") ? ` ${label.detail.split(" · ")[0]}` : "";
      return `<span style="--legend-color:${systemColors[system] || '#43564a'}">${label.title}${qualifier}</span>`;
    }).join("")}</div>`;
  }

  function renderCrossSectionPlot() {
    const image = byId("cross-section-plot");
    const message = byId("cross-section-message");
    const caseSlug = state.caseName.toLowerCase().replaceAll(" ", "_");
    image.hidden = false;
    message.hidden = true;
    image.src = `cross_sections/final_cross_sections_${caseSlug}_${Number(state.span)}m.png?v=20260622`;
    image.alt = `${state.caseName} floor-system cross-sections at a span of ${state.span} m`;
    image.onerror = () => {
      image.hidden = true;
      message.hidden = false;
    };
  }

  function render() {
    renderAllocation();
    renderRanking("struct");
    renderRanking("total");
    renderChart();
    renderCrossSectionPlot();
  }

  document.querySelectorAll("[data-chart-scope]").forEach(button => button.addEventListener("click", () => {
    state.chartScope = button.dataset.chartScope;
    document.querySelectorAll("[data-chart-scope]").forEach(b => b.classList.toggle("active", b === button));
    renderChart();
  }));

  function initializeAssessment() {
    if (!records.length) {
      document.body.innerHTML = "<p style='padding:2rem'>No pairwise data found. Run export_pairwise_web_data.py.</p>";
      return;
    }
    setupWeights();
    setupControls();
  }

  setupAccessGate(initializeAssessment);
})();
