from decimal import Decimal

from rest_framework import serializers

from apps.accounts.models import Branch, User
from apps.accounts.serializers import BranchSerializer

from .models import Customer, Loan
from .selectors import loan_summary

MAX_AMOUNT = Decimal("999999999.99")


class AgentRefSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "full_name"]
        read_only_fields = fields


class CustomerSerializer(serializers.ModelSerializer):
    branch = BranchSerializer(read_only=True)
    assigned_agent = AgentRefSerializer(read_only=True)

    class Meta:
        model = Customer
        fields = ["id", "customer_code", "full_name", "phone", "address", "branch", "assigned_agent",
                  "is_active", "created_at"]
        read_only_fields = fields


PHONE_RE = r"^[0-9]{10}$"
PHONE_MSG = "Mobile number must be exactly 10 digits."


class CustomerCreateSerializer(serializers.Serializer):
    full_name = serializers.CharField(max_length=150)
    phone = serializers.RegexField(PHONE_RE, error_messages={"invalid": PHONE_MSG})
    address = serializers.CharField(required=False, allow_blank=True, default="")
    branch = serializers.PrimaryKeyRelatedField(queryset=Branch.objects.filter(is_active=True), required=False, allow_null=True, default=None)
    assigned_agent = serializers.PrimaryKeyRelatedField(queryset=User.objects.select_related("role"), required=False, allow_null=True, default=None)


class CustomerUpdateSerializer(serializers.Serializer):
    full_name = serializers.CharField(max_length=150, required=False)
    phone = serializers.RegexField(PHONE_RE, required=False, error_messages={"invalid": PHONE_MSG})
    address = serializers.CharField(required=False, allow_blank=True)
    is_active = serializers.BooleanField(required=False)


class AssignAgentSerializer(serializers.Serializer):
    agent = serializers.PrimaryKeyRelatedField(queryset=User.objects.select_related("role"), allow_null=True)


class InstallmentSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    installment_no = serializers.IntegerField()
    due_date = serializers.DateField()
    amount_due = serializers.DecimalField(max_digits=14, decimal_places=2)
    amount_paid = serializers.DecimalField(max_digits=14, decimal_places=2)
    amount_remaining = serializers.DecimalField(max_digits=14, decimal_places=2)
    status = serializers.ChoiceField(choices=["PAID", "PARTIAL", "PENDING", "OVERDUE"])


class LoanSerializer(serializers.ModelSerializer):
    customer = serializers.SerializerMethodField()
    paid = serializers.SerializerMethodField()
    outstanding = serializers.SerializerMethodField()
    due_now = serializers.SerializerMethodField()

    class Meta:
        model = Loan
        fields = ["id", "loan_number", "customer", "principal", "total_payable", "installment_count", "frequency",
                  "start_date", "status", "paid", "outstanding", "due_now", "created_at"]
        read_only_fields = fields

    def get_customer(self, obj) -> dict:
        return {"id": obj.customer_id, "customer_code": obj.customer.customer_code, "full_name": obj.customer.full_name}

    def get_paid(self, obj) -> str:
        return str(loan_summary(obj)["paid"])

    def get_outstanding(self, obj) -> str:
        return str(loan_summary(obj)["outstanding"])

    def get_due_now(self, obj) -> str | None:
        """Amount due up to today and not yet paid (installments due so far minus paid, floored at 0)."""
        due = loan_summary(obj).get("due_now")
        return None if due is None else str(due)


class LoanCreateSerializer(serializers.Serializer):
    customer = serializers.IntegerField()
    principal = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal("0.01"), max_value=MAX_AMOUNT)
    total_payable = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal("0.01"), max_value=MAX_AMOUNT)
    installment_count = serializers.IntegerField(min_value=1, max_value=360)
    frequency = serializers.ChoiceField(choices=Loan.Frequency.choices)
    start_date = serializers.DateField()


class OutstandingSerializer(serializers.Serializer):
    total_payable = serializers.DecimalField(max_digits=14, decimal_places=2)
    paid = serializers.DecimalField(max_digits=14, decimal_places=2)
    outstanding = serializers.DecimalField(max_digits=14, decimal_places=2)
