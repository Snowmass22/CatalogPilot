# CatalogPilot: PRD & ADRs

*An agentic PIM that cleans, enriches and safely syncs product data to WooCommerce. Built for a 3-hour hackathon.*

---

## 0. The Pitch and the Unique Angle

Most teams will build: CSV upload → product table → push to WooCommerce. That is the baseline. It will look the same in every demo.

**CatalogPilot's differentiators (what others won't have):**

| # | Differentiator | Why judges care |
| --- | --- | --- |
| 1 | **Agentic Ingestion**: an AI agent reads any messy supplier CSV, infers the column mapping and normalizes attributes ("Clr" → Color, "XL" / "x-large" → XL) | Real agentic AI, not a chatbot wrapper |
| 2 | **Catalog Health Score**: every product gets a 0–100 completeness and quality score with explainable issues (missing image, weak description, duplicate SKU, price anomaly) | Measurable, visual, demo-friendly |
| 3 | **Sync Plan with Dry-Run, Approval and Rollback**: the agent produces a diff (create / update / skip), a human approves, sync executes, and every sync is a snapshot that can be rolled back ("Sync Time Machine") | Execution quality and safety; shows production thinking |
| 4 | **Natural-language catalog ops**: "Increase prices of all Hoodies by 10% and set stock to 0 for discontinued items" → the agent produces a *previewed* bulk change, never a blind write | Agentic AI with human-in-the-loop |
| 5 | **MCP server** exposing PIM tools (`search_products`, `score_product`, `plan_sync`) so any external agent can drive the PIM | Memorable "wow" extra if time permits (stretch) |

**One-line story for the demo:** *"We turn a messy supplier spreadsheet into a clean, scored, enriched catalog and push it to WooCommerce safely, with the AI proposing and the human approving."*

---

## 1. Product Requirements Document (PRD)

### 1.1 Problem Statement

Merchants receive product data from many suppliers in inconsistent formats. Manually cleaning it, keeping attributes consistent and syncing to WooCommerce is slow and error-prone. Blind bulk pushes can overwrite live store data with no way back.

### 1.2 Goals

- **G1.** Centralize product data in a PIM (single source of truth).
- **G2.** Automate cleanup and enrichment with AI agents, with human approval.
- **G3.** Sync reliably and idempotently with WooCommerce, with preview and rollback.
- **G4.** Be demo-ready, documented and well-tested within 3 hours.

### 1.3 Non-Goals (explicitly out of scope)

Multi-user auth and roles, multi-currency, image hosting or CDN, order management, WooCommerce → PIM full two-way sync (only a one-time **import** is stretch), variable-product variations beyond simple attribute handling.

### 1.4 Personas

- **Maya, Catalog Manager**: uploads supplier files, fixes data quality, approves syncs.
- **Raj, Store Owner**: wants confidence that the live store is not broken by a bad import.

### 1.5 Core Features (the three PS pillars)

#### Pillar A: Product Catalog Management

| ID | Requirement | Priority |
| --- | --- | --- |
| A1 | CRUD for products (SKU, name, description, price, stock, category, images, status) | Must |
| A2 | Category tree (flat or one level nested) | Must |
| A3 | Search, filter (category, status, health score) and pagination | Must |
| A4 | CSV import with **AI column mapping** and preview before commit | Must |
| A5 | Duplicate detection (same SKU, or fuzzy name match) | Should |

#### Pillar B: Attribute Handling

| ID | Requirement | Priority |
| --- | --- | --- |
| B1 | Attribute definitions (name, type: text / select / number, allowed values) | Must |
| B2 | Product ↔ attribute values (e.g. Color = Red, Size = XL) | Must |
| B3 | **AI attribute normalization**: map raw values to canonical values; unknown values are flagged for review | Must |
| B4 | Attribute completeness rules per category (e.g. Apparel requires Size and Color) | Should |
| B5 | Mapping to WooCommerce global attributes and terms | Must |

#### Pillar C: Data Synchronization

| ID | Requirement | Priority |
| --- | --- | --- |
| C1 | WooCommerce connection settings and a "Test connection" button | Must |
| C2 | **Sync plan (dry-run)**: list of create / update / no-change / error items with field-level diffs | Must |
| C3 | Human approval gate before execution | Must |
| C4 | Idempotent execution: match by SKU, store `woo_id` mapping, use WooCommerce batch endpoint | Must |
| C5 | Sync log with per-item status, retries and error messages | Must |
| C6 | **Rollback**: restore previous values of the items touched by a sync run | Should (wow) |
| C7 | Import existing WooCommerce products into the PIM | Could |

#### Pillar D: AI Agents (the scoring bucket)

| Agent | Responsibility | Tools it may call |
| --- | --- | --- |
| **Mapper Agent** | Infer CSV column → PIM field mapping; normalize attribute values | `read_csv_sample`, `get_attribute_schema` |
| **Quality Agent** | Produce Health Score and explainable issues; suggest fixes | `get_product`, `find_duplicates`, `get_category_rules` |
| **Enrichment Agent** | Draft improved descriptions, SEO titles and short descriptions (status = *suggested*, never auto-applied) | `get_product` |
| **Sync Planner Agent** | Build the sync plan, explain risks in plain language ("12 price drops greater than 40%") | `diff_products`, `get_woo_state` |
| **Ops Agent** (NL commands) | Convert natural language to a structured bulk-change spec, previewed before applying | `query_products`, `preview_bulk_change` |

**Rule:** agents *propose*; deterministic code *validates and executes*. Every agent output is schema-validated (Pydantic) before it touches data.

### 1.6 User Flow (demo path)

1. Open dashboard and see the Catalog Health Score (initially empty).
2. Upload a messy supplier CSV. The Mapper Agent proposes a mapping and the user confirms in a preview table.
3. Products appear with health scores and issue chips.
4. Click **"Fix with AI"** to apply suggested normalizations and enrichment. The score rises (before/after).
5. Type a natural-language command ("raise Hoodie prices 10%"). A preview appears, then the user confirms.
6. Click **"Plan Sync"**. A diff is shown with an AI risk summary.
7. Approve. Products appear in WooCommerce (show the live store admin).
8. Click **"Rollback"** on the sync run and show the store reverting.

### 1.7 Functional Requirements: API Surface

| Method | Endpoint | Purpose |
| --- | --- | --- |
| GET/POST/PUT/DELETE | `/api/products` | Catalog CRUD |
| GET/POST | `/api/attributes` | Attribute definitions |
| POST | `/api/imports/preview` | Upload CSV, returns AI mapping and normalized preview |
| POST | `/api/imports/commit` | Commit confirmed import |
| GET | `/api/health` | Catalog score summary |
| POST | `/api/ai/enrich/{id}` | Suggested enrichment |
| POST | `/api/ai/command` | NL command → previewed bulk change |
| POST | `/api/sync/plan` | Build dry-run plan |
| POST | `/api/sync/runs/{plan_id}/execute` | Execute approved plan |
| POST | `/api/sync/runs/{run_id}/rollback` | Roll back a run |
| GET | `/api/sync/runs` | History and logs |

### 1.8 Non-Functional Requirements

- **Reliability:** idempotent sync, retries with backoff (3 attempts), no partial-state ambiguity (per-item status recorded).
- **Safety:** no write to WooCommerce without an approved plan. Secrets only via `.env`.
- **Performance:** sync 100 products in under 30 seconds (batch endpoint, 100 items per call).
- **Observability:** structured logs, a sync run ID on every log line.
- **Resilience demo fallback:** if live WooCommerce or the LLM is unavailable, the app switches to a **Mock WooCommerce adapter** and cached LLM fixtures, so the demo never dies.

### 1.9 Success Metrics (to show judges)

- Average Health Score before vs. after AI fix (e.g. 54 → 91).
- Import time for 50 messy rows: under 1 minute versus manual.
- Sync of N products with 0 duplicates on re-run (idempotency proof).
- Test count and coverage (target above 70% on the core domain and sync modules).

### 1.10 Judging Rubric Mapping

| Criterion | How we address it |
| --- | --- |
| **Code quality** | Layered architecture (api / services / adapters / domain), typing, Pydantic schemas, ruff and mypy, small functions, pytest |
| **Documentation** | README with architecture diagram, `docs/PRD.md`, `docs/adr/*.md`, `.env.example`, a Makefile, API docs (OpenAPI auto) |
| **Execution quality** | Working end-to-end demo, dry-run, idempotency, rollback, graceful errors, fallback mocks |
| **Agentic AI** | 5 tool-using agents, schema-validated outputs, human-in-the-loop approvals, optional MCP server |
| **Uniqueness** | Health Score, Sync Time Machine, NL ops with preview |

---

## 2. Architecture Overview

```
┌──────────────┐   ┌────────────────────────────────────────────┐
│  Web UI      │──▶│  FastAPI (api layer)                       │
│ (HTMX/Jinja) │   │   routers → services (use cases)           │
└──────────────┘   │                                            │
                   │  Domain: Product, Attribute, SyncPlan,     │
                   │          HealthScore (pure Python)         │
                   │                                            │
                   │  Agents: Mapper | Quality | Enrichment |   │
                   │          SyncPlanner | Ops  (LLM port)     │
                   │                                            │
                   │  Ports → Adapters                          │
                   │   StorePort ─┬─ WooCommerceAdapter (REST)  │
                   │              └─ MockStoreAdapter           │
                   │   LLMPort   ─┬─ GeminiAdapter              │
                   │              └─ FixtureLLMAdapter          │
                   └───────────────┬────────────────────────────┘
                                   ▼
                               SQLite (SQLModel)
```

**Suggested folder structure**

```
catalogpilot/
├─ app/
│  ├─ api/            # FastAPI routers (thin)
│  ├─ services/       # use cases: import, scoring, sync, rollback
│  ├─ domain/         # models, scoring rules, diff logic (pure)
│  ├─ agents/         # mapper.py, quality.py, enrichment.py, planner.py, ops.py
│  ├─ adapters/       # woocommerce.py, mock_store.py, llm_gemini.py, llm_fixture.py
│  ├─ db/             # SQLModel tables, session
│  └─ web/            # templates + static
├─ tests/             # unit (domain, scoring, diff) + integration (sync w/ mock store)
├─ docs/              # PRD.md, adr/0001-*.md ... , architecture.md
├─ sample_data/       # messy_supplier.csv (deliberately dirty!)
├─ .env.example
├─ Makefile           # make run | test | lint | seed
└─ README.md
```

**Core data model**

- `Product(id, sku UNIQUE, name, description, price, stock, category_id, status, woo_id, health_score, updated_at)`
- `Category(id, name, parent_id, woo_id)`
- `AttributeDef(id, name, type, allowed_values JSON, woo_attribute_id)`
- `ProductAttribute(product_id, attribute_id, value)`
- `ImportJob(id, filename, mapping JSON, status)`
- `SyncPlan(id, created_at, summary JSON, status)` and `SyncItem(plan_id, product_id, action, diff JSON, status, error)`
- `SyncRun(id, plan_id, started_at, finished_at, status)` and `Snapshot(run_id, product_id, before JSON)` (for rollback)
- `AgentTrace(id, agent, input, output, tokens, ts)` (useful to show in the demo UI)


## 4. 3-Hour Execution Plan

| Time | Milestone | Output |
| --- | --- | --- |
| **0:00–0:15** | Setup | Repo, venv, `.env.example`, folder skeleton, `docker compose up` for WooCommerce running in the background, API keys generated. Commit docs (this PRD and ADRs) first. |
| **0:15–0:50** | Core domain and catalog | Models, DB, product CRUD, attribute defs, category, seed script, catalog page with search and filter |
| **0:50–1:25** | Import + Mapper Agent | CSV upload, AI mapping preview, normalization, commit; `messy_supplier.csv` sample |
| **1:25–1:55** | Health Score + Quality / Enrichment Agents | Rules engine, dashboard with before/after score, "Fix with AI" |
| **1:55–2:30** | WooCommerce sync | Adapter, plan/diff, approve, execute, sync log, idempotency check |
| **2:30–2:45** | Rollback + NL Ops | Snapshot rollback, "raise prices 10%" preview flow |
| **2:45–3:00** | Polish | README, architecture diagram, tests green, record LLM fixtures, rehearse demo, 2-min screen recording as backup |

**Cut order if time runs short (drop from the bottom):** MCP server → WooCommerce import → NL Ops → Rollback → Enrichment Agent. **Never cut:** Import with Mapper Agent, Health Score, Sync Plan with approval, tests, README.

---

## 5. Vibecoding Playbook for Antigravity

1. **Commit the PRD and ADRs first**, then tell the agent: *"Read `docs/PRD.md` and `docs/adr/`. Follow them strictly. Do not add features outside scope."*
2. Work in **vertical slices**, one prompt per slice (see table). After each slice: run tests, commit with a conventional message (`feat: csv import with ai mapping`). A clean git history is visible quality.
3. Ask the agent to write **tests alongside every service** (domain scoring, diff, sync with `MockStoreAdapter`).
4. Add a `GEMINI.md` or `AGENTS.md` rules file: *"Python 3.12, type hints everywhere, ruff and mypy clean, services never import adapters directly, no business logic in routers, no LLM-generated numeric fields."*
5. Use Antigravity's browser agent to **self-test the UI flow** and attach screenshots to the README.

**Slice prompts (copy-ready starters)**

- *Slice 1:* "Scaffold FastAPI + SQLModel per ADR-0001/0002 with the folder structure in the PRD. Implement Product, Category, AttributeDef, ProductAttribute models, CRUD routers, and a seed script. Add pytest tests."
- *Slice 2:* "Implement `LLMPort`, `GeminiAdapter` (structured output) and `FixtureLLMAdapter`. Then the Mapper Agent: given 5 sample CSV rows and the PIM schema, return a validated `ColumnMapping` and normalized attribute values. Build the import preview UI with HTMX."
- *Slice 3:* "Implement the deterministic Health Score per ADR-0007 with unit tests, a dashboard showing average score and top issues, and the Quality Agent that explains issues."
- *Slice 4:* "Implement `StorePort`, `WooCommerceAdapter` (batch endpoint, SKU lookup, retries) and `MockStoreAdapter`. Build SyncPlan generation with field-level diffs, approval endpoint, execution with snapshots, and an idempotency test (run twice, zero creates the second time)."
- *Slice 5:* "Add rollback from snapshots and the NL Ops agent that returns a `BulkChangeSpec` validated against allowed operations, with a preview before applying."
- *Slice 6:* "Write README (setup, architecture diagram in Mermaid, demo script), `.env.example`, Makefile, and ensure `make lint test` pass."

---

## 6. Test Strategy (minimal but visible)

- **Unit:** health score rules, diff generator, attribute normalizer, `BulkChangeSpec` validation.
- **Integration:** import → commit → plan → execute → re-plan shows **zero changes** (idempotency); rollback restores prior state, using the mock store.
- **Contract:** one small test that the `WooCommerceAdapter` builds correct batch payloads (use `responses` or `httpx.MockTransport`).
- **Agent tests:** fixture-based; assert that malformed LLM output is rejected by schema validation and retried once.

---

## 7. Risks and Mitigations

| Risk | Likelihood | Mitigation |
| --- | --- | --- |
| WooCommerce setup eats time | High | Start Docker in minute 5; `STORE_MODE=mock` fallback |
| LLM rate limit or latency during demo | Medium | Fixture replay mode; pre-recorded traces |
| Scope creep | High | Cut order above; PRD non-goals |
| Agent generates wrong code or architecture drift | Medium | Rules file, vertical slices, tests after each slice |
| Messy sample data not impressive | Medium | Hand-craft `messy_supplier.csv` with typos, mixed units, duplicate SKUs, missing fields, inconsistent sizes and colors |

---

## 8. Demo Script (3 minutes)

1. **(20s) Problem:** show the ugly supplier CSV.
2. **(40s) Import:** upload, the AI mapping appears, normalization diff, commit. Dashboard shows score **52**.
3. **(30s) Fix with AI:** score jumps to **90+**, with issue chips disappearing.
4. **(30s) NL command:** "Raise Hoodie prices by 10%" → preview → apply.
5. **(40s) Sync:** Plan (diff plus AI risk summary) → Approve → open the WooCommerce admin and show the products.
6. **(20s) Rollback:** one click, the store reverts. Close with *"agents propose, humans approve, nothing ships blind."*

---

## 9. Definition of Done Checklist

- [ ] `make run` works from a clean clone using `.env.example`
- [ ] Messy CSV → mapped → scored → synced → rolled back, end to end
- [ ] Re-running a sync creates **0 duplicates**
- [ ] `make lint test` is green
- [ ] README with architecture diagram, setup, demo script and screenshots
- [ ] `docs/PRD.md` and `docs/adr/0001–0009` committed
- [ ] LLM fixtures recorded; mock mode verified
- [ ] Backup screen recording saved
