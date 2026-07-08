import { AdminDashboard } from "./components/admin/AdminDashboard";
import { AdminLogin } from "./components/admin/AdminLogin";
import { useAdminAuth } from "./hooks/useAdminAuth";

export default function AdminApp() {
  const { credentials, isAuthenticated, login, logout } = useAdminAuth();

  if (!isAuthenticated || !credentials) {
    return <AdminLogin onLogin={login} />;
  }

  return <AdminDashboard credentials={credentials} onLogout={logout} />;
}
