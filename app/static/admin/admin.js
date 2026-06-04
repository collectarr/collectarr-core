
      const tokenKey = "collectarr.admin.token";
      const state = {
        token: sessionStorage.getItem(tokenKey) || "",
        providers: [],
        proposals: [],
        activeProposalId: "",
        activeProposalTitle: "",
      };

      const $ = (id) => document.getElementById(id);
      const responseBox = $("response");
      const statusBox = $("status");
      const authStatus = $("authStatus");

      function setActiveTab(name) {
        document.querySelectorAll(".tab-button").forEach((button) => {
          button.classList.toggle("active", button.dataset.tab === name);
        });
        document.querySelectorAll(".tab-panel").forEach((panel) => {
          panel.classList.toggle("active", panel.dataset.tabPanel === name);
        });
      }

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

      function renderFacetList(id, items, label) {
        const target = $(id);
        target.innerHTML = "";
        if (!items?.length) {
          target.innerHTML = `<p class="muted">No ${label}.</p>`;
          return;
        }
        for (const item of items) {
          const row = document.createElement("div");
          row.className = "row";
          row.innerHTML = `<span class="badge">${escapeHtml(item.kind || item.key || item.period || item.title)}</span><span class="muted">${escapeHtml(item.count)}</span>`;
          target.appendChild(row);
        }
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

      async function runWithButton(buttonId, fn) {
        const button = $(buttonId);
        setBusy(button, true);
        try {
          return await fn();
        } finally {
          setBusy(button, false);
        }
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

      function safeStatusClass(status) {
        const allowed = new Set(["pending", "approved", "rejected", "live", "stub", "ok", "error"]);
        return allowed.has(status) ? status : "pending";
      }

      function safeImageUrl(rawUrl) {
        if (!rawUrl) {
          return "";
        }
        try {
          const parsed = new URL(rawUrl, window.location.origin);
          if (["http:", "https:"].includes(parsed.protocol)) {
            return parsed.toString();
          }
        } catch {
          return "";
        }
        return "";
      }

      function renderImageMarkup(rawUrl, placeholder = "<div></div>") {
        const imageUrl = safeImageUrl(rawUrl);
        if (!imageUrl) {
          return placeholder;
        }
        return `<img src="${escapeHtml(imageUrl)}" alt="">`;
      }

      function headers(withAuth = false) {
        const value = { "Content-Type": "application/json" };
        if (withAuth && state.token) {
          value.Authorization = `Bearer ${state.token}`;
        }
        return value;
      }

      async function request(path, options = {}) {
        let response;
        try {
          response = await fetch(path, options);
        } catch {
          throw new Error("Network request failed.");
        }
        let text = "";
        try {
          text = await response.text();
        } catch {
          text = "";
        }
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

      function providerStatusItems(data) {
        return Array.isArray(data) ? data : (data?.providers || []);
      }

      function renderProviderCacheStats(cacheStats) {
        const target = $("providerCacheStats");
        if (!cacheStats) {
          target.innerHTML = '<p class="muted">No cache stats yet.</p>';
          return;
        }
        const blocks = [
          ["Search cache", cacheStats.search],
          ["Preview cache", cacheStats.preview],
        ].map(([label, stats]) => {
          const safe = stats || {};
          return `
            <div class="result">
              <h3>${escapeHtml(label)}</h3>
              <div class="row">
                <span class="badge">hits ${escapeHtml(String(safe.hits ?? 0))}</span>
                <span class="badge">misses ${escapeHtml(String(safe.misses ?? 0))}</span>
                <span class="badge">writes ${escapeHtml(String(safe.writes ?? 0))}</span>
                <span class="badge">entries ${escapeHtml(String(safe.entries ?? 0))}</span>
                ${label === "Search cache" ? `<span class="badge">backoffs ${escapeHtml(String(safe.backoffs ?? 0))}</span>` : ""}
              </div>
              <p class="muted">local entries ${escapeHtml(String(safe.local_entries ?? 0))} | redis entries ${escapeHtml(String(safe.redis_entries ?? 0))}</p>
              ${label === "Search cache" ? `<p class="muted">local backoffs ${escapeHtml(String(safe.local_backoffs ?? 0))} | redis backoffs ${escapeHtml(String(safe.redis_backoffs ?? 0))}</p>` : ""}
            </div>
          `;
        });
        target.innerHTML = blocks.join("");
      }

      async function refreshProviderCacheStats() {
        const data = await request("/admin/providers", {
          headers: headers(true),
        });
        renderProviderCacheStats(data.cache_stats);
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
          const coverUrl = item.cover_image_url || "";
          card.innerHTML = `
            <div class="split">
              ${renderImageMarkup(coverUrl)}
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
          const canIngest = selectedProviderSupportsIngest();
          const actionLabel = canIngest
            ? (state.activeProposalId ? "Approve proposal" : "Ingest")
            : "Search only";
          card.innerHTML = `
            <h3>${title}</h3>
            <p class="muted">${safeProviderId}</p>
            <button type="button" class="primary" ${canIngest ? "" : "disabled"}>${actionLabel}</button>
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
          const flags = [
            item.license_name,
            item.requires_attribution ? "attribution" : null,
            item.non_commercial_only ? "non-commercial" : null,
            item.requires_user_key ? "user key" : null,
          ].filter(Boolean);
          card.innerHTML = `
          <h3>${escapeHtml(item.display_name || item.name)} (${escapeHtml(item.kind)})</h3>
            <span class="badge ${safeStatusClass(String(item.status || "pending"))}">${escapeHtml(item.status)}</span>
            ${flags.map((flag) => `<span class="badge">${escapeHtml(flag)}</span>`).join("")}
            <p class="muted">${escapeHtml(item.message)}</p>
            ${item.cache_policy ? `<p class="muted">${escapeHtml(item.cache_policy)}</p>` : ""}
          `;
          target.appendChild(card);
        }
      }

      function renderProviderOptions(items) {
        state.providers = items;
        const providerSelect = $("provider");
        const selectedProvider = providerSelect.value;
        const searchable = items.filter((item) => item.supports_search);
        providerSelect.innerHTML = searchable.length
          ? searchable.map((item) => (
              `<option value="${escapeHtml(item.name)}">${escapeHtml(item.display_name || item.name)}</option>`
            )).join("")
          : '<option value="">No searchable providers</option>';
        providerSelect.value = searchable.some((item) => item.name === selectedProvider)
          ? selectedProvider
          : searchable[0]?.name || "";

        const proposalProviderSelect = $("proposalProvider");
        const selectedProposalProvider = proposalProviderSelect.value;
        proposalProviderSelect.innerHTML = '<option value="">All providers</option>'
          + items.map((item) => (
              `<option value="${escapeHtml(item.name)}">${escapeHtml(item.display_name || item.name)}</option>`
            )).join("");
        if (items.some((item) => item.name === selectedProposalProvider)) {
          proposalProviderSelect.value = selectedProposalProvider;
        }
      }

      function selectedProviderStatus() {
        const provider = $("provider").value;
        return state.providers.find((item) => item.name === provider);
      }

      function selectedProviderSupportsIngest() {
        return selectedProviderStatus()?.supports_ingest === true;
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
          const status = String(item.status || "pending");
          const summary = escapeHtml(item.summary || "");
          const imageUrl = item.image_url || "";
          const actions = item.status === "pending"
            ? `${providerId ? '<button type="button" class="primary" data-action="approve">Approve</button>' : '<button type="button" class="primary" data-action="search-provider">Search provider</button>'}
              <button type="button" data-action="reject">Reject</button>`
            : '<span class="muted">Reviewed</span>';
          card.innerHTML = `
            <div class="proposal-body">
              ${renderImageMarkup(imageUrl)}
              <div class="stack">
                <div class="row">
                  <h3>${title}</h3>
                  <span class="badge ${safeStatusClass(status)}">${escapeHtml(status)}</span>
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
        await runWithButton("loginButton", async () => {
          try {
            const data = await request("/auth/login", {
              method: "POST",
              headers: headers(),
              body: JSON.stringify({ email: $("email").value, password: $("password").value }),
            });
            state.token = data.access_token;
            sessionStorage.setItem(tokenKey, state.token);
            updateAuthStatus();
            setStatus("Logged in.", "ok");
            setResponse(data);
            logEvent("Admin login succeeded.");
          } catch (error) {
            setStatus(error.message, "error");
          }
        });
      }

      async function health() {
        await runWithButton("healthButton", async () => {
          try {
            const data = await request("/health");
            setStatus("Health check complete.", "ok");
            setResponse(data);
            logEvent("Health check completed.");
          } catch (error) {
            setStatus(error.message, "error");
          }
        });
      }

      async function catalogSearch() {
        await runWithButton("catalogButton", async () => {
          try {
            const query = encodeURIComponent($("catalogQuery").value);
            const data = await request(`/search?q=${query}`);
            renderCatalogResults($("catalogResults"), data);
            setStatus(`Found ${data.length} catalog items.`, "ok");
            setResponse(data);
          } catch (error) {
            setStatus(error.message, "error");
          }
        });
      }

      async function barcodeLookup() {
        await runWithButton("barcodeButton", async () => {
          try {
            const barcode = encodeURIComponent($("barcode").value);
            const data = await request(`/barcode/${barcode}`);
            renderCatalogResults($("catalogResults"), [data]);
            setStatus("Barcode match found.", "ok");
            setResponse(data);
          } catch (error) {
            setStatus(error.message, "error");
          }
        });
      }

      async function providerSearch() {
        await runWithButton("providerButton", async () => {
          try {
            const provider = $("provider").value;
            if (!provider) {
              throw new Error("Select a provider first.");
            }
            const data = await request("/admin/providers/search", {
              method: "POST",
              headers: headers(true),
              body: JSON.stringify({
                provider,
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
            await refreshProviderCacheStats();
            setResponse(data);
            logEvent(`Provider search returned ${data.length} items.`);
          } catch (error) {
            setStatus(error.message, "error");
          }
        });
      }

      async function loadProviders() {
        await runWithButton("providersButton", async () => {
          try {
            const data = await refreshProviderCacheStats();
            const providers = providerStatusItems(data);
            renderProviderStatuses(providers);
            renderProviderOptions(providers);
            setMetric("providerMetric", providers.filter((item) => item.is_configured).length);
            setStatus("Provider status loaded.", "ok");
            setResponse(data);
            logEvent("Provider status refreshed.");
          } catch (error) {
            setStatus(error.message, "error");
          }
        });
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
          const provider = $("provider").value;
          if (!provider) {
            throw new Error("Select a provider first.");
          }
          if (!selectedProviderSupportsIngest()) {
            throw new Error("Selected provider does not support catalog ingest yet.");
          }
          const data = await request("/admin/providers/ingest", {
            method: "POST",
            headers: headers(true),
            body: JSON.stringify({
              provider,
              provider_item_id: providerItemId,
            }),
          });
          setStatus(data.created ? "Metadata item ingested." : "Metadata item already exists.", "ok");
          setMetric("ingestMetric", data.created ? "new" : "exists");
          await refreshProviderCacheStats();
          setResponse(data);
          logEvent(data.created ? "Metadata item ingested." : "Ingest skipped, item already exists.");
        } catch (error) {
          setStatus(error.message, "error");
        }
      }

      async function loadProposals() {
        await runWithButton("proposalsButton", async () => {
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
          }
        });
      }

      function searchProviderForProposal(item) {
        state.activeProposalId = item.id;
        state.activeProposalTitle = item.title || item.query || item.id;
        setActiveTab("search");
        const provider = item.provider || $("provider").value;
        if (provider) {
          $("provider").value = provider;
        }
        $("providerQuery").value = item.query || item.title || "";
        setStatus("Provider search prepared from proposal.", "ok");
        logEvent("Prepared provider search from metadata proposal.");
        providerSearch();
      }

      async function approveProposalWithProviderItem(id, providerItemId) {
        try {
          const provider = $("provider").value;
          if (!provider) {
            throw new Error("Select a provider first.");
          }
          if (!selectedProviderSupportsIngest()) {
            throw new Error("Selected provider does not support catalog ingest yet.");
          }
          const data = await request(`/admin/metadata/proposals/${id}/approve-provider`, {
            method: "POST",
            headers: headers(true),
            body: JSON.stringify({
              provider,
              provider_item_id: providerItemId,
            }),
          });
          state.activeProposalId = "";
          state.activeProposalTitle = "";
          setStatus("Proposal approved with selected provider item.", "ok");
          setMetric("ingestMetric", data.created ? "new" : "exists");
          await refreshProviderCacheStats();
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
          await refreshProviderCacheStats();
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
        sessionStorage.removeItem(tokenKey);
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
      document.querySelectorAll(".tab-button").forEach((button) => {
        button.addEventListener("click", () => setActiveTab(button.dataset.tab));
      });
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
    
