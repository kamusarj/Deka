import { Navigate, useLocation } from "react-router";
import { useAuth } from "../contexts/useAuth";
import { hasRoleCapability } from "../auth/rolePolicy";
import type { RoleCapability } from "../auth/rolePolicy";
import SessionRecovery from "./SessionRecovery";

interface ProtectedRouteProps {
  children: React.ReactNode;
  roles?: readonly string[];
  requiredCapability?: RoleCapability;
}

export default function ProtectedRoute({ children, roles, requiredCapability }: ProtectedRouteProps) {
  const { isAuthenticated, isLoading, sessionError, user } = useAuth();
  const location = useLocation();

  if (isLoading || sessionError) {
    return <SessionRecovery />;
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (user?.must_change_password && location.pathname !== "/account") {
    return <Navigate to="/account" replace />;
  }

  if (roles && user && !roles.includes(user.role)) {
    return <Navigate to="/dashboard" replace />;
  }

  if (requiredCapability && !hasRoleCapability(user?.role, requiredCapability)) {
    return <Navigate to="/dashboard" replace />;
  }

  return <>{children}</>;
}
