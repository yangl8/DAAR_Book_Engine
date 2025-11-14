document.addEventListener("DOMContentLoaded", () => {
  const apiBase = document.body.dataset.apiBase || "/api";
  const form = document.querySelector("[data-search-form]");
  const queryInput = form?.querySelector("input[name='q']");
  const modeRadios = form?.querySelectorAll("input[name='mode']");
  const orderWrapper = form?.querySelector("[data-order-wrapper]");
  const orderSelect = form?.querySelector("[data-order-select]");
  const modeTip = form?.querySelector("[data-mode-tip]");
  const resultsContainer = document.querySelector("[data-results]");
  const emptyState = document.querySelector("[data-empty]");
  const summary = document.querySelector("[data-results-summary]");
  const errorAlert = document.querySelector("[data-error]");
  const loadingIndicator = document.querySelector("[data-loading]");
  const skeleton = document.querySelector("[data-skeleton]");
  const statsContainer = document.querySelector("[data-stats]");
  const statDocs = document.querySelector("[data-stat-documents]");
  const statAvgLen = document.querySelector("[data-stat-avglen]");
  const statTerms = document.querySelector("[data-stat-terms]");
  const statLastBuild = document.querySelector("[data-stat-lastbuild]");
  const suggestionsList = document.querySelector("[data-suggestions]");
  const exportBtn = document.querySelector("[data-export-btn]");
  const resultTemplate = document.getElementById("result-item-template");
  const recommendationTemplate = document.getElementById(
    "recommendation-item-template",
  );

  if (!form || !queryInput) return;

  const state = {
    lastQuery: queryInput.value.trim(),
    lastMode: getSelectedMode(),
    lastOrder: orderSelect?.value || "default",
    lastResponse: null,
  };

  initFromUrl();
  setupModeInteractions();
  loadGlobalStats();

  if (state.lastQuery) {
    performSearch();
  }

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    performSearch();
  });

  exportBtn?.addEventListener("click", () => {
    if (!state.lastResponse) return;
    const blob = new Blob([JSON.stringify(state.lastResponse, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `search_${Date.now()}.json`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  });

  async function performSearch() {
    const query = queryInput.value.trim();
    const mode = getSelectedMode();
    const order = orderSelect?.value || "default";

    if (!query) {
      renderEmptyState("Please enter a keyword to start searching.");
      state.lastQuery = "";
      summary.textContent = "Type a query to get started.";
      suggestionsList.innerHTML =
        '<li class="text-muted">Enter a query to see recommended titles.</li>';
      exportBtn?.classList.add("d-none");
      return;
    }

    setLoading(true);
    hideError();

    const params = {
      q: query,
      mode,
      order,
      page: 1,
      page_size: 20,
      include_snippet: true,
    };

    updateUrl(params);

    try {
      const data = await request(`${apiBase}/search`, params);
      state.lastQuery = query;
      state.lastMode = mode;
      state.lastOrder = order;
      state.lastResponse = data;
      renderResults(data);
      exportBtn?.classList.remove("d-none");
      loadRecommendations(query);
      summary.textContent = `Found ${data.total ?? 0} results in ${formatDuration(
        data.elapsed_ms,
      )}.`;
    } catch (error) {
      showError(error);
      renderEmptyState("Search failed. Please try again later.");
    } finally {
      setLoading(false);
    }
  }

  function setupModeInteractions() {
    modeRadios?.forEach((radio) => {
      radio.addEventListener("change", () => {
        const mode = getSelectedMode();
        updateModeUI(mode);
      });
    });
    updateModeUI(getSelectedMode());
  }

  function updateModeUI(mode) {
    if (!orderWrapper) return;
    if (mode === "regex") {
      orderWrapper.classList.add("d-none");
      orderSelect.value = "default";
      setModeTip("Regex mode: accepts Django regex syntax, may impact performance.");
    } else if (mode === "graph") {
      orderWrapper.classList.remove("d-none");
      setModeTip("Graph ranking: choose PageRank, Closeness, or Betweenness ordering.");
    } else {
      orderWrapper.classList.remove("d-none");
      setModeTip("Keyword mode: default relevance ranking, switch metrics if needed.");
    }
  }

  function setModeTip(text) {
    if (!modeTip) return;
    modeTip.textContent = text;
  }

  function getSelectedMode() {
    const checked = [...(modeRadios || [])].find((r) => r.checked);
    return checked ? checked.value : "simple";
  }

  async function loadGlobalStats() {
    try {
      const data = await request(`${apiBase}/index/stats`);
      statDocs.textContent = formatNumber(data.documents);
      statAvgLen.textContent = data.avg_doc_length
        ? `${formatNumber(Math.round(data.avg_doc_length))} tokens`
        : "—";
      statTerms.textContent = formatNumber(data.terms);
      statLastBuild.textContent = data.last_full_build
        ? formatDate(data.last_full_build)
        : "—";
    } catch (error) {
      if (statDocs) statDocs.textContent = "—";
    }
  }

  async function loadRecommendations(query) {
    if (!query) return;
    try {
      const data = await request(`${apiBase}/recommendations/query`, {
        q: query,
        limit: 6,
      });
      renderRecommendations(data.items || []);
    } catch (error) {
      renderRecommendations([]);
    }
  }

  function renderResults(data) {
    if (!resultTemplate || !resultsContainer) return;
    resultsContainer.innerHTML = "";
    const results = data.results || [];

    if (!results.length) {
      renderEmptyState("No results matched your query. Try another keyword or mode.");
      return;
    }

    emptyState?.classList.add("d-none");
    const fragment = document.createDocumentFragment();

    results.forEach((item, index) => {
      const clone = resultTemplate.content.cloneNode(true);
      const rankEl = clone.querySelector("[data-rank]");
      const titleEl = clone.querySelector("[data-title]");
      const authorsEl = clone.querySelector("[data-authors]");
      const langEl = clone.querySelector("[data-language]");
      const lenEl = clone.querySelector("[data-length]");
      const snippetEl = clone.querySelector("[data-snippet]");
      const tagsEl = clone.querySelector("[data-tags]");

      if (rankEl) rankEl.textContent = `#${index + 1}`;
      if (titleEl) titleEl.textContent = item.title || "未命名书籍";
      if (authorsEl)
        authorsEl.textContent = item.authors?.join(", ") || "作者未知";
      if (langEl) langEl.textContent = item.language || "语言未知";
      if (lenEl)
        lenEl.textContent = item.doc_len_tokens
          ? `${formatNumber(item.doc_len_tokens)} tokens`
          : "长度未知";

      if (snippetEl) {
        snippetEl.innerHTML = highlightTerms(
          item.snippet || "暂无摘要片段。",
          state.lastQuery,
        );
      }

      if (tagsEl) {
        tagsEl.innerHTML = "";
        const features = item.rank_features || {};
        Object.entries(features).forEach(([key, value]) => {
          if (value === undefined || value === null) return;
          const badge = document.createElement("span");
          badge.className = "badge";
          badge.textContent = `${key}: ${formatFloat(value)}`;
          tagsEl.appendChild(badge);
        });
        if (item.match_terms) {
          const matchBadge = document.createElement("span");
          matchBadge.className = "badge";
          matchBadge.textContent = `Match: ${item.match_terms.join(", ")}`;
          tagsEl.appendChild(matchBadge);
        }
      }

      fragment.appendChild(clone);
    });

    resultsContainer.appendChild(fragment);
  }

  function renderEmptyState(message) {
    if (!emptyState) return;
    resultsContainer.innerHTML = "";
    emptyState.textContent = message;
    emptyState.classList.remove("d-none");
  }

  function renderRecommendations(items) {
    if (!suggestionsList || !recommendationTemplate) return;
    suggestionsList.innerHTML = "";
    if (!items.length) {
      suggestionsList.innerHTML =
        '<li class="text-muted">No suggestions yet. Try another query.</li>';
      return;
    }
    const fragment = document.createDocumentFragment();
    items.forEach((item) => {
      const clone = recommendationTemplate.content.cloneNode(true);
      const titleEl = clone.querySelector("[data-rec-title]");
      const reasonEl = clone.querySelector("[data-rec-reason]");
      if (titleEl) titleEl.textContent = item.title || `书目 #${item.book_id}`;
      if (reasonEl) reasonEl.textContent = item.reason || "匹配度较高";
      fragment.appendChild(clone);
    });
    suggestionsList.appendChild(fragment);
  }

  function setLoading(active) {
    if (active) {
      loadingIndicator?.classList.remove("d-none");
      skeleton?.classList.remove("d-none");
    } else {
      loadingIndicator?.classList.add("d-none");
      skeleton?.classList.add("d-none");
    }
  }

  function showError(error) {
    if (!errorAlert) return;
    errorAlert.classList.remove("d-none");
    errorAlert.textContent =
      error?.message || "Request failed. Check your network or try again.";
  }

  function hideError() {
    errorAlert?.classList.add("d-none");
  }

  async function request(path, params = {}) {
    const url = new URL(path, window.location.origin);
    Object.entries(params).forEach(([key, value]) => {
      if (value === undefined || value === null || value === "") return;
      url.searchParams.append(key, value);
    });

    const response = await fetch(url.toString(), {
      headers: {
        Accept: "application/json",
      },
    });

    if (!response.ok) {
      const text = await response.text();
      throw new Error(extractErrorMessage(text) || response.statusText);
    }

    return response.json();
  }

  function extractErrorMessage(text) {
    try {
      const data = JSON.parse(text);
      if (data?.error?.message) return data.error.message;
    } catch (_err) {
      /* ignore */
    }
    return null;
  }

  function formatNumber(value) {
    if (value === undefined || value === null || Number.isNaN(value)) return "—";
    return new Intl.NumberFormat("zh-CN").format(value);
  }

  function formatFloat(value) {
    if (value === undefined || value === null || Number.isNaN(value)) return "—";
    if (Math.abs(value) >= 100) return value.toFixed(0);
    if (Math.abs(value) >= 1) return value.toFixed(2);
    return value.toPrecision(2);
  }

  function formatDuration(ms) {
    if (!ms && ms !== 0) return "unknown time";
    if (ms < 1000) return `${Math.round(ms)} ms`;
    return `${(ms / 1000).toFixed(2)} s`;
  }

  function formatDate(value) {
    try {
      const date = new Date(value);
      if (Number.isNaN(date.getTime())) return "—";
      return date.toLocaleString("zh-CN", {
        hour12: false,
      });
    } catch (error) {
      return "—";
    }
  }

  function highlightTerms(text, query) {
    if (!query) return text;
    try {
      const safeQuery = query.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
      const regex = new RegExp(`(${safeQuery})`, "gi");
      return text.replace(regex, '<mark class="highlight">$1</mark>');
    } catch (error) {
      return text;
    }
  }

  function updateUrl(params) {
    const url = new URL(window.location.href);
    url.searchParams.set("q", params.q);
    url.searchParams.set("mode", params.mode);
    url.searchParams.set("order", params.order);
    history.replaceState(null, "", `${url.pathname}?${url.searchParams}`);
  }

  function initFromUrl() {
    const url = new URL(window.location.href);
    const q = url.searchParams.get("q");
    const mode = url.searchParams.get("mode");
    const order = url.searchParams.get("order");

    if (q) queryInput.value = q;
    if (mode) {
      const radio = form.querySelector(`input[name="mode"][value="${mode}"]`);
      if (radio) radio.checked = true;
    }
    if (order && orderSelect) {
      orderSelect.value = order;
    }
  }
});

