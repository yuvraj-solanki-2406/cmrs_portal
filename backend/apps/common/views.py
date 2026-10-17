from django.http import JsonResponse

from .middleware import get_request_id


def _wants_json(request) -> bool:
    return request.path.startswith("/api/")


def not_found(request, exception=None):
    if _wants_json(request):
        return JsonResponse({"code": "NOT_FOUND", "message": "Not found.", "details": {}, "request_id": get_request_id()}, status=404)
    return JsonResponse({"code": "NOT_FOUND", "message": "Not found."}, status=404)


def server_error(request):
    """Generic body only: no exception text, no stack trace. The request id lets support find the log entry."""
    return JsonResponse({"code": "SERVER_ERROR", "message": "An unexpected error occurred.", "details": {},
                         "request_id": get_request_id()}, status=500)
