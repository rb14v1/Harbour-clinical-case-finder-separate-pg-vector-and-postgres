# Clinical Case Similarity Finder

Clinicians log patient encounters (chief complaint, free-text notes,
diagnosis, treatment). For any encounter, "Find similar cases" searches
consented past encounters from the same specialty - theirs and OTHER
clinicians' - by clinical similarity, and shows what they were diagnosed and
treated as. Patients must have consented (`consent_for_research=True`)
before their encounter is eligible to surface in someone else's search.

Stack: React + Vite + TS frontend, Django REST Framework backend. Two
clinician roles (`clinician`, `admin`): a clinician only ever sees/edits
their own encounters directly; an admin sees every encounter. No
Celery/Redis - there is no background work to run.

## Architecture: two separate databases, not pgvector

This project has 6 earlier "AI apps" (doc-search, faq-chatbot, job-matcher,
product-recommender, ticket-triage, recipe-finder) that store embeddings as
a `pgvector` column directly on Postgres. **This app is different.** It uses
two genuinely separate database systems with **no foreign-key/transactional
consistency between them**:

1. **Postgres** (plain - no `vector` extension) for all relational data:
   `User`, `Patient`, `Encounter`.
2. **Qdrant** (a dedicated vector database, via the `qdrant-client` Python
   package) for embeddings and semantic similarity search, as a completely
   separate service.

### How the two stores are kept in sync

- `backend/apps/common/qdrant_store.py` - a thin wrapper around
  `qdrant_client.QdrantClient`. Dev/test mode (`QDRANT_URL` unset):
  `QdrantClient(location=":memory:")` - qdrant-client's fully local embedded
  mode, running the real Qdrant engine in-process with no server required.
  Real mode (`QDRANT_URL` set, e.g. `http://localhost:6333`): a real Qdrant
  service. One shared collection, `"encounters"` (`EMBEDDING_DIMENSIONS` =
  1536, Cosine distance). Qdrant point IDs are the `Encounter` model's
  integer primary key directly - that's the join key back to Postgres.
- `backend/apps/encounters/signals.py` - on `Encounter` save, waits for
  `transaction.on_commit` before embedding the encounter's text and
  upserting the Qdrant point, so a vector is never written for a Postgres
  write that later rolls back. On delete, the Qdrant point is removed
  inline (`post_delete`) - no rollback risk there. Both handlers log a
  warning and swallow the error if Qdrant is briefly unreachable, rather
  than failing an otherwise-successful Postgres write.
- `python manage.py sync_vectors` - re-embeds and re-upserts **every**
  existing `Encounter` row into Qdrant from scratch. Idempotent. **This is
  the recovery path if the Qdrant container/volume is ever lost while
  Postgres data survives** - a real risk specific to this architecture,
  since there's no shared transaction or backup coupling between the two
  stores. Run it any time Qdrant looks empty/out of sync.
- The seed data migration (`apps/encounters/migrations/0002_seed_demo_data.py`)
  seeds Qdrant too, not just Postgres, guarded so a briefly-unreachable
  Qdrant doesn't fail the migration - `sync_vectors` repairs it afterwards.

### AI / embeddings (`backend/apps/common/ai.py`)

`get_embedding(text)` calls the real OpenAI embeddings API
(`text-embedding-3-large`, 1536 dims) when `OPENAI_API_KEY` is set,
otherwise returns a deterministic, sha256-seeded fake embedding (no network,
fully reproducible). The stub is **not semantically meaningful** - it
exists so the whole pipeline (migrations, seed data, Qdrant sync, the
`/similar/` endpoint) is buildable and testable with zero network access and
zero cost. Real similarity-search quality requires a real `OPENAI_API_KEY`.

## Data model

- `User` (`apps/accounts`) - email-login custom user. `role`
  (`clinician`/`admin`), `full_name`, `specialty` (clinicians only).
- `Patient` (`apps/patients`) - `full_name`, `date_of_birth`, `mrn` (unique
  medical record number).
- `Encounter` (`apps/encounters`) - `patient` (FK), `clinician` (FK, always
  the requesting user - never client-supplied), `specialty` (cardiology /
  pediatrics / oncology / general_medicine / dermatology), `chief_complaint`,
  `notes`, `diagnosis`, `treatment`, `consent_for_research` (bool, default
  `False`), `created_at`. Embeddings are **not** stored on this model at all
  - they live exclusively in Qdrant.
  - `embedding_text` = `chief_complaint + " " + notes + " " + diagnosis`
    (deliberately excludes `treatment` - that's the historical outcome
    similarity search surfaces, not part of what describes the case).
  - `services/similarity.py` - `find_similar_encounters(encounter, top_k=5)`:
    embeds the query encounter's text, searches Qdrant filtered to
    `consent_for_research=True` AND the same `specialty`, excluding the
    encounter's own ID, and joins the matches back to full `Encounter` rows
    from Postgres with scores.

## API

- `POST /api/auth/register/`, `/login/`, `/refresh/`, `/logout/`
- `GET /api/auth/me/`, `GET /api/users/me/`
- `GET/POST /api/patients/`, `GET/PUT/PATCH/DELETE /api/patients/{id}/`
- `GET/POST /api/encounters/`, `GET/PUT/PATCH/DELETE /api/encounters/{id}/`
  (filterable with `?specialty=` and `?consent_for_research=`) - a clinician
  sees/edits only their own encounters; an admin sees all.
- `GET /api/encounters/{id}/similar/` (`?top_k=`, default 5) - similar past
  encounters (from any consenting clinician, same specialty), each with a
  score, diagnosis, and treatment. `{id}` must be one of the requester's own
  encounters (or any encounter, for an admin) - the object itself is still
  ownership-scoped; only the *matches* it returns cross clinicians.

## Permissions

A clinician can only see/edit their own `Encounter` rows directly
(`/api/encounters/{id}/` 404s for another clinician's encounter) - but
similarity search against OTHER consenting clinicians' encounters is
explicitly allowed, read-only, via `/similar/`. This is the core guarantee
tested in `apps/encounters/tests/test_similar.py::SimilarEncountersPermissionTests`:
clinician B cannot `GET /api/encounters/{clinician_A_id}/` directly, but a
consented encounter from clinician A **does** appear in the `similar`
payload when clinician B searches from their own encounter.

## Seed data

A data migration (`apps/encounters/migrations/0002_seed_demo_data.py`)
seeds:
- `clinician@example.com` / `demo12345` (role=clinician, specialty=cardiology)
- `admin@example.com` / `demo12345` (role=admin)
- 4 patients
- 18 encounters across 5 specialties (cardiology, pediatrics, oncology,
  general_medicine, dermatology), 14 consented / 4 not, with varied clinical
  text so semantic similarity search has something meaningful to
  differentiate. Idempotent - re-running `migrate` skips seeding if the demo
  clinician already has encounters.

## Running locally without Docker (SQLite + in-memory Qdrant)

```
cd backend
python -m venv venv
source venv/Scripts/activate   # Windows Git Bash; use venv\Scripts\activate on cmd/PowerShell
pip install -r requirements.txt
export USE_SQLITE=True
export DJANGO_SETTINGS_MODULE=config.settings.dev
python manage.py migrate
python manage.py runserver
```

```
cd frontend
npm install
npm run dev
```

## Running with Docker (Postgres + Qdrant)

```
cp .env.example .env
docker compose up --build
```

The `postgres` service is plain `postgres:16` (no extension needed). The
`qdrant` service is `qdrant/qdrant:latest`, exposed on `6333` (REST) /
`6334` (gRPC), with its own named volume (`qdrant_data`) so vector data
survives container restarts (though see the "two databases" trade-off above
for what to do if that volume is ever lost: `python manage.py sync_vectors`).

**Port note:** this app's Postgres runs on the native default port `5432`
(a native Postgres 18 install on this machine, role/database
`clinical_case_finder`). This is different from the 6 earlier "AI apps" in
this project, whose Postgres+pgvector container runs on port `5433` - see
the comment in `.env.example`.

## Verification performed in this build

No live Postgres/Qdrant service or `OPENAI_API_KEY` was used for
verification; everything ran against SQLite (`USE_SQLITE=True`) and
qdrant-client's embedded `:memory:` mode, per the dual-path design above,
exercising identical application code:

- `manage.py check` - clean.
- `manage.py makemigrations --check --dry-run` - clean (no drift).
- `manage.py migrate` on a fresh DB - 2 demo users, 4 patients, 18 encounters
  seeded into Postgres AND Qdrant; confirmed via `shell` and
  `manage.py sync_vectors` (reported "Synced 18 encounter(s) to Qdrant").
- `manage.py migrate` run again - 0 new migrations applied, seed data
  unchanged (idempotent).
- `manage.py test` - **62/62 passing**, covering: JWT auth/register/refresh/
  logout, patient CRUD, encounter CRUD with specialty/consent filters,
  cross-clinician ownership (list/retrieve/update/delete all 404 for another
  clinician's encounter; admin sees everything), the Qdrant sync-on-save
  signal (verified end-to-end with `captureOnCommitCallbacks`, including
  that a rolled-back create never reaches Qdrant), the `qdrant_store` wrapper
  in isolation, hand-crafted-vector similarity ranking (nearest-first,
  self-excluded, specialty-filtered, consent-filtered), the core
  cross-clinician permission guarantee (direct 404 vs. read-only surfacing
  via `/similar/`), the embedding stub, and seed-migration row counts.
- `npm install` / `npm run build` (frontend) - clean TypeScript build, no
  errors.

### What's left once real Postgres/Qdrant/OpenAI are available

1. Run `docker compose up --build` (or point `DATABASES`/`QDRANT_URL` at the
   already-running native Postgres on `5432` and Qdrant container on
   `6333`) and re-run `manage.py migrate` / `manage.py test` against them -
   no code path differs, only the transport (`QdrantClient(url=...)` vs.
   `:memory:`, and real Postgres vs. SQLite).
2. Optionally set `OPENAI_API_KEY` to exercise the real embeddings code path
   in `apps/common/ai.py` (never executed in this stub-only verification).
