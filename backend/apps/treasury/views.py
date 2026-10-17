import django_filters
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts import roles
from apps.common.permissions import has_role

from . import selectors, services
from .models import BankDeposit, Settlement
from .serializers import (ConfirmSettlementSerializer, DepositDetailSerializer, DepositSerializer,
                          EligibleSubmissionSerializer, FailSettlementSerializer, RecordDepositSerializer)

READ_ROLES = (roles.BRANCH_MANAGER, roles.FINANCE, roles.ADMIN)


class DepositFilter(django_filters.FilterSet):
    status = django_filters.ChoiceFilter(field_name="settlement__status", choices=Settlement.Status.choices)
    delayed = django_filters.BooleanFilter(method="filter_delayed")
    date_from = django_filters.DateFilter(field_name="deposit_date", lookup_expr="gte")
    date_to = django_filters.DateFilter(field_name="deposit_date", lookup_expr="lte")

    class Meta:
        model = BankDeposit
        fields = ["branch", "bank_name"]

    def filter_delayed(self, queryset, name, value):
        return queryset.filter(selectors.delayed_q()) if value else queryset.exclude(selectors.delayed_q())


class DepositViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """No PATCH/PUT/DELETE: deposits are immutable; settlement changes only via the settlement actions."""

    serializer_class = DepositSerializer
    filterset_class = DepositFilter
    search_fields = ["deposit_no", "reference_number"]
    ordering_fields = ["id", "deposit_date", "amount"]

    def get_permissions(self):
        allowed = {"create": (roles.BRANCH_MANAGER,), "eligible_submissions": (roles.BRANCH_MANAGER,),
                   "confirm": (roles.FINANCE,), "fail": (roles.FINANCE,)}.get(self.action, READ_ROLES)
        return [p() for p in (*self.permission_classes, has_role(*allowed))]

    def get_queryset(self):
        return selectors.deposits_for(self.request.user)

    def get_serializer_class(self):
        return DepositDetailSerializer if self.action == "retrieve" else DepositSerializer

    def _detail(self, pk):
        return DepositDetailSerializer(self.get_queryset().prefetch_related("submissions__agent").get(pk=pk)).data

    @extend_schema(responses=EligibleSubmissionSerializer(many=True))
    @action(detail=False, methods=["get"], url_path="eligible-submissions", pagination_class=None)
    def eligible_submissions(self, request):
        return Response(EligibleSubmissionSerializer(selectors.eligible_submissions(request.user), many=True).data)

    @extend_schema(request=RecordDepositSerializer, responses={201: DepositDetailSerializer})
    def create(self, request, *args, **kwargs):
        serializer = RecordDepositSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        deposit = services.record_deposit(actor=request.user, **serializer.validated_data)
        return Response(self._detail(deposit.pk), status=status.HTTP_201_CREATED)

    @extend_schema(request=ConfirmSettlementSerializer, responses=DepositDetailSerializer)
    @action(detail=True, methods=["post"], url_path="settlement/confirm")
    def confirm(self, request, pk=None):
        serializer = ConfirmSettlementSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.confirm_settlement(actor=request.user, deposit_id=int(pk), **serializer.validated_data)
        return Response(self._detail(pk))

    @extend_schema(request=FailSettlementSerializer, responses=DepositDetailSerializer)
    @action(detail=True, methods=["post"], url_path="settlement/fail")
    def fail(self, request, pk=None):
        serializer = FailSettlementSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.fail_settlement(actor=request.user, deposit_id=int(pk), reason=serializer.validated_data["reason"])
        return Response(self._detail(pk))
