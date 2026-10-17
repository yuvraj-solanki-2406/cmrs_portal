import uuid
from decimal import Decimal

from rest_framework import serializers

from .models import Collection


class CollectionSerializer(serializers.ModelSerializer):
    loan = serializers.SerializerMethodField()
    customer = serializers.SerializerMethodField()
    agent = serializers.SerializerMethodField()
    branch = serializers.CharField(source="branch.code", read_only=True)

    class Meta:
        model = Collection
        fields = ["id", "receipt_number", "loan", "customer", "agent", "branch", "amount", "collected_at",
                  "collection_date", "status", "note", "voided_at", "void_reason"]
        read_only_fields = fields

    def get_loan(self, obj) -> dict:
        return {"id": obj.loan_id, "loan_number": obj.loan.loan_number}

    def get_customer(self, obj) -> dict:
        c = obj.loan.customer
        return {"id": c.pk, "customer_code": c.customer_code, "full_name": c.full_name}

    def get_agent(self, obj) -> dict:
        return {"id": obj.agent_id, "username": obj.agent.username, "full_name": obj.agent.full_name}


class RecordRepaymentSerializer(serializers.Serializer):
    loan = serializers.IntegerField()
    amount = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal("0.01"),
                                      max_value=Decimal("999999999.99"))
    note = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    confirm_duplicate = serializers.BooleanField(required=False, default=False)


class VoidSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=255)


def parse_idempotency_key(raw: str | None) -> uuid.UUID:
    if not raw:
        raise serializers.ValidationError({"Idempotency-Key": ["This header is required (a UUID)."]})
    try:
        return uuid.UUID(raw)
    except ValueError as exc:
        raise serializers.ValidationError({"Idempotency-Key": ["Must be a valid UUID."]}) from exc
