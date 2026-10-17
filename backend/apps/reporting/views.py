from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import generics, serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import roles
from apps.cash.selectors import submissions_for
from apps.cash.views import SubmissionFilter
from apps.collections.selectors import collections_for
from apps.collections.views import CollectionFilter
from apps.common.exceptions import NotFound
from apps.common.permissions import has_role
from apps.treasury.selectors import deposits_for
from apps.treasury.views import DepositFilter

from . import selectors, trace
from .csvutil import csv_response
from .filters import FilterParamsSerializer, resolve_filters

ALL = (roles.AGENT, roles.BRANCH_MANAGER, roles.FINANCE, roles.ADMIN)
OVERSIGHT = (roles.BRANCH_MANAGER, roles.FINANCE, roles.ADMIN)
FILTER_DOC = [OpenApiParameter(n, required=False) for n in ("date_from", "date_to", "branch", "agent", "stage")]


class SummaryView(APIView):
    permission_classes = [has_role(*ALL)]

    @extend_schema(parameters=FILTER_DOC, responses=inline_serializer("DashboardSummary", {
        "metrics": serializers.DictField(), "funnel": serializers.ListField(), "attribution": serializers.CharField()}))
    def get(self, request):
        return Response(selectors.summary(resolve_filters(request.user, request.query_params)))


class StageRecordsView(APIView):
    permission_classes = [has_role(*ALL)]

    @extend_schema(parameters=FILTER_DOC, responses=inline_serializer("StageRecords", {
        "stage": serializers.CharField(), "total": serializers.IntegerField(), "truncated": serializers.BooleanField(),
        "rows": serializers.ListField()}))
    def get(self, request):
        f = resolve_filters(request.user, request.query_params)
        if not f.stage:
            from apps.common.exceptions import ValidationFailed
            raise ValidationFailed("stage is required.", details={"fields": {"stage": ["Required."]}})
        return Response(selectors.stage_records(f))


class BranchSummaryView(APIView):
    permission_classes = [has_role(*OVERSIGHT)]

    @extend_schema(parameters=FILTER_DOC, responses=inline_serializer("BranchSummary", {"branches": serializers.ListField()}))
    def get(self, request):
        return Response({"branches": selectors.branch_summary(resolve_filters(request.user, request.query_params))})


class DiscrepancySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    reference_no = serializers.CharField()
    agent = serializers.CharField(source="agent.username")
    branch = serializers.CharField(source="branch.code")
    reviewed_at = serializers.DateTimeField()
    reviewed_by = serializers.CharField(source="reviewed_by.username")
    expected_amount = serializers.DecimalField(max_digits=14, decimal_places=2)
    received_amount = serializers.DecimalField(max_digits=14, decimal_places=2)
    discrepancy_amount = serializers.DecimalField(max_digits=14, decimal_places=2)
    discrepancy_reason = serializers.CharField()


class DiscrepancyReportView(generics.ListAPIView):
    permission_classes = [has_role(*OVERSIGHT)]
    serializer_class = DiscrepancySerializer
    filter_backends: list = []

    @extend_schema(parameters=FILTER_DOC)
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        return selectors.discrepancy_rows(resolve_filters(self.request.user, self.request.query_params))


class MismatchReportView(APIView):
    permission_classes = [has_role(*OVERSIGHT)]

    @extend_schema(parameters=FILTER_DOC, responses=inline_serializer("MismatchReport", {"rows": serializers.ListField()}))
    def get(self, request):
        return Response({"rows": selectors.mismatch_rows(resolve_filters(request.user, request.query_params))})


class LifecycleView(APIView):
    permission_classes = [has_role(*ALL)]

    @extend_schema(responses=inline_serializer("Lifecycle", {
        "root": serializers.DictField(), "collections": serializers.ListField(), "submissions": serializers.ListField(),
        "deposits": serializers.ListField(), "timeline": serializers.ListField()}))
    def get(self, request, kind, pk):
        return Response(trace.build(request.user, kind, pk))


# ---- CSV exports (same scope + filters as the matching list endpoints) -----------------------

class _CsvView(APIView):
    permission_classes = [has_role(*ALL)]
    filename = "export.csv"

    @extend_schema(responses={(200, "text/csv"): bytes})
    def get(self, request):
        return self.build(request)


class CollectionsCsv(_CsvView):
    permission_classes = [has_role(*ALL)]

    def build(self, request):
        qs = CollectionFilter(request.query_params, queryset=collections_for(request.user)).qs.order_by("id")
        return csv_response("collections.csv",
                            ["receipt_number", "date", "branch", "agent", "customer", "loan_number", "amount", "status", "note"],
                            ([c.receipt_number, c.collection_date, c.branch.code, c.agent.username, c.loan.customer.full_name,
                              c.loan.loan_number, c.amount, c.status, c.note] for c in qs))


class SubmissionsCsv(_CsvView):
    def build(self, request):
        qs = SubmissionFilter(request.query_params, queryset=submissions_for(request.user)).qs.order_by("id")
        return csv_response("submissions.csv",
                            ["reference_no", "submitted_at", "branch", "agent", "status", "expected", "received", "discrepancy",
                             "discrepancy_reason", "reviewed_by", "rejection_reason"],
                            ([s.reference_no, s.submitted_at.isoformat(), s.branch.code, s.agent.username, s.status,
                              s.expected_amount, s.received_amount, s.discrepancy_amount, s.discrepancy_reason,
                              s.reviewed_by.username if s.reviewed_by else "", s.rejection_reason] for s in qs))


class DepositsCsv(_CsvView):
    permission_classes = [has_role(*OVERSIGHT)]

    def build(self, request):
        qs = DepositFilter(request.query_params, queryset=deposits_for(request.user)).qs.order_by("id")
        return csv_response("deposits.csv",
                            ["deposit_no", "deposit_date", "branch", "bank", "reference", "reconciled", "deposited", "variance",
                             "variance_note", "settlement_status", "settled_amount", "settled_on", "settlement_variance"],
                            ([d.deposit_no, d.deposit_date, d.branch.code, d.bank_name, d.reference_number, d.reconciled_amount,
                              d.amount, d.variance_amount, d.variance_note, d.settlement.status, d.settlement.settled_amount,
                              d.settlement.settled_on, d.settlement.variance_amount] for d in qs))


class DiscrepanciesCsv(_CsvView):
    permission_classes = [has_role(*OVERSIGHT)]

    def build(self, request):
        qs = selectors.discrepancy_rows(resolve_filters(request.user, request.query_params))
        return csv_response("discrepancies.csv",
                            ["reference_no", "reviewed_at", "branch", "agent", "reviewed_by", "expected", "received",
                             "discrepancy", "reason"],
                            ([s.reference_no, s.reviewed_at.isoformat(), s.branch.code, s.agent.username, s.reviewed_by.username,
                              s.expected_amount, s.received_amount, s.discrepancy_amount, s.discrepancy_reason] for s in qs))


class MismatchesCsv(_CsvView):
    permission_classes = [has_role(*OVERSIGHT)]

    def build(self, request):
        rows = selectors.mismatch_rows(resolve_filters(request.user, request.query_params))
        return csv_response("mismatches.csv",
                            ["type", "deposit_no", "branch", "date", "expected", "actual", "difference", "reason", "settlement_status"],
                            ([r["type"], r["deposit_no"], r["branch"], r["date"], r["expected"], r["actual"], r["difference"],
                              r["reason"], r["settlement_status"]] for r in rows))
