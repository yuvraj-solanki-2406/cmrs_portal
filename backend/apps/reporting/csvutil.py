import csv
import re
from decimal import Decimal

from django.http import HttpResponse

_NUMERIC = re.compile(r"^-?\d+(\.\d+)?$")


def safe_cell(value):
    """Neutralise spreadsheet formula injection: text starting with = + - @ gets a leading apostrophe.
    Genuine numbers (including negatives like -500.00) are left untouched."""
    if value is None:
        return ""
    if isinstance(value, (int, Decimal)):
        return str(value)
    text = str(value)
    if text and text[0] in "=+-@\t\r" and not _NUMERIC.match(text):
        return "'" + text
    return text


def csv_response(filename: str, header: list[str], rows) -> HttpResponse:
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    writer = csv.writer(response)
    writer.writerow(header)
    for row in rows:
        writer.writerow([safe_cell(v) for v in row])
    return response
