from django.test import TestCase

from apps.common import qdrant_store
from apps.common.test_utils import pad_vector


class QdrantStoreTests(TestCase):
    """Unit tests for the apps/common/qdrant_store.py wrapper itself,
    independent of any Django model - exercises the embedded `:memory:`
    Qdrant engine directly."""

    def setUp(self):
        qdrant_store.reset_client()

    def test_ensure_collection_is_idempotent(self):
        qdrant_store.ensure_collection()
        qdrant_store.ensure_collection()  # must not raise on the second call

    def test_upsert_and_search_nearest_first(self):
        qdrant_store.upsert_point(1, pad_vector([1.0, 0.0, 0.0]), {"specialty": "cardiology", "consent_for_research": True})
        qdrant_store.upsert_point(2, pad_vector([0.0, 1.0, 0.0]), {"specialty": "cardiology", "consent_for_research": True})

        results = qdrant_store.search(pad_vector([1.0, 0.0, 0.0]), top_k=5)
        ids = [point_id for point_id, _score in results]
        self.assertEqual(ids[0], 1)
        self.assertIn(2, ids)

    def test_search_applies_payload_filter(self):
        qdrant_store.upsert_point(1, pad_vector([1.0, 0.0, 0.0]), {"specialty": "cardiology"})
        qdrant_store.upsert_point(2, pad_vector([1.0, 0.0, 0.0]), {"specialty": "dermatology"})

        results = qdrant_store.search(pad_vector([1.0, 0.0, 0.0]), top_k=5, query_filter={"specialty": "cardiology"})
        ids = [point_id for point_id, _score in results]
        self.assertEqual(ids, [1])

    def test_search_applies_multiple_filter_fields_as_and(self):
        qdrant_store.upsert_point(1, pad_vector([1.0, 0.0, 0.0]), {"specialty": "cardiology", "consent_for_research": True})
        qdrant_store.upsert_point(2, pad_vector([1.0, 0.0, 0.0]), {"specialty": "cardiology", "consent_for_research": False})

        results = qdrant_store.search(
            pad_vector([1.0, 0.0, 0.0]), top_k=5,
            query_filter={"specialty": "cardiology", "consent_for_research": True},
        )
        ids = [point_id for point_id, _score in results]
        self.assertEqual(ids, [1])

    def test_search_excludes_given_id(self):
        qdrant_store.upsert_point(1, pad_vector([1.0, 0.0, 0.0]), {})
        qdrant_store.upsert_point(2, pad_vector([1.0, 0.0, 0.0]), {})

        results = qdrant_store.search(pad_vector([1.0, 0.0, 0.0]), top_k=5, exclude_id=1)
        ids = [point_id for point_id, _score in results]
        self.assertEqual(ids, [2])

    def test_top_k_limits_results(self):
        for i in range(5):
            qdrant_store.upsert_point(i + 1, pad_vector([1.0, 0.0, 0.0]), {})
        results = qdrant_store.search(pad_vector([1.0, 0.0, 0.0]), top_k=2)
        self.assertEqual(len(results), 2)

    def test_delete_point_removes_it_from_search(self):
        qdrant_store.upsert_point(1, pad_vector([1.0, 0.0, 0.0]), {})
        qdrant_store.delete_point(1)
        results = qdrant_store.search(pad_vector([1.0, 0.0, 0.0]), top_k=5)
        self.assertEqual(results, [])

    def test_search_on_empty_collection_returns_empty_list(self):
        qdrant_store.ensure_collection()
        results = qdrant_store.search(pad_vector([1.0, 0.0, 0.0]), top_k=5)
        self.assertEqual(results, [])
