/* Tenline — company page. 100% static: reads one pre-computed JSON file for
   the requested ticker, renders with Chart.js. No runtime API calls.

   Provenance & disclosure layer: each company JSON now carries, per fiscal
   year, a `prov` map (per-metric lineage — the us-gaap tag(s), unit, SEC
   accession and transformation rule behind every displayed number), plus a
   top-level `disclosure_changes` list (fiscal-year-over-year reporting
   changes: a tag/unit switch a company made in HOW it reports a line item,
   which shouldn't be mistaken for a change in the business). Both are surfaced
   here so a reader can verify a number against the source filing without
   re-deriving it. Older data files without these fields degrade gracefully. */

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
function fmtPct2(v) { return fmtPct(v, 1); }
function fmtShares(v) { return v === null || v === undefined ? "—" : fmtUSD(v); }
function fmtRatio(v) { return v === null || v === undefined ? "—" : v.toFixed(2) + "x"; }
function signCls(v) { return v > 0.0001 ? "pos" : v < -0.0001 ? "neg" : "flat"; }

/* ---- provenance helpers ------------------------------------------------- */
const METRIC_FMT = {
  revenue: fmtUSD$, gross_margin: fmtPct2, operating_margin: fmtPct2, net_margin: fmtPct2,
  eps_diluted: v => v == null ? "—" : "$" + v.toFixed(2), fcf: fmtUSD$, fcf_margin: fmtPct2,
  roe: fmtPct2, roic: fmtPct2, diluted_shares: fmtShares, net_debt_to_equity: fmtRatio,
};
const METRIC_LABEL = {
  revenue: "Revenue", gross_margin: "Gross margin", operating_margin: "Operating margin",
  net_margin: "Net margin", eps_diluted: "EPS (diluted)", fcf: "Free cash flow",
  fcf_margin: "FCF margin", roe: "ROE", roic: "ROIC", diluted_shares: "Diluted shares",
  net_debt_to_equity: "Net debt / equity",
};

function esc(s) {
  return String(s == null ? "" : s).replace(/[&<>"]/g,
    c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}
// Deep-link to the exact filing on EDGAR from a bare accession number.
function edgarFilingUrl(cik, accn) {
  if (!cik || !accn) return null;
  const cikInt = parseInt(cik, 10);
  const bare = accn.replace(/-/g, "");
  return `https://www.sec.gov/Archives/edgar/data/${cikInt}/${bare}/${esc(accn)}-index.htm`;
}
// Short "us-gaap:Tag" chip, but pass derived/computed strings through as-is.
function tagChip(tag) {
  if (!tag) return "—";
  if (tag.startsWith("derived")) return esc(tag);
  return "us-gaap:" + esc(tag);
}

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
  const disclosures = d.disclosure_changes || [];
  const cik = d.cik;

  app.innerHTML = `
    <div class="company-head">
      <div class="company-title">
        <span class="ticker-badge">${esc(d.ticker)}</span>
        <h2>${esc(d.name)}</h2>
        <span class="sector-tag">${esc(d.sector)}</span>
      </div>
      <div class="company-links">
        ${d.edgar_filings_url ? `<div><a href="${esc(d.edgar_filings_url)}" target="_blank" rel="noopener">Filings on EDGAR ↗</a></div>` : ""}
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

    ${disclosureSummaryHtml(disclosures)}

    <div class="chart-grid" id="chart-grid"></div>

    <p class="disclaimer">⚠ Personal / educational project, not investment advice, not a SEBI-registered research or advisory service. All figures are as filed with the SEC (source: <a href="https://data.sec.gov/api/xbrl/companyfacts/CIK${esc(d.cik)}.json" target="_blank" rel="noopener">EDGAR XBRL companyfacts</a>) — a gap means the underlying filing didn't disclose that concept under a resolvable tag, never an estimate. Every metric's exact tag, unit, accession and formula is in its "Data & sources" panel.</p>
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

  specs.forEach((spec, i) => grid.appendChild(buildChartBlock(spec, years, labels, notes, disclosures, cik, i)));
}

/* Top-of-page summary of every fiscal-year reporting change detected. */
function disclosureSummaryHtml(disclosures) {
  if (!disclosures || !disclosures.length) return "";
  const items = disclosures.map(e => `
    <li>
      <span class="disc-badge" title="Reporting change">⚑</span>
      <span class="disc-when">FY${esc(e.fy_from)} → FY${esc(e.fy_to)}</span>
      <span class="disc-text">${esc(e.note)}</span>
    </li>`).join("");
  return `
    <details class="disclosure-panel" open>
      <summary><span class="disc-badge">⚑</span> Reporting changes detected (${disclosures.length}) — how a line item is reported changed between years, not necessarily the business</summary>
      <ul class="disclosure-list">${items}</ul>
    </details>`;
}

function buildChartBlock(spec, years, labels, notes, disclosures, cik, i) {
  const block = document.createElement("div");
  block.className = "chart-block";
  block.style.setProperty("--i", i);

  const allFields = spec.series.map(s => s.field);
  const relevantNotes = (spec.notesKeys || allFields).filter(k => notes[k]);
  const allNull = allFields.every(f => years.every(y => y[f] == null));

  const cagrChipHtml = spec.cagrChip != null
    ? `<span class="cagr-chip">${fmtPct(spec.cagrChip)} CAGR</span>` : "";

  // Disclosure events touching any metric shown in this block.
  const blockDiscs = (disclosures || []).filter(e => (e.affects || []).some(m => allFields.includes(m)));
  const discFlagHtml = blockDiscs.length ? `
    <div class="chart-disc">
      ${blockDiscs.map(e => `<div class="chart-disc-row"><span class="disc-badge">⚑</span> ${esc(e.note)}</div>`).join("")}
    </div>` : "";

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
      <div class="chart-title">${spec.title}${cagrChipHtml}${blockDiscs.length ? ` <span class="disc-badge" title="A reporting change affects this metric — see below">⚑</span>` : ""}</div>
      ${legendHtml}
    </div>
    <div class="chart-canvas-wrap"><canvas id="${canvasId}"></canvas></div>
    ${spec.footnote ? `<p class="chart-footnote">${spec.footnote}</p>` : ""}
    ${relevantNotes.length ? `<p class="chart-footnote">${relevantNotes.map(k => notes[k]).join(" ")}</p>` : ""}
    ${hasPartialGap && !relevantNotes.length ? `<p class="chart-footnote">Gaps indicate a fiscal year not disclosed under a resolvable tag in that year's filing.</p>` : ""}
    ${discFlagHtml}
    ${provenancePanelHtml(spec, years, cik)}
  `;

  requestAnimationFrame(() => drawChart(canvasId, spec, years, labels));
  return block;
}

/* Expandable per-metric lineage table: FY · value · rule · source tag(s) ·
   unit · filing. Reads year.prov[field] written by the pipeline. */
function provenancePanelHtml(spec, years, cik) {
  const fields = spec.series.map(s => s.field).filter(f => METRIC_FMT[f]);
  const ordered = years.slice().reverse(); // newest first
  const tables = fields.map(field => {
    const rows = ordered.map(y => {
      const val = METRIC_FMT[field] ? METRIC_FMT[field](y[field]) : (y[field] ?? "—");
      const p = (y.prov || {})[field];
      if (!p) {
        return `<tr><td>${esc(y.fy)}</td><td class="num">${val}</td><td colspan="4" class="muted">— not disclosed —</td></tr>`;
      }
      const inputs = p.inputs || [];
      const tags = inputs.map(inp => `<span class="tag" title="${esc(inp.label)}">${tagChip(inp.tag)}</span>`).join(" ");
      const unit = inputs.length ? esc(inputs[0].unit || "") : "";
      // Link the primary input's filing; note if inputs span multiple filings.
      const accns = [...new Set(inputs.map(inp => inp.accn).filter(Boolean))];
      let filing = "—";
      if (accns.length) {
        const url = edgarFilingUrl(cik, accns[0]);
        filing = url ? `<a href="${url}" target="_blank" rel="noopener">${esc(accns[0])}</a>` : esc(accns[0]);
        if (accns.length > 1) filing += ` <span class="muted">+${accns.length - 1}</span>`;
      }
      return `<tr>
        <td>${esc(y.fy)}</td>
        <td class="num">${val}</td>
        <td class="rule">${esc(p.rule)}</td>
        <td class="tags">${tags}</td>
        <td>${unit}</td>
        <td class="filing">${filing}</td>
      </tr>`;
    }).join("");
    const title = fields.length > 1 ? `<div class="prov-metric">${esc(METRIC_LABEL[field] || field)}</div>` : "";
    return `${title}
      <table class="prov-table">
        <thead><tr><th>FY</th><th class="num">Value</th><th>Rule</th><th>Source tag(s)</th><th>Unit</th><th>Filing</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>`;
  }).join("");

  return `
    <details class="prov-panel">
      <summary>Data &amp; sources — verify every number against its filing</summary>
      <div class="prov-body">
        ${tables}
        <p class="prov-note">Each value traces to the exact fact as filed: its us-gaap taxonomy tag, unit, and the SEC accession of the 10-K it came from (click to open the filing on EDGAR). "Rule" is the transformation applied to the raw filing fact(s).</p>
      </div>
    </details>`;
}

function drawChart(canvasId, spec, years, labels) {
  const ctx = document.getElementById(canvasId);
  if (!ctx) return;

  // Tooltip footer: show the source tag(s) behind the hovered fiscal year, so
  // provenance is one hover away without opening the table.
  const provAfterBody = (items) => {
    if (!items || !items.length) return "";
    const idx = items[0].dataIndex;
    const y = years[idx];
    if (!y || !y.prov) return "";
    const lines = [];
    spec.series.forEach(s => {
      const p = y.prov[s.field];
      if (!p || !p.inputs || !p.inputs.length) return;
      const tags = [...new Set(p.inputs.map(inp => inp.tag))].join(", ");
      lines.push(`source: ${tags}`);
    });
    return lines.length ? ["", ...[...new Set(lines)]] : "";
  };

  const baseOpts = {
    responsive: true, maintainAspectRatio: false,
    interaction: { mode: "index", intersect: false },
    plugins: {
      legend: { display: false },
      tooltip: {
        callbacks: {
          label: (item) => `${item.dataset.label}: ${spec.seriesFmt ? spec.seriesFmt[item.datasetIndex](item.raw) : spec.fmt(item.raw)}`,
          afterBody: provAfterBody,
        }
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
