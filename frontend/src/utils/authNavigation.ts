import type { Location } from "react-router";

type AuthLocationState = { from?: Pick<Location, "pathname" | "search" | "hash"> } | null;

export function getPostAuthPath(state: unknown): string {
  const from = (state as AuthLocationState)?.from;
  if (!from?.pathname || !from.pathname.startsWith("/") || from.pathname.startsWith("//")) {
    return "/dashboard";
  }
  if (from.pathname === "/login" || from.pathname === "/register") return "/dashboard";
  return `${from.pathname}${from.search ?? ""}${from.hash ?? ""}`;
}
