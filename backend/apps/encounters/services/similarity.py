"""
The core value of this app: given one encounter, find clinically similar
past encounters from OTHER consenting clinicians (or the same clinician) in
the same specialty, and show what they were diagnosed/treated as.
"""
from apps.common import qdrant_store
from apps.common.ai import get_embedding
from apps.encounters.models import Encounter


def find_similar_encounters(encounter: Encounter, top_k: int = 5) -> list[dict]:
    vector = get_embedding(encounter.embedding_text)

    matches = qdrant_store.search(
        vector=vector,
        top_k=top_k,
        query_filter={
            "consent_for_research": True,
            "specialty": encounter.specialty,
        },
        exclude_id=encounter.id,
    )
    if not matches:
        return []

    scores_by_id = {point_id: score for point_id, score in matches}
    matched_encounters = Encounter.objects.filter(id__in=scores_by_id.keys()).select_related(
        "patient", "clinician"
    )
    by_id = {e.id: e for e in matched_encounters}

    results = []
    for point_id, score in matches:
        match = by_id.get(point_id)
        if match is None:
            # Point exists in Qdrant but the Postgres row is gone (e.g. the
            # two stores briefly drifted) - skip rather than error.
            continue
        results.append(
            {
                "encounter_id": match.id,
                "score": round(float(score), 4),
                "specialty": match.specialty,
                "chief_complaint": match.chief_complaint,
                "diagnosis": match.diagnosis,
                "treatment": match.treatment,
                "clinician_id": match.clinician_id,
            }
        )
    return results
