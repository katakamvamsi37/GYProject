import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Loading, ErrorNotice } from '../components/Feedback';
export default function ProtectedRoute({ roles }) {
  const { user, loading, sessionError, retry } = useAuth();
  const location = useLocation();
  if (loading) return <Loading label="Validating your session…" />;
  if (sessionError) return <ErrorNotice message={sessionError} onRetry={retry} />;
  if (!user) return <Navigate to="/signin" replace state={{ from: location.pathname }} />;
  if (roles && !roles.includes(user.role)) return <Navigate to="/home" replace />;
  return <Outlet />;
}
