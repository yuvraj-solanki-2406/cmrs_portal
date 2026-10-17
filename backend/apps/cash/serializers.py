import uuid
from decimal import Decimal

from rest_framework import serializers

from apps.collections.serializers import CollectionSerializer

from .models import CashSubmission, CashSubmissionItem


class SubmissionItemSerializer(serializers.ModelSerializer):
    receipt_number = serializers.CharField(source="collection.receipt_number")
    customer = serializers.CharField(source="collection.loan.customer.full_name")
    loan_number = serializers.CharField(source="collection.loan.loan_number")

    class Meta:
        model = CashSubmissionItem
        fields = ["id", "collection", "receipt_number", "customer", "loan_number", "amount", "is_active"]
        read_only_fields = fields


class SubmissionSerializer(serializers.ModelSerializer):
    agent = serializers.SerializerMethodField()
    branch = serializers.CharField(source="branch.code")
    reviewed_by = serializers.CharField(source="reviewed_by.username", default=None)
    item_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = CashSubmission
        fields = ["id", "reference_no", "agent", "branch", "submitted_at", "status", "expected_amount",
                  "received_amount", "discrepancy_amount", "discrepancy_reason", "reviewed_by", "reviewed_at",
                  "rejection_reason", "note", "item_count"]
        read_only_fields = fields

    def get_agent(self, obj) -> dict:
        return {"id": obj.agent_id, "username": obj.agent.username, "full_name": obj.agent.full_name}


class SubmissionDetailSerializer(SubmissionSerializer):
    items = SubmissionItemSerializer(many=True, read_only=True)

    class Meta(SubmissionSerializer.Meta):
        fields = SubmissionSerializer.Meta.fields + ["items"]
        read_only_fields = fields


class SubmitCashSerializer(serializers.Serializer):
    collection_ids = serializers.ListField(child=serializers.IntegerField(), allow_empty=False, max_length=500)
    note = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")


class ApproveSerializer(serializers.Serializer):
    received_amount = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal("0"),
                                               max_value=Decimal("999999999.99"))
    discrepancy_reason = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")


class RejectSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=255)


class PendingCollectionsSerializer(serializers.Serializer):
    collections = CollectionSerializer(many=True)
    count = serializers.IntegerField()
    total = serializers.DecimalField(max_digits=14, decimal_places=2)
    in_transit = serializers.DecimalField(max_digits=14, decimal_places=2)
    open_shortfall = serializers.DecimalField(max_digits=14, decimal_places=2)
