from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["admin"])


@router.get("/admin/ui", response_class=HTMLResponse)
async def admin_ui() -> HTMLResponse:
    return HTMLResponse(_ADMIN_UI_HTML)


_ADMIN_UI_HTML = """
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Collectarr Admin</title>
    <style>
      :root {
        color-scheme: dark;
        --bg: #0f1113;
        --panel: #1d1d1d;
        --panel-2: #2d2d2d;
        --line: #444;
        --text: #f2f5f8;
        --muted: #9ea9b6;
        --accent: #4dbbd5;
        --yellow: #ffd400;
        --danger: #ff6b6b;
        --ok: #75d490;
      }
      * { box-sizing: border-box; }
      body {
        margin: 0;
        min-height: 100vh;
        background: var(--bg);
        color: var(--text);
        font: 14px/1.45 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      }
      header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 16px;
        padding: 14px 20px;
        background: var(--accent);
        border-bottom: 1px solid var(--line);
      }
      header .muted { color: #10262c; font-weight: 700; }
      header button {
        background: #202020;
        color: #fff;
        border-color: #202020;
      }
      h1, h2, h3, p { margin: 0; }
      h1 { font-size: 18px; letter-spacing: 0; }
      h2 { font-size: 15px; margin-bottom: 12px; }
      h3 { font-size: 14px; margin-bottom: 4px; }
      main {
        display: grid;
        grid-template-columns: minmax(240px, 320px) minmax(0, 1fr);
        min-height: calc(100vh - 54px);
      }
      aside {
        padding: 16px;
        border-right: 1px solid var(--line);
        background: #151a20;
      }
      section { padding: 16px; }
      .stack { display: grid; gap: 12px; }
      .panel {
        background: var(--panel);
        border: 1px solid var(--line);
        border-radius: 8px;
        padding: 14px;
      }
      .row {
        display: flex;
        align-items: center;
        gap: 8px;
        flex-wrap: wrap;
      }
      label {
        display: grid;
        gap: 6px;
        color: var(--muted);
        font-size: 12px;
      }
      input, select, textarea, button {
        border: 1px solid var(--line);
        border-radius: 6px;
        background: var(--panel-2);
        color: var(--text);
        font: inherit;
      }
      input, select, textarea {
        width: 100%;
        padding: 9px 10px;
      }
      textarea {
        min-height: 180px;
        resize: vertical;
        font-family: ui-monospace, SFMono-Regular, Consolas, "Liberation Mono", monospace;
        font-size: 12px;
      }
      button {
        cursor: pointer;
        padding: 9px 12px;
      }
      button.primary {
        background: var(--accent);
        border-color: var(--accent);
        color: #071217;
        font-weight: 700;
      }
      button:disabled { cursor: wait; opacity: .65; }
      .muted { color: var(--muted); }
      .status {
        padding: 8px 10px;
        border-radius: 6px;
        background: var(--panel-2);
        color: var(--muted);
        border: 1px solid var(--line);
        min-height: 38px;
      }
      .status.ok { color: var(--ok); }
      .status.error { color: var(--danger); }
      .grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
        gap: 12px;
      }
      .dashboard {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
        gap: 10px;
      }
      .metric {
        display: grid;
        gap: 4px;
        padding: 12px;
        background: #222;
        border: 1px solid var(--line);
        border-radius: 8px;
      }
      .metric span {
        color: var(--muted);
        font-size: 12px;
        font-weight: 700;
      }
      .metric strong {
        color: var(--accent);
        font-size: 24px;
        line-height: 1;
      }
      .metric.warn strong { color: var(--yellow); }
      .metric.ok strong { color: var(--ok); }
      .badge {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        width: fit-content;
        padding: 2px 7px;
        border-radius: 999px;
        border: 1px solid var(--line);
        background: #171717;
        color: var(--muted);
        font-size: 11px;
        font-weight: 800;
        text-transform: uppercase;
      }
      .badge.live, .badge.approved { color: var(--ok); border-color: #2d7a43; }
      .badge.stub, .badge.pending { color: var(--yellow); border-color: #8a7600; }
      .badge.rejected { color: var(--danger); border-color: #7a2d2d; }
      .results {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
        gap: 10px;
      }
      .proposal-toolbar {
        display: grid;
        grid-template-columns: minmax(140px, 170px) minmax(140px, 170px) minmax(160px, 1fr) auto;
        gap: 8px;
        align-items: end;
      }
      .quick-filters {
        display: flex;
        gap: 6px;
        flex-wrap: wrap;
      }
      .quick-filters button.active {
        background: var(--accent);
        border-color: var(--accent);
        color: #071217;
        font-weight: 800;
      }
      .proposal-list {
        display: grid;
        gap: 8px;
      }
      .proposal {
        display: grid;
        grid-template-columns: minmax(0, 1fr) auto;
        gap: 12px;
        padding: 10px;
        background: var(--panel-2);
        border: 1px solid var(--line);
        border-radius: 8px;
      }
      .proposal-body {
        display: grid;
        grid-template-columns: 58px minmax(0, 1fr);
        min-height: 0;
        gap: 10px;
      }
      .proposal img {
        width: 50px;
        height: 74px;
        object-fit: cover;
        border-radius: 4px;
        background: #0b0d10;
      }
      .proposal-actions {
        display: flex;
        align-items: flex-start;
        gap: 6px;
        flex-wrap: wrap;
        justify-content: flex-end;
      }
      .result {
        display: grid;
        gap: 8px;
        padding: 10px;
        background: var(--panel-2);
        border: 1px solid var(--line);
        border-radius: 8px;
      }
      .result img {
        width: 72px;
        height: 104px;
        object-fit: cover;
        border-radius: 4px;
        background: #0b0d10;
      }
      .split {
        display: grid;
        grid-template-columns: 80px minmax(0, 1fr);
        gap: 10px;
      }
      .log {
        display: grid;
        gap: 6px;
        max-height: 190px;
        overflow: auto;
      }
      .log-entry {
        padding: 8px 10px;
        background: #151515;
        border: 1px solid #303030;
        border-radius: 6px;
        color: var(--muted);
      }
      .summary {
        max-height: 170px;
        overflow: auto;
        padding: 8px;
        background: #151515;
        border: 1px solid #303030;
        border-radius: 6px;
      }
      pre {
        overflow: auto;
        white-space: pre-wrap;
        margin: 0;
        color: var(--muted);
        font-family: ui-monospace, SFMono-Regular, Consolas, "Liberation Mono", monospace;
        font-size: 12px;
      }
      @media (max-width: 780px) {
        main { grid-template-columns: 1fr; }
        aside { border-right: 0; border-bottom: 1px solid var(--line); }
        .proposal-toolbar, .proposal { grid-template-columns: 1fr; }
        .proposal-body { grid-template-columns: 1fr; }
        .proposal-actions { justify-content: flex-start; }
      }
    </style>
  </head>
  <body>
    <header>
      <div>
        <h1>Collectarr Admin</h1>
        <p class="muted">Canonical metadata console. Personal library data stays local.</p>
      </div>
      <button id="healthButton" type="button">Check health</button>
    </header>
    <main>
      <aside class="stack">
        <div class="panel stack">
          <h2>Admin token</h2>
          <label>Email <input id="email" autocomplete="username"></label>
          <label>Password <input id="password" type="password" autocomplete="current-password"></label>
          <button id="loginButton" class="primary" type="button">Login</button>
          <button id="clearTokenButton" type="button">Clear token</button>
          <div id="authStatus" class="status">No token loaded.</div>
        </div>
        <div class="panel stack">
          <h2>Barcode lookup</h2>
          <label>Barcode <input id="barcode" placeholder="75960604716100111"></label>
          <button id="barcodeButton" type="button">Lookup comic</button>
        </div>
        <div class="panel stack">
          <h2>Providers</h2>
          <button id="providersButton" type="button">Load provider status</button>
          <div id="providerStatusList" class="stack"></div>
        </div>
      </aside>
      <section class="stack">
        <div class="dashboard">
          <div class="metric warn">
            <span>Pending proposals</span>
            <strong id="proposalMetric">-</strong>
          </div>
          <div class="metric ok">
            <span>Approved</span>
            <strong id="approvedProposalMetric">-</strong>
          </div>
          <div class="metric">
            <span>Rejected</span>
            <strong id="rejectedProposalMetric">-</strong>
          </div>
          <div class="metric ok">
            <span>Providers online</span>
            <strong id="providerMetric">-</strong>
          </div>
          <div class="metric">
            <span>Last ingest</span>
            <strong id="ingestMetric">-</strong>
          </div>
        </div>
        <div class="grid">
          <div class="panel stack">
            <h2>Catalog search</h2>
            <div class="row">
              <label style="flex: 1 1 220px">Query <input id="catalogQuery" placeholder="Superman"></label>
              <button id="catalogButton" type="button">Search</button>
            </div>
            <div id="catalogResults" class="results"></div>
          </div>
          <div class="panel stack">
            <h2>Provider ingest</h2>
            <label>Provider
              <select id="provider">
                <option value="comicvine">ComicVine</option>
                <option value="igdb">IGDB</option>
                <option value="tmdb">TMDb</option>
              </select>
            </label>
            <div class="row">
              <label style="flex: 1 1 220px">Provider query
                <input id="providerQuery" placeholder="Batman #1">
              </label>
              <button id="providerButton" type="button">Search provider</button>
            </div>
            <div id="providerResults" class="results"></div>
          </div>
          <div class="panel stack">
            <h2>Metadata proposals</h2>
            <div class="quick-filters" id="proposalQuickFilters">
              <button type="button" data-status="pending" class="active">Pending</button>
              <button type="button" data-status="approved">Approved</button>
              <button type="button" data-status="rejected">Rejected</button>
            </div>
            <div class="proposal-toolbar">
              <label>Status
                <select id="proposalStatus">
                  <option value="pending">Pending</option>
                  <option value="approved">Approved</option>
                  <option value="rejected">Rejected</option>
                </select>
              </label>
              <label>Provider
                <select id="proposalProvider">
                  <option value="">All providers</option>
                  <option value="comicvine">ComicVine</option>
                  <option value="igdb">IGDB</option>
                  <option value="tmdb">TMDb</option>
                  <option value="anilist">AniList</option>
                  <option value="openlibrary">OpenLibrary</option>
                  <option value="bgg">BoardGameGeek</option>
                </select>
              </label>
              <label>Search proposals
                <input id="proposalSearch" placeholder="title, query, summary, provider">
              </label>
              <button id="proposalsButton" type="button">Load</button>
            </div>
            <div id="proposalResults" class="proposal-list"></div>
          </div>
          <div class="panel stack">
            <h2>Ingest log</h2>
            <div id="ingestLog" class="log">
              <div class="log-entry">No admin actions yet.</div>
            </div>
          </div>
        </div>
        <div class="panel stack">
          <h2>Response</h2>
          <div id="status" class="status">Ready.</div>
          <textarea id="response" readonly></textarea>
        </div>
      </section>
    </main>
    <script>
      const tokenKey = "collectarr.admin.token";
      const state = {
        token: localStorage.getItem(tokenKey) || "",
        proposals: [],
        activeProposalId: "",
        activeProposalTitle: "",
      };

      const $ = (id) => document.getElementById(id);
      const responseBox = $("response");
      const statusBox = $("status");
      const authStatus = $("authStatus");

      function setStatus(message, type = "") {
        statusBox.className = `status ${type}`;
        statusBox.textContent = message;
      }

      function setResponse(value) {
        responseBox.value = typeof value === "string" ? value : JSON.stringify(value, null, 2);
      }

      function setMetric(id, value) {
        $(id).textContent = value;
      }

      function updateProposalQuickFilters(status) {
        document.querySelectorAll("#proposalQuickFilters button").forEach((button) => {
          button.classList.toggle("active", button.dataset.status === status);
        });
      }

      function logEvent(message) {
        const target = $("ingestLog");
        if (target.firstElementChild?.textContent === "No admin actions yet.") {
          target.innerHTML = "";
        }
        const entry = document.createElement("div");
        entry.className = "log-entry";
        entry.textContent = `${new Date().toLocaleTimeString()} - ${message}`;
        target.prepend(entry);
      }

      function setBusy(button, isBusy) {
        button.disabled = isBusy;
      }

      function escapeHtml(value) {
        return String(value ?? "")
          .replaceAll("&", "&amp;")
          .replaceAll("<", "&lt;")
          .replaceAll(">", "&gt;")
          .replaceAll('"', "&quot;")
          .replaceAll("'", "&#039;");
      }

      function updateAuthStatus() {
        authStatus.className = `status ${state.token ? "ok" : ""}`;
        authStatus.textContent = state.token ? "Admin token loaded." : "No token loaded.";
      }

      function headers(withAuth = false) {
        const value = { "Content-Type": "application/json" };
        if (withAuth && state.token) {
          value.Authorization = `Bearer ${state.token}`;
        }
        return value;
      }

      async function request(path, options = {}) {
        const response = await fetch(path, options);
        const text = await response.text();
        let data = null;
        if (text) {
          try {
            data = JSON.parse(text);
          } catch {
            data = { detail: text };
          }
        }
        if (!response.ok) {
          const message = data?.detail || response.statusText;
          throw new Error(Array.isArray(message) ? JSON.stringify(message) : message);
        }
        return data;
      }

      function renderCatalogResults(target, items) {
        target.innerHTML = "";
        if (!items.length) {
          target.innerHTML = '<p class="muted">No results.</p>';
          return;
        }
        for (const item of items) {
          const card = document.createElement("article");
          card.className = "result";
          const title = escapeHtml(item.title);
          const itemNumber = item.item_number ? ` #${escapeHtml(item.item_number)}` : "";
          const kind = escapeHtml(item.kind || "metadata");
          const id = escapeHtml(item.id || "");
          const coverUrl = escapeHtml(item.cover_image_url || "");
          card.innerHTML = `
            <div class="split">
              ${coverUrl ? `<img src="${coverUrl}" alt="">` : "<div></div>"}
              <div>
                <h3>${title}${itemNumber}</h3>
                <p class="muted">${kind}</p>
                <pre>${id}</pre>
              </div>
            </div>
          `;
          target.appendChild(card);
        }
      }

      function renderProviderResults(items) {
        const target = $("providerResults");
        target.innerHTML = "";
        if (!items.length) {
          target.innerHTML = '<p class="muted">No provider results.</p>';
          return;
        }
        for (const item of items) {
          const card = document.createElement("article");
          card.className = "result";
          const providerId = item.provider_item_id || item.id || "";
          const title = escapeHtml(item.title || "Untitled");
          const safeProviderId = escapeHtml(providerId);
          const actionLabel = state.activeProposalId ? "Approve proposal" : "Ingest";
          card.innerHTML = `
            <h3>${title}</h3>
            <p class="muted">${safeProviderId}</p>
            <button type="button" class="primary">${actionLabel}</button>
          `;
          card.querySelector("button").addEventListener("click", () => {
            if (state.activeProposalId) {
              approveProposalWithProviderItem(state.activeProposalId, providerId);
            } else {
              ingestProviderItem(providerId);
            }
          });
          target.appendChild(card);
        }
      }

      function renderProviderStatuses(items) {
        const target = $("providerStatusList");
        target.innerHTML = "";
        if (!items.length) {
          target.innerHTML = '<p class="muted">No providers.</p>';
          return;
        }
        for (const item of items) {
          const card = document.createElement("article");
          card.className = "result";
          card.innerHTML = `
          <h3>${escapeHtml(item.name)} (${escapeHtml(item.kind)})</h3>
            <span class="badge ${escapeHtml(item.status)}">${escapeHtml(item.status)}</span>
            <p class="muted">${escapeHtml(item.message)}</p>
          `;
          target.appendChild(card);
        }
      }

      function renderProposals(items) {
        const target = $("proposalResults");
        target.innerHTML = "";
        state.proposals = items;
        const filtered = filterProposals(items);
        if (!items.length) {
          target.innerHTML = '<p class="muted">No proposals for this status.</p>';
          return;
        }
        if (!filtered.length) {
          target.innerHTML = '<p class="muted">No proposals match this filter.</p>';
          return;
        }
        for (const item of filtered) {
          const card = document.createElement("article");
          card.className = "proposal";
          const title = escapeHtml(item.title || item.query || "Untitled proposal");
          const query = escapeHtml(item.query || "");
          const provider = escapeHtml(item.provider || "");
          const providerId = escapeHtml(item.provider_item_id || "");
          const status = escapeHtml(item.status || "pending");
          const summary = escapeHtml(item.summary || "");
          const imageUrl = escapeHtml(item.image_url || "");
          const actions = item.status === "pending"
            ? `${providerId ? '<button type="button" class="primary" data-action="approve">Approve</button>' : '<button type="button" class="primary" data-action="search-provider">Search provider</button>'}
              <button type="button" data-action="reject">Reject</button>`
            : '<span class="muted">Reviewed</span>';
          card.innerHTML = `
            <div class="proposal-body">
              ${imageUrl ? `<img src="${imageUrl}" alt="">` : "<div></div>"}
              <div class="stack">
                <div class="row">
                  <h3>${title}</h3>
                  <span class="badge ${status}">${status}</span>
                </div>
                <p class="muted">${provider} ${providerId || "manual correction / proposal"}${query ? ` - ${query}` : ""}</p>
                <div class="row">
                  <span class="badge">${provider || "manual"}</span>
                  ${providerId ? `<span class="badge">Provider ID ${providerId}</span>` : '<span class="badge">Needs provider match</span>'}
                </div>
                ${summary ? `<pre class="summary">${summary}</pre>` : ""}
              </div>
            </div>
            <div class="proposal-actions">
              ${actions}
            </div>
          `;
          card.querySelector('[data-action="approve"]')?.addEventListener("click", () => approveProposal(item.id));
          card.querySelector('[data-action="search-provider"]')?.addEventListener("click", () => searchProviderForProposal(item));
          card.querySelector('[data-action="reject"]')?.addEventListener("click", () => rejectProposal(item.id));
          target.appendChild(card);
        }
      }

      function filterProposals(items) {
        const needle = $("proposalSearch").value.trim().toLowerCase();
        if (!needle) {
          return items;
        }
        return items.filter((item) => [
          item.title,
          item.query,
          item.provider,
          item.provider_item_id,
          item.summary,
          item.status,
        ].some((value) => String(value || "").toLowerCase().includes(needle)));
      }

      async function login() {
        const button = $("loginButton");
        setBusy(button, true);
        try {
          const data = await request("/auth/login", {
            method: "POST",
            headers: headers(),
            body: JSON.stringify({ email: $("email").value, password: $("password").value }),
          });
          state.token = data.access_token;
          localStorage.setItem(tokenKey, state.token);
          updateAuthStatus();
          setStatus("Logged in.", "ok");
          setResponse(data);
          logEvent("Admin login succeeded.");
        } catch (error) {
          setStatus(error.message, "error");
        } finally {
          setBusy(button, false);
        }
      }

      async function health() {
        const button = $("healthButton");
        setBusy(button, true);
        try {
          const data = await request("/health");
          setStatus("Health check complete.", "ok");
          setResponse(data);
          logEvent("Health check completed.");
        } catch (error) {
          setStatus(error.message, "error");
        } finally {
          setBusy(button, false);
        }
      }

      async function catalogSearch() {
        const button = $("catalogButton");
        setBusy(button, true);
        try {
          const query = encodeURIComponent($("catalogQuery").value);
          const data = await request(`/search?q=${query}&kind=comic`);
          renderCatalogResults($("catalogResults"), data);
          setStatus(`Found ${data.length} catalog items.`, "ok");
          setResponse(data);
        } catch (error) {
          setStatus(error.message, "error");
        } finally {
          setBusy(button, false);
        }
      }

      async function barcodeLookup() {
        const button = $("barcodeButton");
        setBusy(button, true);
        try {
          const barcode = encodeURIComponent($("barcode").value);
          const data = await request(`/barcode/${barcode}?kind=comic`);
          renderCatalogResults($("catalogResults"), [data]);
          setStatus("Barcode match found.", "ok");
          setResponse(data);
        } catch (error) {
          setStatus(error.message, "error");
        } finally {
          setBusy(button, false);
        }
      }

      async function providerSearch() {
        const button = $("providerButton");
        setBusy(button, true);
        try {
          const data = await request("/admin/providers/search", {
            method: "POST",
            headers: headers(true),
            body: JSON.stringify({
              provider: $("provider").value,
              query: $("providerQuery").value,
            }),
          });
          renderProviderResults(data);
          setStatus(
            state.activeProposalId
              ? `Found ${data.length} provider items for proposal ${state.activeProposalTitle}.`
              : `Found ${data.length} provider items.`,
            "ok"
          );
          setResponse(data);
          logEvent(`Provider search returned ${data.length} items.`);
        } catch (error) {
          setStatus(error.message, "error");
        } finally {
          setBusy(button, false);
        }
      }

      async function loadProviders() {
        const button = $("providersButton");
        setBusy(button, true);
        try {
          const data = await request("/admin/providers", {
            headers: headers(true),
          });
          renderProviderStatuses(data);
          setMetric("providerMetric", data.filter((item) => item.is_configured).length);
          setStatus("Provider status loaded.", "ok");
          setResponse(data);
          logEvent("Provider status refreshed.");
        } catch (error) {
          setStatus(error.message, "error");
        } finally {
          setBusy(button, false);
        }
      }

      async function loadProposalSummary() {
        try {
          const data = await request("/admin/metadata/proposals/summary", {
            headers: headers(true),
          });
          setMetric("proposalMetric", data.pending);
          setMetric("approvedProposalMetric", data.approved);
          setMetric("rejectedProposalMetric", data.rejected);
        } catch (error) {
          setMetric("proposalMetric", "!");
          setMetric("approvedProposalMetric", "!");
          setMetric("rejectedProposalMetric", "!");
        }
      }

      async function ingestProviderItem(providerItemId) {
        try {
          const data = await request("/admin/providers/ingest", {
            method: "POST",
            headers: headers(true),
            body: JSON.stringify({
              provider: $("provider").value,
              provider_item_id: providerItemId,
            }),
          });
          setStatus(data.created ? "Metadata item ingested." : "Metadata item already exists.", "ok");
          setMetric("ingestMetric", data.created ? "new" : "exists");
          setResponse(data);
          logEvent(data.created ? "Metadata item ingested." : "Ingest skipped, item already exists.");
        } catch (error) {
          setStatus(error.message, "error");
        }
      }

      async function loadProposals() {
        const button = $("proposalsButton");
        setBusy(button, true);
        try {
          const status = encodeURIComponent($("proposalStatus").value);
          const provider = $("proposalProvider").value;
          const providerParam = provider ? `&provider=${encodeURIComponent(provider)}` : "";
          const data = await request(`/admin/metadata/proposals?status=${status}${providerParam}`, {
            headers: headers(true),
          });
          renderProposals(data);
          updateProposalQuickFilters($("proposalStatus").value);
          loadProposalSummary();
          setStatus(`Loaded ${data.length} ${$("proposalStatus").value} proposals.`, "ok");
          setResponse(data);
          logEvent(`Loaded ${data.length} ${$("proposalStatus").value} proposals.`);
        } catch (error) {
          setStatus(error.message, "error");
        } finally {
          setBusy(button, false);
        }
      }

      function searchProviderForProposal(item) {
        state.activeProposalId = item.id;
        state.activeProposalTitle = item.title || item.query || item.id;
        $("provider").value = item.provider || "comicvine";
        $("providerQuery").value = item.query || item.title || "";
        setStatus("Provider search prepared from proposal.", "ok");
        logEvent("Prepared provider search from metadata proposal.");
        providerSearch();
      }

      async function approveProposalWithProviderItem(id, providerItemId) {
        try {
          const data = await request(`/admin/metadata/proposals/${id}/approve-provider`, {
            method: "POST",
            headers: headers(true),
            body: JSON.stringify({
              provider: $("provider").value,
              provider_item_id: providerItemId,
            }),
          });
          state.activeProposalId = "";
          state.activeProposalTitle = "";
          setStatus("Proposal approved with selected provider item.", "ok");
          setMetric("ingestMetric", data.created ? "new" : "exists");
          setResponse(data);
          logEvent("Manual proposal approved with provider item.");
          $("providerResults").innerHTML = "";
          loadProposalSummary();
          loadProposals();
        } catch (error) {
          setStatus(error.message, "error");
        }
      }

      async function approveProposal(id) {
        try {
          const data = await request(`/admin/metadata/proposals/${id}/approve`, {
            method: "POST",
            headers: headers(true),
          });
          setStatus("Proposal approved and ingested.", "ok");
          setMetric("ingestMetric", "approved");
          setResponse(data);
          logEvent("Proposal approved and ingested.");
          loadProposalSummary();
          loadProposals();
        } catch (error) {
          setStatus(error.message, "error");
        }
      }

      async function rejectProposal(id) {
        try {
          const data = await request(`/admin/metadata/proposals/${id}/reject`, {
            method: "POST",
            headers: headers(true),
          });
          setStatus("Proposal rejected.", "ok");
          setResponse(data);
          logEvent("Proposal rejected.");
          loadProposalSummary();
          loadProposals();
        } catch (error) {
          setStatus(error.message, "error");
        }
      }

      $("loginButton").addEventListener("click", login);
      $("clearTokenButton").addEventListener("click", () => {
        state.token = "";
        localStorage.removeItem(tokenKey);
        updateAuthStatus();
      });
      $("healthButton").addEventListener("click", health);
      $("catalogButton").addEventListener("click", catalogSearch);
      $("barcodeButton").addEventListener("click", barcodeLookup);
      $("providersButton").addEventListener("click", loadProviders);
      $("providerButton").addEventListener("click", providerSearch);
      $("proposalsButton").addEventListener("click", loadProposals);
      $("proposalStatus").addEventListener("change", () => {
        updateProposalQuickFilters($("proposalStatus").value);
        loadProposals();
      });
      $("proposalProvider").addEventListener("change", loadProposals);
      $("proposalSearch").addEventListener("input", () => renderProposals(state.proposals));
      document.querySelectorAll("#proposalQuickFilters button").forEach((button) => {
        button.addEventListener("click", () => {
          $("proposalStatus").value = button.dataset.status;
          updateProposalQuickFilters(button.dataset.status);
          loadProposals();
        });
      });
      updateAuthStatus();
      if (state.token) {
        loadProviders();
        loadProposalSummary();
        loadProposals();
      }
    </script>
  </body>
</html>
"""
