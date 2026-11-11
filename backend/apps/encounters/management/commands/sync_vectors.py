"""
Recovery path for the two-database architecture used by this app (see
apps/common/qdrant_store.py and apps/encounters/signals.py): Postgres and
Qdrant have no shared transaction, and Qdrant's data is not backed up the
same way Postgres's is in most deployments. If the Qdrant container/volume
is ever lost while Postgres survives, this command re-embeds and re-upserts
every existing Encounter row into Qdrant from scratch. Idempotent - safe to
run at any time, e.g. on a schedule or after restoring Qdrant from empty.
"""
from django.core.management.base import BaseCommand

from apps.common import qdrant_store
from apps.common.ai import get_embedding
from apps.encounters.models import Encounter


class Command(BaseCommand):
    help = "Re-embed and re-upsert every Encounter row into Qdrant from scratch."

    def handle(self, *args, **options):
        qdrant_store.ensure_collection()

        count = 0
        for encounter in Encounter.objects.all().iterator():
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
            count += 1

        self.stdout.write(self.style.SUCCESS(f"Synced {count} encounter(s) to Qdrant."))
