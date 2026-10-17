from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import auth_views
from .views import AgentListView, BranchViewSet, RoleViewSet, UserViewSet

router = DefaultRouter()
router.register("users", UserViewSet, basename="user")
router.register("branches", BranchViewSet, basename="branch")
router.register("roles", RoleViewSet, basename="role")

urlpatterns = [
    path("auth/login/", auth_views.LoginView.as_view(), name="auth-login"),
    path("auth/refresh/", auth_views.RefreshView.as_view(), name="auth-refresh"),
    path("auth/logout/", auth_views.LogoutView.as_view(), name="auth-logout"),
    path("auth/me/", auth_views.MeView.as_view(), name="auth-me"),
    path("agents/", AgentListView.as_view(), name="agent-list"),
    path("", include(router.urls)),
]
