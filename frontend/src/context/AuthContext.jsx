import { createContext, useContext, useEffect, useState } from 'react';
import { getMe, login as requestLogin, logout as requestLogout } from '../api/auth';
import { readSession, saveSession } from '../api/client';

const AuthContext = createContext(null);
export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [sessionError, setSessionError] = useState('');
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let active = true;
    // Old localStorage sessions are retired, including any roles cached by the old UI.
    localStorage.removeItem('gy_auth');
    const expire = () => {
      saveSession(null);
      setUser(null);
      setLoading(false);
    };
    window.addEventListener('gy:session-expired', expire);
    if (!readSession()) setLoading(false);
    else {
      setLoading(true);
      setSessionError('');
      getMe()
        .then(({ data }) => {
          if (active) setUser(data.user);
        })
        .catch((error) => {
          if (!active) return;
          if (error.response?.status === 401) expire();
          else setSessionError('Unable to validate your session. Check the server and retry.');
        })
        .finally(() => {
          if (active) setLoading(false);
        });
    }
    return () => {
      active = false;
      window.removeEventListener('gy:session-expired', expire);
    };
  }, [attempt]);
  const login = async (payload) => {
    const { data } = await requestLogin(payload);
    saveSession({ access: data.access, refresh: data.refresh });
    setUser(data.user);
    setSessionError('');
  };
  const logout = async () => {
    const refresh = readSession()?.refresh;
    try {
      if (refresh) await requestLogout(refresh);
    } finally {
      saveSession(null);
      setUser(null);
      setSessionError('');
    }
  };
  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        sessionError,
        login,
        logout,
        updateUser: setUser,
        retry: () => setAttempt((x) => x + 1),
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}
export const useAuth = () => useContext(AuthContext);
