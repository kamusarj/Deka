export const DEMO_PASSWORD = "Demo@123456";

export const DEMO_ACCOUNTS = [
  { role: "super_admin", label: "Quản trị hệ thống", email: "superadmin@demo.deka.test" },
  { role: "school_admin", label: "Quản trị trường", email: "schooladmin@demo.deka.test" },
  { role: "teacher", label: "Giáo viên", email: "teacher@demo.deka.test" },
  { role: "viewer", label: "Người xem", email: "viewer@demo.deka.test" },
] as const;

export function isDemoLoginEnabled(): boolean {
  return import.meta.env.VITE_ENABLE_DEMO_LOGIN === "true";
}
