import { useState } from 'react';
import { Navigate, useLocation, useNavigate } from 'react-router-dom';
import { Flower2, ArrowRight, ShieldCheck, BookOpen, Users } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { errorMessage } from '../api/client';
import { ErrorNotice, Loading } from '../components/Feedback';

export default function SignIn() {
  const { user, loading, sessionError, retry, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [form, setForm] = useState({ email: '', password: '' });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  if (loading) return <Loading label="Opening your workspace…" />;
  if (sessionError) return <ErrorNotice message={sessionError} onRetry={retry} />;
  if (user) return <Navigate to="/home" replace />;
  const submit = async (event) => {
    event.preventDefault();
    setBusy(true);
    setError('');
    try {
      await login(form);
      const from = location.state?.from;
      navigate(
        typeof from === 'string' && from.startsWith('/') && !from.startsWith('//') ? from : '/home',
        { replace: true },
      );
    } catch (error) {
      setError(errorMessage(error));
    } finally {
      setBusy(false);
    }
  };
  return (
    <main className="auth-page">
      <section className="auth-story">
        <div className="brand">
          <span className="brand-mark">
            <Flower2 size={28} />
          </span>
          <span>
            <strong>Ganesh Youth</strong>
            <small>FESTIVAL MANAGEMENT</small>
          </span>
        </div>
        <div className="auth-story-content">
          <span className="eyebrow">TOGETHER, FOR A MEANINGFUL CELEBRATION</span>
          <div className="festival-symbol" aria-hidden="true">
            ॐ
          </div>
          <h1>
            Devotion brings us together.
            <br />
            <em>Trust keeps us together.</em>
          </h1>
          <p>A shared home for your festival plans, contributions, and every rupee spent.</p>
          <div className="auth-benefits">
            <span>
              <BookOpen size={18} /> Clear financial records
            </span>
            <span>
              <Users size={18} /> One committee workspace
            </span>
            <span>
              <ShieldCheck size={18} /> Accountable approvals
            </span>
          </div>
        </div>
        <p className="auth-footer">
          गणपती बाप्पा मोरया <span>GANESH YOUTH</span>
        </p>
      </section>
      <section className="auth-form-panel">
        <form className="auth-form" onSubmit={submit}>
          <span className="eyebrow">WELCOME TO THE FESTIVAL DESK</span>
          <h2>Sign in to your workspace</h2>
          <p>Use the account provided by your committee administrator.</p>
          <label>
            Email or username
            <input
              autoComplete="username"
              required
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
              placeholder="you@example.com"
            />
          </label>
          <label>
            Password
            <input
              type="password"
              autoComplete="current-password"
              required
              value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
              placeholder="Enter your password"
            />
          </label>
          {error && <ErrorNotice message={error} />}
          <button className="button primary large" disabled={busy}>
            {busy ? 'Signing in…' : 'Sign in'}
            <ArrowRight size={17} />
          </button>
          <div className="access-note">
            <ShieldCheck size={20} />
            <p>
              <strong>Need access or a password reset?</strong>
              <br />
              Contact your Ganesh Youth administrator.
            </p>
          </div>
        </form>
      </section>
    </main>
  );
}
