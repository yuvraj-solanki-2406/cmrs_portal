import { api, type Paginated } from "@/lib/apiClient";
import type { RoleCode } from "@/lib/roles";
import type { Branch, User } from "@/features/auth/types";

export const listUsers = (page = 1) => api<Paginated<User>>("/users/", { query: { page } });
export const createUser = (body: {
  username: string; password: string; full_name: string; role: RoleCode; branch: number | null;
}) => api<User>("/users/", { method: "POST", body });
export const setUserActive = (id: number, is_active: boolean) =>
  api<User>(`/users/${id}/`, { method: "PATCH", body: { is_active } });

export const listBranches = () => api<Paginated<Branch>>("/branches/", { query: { page_size: 100 } });
export const createBranch = (body: { code: string; name: string }) => api<Branch>("/branches/", { method: "POST", body });
