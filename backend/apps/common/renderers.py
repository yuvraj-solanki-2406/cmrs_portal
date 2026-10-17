from decimal import Decimal

from rest_framework.renderers import JSONRenderer
from rest_framework.utils.encoders import JSONEncoder


class DecimalStringEncoder(JSONEncoder):
    """DRF's default encoder turns Decimal into float for non-serializer data. Money must stay a string."""

    def default(self, obj):
        if isinstance(obj, Decimal):
            return format(obj, "f")
        return super().default(obj)


class MoneySafeJSONRenderer(JSONRenderer):
    encoder_class = DecimalStringEncoder
