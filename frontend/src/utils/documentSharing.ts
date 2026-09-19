import type { DocumentResponse } from "../types";

export function documentSharingLabel(document: DocumentResponse): string {
  if (document.sharing_scope === "school") return "Trong trường";
  if (document.sharing_scope === "system") {
    if (document.sharing_status === "approved") return "Toàn hệ thống";
    if (document.sharing_status === "pending") return "Toàn hệ thống · chờ duyệt";
    if (document.sharing_status === "rejected") return "Toàn hệ thống · chưa được duyệt";
  }
  return "Cá nhân";
}
