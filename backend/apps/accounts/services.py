from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction

from apps.audit.services import record as audit_record
from apps.common.exceptions import ValidationFailed

from . import roles
from .models import Branch, Role, User


def _validate_role_branch(role: Role, branch: Branch | None):
    if role.code in roles.BRANCH_BOUND_ROLES and branch is None:
        raise ValidationFailed(f"A branch is required for role {role.code}.", details={"fields": {"branch": ["Required for this role."]}})
    if role.code not in roles.BRANCH_BOUND_ROLES and branch is not None:
        raise ValidationFailed(f"Role {role.code} must not be tied to a branch.", details={"fields": {"branch": ["Not allowed for this role."]}})
    if branch is not None and not branch.is_active:
        raise ValidationFailed("Branch is inactive.", details={"fields": {"branch": ["Inactive branch."]}})


@transaction.atomic
def create_user(*, actor: User, username: str, password: str, role: Role, branch: Branch | None = None,
                full_name: str = "", email: str = "") -> User:
    _validate_role_branch(role, branch)
    candidate = User(username=username, email=email, full_name=full_name, role=role, branch=branch)
    try:
        validate_password(password, candidate)
    except DjangoValidationError as exc:
        raise ValidationFailed("Password is too weak.", details={"fields": {"password": list(exc.messages)}}) from exc
    candidate.set_password(password)
    candidate.save()
    audit_record(actor=actor, action="USER_CREATED", entity=candidate,
                 after={"username": username, "role": role.code, "branch": branch.code if branch else None})
    return candidate


@transaction.atomic
def update_user(*, actor: User, user: User, role: Role | None = None, branch: Branch | None = None,
                branch_provided: bool = False, **fields) -> User:
    before = {"role": user.role.code, "branch": user.branch.code if user.branch else None,
              "is_active": user.is_active, "full_name": user.full_name, "email": user.email}
    new_role = role or user.role
    new_branch = branch if branch_provided else user.branch
    _validate_role_branch(new_role, new_branch)
    user.role, user.branch = new_role, new_branch
    for name, value in fields.items():
        setattr(user, name, value)
    user.save()
    after = {"role": user.role.code, "branch": user.branch.code if user.branch else None,
             "is_active": user.is_active, "full_name": user.full_name, "email": user.email}
    audit_record(actor=actor, action="USER_UPDATED", entity=user, before=before, after=after)
    return user


@transaction.atomic
def create_branch(*, actor: User, code: str, name: str) -> Branch:
    branch = Branch.objects.create(code=code.upper().strip(), name=name.strip())
    audit_record(actor=actor, action="BRANCH_CREATED", entity=branch, after={"code": branch.code, "name": branch.name})
    return branch
