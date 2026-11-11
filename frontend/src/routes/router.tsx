import { createBrowserRouter, Navigate } from "react-router-dom";

import { ProtectedRoute } from "../auth/ProtectedRoute";
import { EncounterDetailPage } from "../features/encounters/EncounterDetailPage";
import { EncountersPage } from "../features/encounters/EncountersPage";
import { PatientsPage } from "../features/patients/PatientsPage";
import { AppLayout } from "../layouts/AppLayout";
import { LoginPage } from "../pages/LoginPage";
import { RegisterPage } from "../pages/RegisterPage";

export const router = createBrowserRouter([
  { path: "/login", element: <LoginPage /> },
  { path: "/register", element: <RegisterPage /> },
  {
    element: <ProtectedRoute />,
    children: [
      {
        element: <AppLayout />,
        children: [
          { path: "/", element: <EncountersPage /> },
          { path: "/encounters/:id", element: <EncounterDetailPage /> },
          { path: "/patients", element: <PatientsPage /> },
        ],
      },
    ],
  },
  { path: "*", element: <Navigate to="/" replace /> },
]);
