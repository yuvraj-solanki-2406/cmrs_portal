import type { RoleCode } from "@/lib/roles";

export interface Branch {
  id: number;
  code: string;
  name: string;
  is_active: boolean;
}

export interface User {
  id: number;
  username: string;
  full_name: string;
  email: string;
  role: RoleCode;
  branch: Branch | null;
  is_active: boolean;
}
