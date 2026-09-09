import { useState } from 'react';
import { Save, ShieldCheck, KeyRound } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { updateProfile } from '../api/profile';
import { changePassword } from '../api/auth';
import { saveSession, errorMessage } from '../api/client';
import { ErrorNotice } from '../components/Feedback';

export default function Profile() {
  const { user, updateUser } = useAuth();
  const [form, setForm] = useState({
    name: user.name,
    email: user.email,
    phone: user.phone,
    avatar_url: user.avatar_url,
  });
  const [passwords, setPasswords] = useState({ current_password: '', new_password: '' });
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [passwordError, setPasswordError] = useState('');
  const [busy, setBusy] = useState(false);
  const save = async (event) => {
    event.preventDefault();
    setBusy(true);
    setError('');
    setMessage('');
    try {
      const { data } = await updateProfile(user.id, form);
      updateUser(data.user);
      setMessage('Profile updated.');
    } catch (error) {
      setError(errorMessage(error));
    } finally {
      setBusy(false);
    }
  };
  const change = async (event) => {
    event.preventDefault();
    setBusy(true);
    setPasswordError('');
    try {
      await changePassword(passwords);
      saveSession(null);
      window.dispatchEvent(new Event('gy:session-expired'));
    } catch (error) {
      setPasswordError(errorMessage(error));
    } finally {
      setBusy(false);
    }
  };
  return (
    <>
      <div className="page-heading">
        <div>
          <h1>
            My profile<span className="heading-dot">.</span>
          </h1>
          <p>Your identity and responsibilities in the festival committee.</p>
        </div>
      </div>
      <div className="profile-grid">
        <section className="panel">
          <div className="profile-summary">
            <span className="avatar large">{user.name.slice(0, 2).toUpperCase()}</span>
            <div>
              <h2>{user.name}</h2>
              <p>{user.authority}</p>
            </div>
            <ShieldCheck />
          </div>
          <form className="record-form" onSubmit={save}>
            <div className="form-grid">
              {[
                ['name', 'Full name', 'text'],
                ['email', 'Email address', 'email'],
                ['phone', 'Mobile number', 'tel'],
                ['avatar_url', 'Profile image URL', 'url'],
              ].map(([key, label, type]) => (
                <label key={key}>
                  {label}
                  <input
                    type={type}
                    required={key === 'name' || key === 'email'}
                    value={form[key]}
                    onChange={(e) => setForm({ ...form, [key]: e.target.value })}
                  />
                </label>
              ))}
            </div>
            {error && <ErrorNotice message={error} />}
            {message && (
              <p className="notice success" role="status">
                {message}
              </p>
            )}
            <button className="button primary" disabled={busy}>
              <Save size={16} />
              Save profile
            </button>
          </form>
        </section>
        <section className="panel">
          <div className="panel-heading">
            <div>
              <h2>Change password</h2>
              <p>You’ll sign in again after changing it.</p>
            </div>
            <KeyRound size={20} />
          </div>
          <form className="record-form" onSubmit={change}>
            <label>
              Current password
              <input
                type="password"
                autoComplete="current-password"
                required
                value={passwords.current_password}
                onChange={(e) => setPasswords({ ...passwords, current_password: e.target.value })}
              />
            </label>
            <label>
              New password
              <input
                type="password"
                autoComplete="new-password"
                minLength={10}
                required
                value={passwords.new_password}
                onChange={(e) => setPasswords({ ...passwords, new_password: e.target.value })}
              />
            </label>
            {passwordError && <ErrorNotice message={passwordError} />}
            <button className="button secondary" disabled={busy}>
              Update password
            </button>
          </form>
        </section>
      </div>
    </>
  );
}
