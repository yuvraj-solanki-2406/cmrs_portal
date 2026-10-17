from drf_spectacular.utils import extend_schema
from rest_framework import generics, mixins, status, viewsets
from rest_framework.response import Response

from apps.accounts import roles
from apps.common.permissions import IsAdmin, has_role

from . import services
from .models import Branch, Role, User
from .serializers import (BranchSerializer, RoleSerializer, UserCreateSerializer, UserSerializer,
                          UserUpdateSerializer)


class BranchViewSet(viewsets.ModelViewSet):
    """Any authenticated user may read branches (needed for filters); only ADMIN may write."""

    queryset = Branch.objects.all()
    serializer_class = BranchSerializer
    filterset_fields = ["is_active"]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return super().get_permissions()
        return [IsAdmin()]

    def perform_create(self, serializer):
        serializer.instance = services.create_branch(actor=self.request.user, **serializer.validated_data)

    def perform_update(self, serializer):
        from apps.audit.services import record
        before = {"name": serializer.instance.name, "is_active": serializer.instance.is_active}
        instance = serializer.save()
        record(actor=self.request.user, action="BRANCH_UPDATED", entity=instance, before=before,
               after={"name": instance.name, "is_active": instance.is_active})


class RoleViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    queryset = Role.objects.all()
    serializer_class = RoleSerializer
    permission_classes = [IsAdmin]
    pagination_class = None


class UserViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin,
                  mixins.UpdateModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsAdmin]
    queryset = User.objects.select_related("role", "branch").order_by("username")
    filterset_fields = {"role__code": ["exact"], "branch": ["exact"], "is_active": ["exact"]}
    search_fields = ["username", "full_name"]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_serializer_class(self):
        if self.action == "create":
            return UserCreateSerializer
        if self.action in ("update", "partial_update"):
            return UserUpdateSerializer
        return UserSerializer

    @extend_schema(request=UserCreateSerializer, responses={201: UserSerializer})
    def create(self, request, *args, **kwargs):
        serializer = UserCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = services.create_user(actor=request.user, **serializer.validated_data)
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=UserUpdateSerializer, responses={200: UserSerializer})
    def partial_update(self, request, *args, **kwargs):
        user = self.get_object()
        serializer = UserUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        branch_provided = "branch" in data
        branch = data.pop("branch", None)
        role = data.pop("role", None)
        user = services.update_user(actor=request.user, user=user, role=role, branch=branch,
                                    branch_provided=branch_provided, **data)
        return Response(UserSerializer(user).data)

    def update(self, request, *args, **kwargs):
        return self.partial_update(request, *args, **kwargs)


class AgentListView(generics.ListAPIView):
    """Active agents for pickers/filters. MANAGER: own branch only. ADMIN/FINANCE: any (?branch=)."""

    serializer_class = UserSerializer
    permission_classes = [has_role(roles.BRANCH_MANAGER, roles.ADMIN, roles.FINANCE)]
    pagination_class = None
    filterset_fields = {"branch": ["exact"]}

    def get_queryset(self):
        qs = User.objects.select_related("role", "branch").filter(role__code=roles.AGENT, is_active=True)
        if getattr(self.request.user, "role_code", None) == roles.BRANCH_MANAGER:
            qs = qs.filter(branch_id=self.request.user.branch_id)
        return qs.order_by("username")
