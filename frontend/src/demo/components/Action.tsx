import type { ReactNode } from "react";
import { Link } from "react-router";

export default function Action({
  children,
  to,
  secondary = false,
}: {
  children: ReactNode;
  to: string;
  secondary?: boolean;
}) {
  return (
    <Link
      className={`demo-button${secondary ? " demo-button-secondary" : ""}`}
      to={to}
    >
      {children}
    </Link>
  );
}
