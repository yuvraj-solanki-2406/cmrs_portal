from django.conf import settings
from django.contrib.auth import authenticate
from drf_spectacular.utils import OpenApiResponse, extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from apps.audit.services import record as audit_record
from apps.common.exceptions import NotAllowed

from .models import User
from .serializers import LoginSerializer, UserSerializer

TokenResponse = inline_serializer("TokenResponse", {"access": serializers.CharField(), "user": UserSerializer()})


def _set_refresh_cookie(response: Response, refresh: RefreshToken):
    response.set_cookie(
        settings.REFRESH_COOKIE_NAME,
        str(refresh),
        max_age=int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds()),
        httponly=True,
        secure=settings.REFRESH_COOKIE_SECURE,
        samesite="Lax",
        path=settings.REFRESH_COOKIE_PATH,
    )
    # Non-secret presence flag so the Next.js proxy can redirect unauthenticated page loads.
    # Carries no credentials; real authorization is always enforced by the backend.
    response.set_cookie(
        settings.SESSION_FLAG_COOKIE_NAME,
        "1",
        max_age=int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds()),
        httponly=True,
        secure=settings.REFRESH_COOKIE_SECURE,
        samesite="Lax",
        path="/",
    )


def _clear_refresh_cookie(response: Response):
    response.delete_cookie(settings.REFRESH_COOKIE_NAME, path=settings.REFRESH_COOKIE_PATH, samesite="Lax")
    response.delete_cookie(settings.SESSION_FLAG_COOKIE_NAME, path="/", samesite="Lax")


def _require_client_header(request):
    # Cross-site form posts cannot set custom headers, so this blocks CSRF on cookie-based endpoints.
    if not request.META.get(settings.CSRF_GUARD_HEADER):
        raise NotAllowed("Missing X-CMRS-Client header.", code="CSRF_GUARD")


class LoginView(APIView):
    authentication_classes: list = []
    permission_classes = [AllowAny]
    throttle_scope = "login"

    @extend_schema(request=LoginSerializer, responses={200: TokenResponse}, tags=["auth"])
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = authenticate(request, username=serializer.validated_data["username"],
                            password=serializer.validated_data["password"])
        if user is None or not user.is_active:
            from rest_framework.exceptions import AuthenticationFailed
            raise AuthenticationFailed("Invalid username or password.")
        refresh = RefreshToken.for_user(user)
        audit_record(actor=user, action="LOGIN", entity=user)
        response = Response({"access": str(refresh.access_token), "user": UserSerializer(user).data})
        _set_refresh_cookie(response, refresh)
        return response


class RefreshView(APIView):
    authentication_classes: list = []
    permission_classes = [AllowAny]
    throttle_scope = "refresh"

    @extend_schema(request=None, responses={200: TokenResponse, 401: OpenApiResponse(description="No/invalid refresh cookie")}, tags=["auth"])
    def post(self, request):
        _require_client_header(request)
        from rest_framework.exceptions import AuthenticationFailed
        raw = request.COOKIES.get(settings.REFRESH_COOKIE_NAME)
        if not raw:
            raise AuthenticationFailed("No refresh token.")
        try:
            old = RefreshToken(raw)
            user = User.objects.select_related("role", "branch").get(pk=old["user_id"])
            if not user.is_active:
                raise AuthenticationFailed("User is inactive.")
            old.blacklist()
            new_refresh = RefreshToken.for_user(user)
        except (TokenError, User.DoesNotExist) as exc:
            raise AuthenticationFailed("Invalid refresh token.") from exc
        response = Response({"access": str(new_refresh.access_token), "user": UserSerializer(user).data})
        _set_refresh_cookie(response, new_refresh)
        return response


class LogoutView(APIView):
    authentication_classes: list = []
    permission_classes = [AllowAny]

    @extend_schema(request=None, responses={204: None}, tags=["auth"])
    def post(self, request):
        _require_client_header(request)
        raw = request.COOKIES.get(settings.REFRESH_COOKIE_NAME)
        if raw:
            try:
                RefreshToken(raw).blacklist()
            except TokenError:
                pass
        response = Response(status=204)
        _clear_refresh_cookie(response)
        return response


class MeView(APIView):
    @extend_schema(responses=UserSerializer, tags=["auth"])
    def get(self, request):
        return Response(UserSerializer(request.user).data)
