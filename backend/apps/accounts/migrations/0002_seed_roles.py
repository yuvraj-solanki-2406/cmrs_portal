from django.db import migrations

ROLES = [
    ("AGENT", "Collection Agent", "Collects repayments from assigned customers and submits cash to the branch."),
    ("BRANCH_MANAGER", "Branch Manager", "Reconciles agent cash, records bank deposits, manages branch customers and loans."),
    ("FINANCE", "Finance Officer", "Confirms or fails settlements across all branches."),
    ("ADMIN", "Administrator", "Manages users and branches; read-only on financial transactions."),
]


def seed_roles(apps, schema_editor):
    Role = apps.get_model("accounts", "Role")
    for code, name, description in ROLES:
        Role.objects.update_or_create(code=code, defaults={"name": name, "description": description})


class Migration(migrations.Migration):
    dependencies = [("accounts", "0001_initial")]
    operations = [migrations.RunPython(seed_roles, migrations.RunPython.noop)]
