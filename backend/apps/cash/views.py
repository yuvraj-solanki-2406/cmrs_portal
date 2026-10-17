import django_filters
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts import roles
from apps.collections.serializers import CollectionSerializer, parse_idempotency_key
from apps.common.permissions import has_role

from . import selectors, services
from .models import CashSubmission
from .serializers import (ApproveSerializer, PendingCollectionsSerializer, RejectSerializer, SubmissionDetailSerializer,
                          SubmissionSerializer, SubmitCashSerializer)

IDEMPOTENCY_PARAM = OpenApiParameter("Idempotency-Key", OpenApiTypes.UUID, OpenApiParameter.HEADER, required=True)
READ_ROLES = (roles.AGENT, roles.BRANCH_MANAGER, roles.FINANCE, roles.ADMIN)


class SubmissionFilter(django_filters.FilterSet):
    date_from = django_filters.DateFilter(field_name="submitted_at", lookup_expr="date__gte")
    date_to = django_filters.DateFilter(field_name="submitted_at", lookup_expr="date__lte")

    class Meta:
        model = CashSubmission
        fields = ["agent", "branch", "status"]


class SubmissionViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """No PATCH/PUT/DELETE: a submission changes state only through the approve/reject actions."""

    serializer_class = SubmissionSerializer
    filterset_class = SubmissionFilter
    search_fields = ["reference_no", "agent__username", "agent__full_name"]
    ordering_fields = ["id", "submitted_at", "expected_amount"]

    def get_permissions(self):
        allowed = {"create": (roles.AGENT,), "pending_collections": (roles.AGENT,),
                   "approve": (roles.BRANCH_MANAGER,), "reject": (roles.BRANCH_MANAGER,)}.get(self.action, READ_ROLES)
        return [p() for p in (*self.permission_classes, has_role(*allowed))]

    def get_queryset(self):
        return selectors.submissions_for(self.request.user)

    def get_serializer_class(self):
        return SubmissionDetailSerializer if self.action == "retrieve" else SubmissionSerializer

    def _detail(self, pk):
        return SubmissionDetailSerializer(
            self.get_queryset().prefetch_related("items__collection__loan__customer").get(pk=pk)).data

    @extend_schema(responses=PendingCollectionsSerializer)
    @action(detail=False, methods=["get"], url_path="pending-collections")
    def pending_collections(self, request):
        """What this agent can submit now (cash held), plus in-transit and open-shortfall totals."""
        qs = selectors.eligible_collections(request.user)
        position = selectors.agent_cash_position(request.user)
        rows = list(qs)
        return Response({"collections": CollectionSerializer(rows, many=True).data, "count": len(rows),
                         "total": str(position["held"]), "in_transit": str(position["in_transit"]),
                         "open_shortfall": str(position["open_shortfall"])})

    @extend_schema(request=SubmitCashSerializer, parameters=[IDEMPOTENCY_PARAM],
                   responses={201: SubmissionDetailSerializer, 200: SubmissionDetailSerializer})
    def create(self, request, *args, **kwargs):
        key = parse_idempotency_key(request.META.get("HTTP_IDEMPOTENCY_KEY"))
        serializer = SubmitCashSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        submission, replayed = services.submit_cash(
            actor=request.user, collection_ids=serializer.validated_data["collection_ids"],
            idempotency_key=key, note=serializer.validated_data["note"])
        response = Response(self._detail(submission.pk), status=200 if replayed else status.HTTP_201_CREATED)
        if replayed:
            response["Idempotent-Replay"] = "true"
        return response

    @extend_schema(request=ApproveSerializer, responses=SubmissionDetailSerializer)
    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        serializer = ApproveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.approve_submission(actor=request.user, submission_id=int(pk), **serializer.validated_data)
        return Response(self._detail(pk))

    @extend_schema(request=RejectSerializer, responses=SubmissionDetailSerializer)
    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        serializer = RejectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.reject_submission(actor=request.user, submission_id=int(pk), reason=serializer.validated_data["reason"])
        return Response(self._detail(pk))
