/* Tenline — search landing page. 100% static: reads manifest.json once,
   filters/keyboard-navigates client-side, no runtime API calls. */

const state = { companies: [], matches: [], activeIndex: -1 };

async function boot() {
  try {
    const manifest = await fetch("data/manifest.json").then(r => r.json());
    state.companies = manifest.companies || [];
    document.getElementById("updated-at").textContent = manifest.updated_at || "—";
    const asOf = manifest.universe_as_of ? ` · universe as of ${manifest.universe_as_of}` : "";
    document.getElementById("universe-note").textContent =
      `${state.companies.length} companies covered${asOf}`;
    renderPilotGrid();
  } catch (e) {
    console.error(e);
    document.getElementById("universe-note").textContent =
      "Could not load company list. If running locally, serve with python -m http.server.";
  }
}

function renderPilotGrid() {
  const grid = document.getElementById("pilot-grid");
  grid.innerHTML = "";
  state.companies.forEach((c, i) => {
    const el = document.createElement("div");
    el.className = "pilot-card";
    el.style.setProperty("--i", i);
    el.innerHTML = `
      <span class="t-ticker">${c.ticker}</span>
      <span class="t-name">${c.name} · ${c.sector}</span>
      <span class="t-cov">${(c.coverage_pct * 100).toFixed(0)}% metric coverage</span>`;
    el.addEventListener("click", () => go(c.ticker));
    grid.appendChild(el);
  });
}

function go(ticker) {
  window.location.href = `company.html?t=${encodeURIComponent(ticker)}`;
}

function search(q) {
  q = q.trim().toLowerCase();
  if (!q) return [];
  return state.companies.filter(c =>
    c.ticker.toLowerCase().startsWith(q) || c.name.toLowerCase().includes(q)
  ).slice(0, 12);
}

function renderResults() {
  const box = document.getElementById("search-results");
  const input = document.getElementById("search-input");
  if (!state.matches.length) {
    box.innerHTML = state.query
      ? `<div class="search-empty">No match for "${state.query}" in the current ${state.companies.length}-company universe.</div>`
      : "";
    box.classList.toggle("open", !!state.query);
    input.setAttribute("aria-expanded", String(!!state.query));
    return;
  }
  box.innerHTML = state.matches.map((c, i) => `
    <div class="search-item${i === state.activeIndex ? " active" : ""}" role="option" data-ticker="${c.ticker}">
      <span><span class="t-ticker">${c.ticker}</span><span class="t-name">${c.name}</span></span>
      <span class="t-sector">${c.sector}</span>
    </div>`).join("");
  box.classList.add("open");
  input.setAttribute("aria-expanded", "true");
  box.querySelectorAll(".search-item").forEach(el =>
    el.addEventListener("click", () => go(el.dataset.ticker)));
}

const input = document.getElementById("search-input");
input.addEventListener("input", () => {
  state.query = input.value;
  state.matches = search(input.value);
  state.activeIndex = state.matches.length ? 0 : -1;
  renderResults();
});
input.addEventListener("keydown", e => {
  if (!state.matches.length) return;
  if (e.key === "ArrowDown") {
    e.preventDefault();
    state.activeIndex = (state.activeIndex + 1) % state.matches.length;
    renderResults();
  } else if (e.key === "ArrowUp") {
    e.preventDefault();
    state.activeIndex = (state.activeIndex - 1 + state.matches.length) % state.matches.length;
    renderResults();
  } else if (e.key === "Enter") {
    e.preventDefault();
    if (state.activeIndex >= 0) go(state.matches[state.activeIndex].ticker);
  } else if (e.key === "Escape") {
    input.value = "";
    state.matches = []; state.query = "";
    renderResults();
  }
});
document.addEventListener("click", e => {
  if (!e.target.closest(".search-wrap")) {
    document.getElementById("search-results").classList.remove("open");
  }
});

boot();
