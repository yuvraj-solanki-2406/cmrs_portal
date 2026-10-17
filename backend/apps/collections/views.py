import django_filters
from django.db.models import Count, Sum
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import generics, mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts import roles
from apps.common.permissions import has_role
from apps.lending.selectors import loans_for

from . import selectors, services
from .models import Collection
from .serializers import CollectionSerializer, RecordRepaymentSerializer, VoidSerializer, parse_idempotency_key

IDEMPOTENCY_PARAM = OpenApiParameter("Idempotency-Key", OpenApiTypes.UUID, OpenApiParameter.HEADER, required=True)
READ_ROLES = (roles.AGENT, roles.BRANCH_MANAGER, roles.FINANCE, roles.ADMIN)


class CollectionFilter(django_filters.FilterSet):
    date_from = django_filters.DateFilter(field_name="collection_date", lookup_expr="gte")
    date_to = django_filters.DateFilter(field_name="collection_date", lookup_expr="lte")

    class Meta:
        model = Collection
        fields = ["agent", "branch", "status", "loan"]


class CollectionViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = CollectionSerializer
    filterset_class = CollectionFilter
    search_fields = ["receipt_number", "loan__loan_number", "loan__customer__full_name"]
    ordering_fields = ["id", "collected_at", "amount"]

    def get_permissions(self):
        allowed = {"create": (roles.AGENT,), "void": (roles.BRANCH_MANAGER,)}.get(self.action, READ_ROLES)
        return [p() for p in (*self.permission_classes, has_role(*allowed))]

    def get_queryset(self):
        return selectors.collections_for(self.request.user)

    @extend_schema(request=RecordRepaymentSerializer, parameters=[IDEMPOTENCY_PARAM],
                   responses={201: CollectionSerializer, 200: CollectionSerializer})
    def create(self, request, *args, **kwargs):
        key = parse_idempotency_key(request.META.get("HTTP_IDEMPOTENCY_KEY"))
        serializer = RecordRepaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        collection, replayed = services.record_repayment(
            actor=request.user, loan_id=data["loan"], amount=data["amount"], idempotency_key=key,
            note=data["note"], confirm_duplicate=data["confirm_duplicate"])
        body = CollectionSerializer(self.get_queryset().get(pk=collection.pk)).data
        response = Response(body, status=status.HTTP_200_OK if replayed else status.HTTP_201_CREATED)
        if replayed:
            response["Idempotent-Replay"] = "true"
        return response

    @extend_schema(request=VoidSerializer, responses=CollectionSerializer)
    @action(detail=True, methods=["post"])
    def void(self, request, pk=None):
        serializer = VoidSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        collection = services.void_collection(actor=request.user, collection_id=int(pk),
                                              reason=serializer.validated_data["reason"])
        return Response(CollectionSerializer(self.get_queryset().get(pk=collection.pk)).data)

    @extend_schema(responses=inline_serializer("CollectionSummary", {
        "count": serializers.IntegerField(), "total_amount": serializers.DecimalField(max_digits=14, decimal_places=2)}))
    @action(detail=False, methods=["get"])
    def summary(self, request):
        """Totals over the same filters as the list (VALID collections only)."""
        qs = self.filter_queryset(self.get_queryset()).filter(status=Collection.Status.VALID)
        agg = qs.aggregate(count=Count("id"), total=Sum("amount"))
        return Response({"count": agg["count"], "total_amount": str(agg["total"] or "0.00")})


class LoanRepaymentsView(generics.ListAPIView):
    """GET /loans/{id}/repayments/ — repayment history of one loan (scoped via the loan)."""

    serializer_class = CollectionSerializer
    permission_classes = [has_role(*READ_ROLES)]
    pagination_class = None

    def get_queryset(self):
        from django.http import Http404
        if getattr(self, "swagger_fake_view", False):
            return Collection.objects.none()
        if not loans_for(self.request.user).filter(pk=self.kwargs["loan_id"]).exists():
            raise Http404
        return Collection.objects.select_related("loan", "loan__customer", "agent", "branch").filter(
            loan_id=self.kwargs["loan_id"]).order_by("-collected_at", "-id")
