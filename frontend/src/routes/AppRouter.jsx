import { lazy, Suspense } from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { AuthProvider } from '../context/AuthContext';
import { FestivalProvider } from '../context/FestivalContext';
import { Loading } from '../components/Feedback';
import ErrorBoundary from '../components/ErrorBoundary';
import ProtectedRoute from './ProtectedRoute';
import DashboardRoute from './DashboardRoute';
import SignIn from '../pages/SignIn';
import { managementRoles } from '../utils/format';

const Home = lazy(() => import('../pages/Home'));
const Planning = lazy(() => import('../pages/Planning'));
const Expenses = lazy(() => import('../pages/Expenses'));
const Collections = lazy(() => import('../pages/Collections'));
const Members = lazy(() => import('../pages/Members'));
const Audit = lazy(() => import('../pages/Audit'));
const Users = lazy(() => import('../pages/Users'));
const Profile = lazy(() => import('../pages/Profile'));

export default function AppRouter() {
  return (
    <ErrorBoundary>
      <BrowserRouter>
        <AuthProvider>
          <FestivalProvider>
            <Suspense fallback={<Loading />}>
              <Routes>
                <Route path="/signin" element={<SignIn />} />
                <Route path="/signup" element={<Navigate to="/signin" replace />} />
                <Route element={<ProtectedRoute />}>
                  <Route element={<DashboardRoute />}>
                    <Route path="/home" element={<Home />} />
                    <Route path="/profile" element={<Profile />} />
                    <Route element={<ProtectedRoute roles={managementRoles} />}>
                      <Route path="/planning" element={<Planning />} />
                      <Route path="/expenses" element={<Expenses />} />
                      <Route path="/collections" element={<Collections />} />
                      <Route path="/members" element={<Members />} />
                      <Route path="/audit" element={<Audit />} />
                    </Route>
                    <Route element={<ProtectedRoute roles={['admin']} />}>
                      <Route path="/users" element={<Users />} />
                    </Route>
                  </Route>
                </Route>
                <Route path="*" element={<Navigate to="/home" replace />} />
              </Routes>
            </Suspense>
          </FestivalProvider>
        </AuthProvider>
      </BrowserRouter>
    </ErrorBoundary>
  );
}
