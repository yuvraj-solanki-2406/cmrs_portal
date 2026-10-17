from decimal import Decimal

from rest_framework import serializers

from apps.common.money import ZERO

from .models import BankDeposit, BankName, Settlement
from .selectors import delayed_cutoff


class SettlementSerializer(serializers.ModelSerializer):
    confirmed_by = serializers.CharField(source="confirmed_by.username", default=None)

    class Meta:
        model = Settlement
        fields = ["status", "settled_amount", "settled_on", "bank_credit_reference", "variance_amount",
                  "variance_note", "failure_reason", "confirmed_by", "confirmed_at"]
        read_only_fields = fields


class DepositSubmissionSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    reference_no = serializers.CharField()
    agent = serializers.CharField(source="agent.username")
    received_amount = serializers.DecimalField(max_digits=14, decimal_places=2)
    discrepancy_amount = serializers.DecimalField(max_digits=14, decimal_places=2)


class DepositSerializer(serializers.ModelSerializer):
    branch = serializers.CharField(source="branch.code")
    created_by = serializers.CharField(source="created_by.username")
    settlement = SettlementSerializer(read_only=True)
    submission_count = serializers.IntegerField(read_only=True)
    is_delayed = serializers.SerializerMethodField()
    # reconciled - settled: what the branch reconciled minus what the bank finally credited (null until settled).
    gap_amount = serializers.SerializerMethodField()

    class Meta:
        model = BankDeposit
        fields = ["id", "deposit_no", "branch", "bank_name", "amount", "deposit_date", "reference_number",
                  "reconciled_amount", "variance_amount", "variance_note", "created_by", "created_at",
                  "submission_count", "settlement", "is_delayed", "gap_amount"]
        read_only_fields = fields

    def get_is_delayed(self, obj) -> bool:
        return obj.settlement.status == Settlement.Status.PENDING and obj.deposit_date < delayed_cutoff()

    def get_gap_amount(self, obj) -> str | None:
        settled = obj.settlement.settled_amount
        return None if settled is None else str(obj.reconciled_amount - settled)


class DepositDetailSerializer(DepositSerializer):
    submissions = DepositSubmissionSerializer(many=True, read_only=True)

    class Meta(DepositSerializer.Meta):
        fields = DepositSerializer.Meta.fields + ["submissions"]
        read_only_fields = fields


MONEY = dict(max_digits=14, decimal_places=2, max_value=Decimal("999999999.99"))


class RecordDepositSerializer(serializers.Serializer):
    submission_ids = serializers.ListField(child=serializers.IntegerField(), allow_empty=False, max_length=200)
    bank_name = serializers.ChoiceField(choices=BankName.choices)
    amount = serializers.DecimalField(min_value=Decimal("0.01"), **MONEY)
    deposit_date = serializers.DateField()
    reference_number = serializers.CharField(max_length=60)
    variance_note = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")


class ConfirmSettlementSerializer(serializers.Serializer):
    settled_amount = serializers.DecimalField(min_value=Decimal("0.01"), **MONEY)
    settled_on = serializers.DateField()
    variance_note = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    bank_credit_reference = serializers.CharField(max_length=60, required=False, allow_blank=True, default="")


class FailSettlementSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=255)


class EligibleSubmissionSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    reference_no = serializers.CharField()
    agent = serializers.CharField(source="agent.username")
    submitted_at = serializers.DateTimeField()
    expected_amount = serializers.DecimalField(max_digits=14, decimal_places=2)
    received_amount = serializers.DecimalField(max_digits=14, decimal_places=2)
    discrepancy_amount = serializers.DecimalField(max_digits=14, decimal_places=2)
