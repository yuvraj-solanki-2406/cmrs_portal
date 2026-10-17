from drf_spectacular.utils import extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts import roles
from apps.common.permissions import has_role

from . import selectors, services
from .models import Loan
from .serializers import (AssignAgentSerializer, CustomerCreateSerializer, CustomerSerializer,
                          CustomerUpdateSerializer, InstallmentSerializer, LoanCreateSerializer, LoanSerializer,
                          OutstandingSerializer)

READ_ROLES = (roles.AGENT, roles.BRANCH_MANAGER, roles.FINANCE, roles.ADMIN)
WRITE_ROLES = (roles.BRANCH_MANAGER, roles.ADMIN)


class CustomerViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin,
                      mixins.UpdateModelMixin, viewsets.GenericViewSet):
    serializer_class = CustomerSerializer
    filterset_fields = {"assigned_agent": ["exact"], "branch": ["exact"], "is_active": ["exact"]}
    search_fields = ["full_name", "customer_code", "phone"]
    ordering_fields = ["id", "full_name", "created_at"]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_permissions(self):
        allowed = READ_ROLES if self.action in ("list", "retrieve") else WRITE_ROLES
        return [p() for p in (*self.permission_classes, has_role(*allowed))]

    def get_queryset(self):
        return selectors.customers_for(self.request.user)

    @extend_schema(request=CustomerCreateSerializer, responses={201: CustomerSerializer})
    def create(self, request, *args, **kwargs):
        serializer = CustomerCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        customer = services.create_customer(actor=request.user, **serializer.validated_data)
        return Response(CustomerSerializer(customer).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=CustomerUpdateSerializer, responses={200: CustomerSerializer})
    def partial_update(self, request, *args, **kwargs):
        customer = self.get_object()
        serializer = CustomerUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        customer = services.update_customer(actor=request.user, customer=customer, **serializer.validated_data)
        return Response(CustomerSerializer(self.get_queryset().get(pk=customer.pk)).data)

    @extend_schema(request=AssignAgentSerializer, responses={200: CustomerSerializer})
    @action(detail=True, methods=["post"], url_path="assign-agent")
    def assign_agent(self, request, pk=None):
        customer = self.get_object()
        serializer = AssignAgentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.assign_agent(actor=request.user, customer=customer, agent=serializer.validated_data["agent"])
        return Response(CustomerSerializer(self.get_queryset().get(pk=customer.pk)).data)


class LoanViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet):
    """No update/delete: principal, total and schedule are fixed at creation."""

    serializer_class = LoanSerializer
    filterset_fields = {"status": ["exact"], "customer": ["exact"], "frequency": ["exact"],
                        "customer__branch": ["exact"], "customer__assigned_agent": ["exact"]}
    search_fields = ["loan_number", "customer__full_name", "customer__customer_code"]
    ordering_fields = ["id", "start_date", "total_payable"]

    def get_permissions(self):
        allowed = WRITE_ROLES if self.action == "create" else READ_ROLES
        return [p() for p in (*self.permission_classes, has_role(*allowed))]

    def get_queryset(self):
        qs = selectors.loans_for(self.request.user)
        if self.request.query_params.get("has_due") == "true":
            from django.db.models import F
            qs = qs.filter(status=Loan.Status.ACTIVE, due_to_date__gt=F("paid_amount"))
        return qs

    @extend_schema(request=LoanCreateSerializer, responses={201: LoanSerializer})
    def create(self, request, *args, **kwargs):
        serializer = LoanCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        # Out-of-scope customers must look nonexistent (404), not forbidden.
        customer = selectors.customers_for(request.user).filter(pk=data["customer"]).first()
        if customer is None:
            from apps.common.exceptions import NotFound
            raise NotFound("Customer not found.")
        loan = services.create_loan_with_schedule(actor=request.user, **{**data, "customer": customer})
        body = LoanSerializer(self.get_queryset().get(pk=loan.pk)).data
        body["installments"] = InstallmentSerializer(selectors.installment_statuses(loan), many=True).data
        return Response(body, status=status.HTTP_201_CREATED)

    @extend_schema(responses=InstallmentSerializer(many=True))
    @action(detail=True, methods=["get"], pagination_class=None)
    def installments(self, request, pk=None):
        loan = self.get_object()
        return Response(InstallmentSerializer(selectors.installment_statuses(loan), many=True).data)

    @extend_schema(responses=OutstandingSerializer)
    @action(detail=True, methods=["get"])
    def outstanding(self, request, pk=None):
        return Response(OutstandingSerializer(selectors.loan_summary(self.get_object())).data)
