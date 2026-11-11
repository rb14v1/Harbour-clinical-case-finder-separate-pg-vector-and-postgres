import { NavLink, Outlet } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";

export function AppLayout() {
  const { user, logout } = useAuth();

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="app-header-title">Clinical Case Similarity Finder</div>
        <nav className="app-nav">
          <NavLink to="/" end>Encounters</NavLink>
          <NavLink to="/patients">Patients</NavLink>
        </nav>
        <div className="app-header-user">
          <span>{user?.full_name || user?.email} ({user?.role})</span>
          <button onClick={logout}>Log out</button>
        </div>
      </header>
      <main className="app-content">
        <Outlet />
      </main>
    </div>
  );
}
