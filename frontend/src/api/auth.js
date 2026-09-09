import api from './client';
export const login = (payload) => api.post('/login/', payload);
export const getMe = () => api.get('/me/');
export const logout = (refresh) => api.post('/logout/', { refresh });
export const changePassword = (payload) => api.post('/auth/password/change/', payload);
export const signup = (payload) => api.post('/signup/', payload);
export const updateAccess = (id, payload) => api.patch(`/users/${id}/access/`, payload);
