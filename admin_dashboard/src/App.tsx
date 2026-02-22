import { useQuery } from "@tanstack/react-query";

import DashboardLayout from "./components/DashboardLayout";
import TokenGate from "./components/TokenGate";
import { adminApi } from "./api";
import { useToken } from "./state/token";
import type { AdminUserProfile } from "./types";

function App() {
  const { token, clearToken } = useToken();
  const hasToken = Boolean(token);

  const userQuery = useQuery<AdminUserProfile, Error>({
    queryKey: ["me", token],
    queryFn: () => adminApi.getCurrentUser(token as string),
    enabled: hasToken
  });

  if (!hasToken) {
    return <TokenGate />;
  }

  if (userQuery.isLoading) {
    return (
      <div className="dashboard-shell">
        <main className="section-container">
          <div className="card">Validating session…</div>
        </main>
      </div>
    );
  }

  if (userQuery.isError || !userQuery.data) {
    clearToken();
    return <TokenGate errorMessage="Session expired or invalid. Paste a new token." />;
  }

  return <DashboardLayout profile={userQuery.data} />;
}

export default App;
