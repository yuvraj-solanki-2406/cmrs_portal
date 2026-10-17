AGENT = "AGENT"
BRANCH_MANAGER = "BRANCH_MANAGER"
FINANCE = "FINANCE"
ADMIN = "ADMIN"

ROLE_DEFINITIONS = [
    (AGENT, "Collection Agent", "Collects repayments from assigned customers and submits cash to the branch."),
    (BRANCH_MANAGER, "Branch Manager", "Reconciles agent cash, records bank deposits, manages branch customers and loans."),
    (FINANCE, "Finance Officer", "Confirms or fails settlements across all branches."),
    (ADMIN, "Administrator", "Manages users and branches; read-only on financial transactions."),
]
BRANCH_BOUND_ROLES = (AGENT, BRANCH_MANAGER)
