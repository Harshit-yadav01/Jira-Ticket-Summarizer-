# Request Lens

Request Lens turns Jira support tickets into readable, evidence-grounded summaries and helps analysts locate related HPE Support guidance. It runs without an LLM: summaries, classifications, missing-information checks, and diagnostic prompts are produced by explicit rules and ticket fields.

## What is included

- Eight-phase initial vertical slice: architecture notes, SQLite/demo workflow, read-only Jira sync, deterministic request analysis, HPE references, responsive workbench, access controls, audit events, tests, and deployment instructions.
- Quick summary, category, affected product, priority context, error evidence, actions already attempted, unknowns, and safe next diagnostic steps.
- Search, status/priority filters, source links, editable requester drafts, feedback, and audit history.
- Viewer and analyst API-key roles. Viewers can inspect requests; analysts can analyze, sync, and record feedback.
- Jira text redaction for common credential-shaped values before local storage.

No root cause is presented as confirmed. The analyzer does not generate a speculative resolution or modify Jira.

## Run locally

Prerequisites: Python 3.9 or newer and Node.js 20 or newer.

From the repository root, install the backend and frontend dependencies:

```sh
python3 -m venv backend/.venv
backend/.venv/bin/python -m pip install -r backend/requirements.txt
cd frontend
npm install
```

Start the API in one terminal:

```sh
cd backend
.venv/bin/python -m uvicorn app.main:app --reload --port 8000
```

Start the frontend in another terminal:

```sh
cd frontend
npm run dev
```

Open <http://localhost:5173>. The API and interactive schema are at <http://localhost:8000> and <http://localhost:8000/docs>.

Demo tickets are inserted automatically into `backend/data.sqlite3`. To build the frontend for the API server or a container:

```sh
cd frontend
npm run build
```

After building, start the API and open <http://localhost:8000>; FastAPI serves `frontend/dist` when present.

## Configuration

Copy `.env.example` to `.env`. For local development, load it before starting the API:

```sh
set -a
source .env
set +a
```

Do not commit `.env` or put real credentials in source control. With no API keys configured, the app is intended for local demo use only.

### Jira

Set `JIRA_BASE_URL`, `JIRA_EMAIL`, and `JIRA_API_TOKEN`; optionally set `JIRA_PROJECT_KEY` to restrict the JQL query. Create a Jira API token with the least read-only permissions required for issue search. The connector calls Jira REST API v3 over HTTPS, requests ticket fields and comments, retries transient failures, caps each run at 500 issues, and uses an inclusive `updated` cursor after the initial import. Sync starts manually; set `JIRA_SYNC_INTERVAL_MINUTES` to a positive value to enable scheduled sync. The default `0` disables scheduling. Run status, timestamps, failures, and counts are kept in sync history. Jira is never written to.

### HPE Support

Without `HPE_SEARCH_API_URL`, analysis returns a clearly labeled HPE Support Center search link using the request title and description. That is a portal handoff, not an in-app document fetch.

To show fetched results in the app, configure an approved HPE Support search endpoint in `HPE_SEARCH_API_URL`. The adapter sends a `GET` request with a `query` parameter, optionally adds `Authorization: Bearer <HPE_SEARCH_API_KEY>`, and expects JSON in this shape:

```json
{
	"results": [
		{
			"title": "Document title",
			"url": "https://support.hpe.com/...",
			"snippet": "Short source excerpt"
		}
	]
}
```

The configured endpoint and every returned document URL must use HTTPS on `support.hpe.com` or a subdomain. The project does not assume an undocumented HPE API or scrape the support portal. Confirm the endpoint and its access terms with HPE before configuring it.

### Access keys

- `APP_VIEWER_API_KEY`: permits request and audit reads.
- `APP_ANALYST_API_KEY`: permits reads, analysis, Jira sync, and feedback.
- `APP_API_KEY`: compatibility option; treated as an analyst key.

When access keys are configured, enter the appropriate key in the UI. It is kept in browser `sessionStorage` for the current tab. Protect the API with TLS and a trusted network boundary; these shared keys are a lightweight local role gate, not enterprise SSO.

## Tests

```sh
cd backend
.venv/bin/python -m unittest discover -s tests -v
```

The tests cover summary grounding, unknown handling, Jira upserts and analysis freshness, credential redaction, role enforcement, incremental cursors, retry policy, sync success/failure history, scheduler startup/shutdown, HPE link allowlisting, and database persistence. Live Jira and HPE services are not contacted by the test suite.

## Container

Build and start the single-container deployment:

```sh
docker compose up --build
```

Set application keys and connector settings in the root `.env` before exposing the service. SQLite data is stored in the `request-data` Docker volume.

## Current limitations

- The default HPE mode creates a Support Center search link. Fetching result titles/snippets into the app requires an approved HPE endpoint implementing the documented adapter contract above.
- Jira sync is manual by default and capped at 500 tickets per run. Incremental sync and an optional interval scheduler are included; long backlogs may need repeated runs.
- Summaries and classification are deliberately rule-based. They can miss nuance in ambiguous or poorly structured requests; analyst review remains necessary.
- SQLite and shared API keys are intended for a small initial deployment. Production multi-user identity, enterprise RBAC/SSO, managed database operations, attachment ingestion, and retention controls need deployment-specific work.
- There are no automated write-back actions, root-cause claims, or model-generated resolutions.
