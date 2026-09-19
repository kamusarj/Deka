export const DEMO_PASSWORD = "Demo@123456";

export const DEMO_ACCOUNTS = [
  { role: "super_admin", label: "Quản trị hệ thống", email: "superadmin@demo.smart-exam.test" },
  { role: "school_admin", label: "Quản trị trường", email: "schooladmin@demo.smart-exam.test" },
  { role: "teacher", label: "Giáo viên", email: "teacher@demo.smart-exam.test" },
  { role: "viewer", label: "Người xem", email: "viewer@demo.smart-exam.test" },
] as const;

export function isDemoLoginEnabled(): boolean {
  return import.meta.env.VITE_ENABLE_DEMO_LOGIN === "true";
}
