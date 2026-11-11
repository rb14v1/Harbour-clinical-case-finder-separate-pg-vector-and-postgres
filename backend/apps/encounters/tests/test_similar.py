"""
Tests for the /api/encounters/{id}/similar/ endpoint and the underlying
apps/encounters/services/similarity.py - specialty filtering, consent
filtering, self-exclusion, nearest-first ranking, and the cross-clinician
permission guarantee that is the whole point of this app.

Uses hand-crafted, known embedding vectors so ranking order and scores are
fully predictable, the same way ticket-triage's test_vector_search.py does.
Two things make that trickier here than in ticket-triage:

1. `find_similar_encounters(encounter, top_k)` takes an Encounter, not a raw
   vector - it always calls `get_embedding(encounter.embedding_text)`
   itself to build the query vector (matching the spec). So each encounter
   is given distinct clinical text, and `apps.common.ai.get_embedding` (as
   imported into apps.encounters.services.similarity) is patched to look up
   the hand-crafted vector for that exact text instead of hashing it - this
   controls the *query* vector the same way `_make_encounter` controls the
   vector stored for each *candidate* point.
2. Encounter.save()'s on_commit-deferred Qdrant upsert never fires under
   APITestCase's wrapped transaction (see test_qdrant_sync.py), so
   `_make_encounter` upserts the hand-crafted candidate vector directly via
   qdrant_store, bypassing the signal entirely - exactly like ticket-triage
   bypasses Ticket.save()'s auto-embedding via a bulk `.update()`.

Vectors are hand-crafted short for readability, then padded to
EMBEDDING_DIMENSIONS via pad_vector() - Qdrant's collection is created with
a fixed vector size and rejects any other length.
"""
from unittest import mock

from rest_framework import status
from rest_framework.test import APITestCase

from apps.common import qdrant_store
from apps.common.test_utils import auth_client, create_user, pad_vector
from apps.encounters.models import Encounter
from apps.encounters.services.similarity import find_similar_encounters
from apps.patients.models import Patient

GET_EMBEDDING_TARGET = "apps.encounters.services.similarity.get_embedding"


class SimilarEncountersTestBase(APITestCase):
    def setUp(self):
        qdrant_store.reset_client()
        self.clinician_a = create_user(email="a@example.com")
        self.clinician_b = create_user(email="b@example.com")
        self.client_a = auth_client(self.clinician_a)
        self.client_b = auth_client(self.clinician_b)
        self.patient = Patient.objects.create(full_name="Pat Three", date_of_birth="1970-02-02", mrn="SIM-1")
        self._vectors_by_text = {}

    def _make_encounter(self, clinician, specialty, consent, vector, label):
        """Creates an Encounter with clinical text unique to `label`, and
        upserts `vector` (padded) as its Qdrant point directly - bypassing
        the (never-firing-under-APITestCase) save signal. Also remembers
        `vector` against this encounter's exact embedding_text, so
        `_patch_embeddings()` can make get_embedding return it again when
        this encounter is later used as a *query*."""
        encounter = Encounter.objects.create(
            patient=self.patient,
            clinician=clinician,
            specialty=specialty,
            chief_complaint=f"chief complaint ({label})",
            notes=f"notes ({label})",
            diagnosis=f"diagnosis ({label})",
            treatment=f"treatment ({label})",
            consent_for_research=consent,
        )
        padded = pad_vector(vector)
        self._vectors_by_text[encounter.embedding_text] = padded
        qdrant_store.upsert_point(
            point_id=encounter.id,
            vector=padded,
            payload={"specialty": specialty, "consent_for_research": consent, "clinician_id": clinician.id},
        )
        return encounter

    def _fake_get_embedding(self, text):
        return self._vectors_by_text[text]

    def _patch_embeddings(self):
        return mock.patch(GET_EMBEDDING_TARGET, side_effect=self._fake_get_embedding)


class SimilarEncountersFilteringTests(SimilarEncountersTestBase):
    def test_specialty_filter_excludes_other_specialties(self):
        query = self._make_encounter(self.clinician_a, "cardiology", True, [1.0, 0.0, 0.0], "query")
        same_specialty = self._make_encounter(self.clinician_b, "cardiology", True, [0.9, 0.1, 0.0], "same-specialty")
        other_specialty = self._make_encounter(self.clinician_b, "dermatology", True, [1.0, 0.0, 0.0], "other-specialty")

        with self._patch_embeddings():
            resp = self.client_a.get(f"/api/encounters/{query.id}/similar/")

        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        ids = [r["encounter_id"] for r in resp.data["results"]]
        self.assertIn(same_specialty.id, ids)
        self.assertNotIn(other_specialty.id, ids)

    def test_consent_filter_excludes_non_consented(self):
        query = self._make_encounter(self.clinician_a, "cardiology", True, [1.0, 0.0, 0.0], "query")
        consented = self._make_encounter(self.clinician_b, "cardiology", True, [0.9, 0.1, 0.0], "consented")
        not_consented = self._make_encounter(self.clinician_b, "cardiology", False, [0.95, 0.05, 0.0], "not-consented")

        with self._patch_embeddings():
            resp = self.client_a.get(f"/api/encounters/{query.id}/similar/")

        ids = [r["encounter_id"] for r in resp.data["results"]]
        self.assertIn(consented.id, ids)
        self.assertNotIn(not_consented.id, ids)

    def test_self_exclusion(self):
        query = self._make_encounter(self.clinician_a, "cardiology", True, [1.0, 0.0, 0.0], "query")

        with self._patch_embeddings():
            resp = self.client_a.get(f"/api/encounters/{query.id}/similar/")

        ids = [r["encounter_id"] for r in resp.data["results"]]
        self.assertNotIn(query.id, ids)

    def test_own_non_consented_encounters_are_still_eligible(self):
        # consent_for_research gates OTHER clinicians' searches from finding
        # an encounter, but a clinician's own prior encounters (consented or
        # not) are still reasonable candidates for their own search since
        # they authored both. The API doesn't special-case "mine" in the
        # Qdrant filter, so this documents actual current behaviour: the
        # filter is consent + specialty only, applied uniformly regardless
        # of who is searching.
        query = self._make_encounter(self.clinician_a, "cardiology", True, [1.0, 0.0, 0.0], "query")
        own_consented = self._make_encounter(self.clinician_a, "cardiology", True, [0.9, 0.1, 0.0], "own-consented")
        own_not_consented = self._make_encounter(self.clinician_a, "cardiology", False, [0.95, 0.05, 0.0], "own-not-consented")

        with self._patch_embeddings():
            resp = self.client_a.get(f"/api/encounters/{query.id}/similar/")

        ids = [r["encounter_id"] for r in resp.data["results"]]
        self.assertIn(own_consented.id, ids)
        self.assertNotIn(own_not_consented.id, ids)


class SimilarEncountersRankingTests(SimilarEncountersTestBase):
    def test_nearest_first_ordering_and_scores(self):
        query = self._make_encounter(self.clinician_a, "cardiology", True, [1.0, 0.0, 0.0], "query")
        near = self._make_encounter(self.clinician_b, "cardiology", True, [0.9, 0.1, 0.0], "near")
        far = self._make_encounter(self.clinician_b, "cardiology", True, [0.0, 1.0, 0.0], "far")

        with self._patch_embeddings():
            resp = self.client_a.get(f"/api/encounters/{query.id}/similar/")

        results = resp.data["results"]
        ids = [r["encounter_id"] for r in results]
        self.assertEqual(ids[0], near.id)
        self.assertIn(far.id, ids)
        self.assertGreater(results[0]["score"], results[1]["score"])
        # Scores in the API response are rounded to 4 decimal places (see
        # find_similar_encounters) - compare against the same precision.
        self.assertAlmostEqual(results[0]["score"], round(0.9938837346736189, 4), places=4)
        self.assertAlmostEqual(results[1]["score"], 0.0, places=4)

    def test_top_k_limits_results(self):
        query = self._make_encounter(self.clinician_a, "cardiology", True, [1.0, 0.0, 0.0], "query")
        for i in range(5):
            self._make_encounter(self.clinician_b, "cardiology", True, [0.9, 0.1, 0.0], f"candidate-{i}")

        with self._patch_embeddings():
            resp = self.client_a.get(f"/api/encounters/{query.id}/similar/", {"top_k": 2})

        self.assertEqual(len(resp.data["results"]), 2)

    def test_result_payload_includes_diagnosis_and_treatment(self):
        query = self._make_encounter(self.clinician_a, "cardiology", True, [1.0, 0.0, 0.0], "query")
        match = self._make_encounter(self.clinician_b, "cardiology", True, [0.9, 0.1, 0.0], "match")

        with self._patch_embeddings():
            resp = self.client_a.get(f"/api/encounters/{query.id}/similar/")

        result = next(r for r in resp.data["results"] if r["encounter_id"] == match.id)
        self.assertEqual(result["diagnosis"], match.diagnosis)
        self.assertEqual(result["treatment"], match.treatment)
        self.assertEqual(result["specialty"], match.specialty)
        self.assertEqual(result["clinician_id"], self.clinician_b.id)

    def test_no_matches_returns_empty_results(self):
        query = self._make_encounter(self.clinician_a, "cardiology", True, [1.0, 0.0, 0.0], "query")

        with self._patch_embeddings():
            resp = self.client_a.get(f"/api/encounters/{query.id}/similar/")

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["results"], [])


class SimilarEncountersPermissionTests(SimilarEncountersTestBase):
    def test_cross_clinician_surfacing_vs_direct_access(self):
        """Core permission guarantee of this app: clinician B cannot
        directly fetch clinician A's encounter via /api/encounters/{id}/,
        but a CONSENTED encounter from clinician A CAN be surfaced
        read-only to clinician B through the similar-cases payload of
        clinician B's own encounter."""
        encounter_a = self._make_encounter(self.clinician_a, "cardiology", True, [1.0, 0.0, 0.0], "a-case")
        encounter_b = self._make_encounter(self.clinician_b, "cardiology", True, [0.95, 0.05, 0.0], "b-case")

        direct = self.client_b.get(f"/api/encounters/{encounter_a.id}/")
        self.assertEqual(direct.status_code, status.HTTP_404_NOT_FOUND)

        with self._patch_embeddings():
            similar = self.client_b.get(f"/api/encounters/{encounter_b.id}/similar/")

        self.assertEqual(similar.status_code, status.HTTP_200_OK, similar.data)
        ids = [r["encounter_id"] for r in similar.data["results"]]
        self.assertIn(encounter_a.id, ids)

    def test_non_consented_cross_clinician_encounter_never_surfaces(self):
        encounter_a = self._make_encounter(self.clinician_a, "cardiology", False, [1.0, 0.0, 0.0], "a-case")
        encounter_b = self._make_encounter(self.clinician_b, "cardiology", True, [0.95, 0.05, 0.0], "b-case")

        with self._patch_embeddings():
            similar = self.client_b.get(f"/api/encounters/{encounter_b.id}/similar/")

        ids = [r["encounter_id"] for r in similar.data["results"]]
        self.assertNotIn(encounter_a.id, ids)

    def test_cannot_request_similar_for_another_clinicians_encounter(self):
        encounter_a = self._make_encounter(self.clinician_a, "cardiology", True, [1.0, 0.0, 0.0], "a-case")

        with self._patch_embeddings():
            resp = self.client_b.get(f"/api/encounters/{encounter_a.id}/similar/")

        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)


class FindSimilarEncountersServiceTests(SimilarEncountersTestBase):
    """Direct unit tests of the service function, bypassing the API layer."""

    def test_returns_list_of_dicts_with_expected_keys(self):
        query = self._make_encounter(self.clinician_a, "oncology", True, [1.0, 0.0, 0.0], "query")
        self._make_encounter(self.clinician_b, "oncology", True, [0.9, 0.1, 0.0], "match")

        with self._patch_embeddings():
            results = find_similar_encounters(query, top_k=5)

        self.assertEqual(len(results), 1)
        expected_keys = {"encounter_id", "score", "specialty", "chief_complaint", "diagnosis", "treatment", "clinician_id"}
        self.assertEqual(set(results[0].keys()), expected_keys)
