import { useEffect, useState } from "react";
import {
  Activity,
  AlertCircle,
  ArrowDownUp,
  ArrowUpRight,
  BookOpen,
  Check,
  ChevronDown,
  CircleHelp,
  Clock3,
  Copy,
  Database,
  FileText,
  Filter,
  Gauge,
  Layers3,
  LifeBuoy,
  LoaderCircle,
  LockKeyhole,
  MessageSquareText,
  RefreshCw,
  Search,
  Server,
  ShieldCheck,
  Sparkles,
  ThumbsDown,
  ThumbsUp,
  TriangleAlert,
  X,
} from "lucide-react";
import { api, type Analysis, type AnalysisBundle, type AppConfig, type SyncRun, type Ticket } from "./api";

type RequestListResponse = { items: Ticket[]; total: number };
type RequestDetail = { ticket: Ticket; analysis: AnalysisBundle | null; analyzed_at?: string | null };

function App() {
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [syncRuns, setSyncRuns] = useState<SyncRun[]>([]);
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [detail, setDetail] = useState<RequestDetail | null>(null);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("All requests");
  const [priorityFilter, setPriorityFilter] = useState("All priorities");
  const [busy, setBusy] = useState(false);
  const [pageLoading, setPageLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [draft, setDraft] = useState("");
  const [apiKey, setApiKey] = useState(sessionStorage.getItem("request-lens-api-key") || "");
  const [keyEntry, setKeyEntry] = useState("");
  const [feedback, setFeedback] = useState("");
  const [activeView, setActiveView] = useState<"summary" | "investigation">("summary");

  async function loadConfig() {
    const value = await api<AppConfig>("/api/config");
    setConfig(value);
  }

  async function loadSyncHistory() {
    const result = await api<{ items: SyncRun[] }>("/api/sync/history");
    setSyncRuns(result.items);
  }

  async function loadRequests() {
    setError("");
    const params = new URLSearchParams();
    if (search.trim()) params.set("q", search.trim());
    if (statusFilter !== "All requests") params.set("status", statusFilter);
    if (priorityFilter !== "All priorities") params.set("priority", priorityFilter);
    const result = await api<RequestListResponse>(`/api/requests?${params.toString()}`);
    setTickets(result.items);
    if (!selectedId || !result.items.some((item) => item.id === selectedId)) {
      setSelectedId(result.items[0]?.id || "");
    }
  }

  async function loadDetail(ticketId: string) {
    if (!ticketId) {
      setDetail(null);
      return;
    }
    const result = await api<RequestDetail>(`/api/requests/${encodeURIComponent(ticketId)}`);
    setDetail(result);
    setDraft(makeDraft(result.analysis?.analysis));
  }

  useEffect(() => {
    let mounted = true;
    Promise.all([loadConfig(), loadRequests()])
      .catch((reason: Error) => {
        if (mounted) setError(reason.message);
      })
      .finally(() => {
        if (mounted) setPageLoading(false);
      });
    return () => { mounted = false; };
  }, []);

  useEffect(() => {
    if (pageLoading || !config?.api_key_required || !apiKey) return;
    loadRequests().catch((reason: Error) => setError(reason.message));
  }, [apiKey, config?.api_key_required]);

  useEffect(() => {
    if (pageLoading || (config?.api_key_required && !apiKey)) return;
    loadSyncHistory().catch(() => setSyncRuns([]));
  }, [pageLoading, apiKey, config?.api_key_required]);

  useEffect(() => {
    if (pageLoading) return;
    loadRequests().catch((reason: Error) => setError(reason.message));
  }, [search, statusFilter, priorityFilter]);

  useEffect(() => {
    if (!selectedId) return;
    loadDetail(selectedId).catch((reason: Error) => setError(reason.message));
  }, [selectedId]);

  async function analyzeSelected() {
    if (!selectedId) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const result = await api<AnalysisBundle & { ticket: Ticket }>(
        `/api/requests/${encodeURIComponent(selectedId)}/analyze`,
        { method: "POST" },
      );
      setDetail({ ticket: result.ticket, analysis: result });
      setDraft(makeDraft(result.analysis));
      setActiveView("summary");
      setNotice("Analysis ready. Facts are taken from the request; unknowns are called out.");
      await loadRequests();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Analysis failed.");
    } finally {
      setBusy(false);
    }
  }

  async function syncRequests() {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      if (config?.jira_configured) {
        const result = await api<{ synced: number }>("/api/sync", { method: "POST" });
        setNotice(`${result.synced} Jira requests synchronized.`);
      } else {
        setNotice("Demo requests refreshed. Add Jira settings to connect a project.");
      }
      await loadRequests();
      await loadConfig();
      await loadSyncHistory();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Refresh failed.");
      loadSyncHistory().catch(() => setSyncRuns([]));
    } finally {
      setBusy(false);
    }
  }

  async function sendFeedback(rating: "useful" | "not_useful") {
    if (!selectedId) return;
    try {
      await api(`/api/requests/${encodeURIComponent(selectedId)}/feedback`, {
        method: "POST",
        body: JSON.stringify({ rating, note: "" }),
      });
      setFeedback(rating);
      setNotice("Feedback recorded.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not save feedback.");
    }
  }

  async function copyText(text: string, label: string) {
    try {
      await navigator.clipboard.writeText(text);
      setNotice(`${label} copied.`);
    } catch {
      setError("Clipboard access is unavailable in this browser.");
    }
  }

  const stats = {
    open: tickets.filter((ticket) => !/resolved|closed|done/i.test(ticket.status)).length,
    high: tickets.filter((ticket) => /high|critical|highest|urgent/i.test(ticket.priority)).length,
    analyzed: tickets.filter((ticket) => ticket.analyzed).length,
  };
  const analysis = detail?.analysis?.analysis;
  const needsAnalysis = Boolean(detail && !detail.analysis);
  const keyRequired = Boolean(config?.api_key_required && !apiKey);

  if (pageLoading) {
    return <div className="loading-screen"><LoaderCircle className="spin" size={22} /> Loading request workspace</div>;
  }

  if (keyRequired) {
    return (
      <main className="key-screen">
        <div className="key-panel">
          <div className="brand-mark"><Layers3 size={19} /></div>
          <span className="eyebrow">REQUEST LENS / PRIVATE WORKSPACE</span>
          <h1>Enter workspace key</h1>
          <p>This instance is protected. The key stays in this browser tab.</p>
          <form onSubmit={(event) => {
            event.preventDefault();
            sessionStorage.setItem("request-lens-api-key", keyEntry);
            setApiKey(keyEntry);
          }}>
            <label htmlFor="api-key">Workspace key</label>
            <input id="api-key" type="password" value={keyEntry} onChange={(event) => setKeyEntry(event.target.value)} autoComplete="current-password" />
            <button className="button button-dark" type="submit"><LockKeyhole size={16} /> Unlock workspace</button>
          </form>
          {error && <p className="inline-error">{error}</p>}
        </div>
      </main>
    );
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a className="brand" href="#top" aria-label="Request Lens home">
          <span className="brand-mark"><Layers3 size={18} /></span>
          <span><strong>request lens</strong><small>SUPPORT WORKSPACE</small></span>
        </a>

        <div className="workspace-switcher">
          <span className="workspace-dot" />
          <span><strong>{config?.mode === "jira" ? "Jira project" : "Sample workspace"}</strong><small>{config?.mode === "jira" ? "Read-only connection" : "Demo data"}</small></span>
          <ChevronDown size={15} />
        </div>

        <div className="nav-label">WORKSPACE</div>
        <nav className="main-nav" aria-label="Workspace">
          <button className="nav-item active" type="button"><Activity size={17} /><span>Requests</span><span className="nav-count">{tickets.length}</span></button>
          <button className="nav-item" type="button" onClick={() => setStatusFilter("Open")}><Clock3 size={17} /><span>Needs attention</span><span className="nav-count">{stats.open}</span></button>
          <button className="nav-item" type="button" onClick={() => setPriorityFilter("High")}><TriangleAlert size={17} /><span>High priority</span><span className="nav-count">{stats.high}</span></button>
        </nav>

        <div className="nav-label nav-label-spaced">KNOWLEDGE</div>
        <nav className="main-nav" aria-label="Knowledge">
          <a className="nav-item" href="https://support.hpe.com/connect/s/" target="_blank" rel="noreferrer"><BookOpen size={17} /><span>HPE Support Center</span><ArrowUpRight size={14} /></a>
          <button className="nav-item" type="button" onClick={() => setNotice("Knowledge links are matched to the selected request after analysis.")}><FileText size={17} /><span>Source references</span></button>
        </nav>

        <div className="sidebar-spacer" />
        <section className="connection-panel">
          <div className="connection-heading"><span className="connection-led" /><span>CONNECTION</span><span className="connection-state">{config?.jira_configured ? "LIVE" : "DEMO"}</span></div>
          <p>{config?.jira_configured
            ? `${config.last_sync_at ? `Last successful sync ${new Date(config.last_sync_at).toLocaleString()}.` : "Jira read-only sync is configured."}${config.sync_interval_minutes > 0 ? ` Automatic sync every ${config.sync_interval_minutes} minutes.` : ""}`
            : "Sample requests are loaded locally."}</p>
          <button className="text-action" type="button" onClick={syncRequests}><RefreshCw size={14} /> {config?.jira_configured ? "Sync now" : "Refresh sample data"}</button>
          {config?.jira_configured && <details className="sync-history">
            <summary><Clock3 size={13} /> Recent sync runs <span>{syncRuns.filter((run) => run.status === "failed").length || ""}</span></summary>
            <div className="sync-run-list">
              {syncRuns.length ? syncRuns.map((run) => <div className="sync-run" key={run.id}>
                <span className={`sync-run-status ${run.status}`}>{run.status}</span>
                <span>{new Date(run.started_at).toLocaleString()}</span>
                <span>{run.synced_count} requests</span>
                {run.error && <small>{run.error}</small>}
              </div>) : <p className="sync-history-empty">No sync runs recorded yet.</p>}
            </div>
          </details>}
        </section>
        <div className="sidebar-footer"><ShieldCheck size={14} /><span>Read-only analysis</span><span className="version">v1.0</span></div>
      </aside>

      <main className="main-area" id="top">
        <header className="topbar">
          <div className="breadcrumbs"><span>Workspace</span><span className="crumb-slash">/</span><strong>Requests</strong></div>
          <div className="topbar-actions">
            <span className="mode-pill"><span /> {config?.mode === "jira" ? "JIRA CONNECTED" : "DEMO MODE"}</span>
            {config?.api_key_required && <button className="icon-button" type="button" aria-label="Change workspace key" title="Change workspace key" onClick={() => { sessionStorage.removeItem("request-lens-api-key"); setApiKey(""); setKeyEntry(""); setError(""); }}><LockKeyhole size={15} /></button>}
            <button className="icon-button" type="button" aria-label="Help" title="About Request Lens" onClick={() => setNotice("Summaries use deterministic rules. No language model is configured.")}><CircleHelp size={17} /></button>
            <div className="user-avatar" title="Support analyst">SA</div>
          </div>
        </header>

        <div className="page-content">
          <section className="page-heading">
            <div>
              <span className="eyebrow">SUPPORT OPERATIONS <span className="eyebrow-dot">/</span> INBOX</span>
              <h1>Request overview</h1>
              <p>Clear request summaries. Evidence-linked support guidance.</p>
            </div>
            <button className="button button-dark sync-button" type="button" onClick={syncRequests} disabled={busy}>
              {busy ? <LoaderCircle size={16} className="spin" /> : <RefreshCw size={16} />}
              {config?.jira_configured ? "Sync Jira" : "Refresh demo"}
            </button>
          </section>

          {(error || notice) && (
            <div className={`message-banner ${error ? "message-error" : "message-success"}`} role="status">
              {error ? <AlertCircle size={16} /> : <Check size={16} />}
              <span>{error || notice}</span>
              <button className="message-close" type="button" aria-label="Dismiss message" onClick={() => { setError(""); setNotice(""); }}><X size={15} /></button>
            </div>
          )}

          <section className="metric-row" aria-label="Request metrics">
            <div className="metric"><span className="metric-icon metric-icon-coral"><MessageSquareText size={16} /></span><span className="metric-label">TOTAL REQUESTS</span><strong>{tickets.length}</strong><small>in this view</small></div>
            <div className="metric"><span className="metric-icon metric-icon-teal"><Clock3 size={16} /></span><span className="metric-label">OPEN</span><strong>{stats.open}</strong><small>awaiting resolution</small></div>
            <div className="metric"><span className="metric-icon metric-icon-yellow"><TriangleAlert size={16} /></span><span className="metric-label">HIGH PRIORITY</span><strong>{stats.high}</strong><small>check impact</small></div>
            <div className="metric"><span className="metric-icon metric-icon-blue"><Gauge size={16} /></span><span className="metric-label">ANALYZED</span><strong>{stats.analyzed}</strong><small>with grounded summary</small></div>
          </section>

          <section className="workbench" aria-label="Request queue and details">
            <div className="queue-panel">
              <div className="queue-title-row"><div><h2>Request queue</h2><span>{tickets.length} matching requests</span></div><button className="icon-button quiet" type="button" title="Queue filters" aria-label="Queue filters"><Filter size={16} /></button></div>
              <label className="search-box"><Search size={16} /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search requests" /><kbd>⌘ K</kbd></label>
              <div className="filter-row">
                <label><span className="sr-only">Filter by status</span><select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}><option>All requests</option><option>Open</option><option>In Progress</option><option>Waiting for customer</option><option>Resolved</option></select><ChevronDown size={13} /></label>
                <label><span className="sr-only">Filter by priority</span><select value={priorityFilter} onChange={(event) => setPriorityFilter(event.target.value)}><option>All priorities</option><option>Highest</option><option>High</option><option>Medium</option><option>Low</option></select><ChevronDown size={13} /></label>
                <button className="sort-button" type="button" title="Sorted by recent update"><ArrowDownUp size={14} /></button>
              </div>
              <div className="ticket-list">
                {tickets.map((ticket) => (
                  <button key={ticket.id} className={`ticket-row ${selectedId === ticket.id ? "selected" : ""}`} type="button" onClick={() => { setSelectedId(ticket.id); setFeedback(""); }}>
                    <span className={`priority-line ${priorityClass(ticket.priority)}`} />
                    <span className="ticket-row-content">
                      <span className="ticket-id-row"><span>{ticket.source_key}</span><span className={`status-dot ${statusClass(ticket.status)}`} /></span>
                      <strong>{ticket.summary}</strong>
                      <span className="ticket-meta"><span className={`priority-text ${priorityClass(ticket.priority)}`}>{ticket.priority || "Unprioritized"}</span><span className="meta-divider">·</span><span>{ticket.assignee || "Unassigned"}</span></span>
                    </span>
                    {Boolean(ticket.analyzed) && <span className="analyzed-indicator" title="Analyzed"><Check size={13} /></span>}
                  </button>
                ))}
                {tickets.length === 0 && <div className="empty-state"><Search size={20} /><strong>No matching requests</strong><span>Adjust the search or filters.</span></div>}
              </div>
              <div className="queue-footer"><span><span className="live-dot" /> UPDATED JUST NOW</span><span>{tickets.length} / {tickets.length}</span></div>
            </div>

            <section className="detail-panel">
              {!detail ? (
                <div className="empty-detail"><div className="empty-illustration"><Layers3 size={24} /></div><h2>Select a request</h2><p>Choose an item from the queue to inspect its request details.</p></div>
              ) : (
                <>
                  <div className="detail-header">
                    <div className="detail-crumb"><span>REQUEST</span><span>/</span><strong>{detail.ticket.source_key}</strong>{detail.ticket.source_url && <a href={detail.ticket.source_url} target="_blank" rel="noreferrer" aria-label="Open source request" title="Open in Jira"><ArrowUpRight size={14} /></a>}</div>
                    <div className="detail-header-actions"><span className={`status-badge ${statusClass(detail.ticket.status)}`}><span />{detail.ticket.status}</span><button className="icon-button" type="button" title="Copy request ID" aria-label="Copy request ID" onClick={() => copyText(detail.ticket.source_key, "Request ID")}><Copy size={15} /></button></div>
                  </div>
                  <div className="detail-scroll">
                    <div className="request-title-block">
                      <div className="request-title-kicker"><span className={`priority-tag ${priorityClass(detail.ticket.priority)}`}>{detail.ticket.priority || "UNPRIORITIZED"}</span><span className="title-dot">·</span><span>{detail.ticket.assignee || "Unassigned"}</span></div>
                      <h2>{detail.ticket.summary}</h2>
                      <p className="request-description">{detail.ticket.description || "No description was provided in the source request."}</p>
                      {detail.ticket.comments && <div className="comment-line"><MessageSquareText size={14} /><span>{detail.ticket.comments}</span></div>}
                    </div>

                    <div className="analysis-toolbar">
                      <div className="analysis-tabs" role="tablist" aria-label="Analysis view">
                        <button type="button" role="tab" aria-selected={activeView === "summary"} className={activeView === "summary" ? "active" : ""} onClick={() => setActiveView("summary")}><Sparkles size={15} /> Summary</button>
                        <button type="button" role="tab" aria-selected={activeView === "investigation"} className={activeView === "investigation" ? "active" : ""} onClick={() => setActiveView("investigation")}><Server size={15} /> Investigation</button>
                      </div>
                      <button className="button button-accent" type="button" onClick={analyzeSelected} disabled={busy}>
                        {busy ? <LoaderCircle size={15} className="spin" /> : <Sparkles size={15} />}
                        {analysis ? "Re-analyze" : "Analyze request"}
                      </button>
                    </div>

                    {!analysis ? (
                      <div className="analysis-empty"><div className="analysis-empty-icon"><FileText size={19} /></div><div><strong>{needsAnalysis ? "Ready for analysis" : "Choose a request to begin"}</strong><p>Extract key facts, highlight missing details, and search HPE Support for relevant guidance.</p></div></div>
                    ) : activeView === "summary" ? (
                      <SummaryView analysis={analysis} documents={detail.analysis?.documents || []} documentsError={detail.analysis?.documents_error || ""} onCopy={copyText} />
                    ) : (
                      <InvestigationView analysis={analysis} />
                    )}

                    {analysis && <>
                      <section className="draft-section">
                        <div className="section-heading"><div><span className="section-index">03</span><h3>Requester update</h3></div><button className="text-action" type="button" onClick={() => copyText(draft, "Draft response")}><Copy size={14} /> Copy draft</button></div>
                        <textarea aria-label="Editable requester response draft" value={draft} onChange={(event) => setDraft(event.target.value)} rows={4} />
                      </section>
                      <section className="feedback-row">
                        <span>Was this analysis useful?</span>
                        <button className={`feedback-button ${feedback === "useful" ? "picked" : ""}`} type="button" aria-label="Analysis was useful" onClick={() => sendFeedback("useful")}><ThumbsUp size={15} /></button>
                        <button className={`feedback-button ${feedback === "not_useful" ? "picked" : ""}`} type="button" aria-label="Analysis was not useful" onClick={() => sendFeedback("not_useful")}><ThumbsDown size={15} /></button>
                        <span className="analysis-stamp">RULE-BASED · {new Date(detail.analysis?.analyzed_at || Date.now()).toLocaleString()}</span>
                      </section>
                    </>}
                  </div>
                </>
              )}
            </section>
          </section>

          <footer className="page-footer"><span><LockKeyhole size={13} /> Source tickets are never changed by this workspace.</span><span><Database size={13} /> {config?.hpe_search_configured ? "HPE search connected" : "HPE Support links open in a new tab"}</span></footer>
        </div>
      </main>
    </div>
  );
}

function SummaryView({ analysis, documents, documentsError, onCopy }: {
  analysis: Analysis;
  documents: AnalysisBundle["documents"];
  documentsError: string;
  onCopy: (text: string, label: string) => void;
}) {
  return (
    <div className="analysis-content">
      <section className="summary-section">
        <div className="section-heading"><div><span className="section-index">01</span><h3>Quick summary</h3></div><button className="icon-button quiet" title="Copy quick summary" aria-label="Copy quick summary" type="button" onClick={() => onCopy(analysis.quick_summary, "Summary")}><Copy size={14} /></button></div>
        <div className="summary-callout"><span className="callout-marker" /><p>{analysis.quick_summary}</p></div>
        <div className="fact-grid">
          <div className="fact-cell"><span>CLASSIFICATION</span><strong>{analysis.category}</strong></div>
          <div className="fact-cell"><span>AFFECTED PRODUCT</span><strong>{analysis.affected_product}</strong></div>
          <div className="fact-cell fact-wide"><span>IMPACT</span><strong>{analysis.impact}</strong></div>
        </div>
      </section>

      <section className="source-section">
        <div className="section-heading"><div><span className="section-index">02</span><h3>Related HPE guidance</h3></div><span className="result-count">{documents.length} {documents.length === 1 ? "SOURCE" : "SOURCES"}</span></div>
        {documentsError && <p className="doc-error"><AlertCircle size={14} /> {documentsError}</p>}
        <div className="document-list">
          {documents.map((document) => (
            <a className="document-link" key={document.url} href={document.url} target="_blank" rel="noreferrer">
              <span className="document-icon"><BookOpen size={16} /></span>
              <span className="document-copy"><strong>{document.title}</strong><small>{document.snippet || document.source}</small><em>{document.source}</em></span>
              <ArrowUpRight size={15} />
            </a>
          ))}
          {documents.length === 0 && !documentsError && <div className="no-documents"><LifeBuoy size={16} /><span>No matching HPE guidance was returned. Verify the product and error details.</span></div>}
        </div>
      </section>
      <p className="analysis-method"><ShieldCheck size={13} /> {analysis.analysis_method}</p>
    </div>
  );
}

function InvestigationView({ analysis }: { analysis: Analysis }) {
  return (
    <div className="analysis-content investigation-view">
      <section className="investigation-section">
        <div className="section-heading"><div><span className="section-index">01</span><h3>Confirmed from request</h3></div></div>
        <ul className="fact-list">{analysis.confirmed_facts.map((fact) => <li key={fact}><Check size={14} />{fact}</li>)}</ul>
        {analysis.error_evidence.length > 0 && <div className="evidence-block"><span>ERROR EVIDENCE</span><div>{analysis.error_evidence.map((error) => <code key={error}>{error}</code>)}</div></div>}
        {analysis.actions_attempted.length > 0 && <div className="evidence-block"><span>ACTIONS ALREADY TRIED</span><ul>{analysis.actions_attempted.map((action) => <li key={action}>{action}</li>)}</ul></div>}
      </section>
      <section className="investigation-section missing-section">
        <div className="section-heading"><div><span className="section-index">02</span><h3>Information to collect</h3></div><span className="result-count">{analysis.missing_information.length} ITEMS</span></div>
        {analysis.missing_information.length ? <ul className="missing-list">{analysis.missing_information.map((item) => <li key={item}><span className="missing-bullet" />{item}</li>)}</ul> : <p className="all-known"><Check size={15} /> No standard details appear to be missing.</p>}
      </section>
      <section className="investigation-section">
        <div className="section-heading"><div><span className="section-index">03</span><h3>Recommended next steps</h3></div></div>
        <ol className="step-list">{analysis.recommended_next_steps.map((step) => <li key={step}><span>{step}</span></li>)}</ol>
        <div className="caution-note"><TriangleAlert size={15} /><span>These are diagnostic prompts, not a confirmed root cause or an approved change plan.</span></div>
      </section>
    </div>
  );
}

function makeDraft(analysis?: Analysis): string {
  if (!analysis) return "";
  const missing = analysis.missing_information.length
    ? "To help us investigate, please share: " + analysis.missing_information.slice(0, 3).join(", ") + "."
    : "We are reviewing the available details and will share the next update shortly.";
  return `Hello,\n\nWe reviewed your request: ${analysis.quick_summary}\n\n${missing}\n\nRegards,\nSupport team`;
}

function priorityClass(priority: string): string {
  const value = priority.toLowerCase();
  if (value.includes("high") || value.includes("critical") || value.includes("urgent") || value.includes("highest")) return "priority-high";
  if (value.includes("medium") || value.includes("major")) return "priority-medium";
  return "priority-low";
}

function statusClass(status: string): string {
  const value = status.toLowerCase();
  if (value.includes("progress")) return "status-progress";
  if (value.includes("resolved") || value.includes("closed") || value.includes("done")) return "status-resolved";
  if (value.includes("waiting")) return "status-waiting";
  return "status-open";
}

export default App;