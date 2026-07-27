# Five-minute demo script

## 0:00–0:35 — Problem and design choice

“Most incident agents ask an LLM to decide every next tool call. Incident Commander uses AI only
to design a workflow once. The backend compiles that plan into a validated JSON DAG, so every
future incident runs deterministically.”

Show the workflow row and mention the seven primitives.

## 0:35–1:35 — Run the bad-deployment scenario

Select **Bad deployment — checkout-api** and click **Run investigation**.

Point out:

- eight sources run in parallel;
- the workflow reaches `awaiting approval`;
- rollback has not executed.

## 1:35–2:35 — Explain the evidence

Read the root-cause summary. Follow the causal chain:

1. release 2.14.0 reduced the database pool;
2. the pool saturated;
3. connection acquisition timed out;
4. payment retries amplified work;
5. checkout p95 increased 18×.

Show that the timeline and evidence ledger carry source names, timestamps, values, and anomaly
scores. Show the graph from release to SLO breach.

## 2:35–3:20 — Safety and approval

Show the recommended command preview and explain that it is data, not arbitrary shell input.
Mention that the compiler rejects a destructive node without an approval ancestor.

Enter the approver name and click **Approve & execute rollback**. The same persisted run resumes,
records the approver, and completes.

## 3:20–4:10 — Backend architecture

Open `workflows/incident-investigation.v1.json`, then:

- `engine/compiler.py`;
- `engine/executor.py`;
- `tools/registry.py`;
- `repository.py`.

Explain that new Prometheus, Loki, GitHub, Jira, or Kubernetes clients replace adapters without
changing the workflow.

## 4:10–4:40 — Durable and chat interfaces

Show:

- the MCP server exposing tool discovery and workflow execution;
- the Slack Socket Mode command and approval button;
- the Temporal worker waiting on an approval signal.

Be explicit that the local interview demo uses fixture adapters; these integration entry points are
provided but not presented as a production deployment.

## 4:40–5:00 — Verification

Show the CI workflow and test suite. Close on:

“This project demonstrates Python backend design, async execution, APIs, persistence, workflow
validation, human-in-the-loop safety, and an AI product architecture where the model is not inside
every runtime step.”

