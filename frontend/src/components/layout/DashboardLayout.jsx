import { useState } from 'react';
import { NavLink, useLocation, Link } from 'react-router-dom';
import {
  LayoutDashboard,
  Wallet,
  BookOpen,
  Users,
  ShieldCheck,
  LogOut,
  Menu,
  X,
  Flower2,
  ClipboardList,
  ArrowUpRight,
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { useFestival } from '../../context/FestivalContext';
import { managementRoles } from '../../utils/format';

const links = [
  ['/home', 'Overview', LayoutDashboard],
  ['/planning', 'Festival budgets', ClipboardList],
  ['/expenses', 'Expense ledger', BookOpen],
  ['/collections', 'Collections', Wallet],
  ['/members', 'Committee & volunteers', Users],
  ['/audit', 'Audit trail', ShieldCheck],
];
export default function DashboardLayout({ children }) {
  const { user, logout } = useAuth();
  const { year, setYear } = useFestival();
  const [open, setOpen] = useState(false);
  const [leaving, setLeaving] = useState(false);
  const location = useLocation();
  const management = managementRoles.includes(user.role);
  const navigation = links.filter(([path]) => path === '/home' || management);
  if (user.role === 'admin') navigation.push(['/users', 'Access management', Users]);
  const title = navigation.find(([path]) => path === location.pathname)?.[1] || 'My profile';
  const signOut = async () => {
    setLeaving(true);
    try {
      await logout();
    } catch {
      /* Local session is always cleared by AuthProvider. */
    } finally {
      setLeaving(false);
    }
  };
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        Skip to content
      </a>
      {open && (
        <button
          className="nav-scrim"
          aria-label="Close navigation"
          onClick={() => setOpen(false)}
        />
      )}
      <aside className={`sidebar ${open ? 'is-open' : ''}`}>
        <Link className="brand" to="/home" onClick={() => setOpen(false)}>
          <span className="brand-mark">
            <Flower2 size={27} />
          </span>
          <span>
            <strong>Ganesh Youth</strong>
            <small>FESTIVAL MANAGEMENT</small>
          </span>
        </Link>
        <button
          className="mobile-close icon-button"
          onClick={() => setOpen(false)}
          aria-label="Close navigation"
        >
          <X />
        </button>
        <div className="workspace-label">
          <span className="live-dot" /> Festival workspace <span>{year}</span>
        </div>
        <p className="nav-caption">WORKSPACE</p>
        <nav aria-label="Main navigation">
          {navigation.map(([path, label, Icon]) => (
            <NavLink
              to={path}
              key={path}
              onClick={() => setOpen(false)}
              className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
            >
              <Icon size={18} />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-note">
          <ShieldCheck size={20} />
          <strong>Every contribution counts.</strong>
          <p>Clear records. Shared responsibility. A festival we build together.</p>
          <Link to={management ? '/audit' : '/home'} onClick={() => setOpen(false)}>
            View workspace <ArrowUpRight size={14} />
          </Link>
        </div>
        <div className="sidebar-account">
          <Link to="/profile" onClick={() => setOpen(false)}>
            <span className="avatar">{user.name.slice(0, 2).toUpperCase()}</span>
            <span>
              <strong>{user.name}</strong>
              <small>{user.authority}</small>
            </span>
          </Link>
          <button
            className="icon-button"
            onClick={signOut}
            disabled={leaving}
            aria-label="Sign out"
          >
            <LogOut size={17} />
          </button>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div className="breadcrumb">
            <button
              className="mobile-menu icon-button"
              aria-label="Open navigation"
              aria-expanded={open}
              onClick={() => setOpen(true)}
            >
              <Menu />
            </button>
            <span>Workspace</span>
            <span>/</span>
            <strong>{title}</strong>
          </div>
          <div className="topbar-actions">
            <span className="desktop-date">
              {new Date().toLocaleDateString('en-IN', {
                day: 'numeric',
                month: 'short',
                year: 'numeric',
              })}
            </span>
            <span className="topbar-divider" />
            <Link to="/profile" className="avatar" aria-label="Open my profile">
              {user.name.slice(0, 2).toUpperCase()}
            </Link>
          </div>
        </header>
        <main id="main-content" className="main-content">
          <div className="workspace-toolbar">
            <span>
              <span className="small-dot" /> GANESH UTSAV · OPERATIONS DESK
            </span>
            <label>
              Festival year{' '}
              <select
                aria-label="Festival year"
                value={year}
                onChange={(event) => setYear(Number(event.target.value))}
              >
                {Array.from({ length: 12 }, (_, i) => new Date().getFullYear() + 2 - i).map(
                  (value) => (
                    <option key={value}>{value}</option>
                  ),
                )}
              </select>
            </label>
          </div>
          {children}
          <footer className="workspace-footer">
            <Flower2 size={15} />
            <span>Ganesh Youth · Built for accountable celebrations</span>
            <span>Festival year: January – December {year}</span>
          </footer>
        </main>
      </div>
    </div>
  );
}
