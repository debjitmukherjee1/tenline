/* Tenline — company page. 100% static: reads one pre-computed JSON file for
   the requested ticker, renders with Chart.js. No runtime API calls. */

const params = new URLSearchParams(window.location.search);
const ticker = (params.get("t") || "").toUpperCase();

const ACCENT = "#9c6b2e", ACCENT2 = "#7c5522", BULL = "#266b43", BEAR = "#963527", NEUTRAL = "#635c50";
const AXIS_COLOR = "#9a8f79", GRID_COLOR = "rgba(43,36,26,.08)", FONT = "EB Garamond";

function fmtUSD(v) {
  if (v === null || v === undefined) return "—";
  const abs = Math.abs(v);
  if (abs >= 1e9) return (v / 1e9).toFixed(1) + "B";
  if (abs >= 1e6) return (v / 1e6).toFixed(1) + "M";
  if (abs >= 1e3) return (v / 1e3).toFixed(1) + "K";
  return v.toFixed(0);
}
function fmtUSD$(v) { return v === null || v === undefined ? "—" : "$" + fmtUSD(v); }
function fmtPct(v, d = 1) { return v === null || v === undefined ? "—" : (v * 100).toFixed(d) + "%"; }
function fmtShares(v) { return v === null || v === undefined ? "—" : fmtUSD(v); }
function fmtRatio(v) { return v === null || v === undefined ? "—" : v.toFixed(2) + "x"; }
function signCls(v) { return v > 0.0001 ? "pos" : v < -0.0001 ? "neg" : "flat"; }

async function boot() {
  const app = document.getElementById("app");
  if (!ticker) {
    app.innerHTML = `<p class="muted">No company selected. <a href="index.html">Go back and search</a>.</p>`;
    return;
  }
  try {
    const data = await fetch(`data/companies/${ticker}.json`).then(r => {
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return r.json();
    });
    document.getElementById("page-title").textContent = `${data.name} (${data.ticker}) — Tenline`;
    document.getElementById("updated-at").textContent = data.updated_at || "—";
    render(data);
  } catch (e) {
    console.error(e);
    app.innerHTML = `<p class="muted">Could not load data for "${ticker}". If running locally, serve with
      <code>python -m http.server</code>. <a href="index.html">Back to search</a>.</p>`;
  }
}

function render(d) {
  const app = document.getElementById("app");
  const years = d.years || [];
  const labels = years.map(y => y.fy);
  const notes = d.notes || {};
  const decade = d.decade || {};

  app.innerHTML = `
    <div class="company-head">
      <div class="company-title">
        <span class="ticker-badge">${d.ticker}</span>
        <h2>${d.name}</h2>
        <span class="sector-tag">${d.sector}</span>
      </div>
      <div class="company-links">
        ${d.edgar_filings_url ? `<div><a href="${d.edgar_filings_url}" target="_blank" rel="noopener">Filings on EDGAR ↗</a></div>` : ""}
        <div class="muted small">${years.length} fiscal years · ${(d.coverage.pct * 100).toFixed(0)}% of metrics resolved</div>
      </div>
    </div>
    <hr class="rule" />

    <div class="stat-row">
      <div class="stat">
        <div class="stat-label">10-Yr Revenue CAGR</div>
        <div class="stat-value ${decade.revenue_cagr != null ? signCls(decade.revenue_cagr) : ''}">${fmtPct(decade.revenue_cagr)}</div>
      </div>
      <div class="stat">
        <div class="stat-label">Median Net Margin</div>
        <div class="stat-value">${fmtPct(decade.median_net_margin)}</div>
      </div>
      <div class="stat">
        <div class="stat-label">Share Count Change</div>
        <div class="stat-value ${decade.share_count_change_pct != null ? signCls(-decade.share_count_change_pct) : ''}">${fmtPct(decade.share_count_change_pct)}</div>
        <div class="stat-sub">${decade.share_count_change_pct == null ? '' : (decade.share_count_change_pct < 0 ? 'net buybacks' : 'net dilution')}</div>
      </div>
      <div class="stat">
        <div class="stat-label">FCF Conversion</div>
        <div class="stat-value">${fmtRatio(decade.fcf_conversion_median)}</div>
        <div class="stat-sub">median FCF / net income</div>
      </div>
    </div>

    <div class="chart-grid" id="chart-grid"></div>

    <p class="disclaimer">⚠ Personal / educational project, not investment advice, not a SEBI-registered research or advisory service. All figures are as filed with the SEC (source: <a href="https://data.sec.gov/api/xbrl/companyfacts/CIK${d.cik}.json" target="_blank" rel="noopener">EDGAR XBRL companyfacts</a>) — a gap means the underlying filing didn't disclose that concept under a resolvable tag, never an estimate.</p>
  `;

  const grid = document.getElementById("chart-grid");
  const specs = [
    { key: "revenue", title: "Revenue", cagrChip: decade.revenue_cagr, kind: "bar", fmt: fmtUSD$, series: [{ field: "revenue", label: "Revenue", color: ACCENT }] },
    { key: "margins", title: "Gross / Operating / Net Margin", kind: "line", fmt: fmtPct2, series: [
        { field: "gross_margin", label: "Gross margin", color: ACCENT },
        { field: "operating_margin", label: "Operating margin", color: BULL },
        { field: "net_margin", label: "Net margin", color: BEAR },
      ], multi: true, notesKeys: ["gross_margin", "operating_margin", "net_margin"] },
    { key: "eps_diluted", title: "EPS (Diluted)", kind: "bar", fmt: v => v == null ? "—" : "$" + v.toFixed(2), series: [{ field: "eps_diluted", label: "EPS diluted", color: ACCENT }] },
    { key: "fcf", title: "Free Cash Flow & FCF Margin", kind: "combo", fmt: fmtUSD$, series: [
        { field: "fcf", label: "FCF ($)", color: ACCENT, type: "bar", axis: "y" },
        { field: "fcf_margin", label: "FCF margin (%)", color: BULL, type: "line", axis: "y1" },
      ], combo: true, notesKeys: ["fcf_margin"] },
    { key: "returns", title: "ROE & ROIC", kind: "line", fmt: fmtPct2, series: [
        { field: "roe", label: "ROE", color: ACCENT },
        { field: "roic", label: "ROIC", color: BULL },
      ], multi: true, notesKeys: ["roe", "roic"] },
    { key: "diluted_shares", title: "Diluted Share Count", kind: "bar", fmt: fmtShares, series: [{ field: "diluted_shares", label: "Diluted shares", color: ACCENT }],
      footnote: "Each year shows the figure as originally filed in that year's own 10-K (not retroactively restated by later filings) — a sudden jump usually reflects a stock split, not dilution." },
    { key: "net_debt_to_equity", title: "Net Debt / Equity", kind: "bar", fmt: fmtRatio, series: [{ field: "net_debt_to_equity", label: "Net debt / equity", color: ACCENT }],
      footnote: "Debt here is long-term + short-term borrowings only — it excludes customer deposits, trading liabilities, and insurance reserves, so this ratio understates real leverage for banks, insurers, and other deposit-funded financials." },
  ];

  specs.forEach((spec, i) => grid.appendChild(buildChartBlock(spec, years, labels, notes, i)));
}

function fmtPct2(v) { return fmtPct(v, 1); }

function buildChartBlock(spec, years, labels, notes, i) {
  const block = document.createElement("div");
  block.className = "chart-block";
  block.style.setProperty("--i", i);

  const allFields = spec.series.map(s => s.field);
  const relevantNotes = (spec.notesKeys || allFields).filter(k => notes[k]);
  const allNull = allFields.every(f => years.every(y => y[f] == null));

  const cagrChipHtml = spec.cagrChip != null
    ? `<span class="cagr-chip">${fmtPct(spec.cagrChip)} CAGR</span>` : "";

  if (allNull) {
    block.innerHTML = `
      <div class="chart-head"><div class="chart-title">${spec.title}${cagrChipHtml}</div></div>
      <div class="chart-empty">${relevantNotes.map(k => notes[k]).join(" ") || "Not disclosed in this company's filings."}</div>`;
    return block;
  }

  const canvasId = `chart-${spec.key}`;
  const hasPartialGap = allFields.some(f => years.some(y => y[f] == null) && !years.every(y => y[f] == null));
  const legendHtml = spec.series.length > 1
    ? `<div class="legend-inline">${spec.series.map(s => `<span><span class="swatch" style="border-top-color:${s.color}"></span>${s.label}</span>`).join("")}</div>`
    : "";

  block.innerHTML = `
    <div class="chart-head">
      <div class="chart-title">${spec.title}${cagrChipHtml}</div>
      ${legendHtml}
    </div>
    <div class="chart-canvas-wrap"><canvas id="${canvasId}"></canvas></div>
    ${spec.footnote ? `<p class="chart-footnote">${spec.footnote}</p>` : ""}
    ${relevantNotes.length ? `<p class="chart-footnote">${relevantNotes.map(k => notes[k]).join(" ")}</p>` : ""}
    ${hasPartialGap && !relevantNotes.length ? `<p class="chart-footnote">Gaps indicate a fiscal year not disclosed under a resolvable tag in that year's filing.</p>` : ""}
  `;

  requestAnimationFrame(() => drawChart(canvasId, spec, years, labels));
  return block;
}

function drawChart(canvasId, spec, years, labels) {
  const ctx = document.getElementById(canvasId);
  if (!ctx) return;

  const baseOpts = {
    responsive: true, maintainAspectRatio: false,
    interaction: { mode: "index", intersect: false },
    plugins: {
      legend: { display: false },
      tooltip: {
        callbacks: { label: (item) => `${item.dataset.label}: ${spec.seriesFmt ? spec.seriesFmt[item.datasetIndex](item.raw) : spec.fmt(item.raw)}` }
      }
    },
    scales: {
      x: { ticks: { color: AXIS_COLOR, font: { family: FONT } }, grid: { color: GRID_COLOR } },
      y: { ticks: { color: AXIS_COLOR, font: { family: FONT }, callback: v => spec.fmt(v) }, grid: { color: GRID_COLOR } }
    },
    animation: { duration: 450, easing: "easeOutQuart" }
  };

  if (spec.combo) {
    const datasets = spec.series.map(s => ({
      label: s.label,
      type: s.type,
      data: years.map(y => y[s.field]),
      borderColor: s.color,
      backgroundColor: s.type === "bar" ? s.color + "cc" : "transparent",
      yAxisID: s.axis,
      borderWidth: s.type === "line" ? 2.4 : 1,
      pointRadius: s.type === "line" ? 2 : 0,
      tension: .15,
      spanGaps: false,
      order: s.type === "line" ? 0 : 1,
    }));
    baseOpts.scales.y1 = { position: "right", ticks: { color: AXIS_COLOR, font: { family: FONT }, callback: v => fmtPct(v) }, grid: { display: false } };
    baseOpts.scales.y.ticks.callback = v => fmtUSD$(v);
    baseOpts.plugins.legend.display = true;
    baseOpts.plugins.legend.labels = { color: "#6b6153", font: { family: FONT, size: 11 } };
    baseOpts.plugins.tooltip.callbacks.label = (item) => {
      const s = spec.series[item.datasetIndex];
      return `${s.label}: ${s.axis === "y1" ? fmtPct(item.raw) : fmtUSD$(item.raw)}`;
    };
    new Chart(ctx, { data: { labels, datasets }, options: baseOpts });
    return;
  }

  if (spec.kind === "bar") {
    new Chart(ctx, {
      type: "bar",
      data: { labels, datasets: [{
        label: spec.series[0].label,
        data: years.map(y => y[spec.series[0].field]),
        backgroundColor: spec.series[0].color + "cc",
        borderRadius: 3,
      }] },
      options: baseOpts,
    });
    return;
  }

  // line / multi-line
  const datasets = spec.series.map(s => ({
    label: s.label,
    data: years.map(y => y[s.field]),
    borderColor: s.color,
    backgroundColor: s.color + "1f",
    borderWidth: 2.2,
    pointRadius: 2,
    tension: .15,
    fill: spec.series.length === 1,
    spanGaps: false,
  }));
  new Chart(ctx, { type: "line", data: { labels, datasets }, options: baseOpts });
}

boot();
