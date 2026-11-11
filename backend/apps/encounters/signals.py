"""
Keeps Qdrant in sync with Postgres writes to `Encounter`.

*** ARCHITECTURE NOTE ***: Postgres and Qdrant are two separate databases
with no shared transaction. On save, we therefore wait for
`transaction.on_commit` before touching Qdrant, so a vector is never written
for a Postgres write that later rolls back. On delete there is no such risk
(the row is already gone), so `post_delete` fires the Qdrant delete inline.

If Qdrant is briefly unreachable, these handlers log a warning and swallow
the error rather than raising - a failed request shouldn't result from a
Postgres write that otherwise succeeded. The recovery path for any encounter
that drifted out of sync this way is `python manage.py sync_vectors`.
"""
import logging

from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.common import qdrant_store
from apps.common.ai import get_embedding
from apps.encounters.models import Encounter

logger = logging.getLogger(__name__)


def _sync_encounter_to_qdrant(encounter_id: int) -> None:
    try:
        encounter = Encounter.objects.get(pk=encounter_id)
    except Encounter.DoesNotExist:
        # Deleted again (or in another transaction) before this ran - the
        # post_delete handler below will have already removed the point.
        return

    try:
        vector = get_embedding(encounter.embedding_text)
        qdrant_store.upsert_point(
            point_id=encounter.id,
            vector=vector,
            payload={
                "specialty": encounter.specialty,
                "consent_for_research": encounter.consent_for_research,
                "clinician_id": encounter.clinician_id,
            },
        )
    except Exception:
        logger.warning(
            "Failed to upsert encounter %s into Qdrant - it will be out of "
            "sync until `manage.py sync_vectors` is run.",
            encounter_id,
            exc_info=True,
        )


@receiver(post_save, sender=Encounter)
def encounter_saved(sender, instance, **kwargs):
    transaction.on_commit(lambda: _sync_encounter_to_qdrant(instance.pk))


@receiver(post_delete, sender=Encounter)
def encounter_deleted(sender, instance, **kwargs):
    try:
        qdrant_store.delete_point(instance.pk)
    except Exception:
        logger.warning(
            "Failed to delete Qdrant point for encounter %s.",
            instance.pk,
            exc_info=True,
        )
