import { Outlet } from 'react-router-dom';
import DashboardLayout from '../components/layout/DashboardLayout';
export default function DashboardRoute() {
  return (
    <DashboardLayout>
      <Outlet />
    </DashboardLayout>
  );
}
