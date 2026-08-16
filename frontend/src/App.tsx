import React, { useEffect } from 'react';
import { Routes, Route, Navigate, useNavigate, useLocation } from 'react-router-dom';
import { useAuthStore } from './stores/authStore';
import { AppShell } from './components/layout/AppShell';
import { LoginPage } from './pages/LoginPage';
import { ChatPage } from './pages/ChatPage';
import { ReportsPage } from './pages/ReportsPage';
import { TrendsPage } from './pages/TrendsPage';
import { CareGapPage } from './pages/CareGapPage';
import { CoveragePage } from './pages/CoveragePage';
import { AdminPage } from './pages/AdminPage';
import { EcgLoader } from './components/common/EcgLoader';

// Protected Route Guard
const ProtectedRoute: React.FC<{ children: React.ReactNode; requireAdmin?: boolean }> = ({
  children,
  requireAdmin = false,
}) => {
  const { isAuthenticated, isInitialized, role } = useAuthStore();
  const location = useLocation();

  if (!isInitialized) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-canvas text-ink">
        <EcgLoader label="Restoring Clinical Session..." sublabel="Validating JWT token claims and user identity..." />
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (requireAdmin && role !== 'admin') {
    return <Navigate to="/chat" replace />;
  }

  return <>{children}</>;
};

export const App: React.FC = () => {
  const { restoreSession, isInitialized } = useAuthStore();
  const navigate = useNavigate();

  useEffect(() => {
    restoreSession();
  }, [restoreSession]);

  return (
    <Routes>
      {/* Public Login Route */}
      <Route path="/login" element={<LoginPage />} />

      {/* Protected Routes inside AppShell */}
      <Route
        element={
          <ProtectedRoute>
            <AppShell />
          </ProtectedRoute>
        }
      >
        <Route path="/" element={<Navigate to="/chat" replace />} />
        <Route path="/chat" element={<ChatPage />} />
        <Route path="/reports" element={<ReportsPage />} />
        <Route path="/trends" element={<TrendsPage />} />
        <Route path="/caregap" element={<CareGapPage />} />
        <Route path="/coverage" element={<CoveragePage />} />
        <Route
          path="/admin"
          element={
            <ProtectedRoute requireAdmin={true}>
              <AdminPage />
            </ProtectedRoute>
          }
        />
      </Route>

      {/* Catch-all fallback */}
      <Route path="*" element={<Navigate to="/chat" replace />} />
    </Routes>
  );
};
