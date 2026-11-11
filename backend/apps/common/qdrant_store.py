"""
Thin wrapper around `qdrant_client.QdrantClient` - the single integration
point between this app and its vector database.

*** ARCHITECTURE NOTE ***: unlike the earlier "AI apps" in this project
(doc-search, faq-chatbot, job-matcher, product-recommender, ticket-triage,
recipe-finder), which stored embeddings as a pgvector column directly on the
relational Postgres database, this app uses Qdrant as a genuinely separate
database system. There is NO foreign-key/transactional consistency between
Postgres and Qdrant - a Postgres write can commit while a Qdrant write fails
(or vice versa), so code that writes to both (see apps/encounters/signals.py)
must be deliberate about ordering and failure handling, and the recovery
path (`python manage.py sync_vectors`) exists specifically because of this.

Dev/test mode: when `QDRANT_URL` is unset, `get_client()` constructs a
`QdrantClient(location=":memory:")` - qdrant-client's fully local embedded
mode. This needs no running server and runs the identical real Qdrant search
engine in-process, so it is a much higher-fidelity stand-in than the other
apps' SQLite-for-pgvector fallback: there is no separate code path to keep in
sync with "real" Qdrant behaviour, only a different transport.

Real mode: when `QDRANT_URL` is set (e.g. http://localhost:6333), constructs
a `QdrantClient(url=QDRANT_URL)` that talks to a real Qdrant service.

One shared collection for the whole app, named by `settings.QDRANT_COLLECTION`
(default "encounters"), vector size `settings.EMBEDDING_DIMENSIONS` (1536),
distance Cosine. Qdrant point IDs are the Django `Encounter` model's integer
primary key directly - that integer is the join key back to Postgres, and
Qdrant point IDs must be unsigned ints or UUIDs, which a Django BigAutoField
PK always satisfies.
"""
import logging
import threading

from django.conf import settings
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

logger = logging.getLogger(__name__)

_client_lock = threading.Lock()
_client: QdrantClient | None = None


def get_client() -> QdrantClient:
    """Return a process-wide shared QdrantClient.

    A single `:memory:` client is reused across calls within a process so
    that in dev/test mode, data upserted earlier in the same process is
    still visible later (a fresh `:memory:` client starts with an empty
    database with nothing in it)."""
    global _client
    if _client is not None:
        return _client
    with _client_lock:
        if _client is None:
            if settings.QDRANT_URL:
                _client = QdrantClient(url=settings.QDRANT_URL)
            else:
                _client = QdrantClient(location=":memory:")
        return _client


def reset_client() -> None:
    """Drop the cached client so the next `get_client()` call builds a fresh
    one. Intended for tests that need a clean `:memory:` database between
    test cases/classes."""
    global _client
    with _client_lock:
        _client = None


def ensure_collection(client: QdrantClient | None = None) -> None:
    """Idempotently create the shared collection if it doesn't already
    exist."""
    client = client or get_client()
    collection_name = settings.QDRANT_COLLECTION
    if not client.collection_exists(collection_name):
        client.create_collection(
            collection_name=collection_name,
            vectors_config=qmodels.VectorParams(
                size=settings.EMBEDDING_DIMENSIONS,
                distance=qmodels.Distance.COSINE,
            ),
        )


def upsert_point(point_id: int, vector: list[float], payload: dict) -> None:
    client = get_client()
    ensure_collection(client)
    client.upsert(
        collection_name=settings.QDRANT_COLLECTION,
        points=[qmodels.PointStruct(id=point_id, vector=vector, payload=payload)],
    )


def delete_point(point_id: int) -> None:
    """Idempotent: deleting a point that doesn't exist (e.g. it was never
    successfully synced in the first place - see signals.py) is a no-op,
    not an error."""
    client = get_client()
    ensure_collection(client)
    existing = client.retrieve(collection_name=settings.QDRANT_COLLECTION, ids=[point_id])
    if not existing:
        return
    client.delete(
        collection_name=settings.QDRANT_COLLECTION,
        points_selector=qmodels.PointIdsList(points=[point_id]),
    )


def _build_filter(query_filter: dict | None, exclude_id: int | None) -> qmodels.Filter | None:
    must = []
    if query_filter:
        for key, value in query_filter.items():
            must.append(qmodels.FieldCondition(key=key, match=qmodels.MatchValue(value=value)))
    must_not = []
    if exclude_id is not None:
        must_not.append(qmodels.HasIdCondition(has_id=[exclude_id]))
    if not must and not must_not:
        return None
    return qmodels.Filter(must=must or None, must_not=must_not or None)


def search(
    vector: list[float],
    top_k: int = 5,
    query_filter: dict | None = None,
    exclude_id: int | None = None,
) -> list[tuple[int, float]]:
    """Return up to `top_k` `(point_id, score)` pairs, nearest-first (cosine
    similarity, higher = more similar), matching `query_filter` (an exact-
    match AND filter over payload fields) and excluding `exclude_id`."""
    client = get_client()
    ensure_collection(client)
    result = client.query_points(
        collection_name=settings.QDRANT_COLLECTION,
        query=vector,
        limit=top_k,
        query_filter=_build_filter(query_filter, exclude_id),
        with_payload=False,
        with_vectors=False,
    )
    return [(point.id, point.score) for point in result.points]
