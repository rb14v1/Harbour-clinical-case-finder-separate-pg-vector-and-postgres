from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.encounters.models import Encounter
from apps.encounters.permissions import IsClinicianOrAdmin
from apps.encounters.serializers import EncounterSerializer
from apps.encounters.services.similarity import find_similar_encounters

DEFAULT_TOP_K = 5


class EncounterViewSet(viewsets.ModelViewSet):
    serializer_class = EncounterSerializer
    permission_classes = [permissions.IsAuthenticated, IsClinicianOrAdmin]
    filterset_fields = ["specialty", "consent_for_research"]

    def get_queryset(self):
        # A clinician only ever sees their own encounters directly (list,
        # retrieve, update, delete) - admins see every encounter. Similarity
        # search against OTHER clinicians' consented encounters is a
        # deliberate, separate exception handled by the `similar` action
        # below, never by widening this queryset.
        qs = Encounter.objects.select_related("patient", "clinician").all()
        if self.request.user.is_admin:
            return qs
        return qs.filter(clinician=self.request.user)

    def perform_create(self, serializer):
        serializer.save(clinician=self.request.user)

    @action(detail=True, methods=["get"])
    def similar(self, request, pk=None):
        encounter = self.get_object()

        try:
            top_k = int(request.query_params.get("top_k", DEFAULT_TOP_K))
        except ValueError:
            top_k = DEFAULT_TOP_K

        results = find_similar_encounters(encounter, top_k=top_k)
        return Response({"results": results})
