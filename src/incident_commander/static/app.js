const state = {
  workflow: null,
  scenarios: [],
  summary: null,
};

const $ = (selector) => document.querySelector(selector);

const elements = {
  form: $("#incident-form"),
  scenario: $("#scenario"),
  runButton: $("#run-button"),
  workflow: $("#workflow"),
  approvalPanel: $("#approval-panel"),
  approveButton: $("#approve-button"),
  approver: $("#approver"),
  toast: $("#toast"),
};

function escapeHtml(value = "") {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

async function request(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.detail || `Request failed with ${response.status}`);
  }
  return payload;
}

function toast(message) {
  elements.toast.textContent = message;
  elements.toast.classList.add("visible");
  window.setTimeout(() => elements.toast.classList.remove("visible"), 2800);
}

function setBusy(isBusy) {
  elements.runButton.disabled = isBusy;
  elements.runButton.querySelector("span").textContent = isBusy
    ? "Collecting evidence…"
    : "Run investigation";
}

function formatTime(value) {
  return new Intl.DateTimeFormat("en", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(new Date(value));
}

function renderWorkflow(summary = null) {
  if (!state.workflow) return;
  const nodeStates = summary?.workflow_nodes || {};
  elements.workflow.innerHTML = state.workflow.nodes
    .map((node, index) => {
      const execution = nodeStates[node.id] || { status: "pending", duration_ms: 0 };
      const duration = execution.duration_ms ? `${execution.duration_ms} ms` : node.kind;
      return `
        <article class="workflow-node ${escapeHtml(execution.status)}">
          <div class="node-top">
            <span class="node-index">${String(index + 1).padStart(2, "0")}</span>
            <i class="node-state" title="${escapeHtml(execution.status)}"></i>
          </div>
          <strong>${escapeHtml(node.name)}</strong>
          <small>${escapeHtml(duration)}</small>
        </article>`;
    })
    .join("");
}

function renderStatus(summary) {
  $("#incident-id").textContent = summary.incident_id;
  $("#severity").textContent = summary.severity;
  $("#affected-service").textContent = summary.affected_service;
  const confidence = summary.root_cause
    ? `${Math.round(summary.root_cause.confidence * 100)}%`
    : "—";
  $("#confidence").textContent = confidence;
  const status = $("#run-status");
  status.textContent = summary.status.replaceAll("_", " ");
  status.className = `pill ${summary.status}`;
}

function renderRootCause(summary) {
  const root = summary.root_cause;
  if (!root) return;
  $("#root-confidence").textContent = `${Math.round(root.confidence * 100)}%`;
  $("#root-summary").textContent = root.summary;
  $("#causal-chain").innerHTML = root.causal_chain
    .map((item) => `<li>${escapeHtml(item)}</li>`)
    .join("");

  const remediation = summary.remediation;
  const card = $("#remediation");
  if (remediation) {
    card.classList.remove("hidden");
    card.innerHTML = `
      <span>Recommended remediation · ${escapeHtml(remediation.risk)}</span>
      <strong>${escapeHtml(remediation.title)}</strong>
      <p>${escapeHtml(remediation.description)}</p>
      <code>${escapeHtml(remediation.command_preview)}</code>`;
  }
}

function renderTimeline(summary) {
  $("#timeline-count").textContent = `${summary.timeline.length} events`;
  const container = $("#timeline");
  container.classList.remove("empty-state");
  container.innerHTML = summary.timeline
    .map(
      (event) => `
        <article class="timeline-item ${escapeHtml(event.severity)}">
          <time class="timeline-time">${formatTime(event.occurred_at)}</time>
          <i class="timeline-marker"></i>
          <div class="timeline-copy">
            <strong>${escapeHtml(event.title)}</strong>
            <p>${escapeHtml(event.detail)}</p>
            <small>${escapeHtml(event.service)} · ${event.evidence_ids.length} evidence links</small>
          </div>
        </article>`,
    )
    .join("");
}

function renderEvidence(summary) {
  $("#evidence-count").textContent = `${summary.evidence.length} signals`;
  const container = $("#evidence-list");
  container.classList.remove("empty-state");
  container.innerHTML = [...summary.evidence]
    .sort((a, b) => b.anomaly_score - a.anomaly_score)
    .map(
      (item) => `
        <article class="evidence-item">
          <i></i>
          <div>
            <strong>${escapeHtml(item.summary)}</strong>
            <small>${escapeHtml(item.source)} · ${escapeHtml(item.service)} · ${escapeHtml(item.value)}</small>
          </div>
          <span class="evidence-score">${Math.round(item.anomaly_score * 100)}</span>
        </article>`,
    )
    .join("");
}

function renderGraph(summary) {
  const graph = summary.evidence_graph;
  if (!graph?.nodes?.length) return;
  const container = $("#evidence-graph");
  container.classList.remove("empty-state");
  const nodeMap = new Map(graph.nodes.map((node) => [node.id, node]));
  const ordered = [graph.nodes[0]];
  let cursor = graph.nodes[0].id;
  while (ordered.length < graph.nodes.length) {
    const edge = graph.edges.find((item) => item.from === cursor);
    if (!edge || !nodeMap.has(edge.to)) break;
    ordered.push(nodeMap.get(edge.to));
    cursor = edge.to;
  }
  container.innerHTML = ordered
    .map((node, index) => {
      const edge = index < ordered.length - 1
        ? graph.edges.find((item) => item.from === node.id && item.to === ordered[index + 1].id)
        : null;
      return `
        <div class="graph-node ${escapeHtml(node.status)}">
          <strong>${escapeHtml(node.label)}</strong>
          <small>${escapeHtml(node.type)}</small>
        </div>
        ${edge ? `<div class="graph-edge">${escapeHtml(edge.label)}</div>` : ""}`;
    })
    .join("");
}

function renderCost(summary) {
  const cost = summary.cost_comparison;
  if (!cost?.agent_loop) return;
  $("#cost-basis").textContent = cost.basis;
  $("#agent-tokens").textContent = `${cost.agent_loop.estimated_tokens.toLocaleString()} tokens`;
  $("#compiled-tokens").textContent = `${cost.compiled_run.estimated_tokens} tokens`;
  $("#agent-detail").textContent =
    `${cost.agent_loop.llm_calls} LLM calls · ~${cost.agent_loop.estimated_latency_seconds}s`;
  $("#compiled-detail").textContent =
    `${cost.compiled_run.llm_calls} LLM calls · ~${cost.compiled_run.estimated_latency_seconds}s`;
  window.requestAnimationFrame(() => {
    $("#agent-bar").style.width = "100%";
    $("#compiled-bar").style.width = "2%";
  });
}

function renderApproval(summary) {
  if (summary.status === "awaiting_approval" && summary.approval) {
    $("#approval-description").textContent = summary.approval.description;
    elements.approvalPanel.hidden = false;
  } else {
    elements.approvalPanel.hidden = true;
  }
}

function renderSummary(summary) {
  state.summary = summary;
  renderStatus(summary);
  renderWorkflow(summary);
  renderRootCause(summary);
  renderTimeline(summary);
  renderEvidence(summary);
  renderGraph(summary);
  renderCost(summary);
  renderApproval(summary);
}

async function startInvestigation(event) {
  event.preventDefault();
  setBusy(true);
  elements.approvalPanel.hidden = true;
  try {
    const summary = await request("/api/incidents/demo", {
      method: "POST",
      body: JSON.stringify({ scenario_id: elements.scenario.value }),
    });
    renderSummary(summary);
    toast(`Investigation ${summary.incident_id} reached the approval gate.`);
    $(".status-strip").scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) {
    toast(error.message);
  } finally {
    setBusy(false);
  }
}

async function approveRemediation() {
  if (!state.summary) return;
  elements.approveButton.disabled = true;
  elements.approveButton.textContent = "Executing rollback…";
  try {
    const summary = await request(`/api/incidents/${state.summary.run_id}/approve`, {
      method: "POST",
      body: JSON.stringify({ approved_by: elements.approver.value.trim() }),
    });
    renderSummary(summary);
    toast("Rollback executed and recorded in the audit trail.");
  } catch (error) {
    toast(error.message);
  } finally {
    elements.approveButton.disabled = false;
    elements.approveButton.textContent = "Approve & execute rollback";
  }
}

async function initialize() {
  try {
    [state.scenarios, state.workflow] = await Promise.all([
      request("/api/scenarios"),
      request("/api/workflow"),
    ]);
    elements.scenario.innerHTML = state.scenarios
      .map(
        (scenario) =>
          `<option value="${escapeHtml(scenario.id)}">${escapeHtml(scenario.fault_type)} — ${escapeHtml(scenario.affected_service)}</option>`,
      )
      .join("");
    renderWorkflow();
  } catch (error) {
    toast(`Unable to initialize: ${error.message}`);
  }
}

elements.form.addEventListener("submit", startInvestigation);
elements.approveButton.addEventListener("click", approveRemediation);
initialize();

