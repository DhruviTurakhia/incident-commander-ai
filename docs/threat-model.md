# Threat model

## Assets

- production credentials and Kubernetes permissions;
- incident evidence that may contain customer or infrastructure data;
- workflow definitions and approval records;
- Slack interactive payloads;
- tenant identity and service ownership metadata.

## Trust boundaries

1. External triggers entering the API or Slack adapter.
2. Planner output entering the compiler.
3. Compiled nodes crossing into tool adapters.
4. Read-only workers crossing into observability systems.
5. Approval events granting access to a protected action.
6. Evidence crossing tenant boundaries or entering long-term storage.

## Main threats and controls

| Threat | Current control | Production control |
| --- | --- | --- |
| Prompt-generated arbitrary tool call | Compiler allowlists registered tools | Signed workflow versions and policy-as-code |
| Expression injection | Restricted path resolver; no `eval` | Independently fuzz and sandbox the DSL |
| Unauthorized rollback | Approval ancestor plus runtime capability | SSO identity, RBAC, quorum approval, short-lived token |
| Secret committed to Git | `.env` ignored | Secret scanning and external secrets manager |
| Cross-tenant evidence access | Not implemented in local demo | Tenant key on every row, scoped credentials, RLS |
| Replay of Slack action | Run status makes approval one-way | Slack signature verification and nonce expiry |
| Tool returns malicious content | Tool result is treated as data | Schema validation, redaction, size limits |
| Evidence tampering | SQLite run record | Append-only signed audit log and object versioning |
| Retry repeats side effects | Read operations are safe; rollback is gated | Idempotency keys at every write adapter |
| Cost or fan-out explosion | Static compiled workflow | Node, loop, time, and budget quotas |

## Deliberate demo limitations

- The dashboard has no login because it runs locally.
- Slack and Temporal entry points are reference integrations and are not exercised in CI.
- Fixture adapters do not represent real production authorization.
- The local SQLite payload is not encrypted.
- Approval uses a typed name; production must use verified identity.

These limits are documented so the project demonstrates engineering judgment without pretending to
be a production SRE platform.

