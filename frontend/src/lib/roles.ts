export type RoleCode = "AGENT" | "BRANCH_MANAGER" | "FINANCE" | "ADMIN";

export const ROLE_LABELS: Record<RoleCode, string> = {
  AGENT: "Collection Agent",
  BRANCH_MANAGER: "Branch Manager",
  FINANCE: "Finance Officer",
  ADMIN: "Administrator",
};

export interface NavItem {
  label: string;
  href: string;
  roles: RoleCode[];
}

// Navigation is a usability aid only. The backend enforces every permission.
export const NAV_ITEMS: NavItem[] = [
  { label: "Dashboard", href: "/dashboard", roles: ["AGENT", "BRANCH_MANAGER", "FINANCE", "ADMIN"] },
  { label: "Today", href: "/today", roles: ["AGENT"] },
  { label: "Customers", href: "/customers", roles: ["AGENT", "BRANCH_MANAGER", "FINANCE", "ADMIN"] },
  { label: "Collections", href: "/collections", roles: ["AGENT", "BRANCH_MANAGER", "FINANCE", "ADMIN"] },
  { label: "Cash Holding", href: "/cash", roles: ["AGENT"] },
  { label: "Submissions", href: "/submissions", roles: ["AGENT", "BRANCH_MANAGER", "FINANCE", "ADMIN"] },
  { label: "Deposits", href: "/deposits", roles: ["BRANCH_MANAGER", "FINANCE", "ADMIN"] },
  { label: "Discrepancies", href: "/reports/discrepancies", roles: ["BRANCH_MANAGER", "FINANCE", "ADMIN"] },
  { label: "Mismatches", href: "/reports/mismatches", roles: ["BRANCH_MANAGER", "FINANCE", "ADMIN"] },
  { label: "Audit log", href: "/audit", roles: ["BRANCH_MANAGER", "FINANCE", "ADMIN"] },
  { label: "Users", href: "/admin/users", roles: ["ADMIN"] },
  { label: "Branches", href: "/admin/branches", roles: ["ADMIN"] },
];

export function navFor(role: RoleCode): NavItem[] {
  return NAV_ITEMS.filter((item) => item.roles.includes(role)).map((item) =>
    role === "AGENT" && item.href === "/customers" ? { ...item, label: "My Customers" }
      : role === "AGENT" && item.href === "/collections" ? { ...item, label: "My Collections" }
      : role === "AGENT" && item.href === "/submissions" ? { ...item, label: "My Submissions" }
      : role === "BRANCH_MANAGER" && item.href === "/submissions" ? { ...item, label: "Reconciliation" }
      : role === "FINANCE" && item.href === "/deposits" ? { ...item, label: "Settlements" } : item,
  );
}

// Routes reachable without a nav entry (detail pages).
export const EXTRA_ROUTES: { prefix: string; roles: RoleCode[] }[] = [
  { prefix: "/loans", roles: ["AGENT", "BRANCH_MANAGER", "FINANCE", "ADMIN"] },
  { prefix: "/trace", roles: ["AGENT", "BRANCH_MANAGER", "FINANCE", "ADMIN"] },
];

export const canManageLending = (role: RoleCode) => role === "BRANCH_MANAGER" || role === "ADMIN";
