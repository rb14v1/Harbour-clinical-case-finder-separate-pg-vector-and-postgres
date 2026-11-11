"""
Dual-path AI layer: real OpenAI calls when `OPENAI_API_KEY` is set, otherwise
a fully offline, deterministic stub. This lets the whole similarity-search
pipeline (embeddings, migrations, seed data, Qdrant sync, the `/similar/`
endpoint) be built, run, and tested with zero network access and zero cost.

*** IMPORTANT ***: the stub embedding is NOT semantically meaningful. It is
a reproducible pseudo-random vector derived from a hash of the input text, so
the same text always embeds to the same vector (useful for exercising the
pipeline/tests), but two clinically similar encounters worded differently
will NOT reliably score as more similar than unrelated ones. Real similarity
search quality - actually finding clinically similar past cases - requires a
real OPENAI_API_KEY so `get_embedding` calls the real embeddings API.
"""
import hashlib
import math
import random

from django.conf import settings


def is_stub_mode() -> bool:
    return not bool(settings.OPENAI_API_KEY)


def get_embedding(text: str) -> list[float]:
    """Return an EMBEDDING_DIMENSIONS-length vector for `text`.

    Real path (OPENAI_API_KEY set): calls the OpenAI embeddings API.
    Stub path (no key): deterministic pseudo-random vector seeded from a
    sha256 hash of the text, L2-normalized. NOT semantically meaningful -
    see module docstring.
    """
    if settings.OPENAI_API_KEY:
        from openai import OpenAI

        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        response = client.embeddings.create(
            model=settings.OPENAI_EMBEDDING_MODEL,
            input=text,
            dimensions=settings.EMBEDDING_DIMENSIONS,
        )
        return response.data[0].embedding

    seed = hashlib.sha256(text.encode("utf-8")).hexdigest()
    rng = random.Random(seed)
    vector = [rng.uniform(-1.0, 1.0) for _ in range(settings.EMBEDDING_DIMENSIONS)]
    norm = math.sqrt(sum(v * v for v in vector)) or 1.0
    return [v / norm for v in vector]
