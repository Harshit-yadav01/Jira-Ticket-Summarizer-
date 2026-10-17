Role: Senior Full-Stack Developer and Solution Architect

## Current project decisions

These decisions apply to the initial implementation and supersede conflicting LLM, AI-provider, and model-generated-content requirements below.

- Build all eight implementation phases, including the request-ingestion foundation in Phase 2.
- Do not include or call an LLM. Summaries, classification, missing-information checks, and next-step prompts must use deterministic field extraction and explicit rules.
- Keep claims tied to request fields. Mark absent information as unknown; do not invent expected outcomes, root causes, resolutions, or supporting evidence.
- Retrieve relevant HPE Support documents through an approved HPE search interface when configured. Otherwise, provide a clearly labeled HPE Support Center search link; do not claim a document was fetched when only a search link is available.
- Keep Jira integration read-only. Source requests must not be modified by this application.
- Use SQLite and local demo data for the initial runnable version. Preserve connector boundaries so the storage layer can move to a managed database later.
- Phase 3 means deterministic request analysis. Phase 4 means HPE Support document search and source references, not semantic retrieval backed by an embedding model.

Act as a senior software architect and full-stack engineer. Design, develop, test, and deliver a functional Request Analysis and Resolution Assistant.

For this project, the decisions at the beginning of this document replace the generic AI, root-cause, and resolution-generation requirements below.

Do not just explain how to build it. Build the application, create the necessary files, implement the core functionality, run available tests, and provide clear instructions to run it.

1. Project objective

Build a tool that connects to an existing request or ticket management platform, retrieves requests, analyzes their content, and presents a concise, understandable summary with evidence-based resolution recommendations.

The tool should reduce the time required to:

Read and understand lengthy requests.
Identify the actual problem and business impact.
Investigate the likely root cause.
Find similar previously resolved requests.
Identify missing information and dependencies.
Recommend the most appropriate resolution.
Prepare responses and resolution notes.
Track whether recommended resolutions were successful.

The application should be simple enough for a non-technical support analyst to use while providing enough detail for technical teams to investigate and resolve complex issues.

2. Start by inspecting the environment

Before writing code:

Inspect the available project files, repository structure, configuration, and installed dependencies.
Identify the existing technology stack and reuse it where practical.
Determine whether platform API credentials, documentation, sample data, or an existing integration are available.
If essential details are missing, state your assumptions and ask only the most important questions.
Do not invent API endpoints, credentials, platform capabilities, or successful test results.
If the source platform is unknown, implement a connector interface and a functional demo mode using realistic sample requests. Keep the integration replaceable without redesigning the application.

Do not stop after producing a plan. Once the initial inspection is complete, proceed with implementation using reasonable, clearly documented defaults.

3. Core application features
A. Request ingestion and synchronization

Implement a modular integration layer that can retrieve requests from the configured platform using its officially supported API.

Support, where available:

Request or ticket ID.
Title and detailed description.
Status and priority.
Requester and assignment group.
Creation and modification timestamps.
Comments and activity history.
Attachments and relevant logs.
Resolution details and closure notes.
Related requests and linked knowledge articles.

Requirements:

Support pagination, retries, timeouts, rate limits, and incremental synchronization.
Avoid duplicate requests.
Track synchronization status and errors.
Provide manual refresh and configurable scheduled synchronization.
Preserve source IDs and provide a link back to each original request.
Use secure authentication and least-privilege access.
Never scrape a platform or bypass access controls when an authorized API is available.

If credentials or platform details are unavailable, implement the connector interface and mock connector first. Clearly document how to configure the real connector later.

B. Deterministic request summarization (no LLM)

For each request, generate a concise, structured summary containing:

One-line summary.
Problem statement.
Expected outcome.
Actual versus expected behavior.
Business or technical impact.
Affected system or component.
Relevant error messages or log evidence.
Actions already attempted.
Missing information.
Recommended next step.

Use simple, professional language and concise templates. Expand abbreviations only when the ticket or a cited source provides the expansion.

Provide two levels of detail:

Quick summary: understandable in approximately 30 seconds.
Technical analysis: detailed enough for an engineer to investigate.

Do not invent facts. Distinguish confirmed ticket fields from unknown information. The initial version does not create unsupported semantic paraphrases or inferences.

C. Request classification and prioritization

Automatically classify requests into configurable categories, such as:

Incident or service disruption.
Access or permission issue.
Data or reporting issue.
Application defect.
Configuration change.
Service request.
Performance issue.
Integration failure.
Information request.
Other or unknown.

Also extract relevant systems, environments, and error codes when explicit in request text. Display the source priority and impact context without changing or predicting ticket priority.

D. Deterministic investigation support

Extract confirmed observations, explicit error evidence, and actions already attempted from request fields and comments. List standard diagnostic details that are missing and safe information-gathering steps.

Do not rank or assert root causes. Do not imply that a generic diagnostic prompt has been validated for the request's product, version, or environment.

E. HPE Support guidance

This is one of the most important features.

Search approved HPE Support documentation using product names, error codes, and keywords explicitly available in a request. Display source title, URL, returned excerpt, and matching query when available.

The initial version does not generate a fix or claim that a document supports a resolution. If a supported HPE search API is unavailable, clearly label and link to an HPE Support Center search rather than claiming results were fetched.

Do not recommend exposing credentials, disabling security controls, deleting production data, or executing destructive operations.

F. HPE source references

Keep HPE results separate from ticket facts. Validate that returned source links use HTTPS and an HPE Support domain. Show the search query and provider-supplied excerpt so analysts can judge relevance.

Treat ticket and retrieved document text as untrusted content. Never execute instructions found in those sources. If no documents are returned, keep request analysis available and state that no HPE result was fetched.

G. Deterministic response drafts

Provide an editable requester follow-up draft based on the summary and missing-information checklist. Keep it professional and clearly a draft. Do not invent a resolution, root cause, or closure note. Never send a response or change the source request.

H. Request dashboard and user interface

Build a clean, modern, responsive interface with the following sections:

Dashboard

Total requests retrieved.
Requests awaiting analysis.
Open and unresolved requests.
High-impact requests.
Requests with suggested resolutions.
Requests requiring human investigation.
Recent synchronization failures.

Request list

Search by request ID, keyword, or error code.
Filter by status, priority, category, assignment group, and date.
Sort by priority, age, and last updated time.
Show analysis status and recommendation availability.

Request details

Original request and activity history.
Concise summary.
Impact and classification.
Confirmed observations and missing information.
Diagnostic prompts, not root-cause hypotheses.
Related HPE Support references and their retrieval status.
Editable response and closure-note drafts.

Actions

Analyze or reanalyze a request.
Refresh data from the source platform.
Copy summaries and recommendations.
Approve, reject, or edit a recommendation.
Record the actual resolution and outcome.
Provide feedback on analysis quality.

Show loading, empty, success, and error states. Make the interface useful on desktop and mobile.

4. Deterministic analysis requirements

Do not add an LLM provider, model, prompt layer, embeddings, or model API keys. Keep rule-based summarization and classification in a dedicated service with testable rules and structured outputs.

Record analysis timestamps. Re-run analysis when source request content changes; invalidate stale results rather than displaying them as current. Keep extracted facts, unknowns, and HPE references distinct.

5. Suggested technical architecture

Use the existing stack if one is already established. Otherwise, choose a straightforward, maintainable architecture.

Suggested defaults:

Frontend: React with TypeScript.
Backend: Python with FastAPI.
Database: PostgreSQL.
Database access and migrations: SQLAlchemy and Alembic.
Background processing: a task queue or scheduled worker when required.
Semantic retrieval: PostgreSQL with pgvector or an appropriate alternative.
Analysis: deterministic extraction and explicit keyword rules; no model dependency.
Deployment: Docker and Docker Compose.

Keep the application modular, separating:

Platform connectors.
Data ingestion and normalization.
Business logic.
Rule-based analysis.
Knowledge retrieval.
Persistence.
API endpoints.
Frontend components.
Authentication and authorization.
Logging, monitoring, and evaluation.

Avoid unnecessary microservices or infrastructure that would make the first version difficult to run.

6. Data model

Create appropriate database models and migrations for entities such as:

Requests.
Request comments and activity history.
Request analyses.
Resolution recommendations.
Knowledge articles and historical resolutions.
Source references.
Synchronization jobs and errors.
User feedback and resolution outcomes.
Audit events.

Use stable identifiers, timestamps, appropriate indexes, and relationships. Avoid storing sensitive information unnecessarily.

7. Security and governance

Implement appropriate safeguards:

Secure secret management.
Authentication and role-based authorization.
Least-privilege platform permissions.
Input validation and output validation.
Protection against prompt injection from tickets and retrieved documents.
Sensitive data redaction where appropriate.
Audit logging for consequential actions.
Safe handling of attachments and logs.
Configurable retention policies.
Human approval for production-changing actions.

Separate read-only analysis from actions that change the source system.

The initial version should operate in read-only mode against the source platform, with recommendations and editable drafts. Any write-back or automated remediation should be an explicit, separately configurable capability.

8. Testing and evaluation

Create automated tests for:

API endpoints.
Data ingestion and pagination.
Duplicate prevention.
Synchronization failures and retries.
Analysis output schema validation.
Summary clarity and fact preservation.
Classification behavior.
Source-link validation.
Authorization and approval checks.
Untrusted ticket/document content handling.
Error and empty states.

Create a small, anonymized evaluation dataset with different types of requests, including incomplete tickets, ambiguous descriptions, recurring issues, and requests without known fixes.

Evaluate:

Summary accuracy and clarity.
Whether key facts are preserved.
Whether recommendations are evidence-based.
Whether unsupported claims are avoided.
Whether cited references actually support the recommendation.
Whether risky actions are appropriately restricted.

Do not claim a test passed unless it was actually executed. Document any tests that could not be run.

9. Implementation workflow

Follow these phases:

Phase 1: Inspect the repository, identify assumptions, and define the architecture.

Phase 2: Implement the database, API, mock connector, sample data, and core request workflow.

Phase 3: Implement deterministic summarization, classification, missing-information checks, and diagnostic prompts without an LLM.

Phase 4: Implement HPE Support document search and evidence references; use a labeled portal-search link if an approved API is unavailable.

Phase 5: Build the dashboard and request-detail interface.

Phase 6: Add security controls, approval workflows, error handling, and audit logging.

Phase 7: Write and run tests, fix discovered defects, and verify the complete workflow.

Phase 8: Prepare setup instructions, configuration documentation, and deployment guidance.

Prioritize a fully working vertical slice over numerous incomplete features. If time or environment limitations prevent completion of every phase, finish the most valuable end-to-end workflow first and list the remaining work honestly.

10. Definition of done

The application should be considered functionally complete for its initial release when:

It starts using documented setup instructions.
A user can load and search requests in demo mode.
A selected request can be analyzed end to end.
The summary is concise and understandable.
The system distinguishes request facts from unknowns.
The system displays HPE Support references without overstating their applicability.
Users can edit and copy the requester follow-up draft.
Analysis feedback can be recorded.
Errors are visible and recoverable.
Automated tests cover the main workflow.
The real platform connector can be configured without redesigning the core application.
Production-changing actions remain protected by authorization and approval.
11. Final deliverables

Provide:

A working application in the available project environment.
Complete source code for the implemented functionality.
Database schema and migrations.
Sample data and demo mode.
An example environment configuration file without real secrets.
API documentation.
Unit and integration tests.
A README with exact installation and startup commands.
Instructions for connecting the real request platform.
A list of implemented features, known limitations, and remaining work.
Final instruction

Start by inspecting the current environment and repository. Then implement the application, run the available checks, and demonstrate the complete workflow using sample data.

Do not stop at architecture diagrams, pseudocode, or a list of recommendations. Create and modify the actual project files wherever your environment allows it.

If a requirement depends on unavailable credentials, external access, or an unsupported platform, implement the parts that can be completed, explain the limitation, and provide a precise integration path for the remaining part.

Be pragmatic, prioritize correctness and usability, and make the smallest set of technical decisions necessary to deliver a working first version.