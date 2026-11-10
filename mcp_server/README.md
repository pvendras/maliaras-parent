# Maliaras Parent MCP

Separate **FastMCP 3** service for one owner and exactly two accounts: `anna`
and `nikos`. Reuses `../client.py`'s read-only HTTPS transport and
`../lessons.py`'s subject matching, safe projection and Athens date filtering.
Credentials come from Kubernetes-injected environment variables (the same
`MALIARAS_<STUDENT>_USERNAME`/`_PASSWORD` names as the CLI's `.env`).

**No file exports:** no PDFs, export sync, report files, downloads, background
polling or report volumes. On explicit request, `get_report` can return Markdown
text directly to the agent; nothing is saved. `instructions.md` is static server
guidance, not an exported report. Only selected lesson text passes through MCP/proxy.

## Tools

All tools require `student` (`anna` or `nikos`); no account creation/defaults.

| Tool | Other inputs | Result |
| --- | --- | --- |
| `list_subjects` | none | Default-year subject names |
| `get_report` | optional `lesson_date` (`YYYY-MM-DD`), `response_format` (`json` or `markdown`, default `json`) | All subjects on one recorded day, as structured data or Markdown text |
| `get_subject_lessons` | required `subject`, optional `lesson_date` | One uniquely matched subject on one day |

Without a date, select the latest recorded day **on or before today in
Europe/Athens** (subject-specific for `get_subject_lessons`). Never merge each
subject's different latest day into one report. Include all entries on the chosen
day, source URLs, retrieval timestamp, child name and missing-entry indicators.
Explicit dates are exact filters, not fallbacks. For Markdown of a previously
fetched report, pass its recorded date to avoid silently selecting a newer day:

```json
{"student": "anna", "lesson_date": "2026-09-21", "response_format": "markdown"}
```

Markdown uses the existing escaped, HTML-to-text report renderer in memory. It
preserves recorded instructions rather than reproducing a prior agent summary.
No file writer is called and ReportLab is not required. Historical school years,
attachments, grades, announcements and timetable aggregation are not supported.

Server initialization supplies the report/presentation and untrusted-content
rules from `instructions.md`. Each call uses a fresh account-specific cookie jar
and one login. Failures are sanitized, with no automatic retry or account fallback.
No arbitrary URL, lesson ID, file path or credential tool arguments are accepted.

## Configuration

Supply these variables via a Kubernetes Secret (never paste values in chat):

| Secret key in `maliaras-parent` | Container environment |
| --- | --- |
| `anna-username` | `MALIARAS_ANNA_USERNAME` |
| `anna-password` | `MALIARAS_ANNA_PASSWORD` |
| `nikos-username` | `MALIARAS_NIKOS_USERNAME` |
| `nikos-password` | `MALIARAS_NIKOS_PASSWORD` |
| `mcp-token` | `MALIARAS_MCP_TOKEN` |

Generate a high-entropy random MCP token (at least 32 characters; recommended
32 random bytes encoded as hex) in your secret manager. It is **separate from the
ERP passwords**. Provision the same token to the proxy as its backend Bearer
credential. The server fails to start without a sufficiently long token.
The custom verifier compares SHA-256 digests in constant time. This is a private,
single-owner shared-secret scheme, not an OAuth issuer or multi-user identity
system. Do not expose this backend as a public anonymous MCP service.

Provision the Secret using your secret manager/operator, or from protected local
files outside this repository, for example:

```sh
kubectl -n YOUR_NAMESPACE create secret generic maliaras-parent \
  --from-file=anna-username=/secure/path/anna-username \
  --from-file=anna-password=/secure/path/anna-password \
  --from-file=nikos-username=/secure/path/nikos-username \
  --from-file=nikos-password=/secure/path/nikos-password \
  --from-file=mcp-token=/secure/path/mcp-token
```

Files must contain exact values without trailing newlines. Kubernetes Secrets
are not encrypted merely by being base64 encoded: enable encryption at rest and
restrict Secret/pod-exec RBAC. Rotate credentials/token with a coordinated proxy
update and `kubectl rollout restart deployment/maliaras-parent-mcp` because
injected environment variables do not refresh in existing pods.

## Run/test locally (no real account access needed for tests)

From the repository root:

```sh
uv sync --project mcp_server --frozen
uv run --project mcp_server pytest -c mcp_server/pyproject.toml mcp_server/tests -q
# With credentials and token securely injected into the process environment:
uv run --project mcp_server python mcp_server/server.py
```

Streamable HTTP endpoint: `http://localhost:8000/mcp`.
`GET /healthz` is an unauthenticated, data-free process health check; it does not
validate ERP availability or credentials. No real ERP calls occur at startup.

## Container and Kubernetes

Build **from repository root** (the Dockerfile needs the shared modules):

```sh
docker build -f mcp_server/Dockerfile -t YOUR_REGISTRY/maliaras-parent-mcp:0.1.0 .
# Push through your normal image publishing workflow.
```

The Dockerfile-specific context allowlist excludes reports, secrets and history.
Dependencies are pinned in `uv.lock`. The image runs non-root; Kubernetes uses a
read-only root filesystem with only an ephemeral memory-backed `/tmp` volume.

Before applying `k8s/deployment.yaml`:

1. Replace the image with your registry image (prefer a digest).
2. Set the NetworkPolicy's proxy pod selector to your actual litelm labels.
   The example allows only matching proxy pods **in the same namespace**.
   For a proxy in another namespace, use an explicit `namespaceSelector` plus
   `podSelector` in the same `from` entry. A NetworkPolicy-capable CNI is required.
3. Create the Secret in the selected namespace, then apply:

```sh
kubectl -n YOUR_NAMESPACE apply -f mcp_server/k8s/deployment.yaml
```

The Service is ClusterIP only; no public Ingress is created. Egress must allow
cluster DNS and HTTPS to `erp.maliaras.gr`. The supplied policy restricts ingress
only; use your CNI's FQDN policy if you want domain-restricted egress.

## Connect your litelm MCP proxy

Register a backend with these settings in your proxy's actual configuration format:

- **Name:** `maliaras-parent`
- **Transport:** Streamable HTTP (not legacy SSE)
- **URL:** `http://maliaras-parent-mcp.YOUR_NAMESPACE.svc.cluster.local:8000/mcp`
- **Backend header:** `Authorization: Bearer <value from mcp-token Secret>`
- **Access:** only your authenticated proxy identity/key, not every proxy user
- **Timeout:** allow for sequential subject requests (each ERP HTTP request has
  a 30-second timeout); start with 300 seconds and tune to observed latency

Use the proxy's native secret/environment interpolation rather than committing
an expanded token. The backend token grants access to **both** children. The
proxy must not expose this backend through shared/public keys. Disable MCP
request/response body logging, tracing of lesson payloads and caching in the
proxy; school text travels through it. Do not enable server debug logging.

Use HTTPS on the public proxy. The sample backend URL assumes a trusted private
cluster network; use service-mesh mTLS or internal TLS if that trust is not
appropriate. Do not send the Bearer token over public plaintext HTTP.

The exact proxy registration is intentionally not guessed: its configuration
schema, namespace, labels and registry must be supplied for a deployment-specific
patch. This folder does not deploy or publish anything automatically.
