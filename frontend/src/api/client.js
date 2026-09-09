import axios from 'axios';

const STORAGE_KEY = 'gy_session';
export function readSession() {
  try {
    const value = JSON.parse(sessionStorage.getItem(STORAGE_KEY) || 'null');
    return typeof value?.access === 'string' && typeof value?.refresh === 'string' ? value : null;
  } catch {
    sessionStorage.removeItem(STORAGE_KEY);
    return null;
  }
}
let session = readSession();
export function saveSession(value) {
  session = value;
  if (value) sessionStorage.setItem(STORAGE_KEY, JSON.stringify(value));
  else sessionStorage.removeItem(STORAGE_KEY);
}
const baseURL = import.meta.env.VITE_API_URL || '/api';
const apiClient = axios.create({ baseURL, timeout: 20000 });
apiClient.interceptors.request.use((config) => {
  if (session?.access) config.headers.Authorization = `Bearer ${session.access}`;
  return config;
});
let refreshing;
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config;
    if (
      error.response?.status !== 401 ||
      !original ||
      original._retried ||
      original.url === '/login/'
    ) {
      return Promise.reject(error);
    }
    original._retried = true;
    if (!session?.refresh) {
      window.dispatchEvent(new Event('gy:session-expired'));
      return Promise.reject(error);
    }
    try {
      if (!refreshing) {
        const current = session;
        refreshing = axios
          .post(`${baseURL}/auth/token/refresh/`, { refresh: current.refresh }, { timeout: 15000 })
          .then(({ data }) => {
            if (session !== current) throw new Error('Session changed.');
            saveSession({ ...current, ...data });
          })
          .finally(() => {
            refreshing = null;
          });
      }
      await refreshing;
      return apiClient(original);
    } catch (refreshError) {
      saveSession(null);
      window.dispatchEvent(new Event('gy:session-expired'));
      return Promise.reject(refreshError);
    }
  },
);
export function errorMessage(error) {
  if (!error.response)
    return error.message === 'Network Error'
      ? 'Cannot reach the server. Check your connection and retry.'
      : error.message || 'Request failed.';
  const data = error.response.data;
  if (typeof data === 'string') return 'The server could not complete this request.';
  return (
    Object.entries(data || {})
      .map(
        ([field, value]) =>
          `${field === 'detail' || field === 'non_field_errors' ? '' : field.replaceAll('_', ' ') + ': '}${Array.isArray(value) ? value.join(' ') : value}`,
      )
      .join(' ') || 'Request failed.'
  );
}
export default apiClient;
